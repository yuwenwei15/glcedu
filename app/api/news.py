from flask import request, jsonify
from sqlalchemy import desc

from app import db
from app.api import api_bp
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
    article.local_view_count += 1
    db.session.commit()
    return jsonify({'success': True, 'data': article.to_dict(include_content=True)})


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


@api_bp.route('/admin/scrape', methods=['POST'])
def trigger_scrape():
    from flask import current_app
    from app.scraper.task_manager import task_manager

    category_code = request.args.get('category', '')
    max_pages = request.args.get('pages', 2, type=int)
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
def scrape_status(task_id):
    from app.scraper.task_manager import task_manager

    task = task_manager.get(task_id)
    if not task:
        return jsonify({'success': False, 'message': '任务不存在'}), 404
    return jsonify({'success': True, 'data': task})


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
