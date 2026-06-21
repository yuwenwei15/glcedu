"""MediaCrawler 适配器：调用独立的 MediaCrawler 工具抓取 B站 / 贴吧，
读取其落地的 JSON 文件，映射成 Article 入库。

设计原则：
- 与 MediaCrawler 项目解耦：不 import 其源码，仅用标准库 subprocess 调 CLI、json 读结果。
- 多键容错映射：MediaCrawler 不同版本 JSON 字段名可能漂移，映射器同时尝试已知键名。
- 不搬运视频本体：B站仅做摘要展示 + 跳转原链接；贴吧按用户选择抓取完整正文。
- 复用现有 ScrapeLog 记录、Article.original_url 去重。
- 多平台：按 platform 选择 MediaCrawler 平台代号、命令行参数、字段映射、输出目录。
"""
import os
import sys
import glob
import json
import logging
import subprocess
from datetime import datetime

from flask import current_app

from app import db
from app.models import Article, Category, ScrapeLog


logger = logging.getLogger(__name__)

BILI_HOME = 'https://www.bilibili.com'
TIEBA_HOME = 'https://tieba.baidu.com'

# 相关性白名单：标题命中其一才入库，过滤掉搜索结果里只是"文本沾边"的无关内容。
RELEVANCE_KEYWORDS = ['桂林学院']

# ---- 字段名候选（按优先级），应对 MediaCrawler 版本差异 ----
# B站: store/bilibili/__init__.py update_bilibili_video
#   video_id / title / desc / create_time / nickname / video_url / video_cover_url
# 贴吧: model/m_baidu_tieba.py TiebaNote
#   note_id / title / desc / note_url / publish_time / user_nickname / user_avatar / tieba_name
TITLE_KEYS = ['title', 'video_title']
DESC_KEYS = ['desc', 'description', 'content']
LINK_KEYS = ['video_url', 'video_link', 'note_url']
ID_KEYS = ['video_id', 'bvid', 'note_id', 'video_id_str']
COVER_KEYS = ['video_cover_url', 'cover_url', 'cover', 'pic', 'user_avatar']
TIME_KEYS = ['create_time', 'publish_time', 'pubdate']
NICK_KEYS = ['nickname', 'user_nickname', 'user_name', 'author']
TIEBA_NAME_KEYS = ['tieba_name', 'tieba_link']


def _first(rec, keys, default=''):
    for k in keys:
        v = rec.get(k)
        if v:
            return v
    return default


def _to_https(url):
    """外站图片 CDN 走 https 更稳，http 在部分环境（混合内容策略/热链）会 403 或被拦。"""
    if not url:
        return ''
    if url.startswith('http://'):
        return 'https://' + url[len('http://'):]
    return url


def _parse_time(raw):
    """MediaCrawler 的时间字段：可能是 unix 时间戳，也可能是字符串。"""
    if not raw:
        return None
    # 贴吧 publish_time 已经是 "YYYY-MM-DD HH:MM:SS" 字符串
    if isinstance(raw, str):
        for fmt in ('%Y-%m-%d %H:%M:%S', '%Y-%m-%d', '%Y/%m/%d'):
            try:
                return datetime.strptime(raw.strip(), fmt)
            except ValueError:
                continue
    try:
        ts = float(raw)
        if ts > 1e12:  # 毫秒级时间戳兜底
            ts = ts / 1000
        return datetime.fromtimestamp(ts)
    except (TypeError, ValueError, OSError, OverflowError):
        return None


# ---- 平台配置 ----
# 每个平台的 MediaCrawler 代号、内容文件名片段、source 标签、跳转域名
PLATFORMS = {
    'bilibili': {
        'mc_platform': 'bili',
        'content_glob': '*contents*.json',
        'source': 'B站',
        'home': BILI_HOME,
        'login_type': 'qrcode',
    },
    'tieba': {
        'mc_platform': 'tieba',
        # 贴吧 store 用 item_type="contents"（update_tieba_note → store_content）
        'content_glob': '*contents*.json',
        'source': '贴吧',
        'home': TIEBA_HOME,
        # 贴吧扫码登录 DOM 已失效，改用 Cookie 登录
        'login_type': 'cookie',
    },
}


class MediaCrawlerAdapter:
    """调用 MediaCrawler 抓取并入库。支持 bilibili / tieba。"""

    def __init__(self):
        self.mc_dir = current_app.config['MEDIACRAWLER_DIR']
        self.mc_python = current_app.config.get('MEDIACRAWLER_PYTHON') or sys.executable
        self.output_dir_cfg = current_app.config['MEDIACRAWLER_OUTPUT_DIR']
        self.default_keyword = current_app.config['MEDIACRAWLER_KEYWORD']
        self.timeout = current_app.config['MEDIACRAWLER_TIMEOUT']

    # ---------- 对外入口 ----------
    def run(self, platform='bilibili', category_code=None, keyword=None,
            tieba_name=None):
        """抓取指定平台。

        - bilibili: keyword 关键词搜索
        - tieba: tieba_name 指定贴吧名（如"桂林学院"），抓该吧帖子
        """
        if platform not in PLATFORMS:
            raise ValueError(f'不支持的平台: {platform}')
        cfg = PLATFORMS[platform]

        category_code = category_code or current_app.config.get(
            f'MEDIACRAWLER_CATEGORY_CODE_{platform.upper()}',
            current_app.config['MEDIACRAWLER_CATEGORY_CODE'])

        keyword = keyword or self.default_keyword

        category = Category.query.filter_by(code=category_code).first()
        if not category:
            raise ValueError(f'分类不存在: {category_code}')

        log = ScrapeLog(category_id=category.id, started_at=datetime.now())
        db.session.add(log)
        db.session.commit()

        total_found = 0
        total_new = 0
        total_skipped = 0
        try:
            self._invoke_mediacrawler(platform, keyword=keyword,
                                      tieba_name=tieba_name)

            output_dir = self._find_output_dir(platform)
            content_files = self._list_content_files(output_dir, cfg['content_glob'])
            records = []
            for fp in content_files:
                records.extend(self._read_json(fp))

            total_found = len(records)
            for rec in records:
                if not self._is_relevant(rec, platform):
                    total_skipped += 1
                    continue
                try:
                    self._save_article(rec, category.id, platform)
                    total_new += 1
                except Exception as e:
                    logger.warning('%s 记录入库失败: %s | rec=%s',
                                   platform, e, str(rec)[:200])
                    continue

            db.session.commit()
            log.status = 'success'
        except Exception as e:
            logger.exception('MediaCrawler 适配器运行失败')
            log.status = 'failed'
            log.error_message = str(e)[:1000]
            db.session.rollback()
        finally:
            log.finished_at = datetime.now()
            log.articles_found = total_found
            log.articles_new = total_new
            if total_skipped:
                log.error_message = (log.error_message or '') + \
                    f' | 过滤无关内容 {total_skipped} 条'
            db.session.merge(log)
            db.session.commit()

        return {'found': total_found, 'new': total_new, 'skipped': total_skipped}

    # ---------- 调用 MediaCrawler ----------
    def _invoke_mediacrawler(self, platform, keyword=None, tieba_name=None):
        if not self.mc_dir or not os.path.isdir(self.mc_dir):
            raise FileNotFoundError(
                f'MediaCrawler 目录不存在或未配置: {self.mc_dir}。'
                '请 clone https://github.com/NanmiCoder/MediaCrawler 并在 .env 设置 MEDIACRAWLER_DIR。'
            )

        main_py = os.path.join(self.mc_dir, 'main.py')
        if not os.path.isfile(main_py):
            raise FileNotFoundError(f'未找到 MediaCrawler 入口: {main_py}')

        cfg = PLATFORMS[platform]
        env = os.environ.copy()

        cmd = [
            self.mc_python, main_py,
            '--platform', cfg['mc_platform'],
            '--lt', cfg['login_type'],          # 首次需扫码，Cookie 会持久化
            '--type', 'search',                  # search 模式：B站按关键词，贴吧按 TIEBA_NAME_LIST
            '--save_data_option', 'json',        # 输出 JSON 文件
            '--get_comment', 'no',               # 不抓评论
        ]

        if platform == 'bilibili':
            cmd += ['--keywords', keyword or '']
        elif platform == 'tieba':
            # 贴吧 search 模式会同时跑关键词搜索 + TIEBA_NAME_LIST 指定吧。
            # 我们只想要指定吧，所以关键词置空，靠环境变量注入 TIEBA_NAME_LIST。
            cmd += ['--keywords', keyword or '']
            name = tieba_name or current_app.config.get('MEDIACRAWLER_TIEBA_NAME', '桂林学院')
            env['GLCEDU_TIEBA_NAME'] = name
            # 贴吧扫码登录 DOM 已失效，改用 Cookie 登录（config/__init__.py 读取本变量）
            cookie = current_app.config.get('MEDIACRAWLER_TIEBA_COOKIE', '').strip()
            if not cookie:
                raise RuntimeError(
                    '贴吧 Cookie 未配置：请在 .env 设置 MEDIACRAWLER_TIEBA_COOKIE'
                    '（从浏览器复制百度贴吧登录后的 Cookie 字符串）。'
                )
            env['GLCEDU_TIEBA_COOKIE'] = cookie

        logger.info('调用 MediaCrawler: %s', ' '.join(cmd))
        result = subprocess.run(
            cmd,
            cwd=self.mc_dir,
            env=env,
            timeout=self.timeout,
            capture_output=True,
            text=True,
            encoding='utf-8',
            errors='replace',
        )

        if result.returncode != 0:
            tail = (result.stderr or result.stdout or '')[-1500:]
            raise RuntimeError(
                f'MediaCrawler 退出码 {result.returncode}。'
                f'可能未登录或配置有误。输出末尾:\n{tail}'
            )

    # ---------- 文件 / 解析 ----------
    def _find_output_dir(self, platform):
        if self.output_dir_cfg:
            d = self.output_dir_cfg
            if not os.path.isdir(d):
                os.makedirs(d, exist_ok=True)
            return d
        mc_platform = PLATFORMS[platform]['mc_platform']
        candidates = [
            os.path.join(self.mc_dir, 'data', mc_platform, 'json'),
            os.path.join(self.mc_dir, 'data', 'json'),
        ]
        for d in candidates:
            if os.path.isdir(d):
                return d
        d = candidates[0]
        os.makedirs(d, exist_ok=True)
        return d

    @staticmethod
    def _list_json_files(output_dir):
        if not output_dir or not os.path.isdir(output_dir):
            return []
        return glob.glob(os.path.join(output_dir, '*.json'))

    @staticmethod
    def _list_content_files(output_dir, content_glob='*contents*.json'):
        """只取内容文件，排除 comments/creators/contacts/dynamics。"""
        if not output_dir or not os.path.isdir(output_dir):
            return []
        files = glob.glob(os.path.join(output_dir, content_glob))
        if not files:
            files = MediaCrawlerAdapter._list_json_files(output_dir)
        return sorted(files)

    @staticmethod
    def _read_json(filepath):
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                data = json.load(f)
        except (OSError, json.JSONDecodeError) as e:
            logger.warning('读取 JSON 失败 %s: %s', filepath, e)
            return []
        if isinstance(data, list):
            return data
        if isinstance(data, dict):
            for k in ('data', 'items', 'list', 'results'):
                v = data.get(k)
                if isinstance(v, list):
                    return v
            return [data]
        return []

    @staticmethod
    def _is_relevant(rec, platform='bilibili'):
        """相关性过滤。

        - bilibili: 关键词搜索会混入"文本沾边"的无关视频，靠标题必须包含"桂林学院"清洗。
        - tieba: search 模式会同时跑关键词搜索（命中各种吧），靠 tieba_name 必须为
          "桂林学院吧"清洗，只保留指定吧的帖子。
        """
        if platform == 'tieba':
            tieba_name = str(rec.get('tieba_name', ''))
            return tieba_name == '桂林学院吧'
        title = str(_first(rec, TITLE_KEYS))
        return any(kw in title for kw in RELEVANCE_KEYWORDS)

    def _map_record(self, rec, platform):
        """把一条 MediaCrawler 记录映射成 Article 字段 dict。"""
        cfg = PLATFORMS[platform]
        title = _first(rec, TITLE_KEYS) or '无标题'
        desc = _first(rec, DESC_KEYS)
        link = _resolve_link(rec, platform)
        cover = _first(rec, COVER_KEYS)
        nickname = _first(rec, NICK_KEYS)
        pub = _parse_time(_first(rec, TIME_KEYS))

        summary = (desc or '').strip()[:300]
        content = self._build_content(platform, title, desc, link)

        return {
            'title': title,
            'summary': summary or f'来自{cfg["source"]}的内容',
            'content': content,
            'author': nickname,
            'source': cfg['source'],
            'original_url': link or cfg['home'],
            'cover_image': _to_https(cover),
            'published_at': pub,
        }

    @staticmethod
    def _build_content(platform, title, desc, link):
        """正文：标题 + 描述 + 跳转原链接按钮。

        贴吧 desc 即帖子正文（首楼内容），按用户选择展示完整正文；
        B站 desc 为视频简介，仅摘要展示 + 跳转，不内嵌视频本体。
        """
        cfg = PLATFORMS[platform]
        # 贴吧正文可能较长，保留完整；B站 desc 作为简介
        if desc:
            if platform == 'tieba':
                # 贴吧正文按段落展示
                desc_block = ''.join(f'<p>{p}</p>'
                                     for p in str(desc).split('\n') if p.strip())
            else:
                desc_block = f'<p>{desc}</p>'
        else:
            desc_block = ''

        btn = ''
        if link:
            icon = 'forum' if platform == 'tieba' else 'play_circle'
            label = cfg['source']
            btn = (
                f'<div class="pdf-embed-card">'
                f'<span class="pdf-embed-icon material-symbols-outlined">{icon}</span>'
                '<div class="pdf-embed-body">'
                f'<p class="pdf-embed-title">该内容来自{label}</p>'
                f'<p class="pdf-embed-desc">完整内容请点击下方按钮前往{label}原页面查看。</p>'
                f'<a class="pdf-embed-btn" href="{link}" target="_blank" rel="noopener">前往{label} 查看</a>'
                '</div></div>'
            )
        return f'<h2>{title}</h2>{desc_block}{btn}'

    def _save_article(self, rec, category_id, platform):
        data = self._map_record(rec, platform)
        link = data['original_url']
        home = PLATFORMS[platform]['home']
        if not link or link == home:
            return  # 无链接无法去重与展示，跳过

        exists = Article.query.filter_by(original_url=link).first()
        if exists:
            return

        article = Article(
            category_id=category_id,
            title=data['title'],
            summary=data['summary'],
            content=data['content'],
            author=data['author'],
            source=data['source'],
            original_url=link,
            cover_image=data['cover_image'],
            published_at=data['published_at'],
            view_count=0,
        )
        db.session.add(article)


def _resolve_link(rec, platform):
    """取原内容链接。优先记录自带 URL，否则用 ID 拼接。"""
    link = _first(rec, LINK_KEYS)
    if link:
        return link
    rid = _first(rec, ID_KEYS)
    if not rid:
        return ''
    if platform == 'bilibili':
        return f'{BILI_HOME}/video/av{rid}'
    if platform == 'tieba':
        return f'{TIEBA_HOME}/p/{rid}'
    return ''
