from flask import request, jsonify
from sqlalchemy import desc

from app import db
from app.api import api_bp
from app.api.auth import admin_required
from app.api.ratelimit import allow
from app.models import Article, Category, ScrapeLog


@api_bp.route('/news')
def list_news():
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 15, type=int)
    category_code = request.args.get('category', '')

    query = Article.query

    if category_code:
        cat = Category.query.filter_by(code=category_code).first()
        if cat:
            query = query.filter_by(category_id=cat.id)

    pagination = query.order_by(desc(Article.published_at)).paginate(
        page=page, per_page=per_page, error_out=False
    )

    return jsonify({
        'success': True,
        'data': [a.to_dict() for a in pagination.items],
        'pagination': {
            'page': pagination.page,
            'per_page': pagination.per_page,
            'total': pagination.total,
            'pages': pagination.pages,
        }
    })


@api_bp.route('/news/<int:article_id>')
def get_news(article_id):
    article = Article.query.get_or_404(article_id)
    Article.query.filter_by(id=article_id).update(
        {Article.local_view_count: Article.local_view_count + 1})
    db.session.commit()
    article.local_view_count += 1
    return jsonify({'success': True, 'data': article.to_dict(include_content=True)})


@api_bp.route('/news/<int:article_id>/summary', methods=['POST'])
def news_summary(article_id):
    """生成或返回 AI 新闻总结。

    若已有缓存直接返回；否则调用 AI 生成并缓存。
    """
    article = Article.query.get_or_404(article_id)

    # 有缓存直接返回，省 token（缓存读取不限流）
    if article.ai_summary:
        return jsonify({
            'success': True,
            'data': {
                'summary': article.ai_summary,
                'cached': True,
            }
        })

    # 仅对「真正触发 AI 生成」的路径限流：每 IP 每分钟最多 5 次，防脚本刷接口烧 token
    if not allow('ai_summary', limit=5, window=60):
        return jsonify({
            'success': False,
            'message': '生成请求过于频繁，请稍后再试',
        }), 429

    try:
        from app.ai.summary import generate_summary
        summary = generate_summary(article)
    except RuntimeError as e:
        return jsonify({'success': False, 'message': str(e)}), 500
    except Exception as e:
        return jsonify({'success': False,
                        'message': f'生成失败：{e}'}), 500

    return jsonify({
        'success': True,
        'data': {
            'summary': summary,
            'cached': False,
        }
    })


@api_bp.route('/news/search')
def search_news():
    q = request.args.get('q', '').strip()
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 15, type=int)

    if not q:
        return jsonify({'success': True, 'data': [], 'pagination': {'total': 0}})

    query = Article.query.filter(
        db.or_(
            Article.title.contains(q),
            Article.summary.contains(q),
        )
    )

    pagination = query.order_by(desc(Article.published_at)).paginate(
        page=page, per_page=per_page, error_out=False
    )

    return jsonify({
        'success': True,
        'data': [a.to_dict() for a in pagination.items],
        'pagination': {
            'page': pagination.page,
            'per_page': pagination.per_page,
            'total': pagination.total,
            'pages': pagination.pages,
        }
    })


@api_bp.route('/categories')
def list_categories():
    categories = Category.query.order_by(Category.sort_order).all()
    return jsonify({'success': True, 'data': [c.to_dict() for c in categories]})


@api_bp.route('/bootstrap-scrape', methods=['POST'])
def bootstrap_scrape():
    """首次引导抓取：仅当库中尚无任何文章时允许匿名触发，避免在前端硬编码
    管理员令牌。一旦有了数据就返回 403 自动停用；空库时也限流防滥用。"""
    from flask import current_app
    from app.scraper.task_manager import task_manager

    if Article.query.first() is not None:
        return jsonify({'success': False,
                        'message': '已有新闻数据，引导抓取已停用'}), 403

    if not allow('bootstrap_scrape', limit=2, window=300):
        return jsonify({'success': False,
                        'message': '操作过于频繁，请稍后再试'}), 429

    app = current_app._get_current_object()

    def run_scrape():
        with app.app_context():
            from app.scraper.spider import GLCSpider
            spider = GLCSpider()
            return spider.scrape_all(max_pages=2)

    task_id = task_manager.submit(run_scrape)
    return jsonify({'success': True, 'task_id': task_id,
                    'message': '引导抓取任务已启动'})


@api_bp.route('/scrape/status/<task_id>')
def public_scrape_status(task_id):
    """公开的任务状态查询：只暴露运行状态，不含内部 result 细节，
    供引导抓取的前端轮询使用。"""
    from app.scraper.task_manager import task_manager

    task = task_manager.get(task_id)
    if not task:
        return jsonify({'success': False, 'message': '任务不存在'}), 404
    return jsonify({'success': True, 'data': {
        'status': task['status'],
        'error': task.get('error'),
    }})


@api_bp.route('/admin/scrape', methods=['POST'])
@admin_required
def trigger_scrape():
    from flask import current_app
    from app.scraper.task_manager import task_manager

    category_code = request.args.get('category', '')
    # pages 传 0 / 负数 表示全量抓取（一次性回填全部历史新闻）；正整数为只抓前 N 页
    max_pages = request.args.get('pages', 2, type=int)
    if max_pages is not None and max_pages <= 0:
        max_pages = None
    app = current_app._get_current_object()

    def run_scrape():
        with app.app_context():
            from app.scraper.spider import GLCSpider
            spider = GLCSpider()
            if category_code:
                return spider.scrape_category(category_code, max_pages)
            else:
                return spider.scrape_all(max_pages)

    task_id = task_manager.submit(run_scrape)
    return jsonify({'success': True, 'task_id': task_id, 'message': '爬取任务已启动'})


@api_bp.route('/admin/scrape/status/<task_id>')
@admin_required
def scrape_status(task_id):
    from app.scraper.task_manager import task_manager

    task = task_manager.get(task_id)
    if not task:
        return jsonify({'success': False, 'message': '任务不存在'}), 404
    return jsonify({'success': True, 'data': task})


@api_bp.route('/admin/scrape/social', methods=['POST'])
@admin_required
def trigger_social_scrape():
    """触发 MediaCrawler 抓取新媒体分类（B站 / 贴吧）。

    ?platform=bilibili|tieba  默认 bilibili
    ?keyword=                 B站搜索关键词
    ?tieba_name=              贴吧吧名（默认桂林学院）
    ?category=                入库分类 code
    """
    from flask import current_app
    from app.scraper.task_manager import task_manager

    platform = request.args.get('platform', 'bilibili').strip()
    keyword = request.args.get('keyword', '').strip()
    tieba_name = request.args.get('tieba_name', '').strip()
    category_code = request.args.get('category', '').strip()
    app = current_app._get_current_object()

    def run_social():
        with app.app_context():
            from app.scraper.mediacrawler_adapter import MediaCrawlerAdapter
            adapter = MediaCrawlerAdapter()
            return adapter.run(
                platform=platform,
                category_code=category_code or None,
                keyword=keyword or None,
                tieba_name=tieba_name or None,
            )

    task_id = task_manager.submit(run_social)
    label = '贴吧' if platform == 'tieba' else 'B站'
    return jsonify({'success': True, 'task_id': task_id,
                    'message': f'{label}抓取任务已启动（需已扫码登录 MediaCrawler）'})


@api_bp.route('/stats')
def get_stats():
    total_articles = Article.query.count()
    last_log = ScrapeLog.query.order_by(desc(ScrapeLog.started_at)).first()

    return jsonify({
        'success': True,
        'data': {
            'total_articles': total_articles,
            'last_scrape': last_log.to_dict() if last_log else None,
        }
    })
