from flask import Flask, render_template
from flask_sqlalchemy import SQLAlchemy
from flask_cors import CORS

db = SQLAlchemy()


def create_app():
    app = Flask(__name__)
    app.config.from_object('app.config.Config')

    _check_production_secrets(app)

    db.init_app(app)
    CORS(app)

    # 注册封面代理过滤器：B站等外站封面 CDN 会校验 Referer，直接外链会 403，
    # 统一改走 /cover-proxy 由服务端带 Referer 转发。
    from urllib.parse import quote
    from flask import url_for

    @app.template_filter('cover_url')
    def cover_url_filter(src):
        if not src:
            return ''
        # 本站静态资源直接放行
        if src.startswith('/') and not src.startswith('//'):
            return src
        return url_for('views.cover_proxy', url=src)

    from datetime import datetime as _dt
    app.jinja_env.globals['now'] = _dt.now

    # 给静态资源 URL 自动追加文件 mtime 版本号，改了 css/js 后回头客不再吃旧缓存
    import os as _os

    @app.template_global()
    def static_url(filename):
        try:
            mtime = int(_os.path.getmtime(_os.path.join(app.static_folder, filename)))
        except OSError:
            mtime = 0
        return url_for('static', filename=filename, v=mtime)

    from app.api import api_bp
    app.register_blueprint(api_bp, url_prefix='/api')

    from app.views import views_bp
    app.register_blueprint(views_bp)

    from app.scraper.scheduler import init_scheduler
    init_scheduler(app)

    @app.errorhandler(404)
    def page_not_found(e):
        categories = []
        try:
            from app.models import Category
            categories = Category.query.order_by(Category.sort_order).all()
        except Exception:
            pass
        return render_template('404.html', categories=categories), 404

    @app.errorhandler(500)
    def internal_error(e):
        categories = []
        try:
            from app.models import Category
            categories = Category.query.order_by(Category.sort_order).all()
        except Exception:
            pass
        return render_template('500.html', categories=categories), 500

    with app.app_context():
        db.create_all()
        _seed_categories()

    return app


def _check_production_secrets(app):
    """生产环境（APP_ENV=production）下，禁止沿用代码里的弱默认密钥，
    避免忘配 .env 时把可猜的管理员令牌/SECRET_KEY 带上线。开发环境不拦。"""
    if not app.config.get('IS_PRODUCTION'):
        return
    weak = {
        'SECRET_KEY': 'dev-secret-key',
        'ADMIN_TOKEN': 'glcedu-admin-2024',
    }
    for key, default in weak.items():
        val = app.config.get(key)
        if not val or val == default:
            raise RuntimeError(
                f'生产环境（APP_ENV=production）必须通过环境变量配置 {key}，'
                f'不能使用默认值。'
            )


def _seed_categories():
    from app.models import Category
    categories = [
        Category(name='桂院要闻', code='xxxw', url_path='/xwzx/xxxw.htm', sort_order=1),
        Category(name='校园快讯', code='xykx', url_path='/xwzx/xykx.htm', sort_order=2),
        Category(name='学术动态', code='xsdt', url_path='/xwzx/xsdt.htm', sort_order=3),
        Category(name='媒体桂院', code='mtgy', url_path='/xwgk2/mtgy.htm', sort_order=4),
        Category(name='通知公告', code='tzgg', url_path='/xwgk2/tzgg.htm', sort_order=5),
        # 新媒体动态：数据来自 MediaCrawler 抓取 B站，url_path 留空表示不参与官网爬取
        Category(name='新媒体动态', code='xmtx', url_path='', sort_order=6),
        # 贴吧讨论：数据来自 MediaCrawler 抓取桂林学院吧
        Category(name='贴吧讨论', code='tbtl', url_path='', sort_order=7),
    ]
    if Category.query.count() == 0:
        db.session.add_all(categories)
        db.session.commit()
    else:
        # 幂等补齐：已有数据的库也能确保新媒体分类存在
        existing_codes = {c for (c,) in db.session.query(Category.code).all()}
        missing = [c for c in categories if c.code not in existing_codes]
        if missing:
            db.session.add_all(missing)
            db.session.commit()
