import pytest

from app import create_app, db as _db
from app.models import Category, Article


@pytest.fixture(scope='session')
def app():
    """Create a test Flask app with an in-memory SQLite database."""
    import os
    os.environ['DATABASE_URI'] = 'sqlite:///:memory:'
    os.environ['ADMIN_TOKEN'] = 'test-token'

    application = create_app()
    application.config.update({
        'TESTING': True,
        'SQLALCHEMY_DATABASE_URI': 'sqlite:///:memory:',
        'SCHEDULER_API_ENABLED': False,
    })

    with application.app_context():
        _db.create_all()
        yield application
        _db.drop_all()


@pytest.fixture
def db(app):
    with app.app_context():
        yield _db


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def sample_article(app, db):
    """Insert a sample article for testing (unique per call)."""
    import uuid
    with app.app_context():
        cat = Category.query.filter_by(code='xxxw').first()
        unique_id = uuid.uuid4().hex[:8]
        art = Article(
            category_id=cat.id,
            title='测试新闻标题',
            summary='这是一条测试新闻的摘要内容',
            content='<p>测试新闻正文内容</p>',
            author='测试作者',
            source='测试来源',
            original_url=f'https://www.glc.edu.cn/test/article-{unique_id}.htm',
            view_count=0,
            local_view_count=0,
        )
        db.session.add(art)
        db.session.commit()
        art_id = art.id
    return art_id
