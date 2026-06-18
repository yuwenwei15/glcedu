from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_cors import CORS

db = SQLAlchemy()


def create_app():
    app = Flask(__name__)
    app.config.from_object('app.config.Config')

    db.init_app(app)
    CORS(app)

    from app.api import api_bp
    app.register_blueprint(api_bp, url_prefix='/api')

    from app.views import views_bp
    app.register_blueprint(views_bp)

    from app.scraper.scheduler import init_scheduler
    init_scheduler(app)

    with app.app_context():
        db.create_all()
        _seed_categories()

    return app


def _seed_categories():
    from app.models import Category
    if Category.query.count() == 0:
        categories = [
            Category(name='桂院要闻', code='xxxw', url_path='/xwzx/xxxw.htm', sort_order=1),
            Category(name='校园快讯', code='xykx', url_path='/xwzx/xykx.htm', sort_order=2),
            Category(name='学术动态', code='xsdt', url_path='/xwzx/xsdt.htm', sort_order=3),
            Category(name='媒体桂院', code='mtgy', url_path='/xwgk2/mtgy.htm', sort_order=4),
            Category(name='通知公告', code='tzgg', url_path='/xwgk2/tzgg.htm', sort_order=5),
        ]
        db.session.add_all(categories)
        db.session.commit()
