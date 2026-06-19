from flask import Blueprint, render_template, request
from sqlalchemy import desc

from app.models import Article, Category

views_bp = Blueprint('views', __name__)


@views_bp.route('/')
def index():
    featured = Article.query.filter(
        Article.cover_image.isnot(None),
        Article.cover_image != ''
    ).order_by(desc(Article.published_at)).limit(5).all()
    categories = Category.query.order_by(Category.sort_order).all()

    category_articles = {}
    for cat in categories:
        category_articles[cat.code] = Article.query.filter_by(
            category_id=cat.id
        ).order_by(desc(Article.published_at)).limit(3).all()

    return render_template('index.html', featured=featured,
                           categories=categories,
                           category_articles=category_articles)


@views_bp.route('/category/<code>')
def category(code):
    page = request.args.get('page', 1, type=int)
    cat = Category.query.filter_by(code=code).first_or_404()
    categories = Category.query.order_by(Category.sort_order).all()

    pagination = Article.query.filter_by(category_id=cat.id).order_by(
        desc(Article.published_at)
    ).paginate(page=page, per_page=15, error_out=False)

    return render_template('category.html',
                           category=cat, articles=pagination,
                           categories=categories)


@views_bp.route('/article/<int:article_id>')
def article(article_id):
    from app import db
    art = Article.query.get_or_404(article_id)
    art.local_view_count += 1
    db.session.commit()

    categories = Category.query.order_by(Category.sort_order).all()
    related = Article.query.filter(
        Article.category_id == art.category_id,
        Article.id != art.id
    ).order_by(desc(Article.published_at)).limit(5).all()

    return render_template('article.html', article=art,
                           categories=categories, related=related)


@views_bp.route('/search')
def search():
    q = request.args.get('q', '').strip()
    page = request.args.get('page', 1, type=int)
    categories = Category.query.order_by(Category.sort_order).all()

    if not q:
        return render_template('search.html', articles=None, q='',
                               categories=categories)

    pagination = Article.query.filter(
        Article.title.contains(q) | Article.summary.contains(q)
    ).order_by(desc(Article.published_at)).paginate(
        page=page, per_page=15, error_out=False
    )

    return render_template('search.html', articles=pagination, q=q,
                           categories=categories)
