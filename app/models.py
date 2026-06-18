from datetime import datetime
from app import db


class Category(db.Model):
    __tablename__ = 'category'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), nullable=False)
    code = db.Column(db.String(20), unique=True, nullable=False)
    url_path = db.Column(db.String(100), nullable=False)
    sort_order = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime, default=datetime.now)

    articles = db.relationship('Article', backref='category', lazy='dynamic')

    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'code': self.code,
            'article_count': self.articles.count()
        }


class Article(db.Model):
    __tablename__ = 'article'

    id = db.Column(db.Integer, primary_key=True)
    category_id = db.Column(db.Integer, db.ForeignKey('category.id'), nullable=False)
    title = db.Column(db.String(500), nullable=False)
    summary = db.Column(db.Text)
    content = db.Column(db.Text)
    author = db.Column(db.String(100))
    source = db.Column(db.String(200))
    original_url = db.Column(db.String(500), unique=True, nullable=False)
    cover_image = db.Column(db.String(500))
    published_at = db.Column(db.DateTime)
    view_count = db.Column(db.Integer, default=0)
    local_view_count = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime, default=datetime.now)
    updated_at = db.Column(db.DateTime, default=datetime.now, onupdate=datetime.now)

    def to_dict(self, include_content=False):
        data = {
            'id': self.id,
            'title': self.title,
            'summary': self.summary,
            'author': self.author,
            'source': self.source,
            'cover_image': self.cover_image,
            'published_at': self.published_at.strftime('%Y-%m-%d') if self.published_at else None,
            'category': self.category.name if self.category else None,
            'category_code': self.category.code if self.category else None,
            'view_count': self.local_view_count,
        }
        if include_content:
            data['content'] = self.content
            data['original_url'] = self.original_url
        return data


class ScrapeLog(db.Model):
    __tablename__ = 'scrape_log'

    id = db.Column(db.Integer, primary_key=True)
    category_id = db.Column(db.Integer, db.ForeignKey('category.id'))
    started_at = db.Column(db.DateTime, nullable=False, default=datetime.now)
    finished_at = db.Column(db.DateTime)
    articles_found = db.Column(db.Integer, default=0)
    articles_new = db.Column(db.Integer, default=0)
    status = db.Column(db.String(20), default='running')
    error_message = db.Column(db.Text)

    category = db.relationship('Category')

    def to_dict(self):
        return {
            'id': self.id,
            'category': self.category.name if self.category else 'all',
            'started_at': self.started_at.strftime('%Y-%m-%d %H:%M'),
            'finished_at': self.finished_at.strftime('%Y-%m-%d %H:%M') if self.finished_at else None,
            'articles_found': self.articles_found,
            'articles_new': self.articles_new,
            'status': self.status,
        }
