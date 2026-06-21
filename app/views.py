from flask import Blueprint, render_template, request, Response, redirect
from sqlalchemy import desc, func

from app.models import Article, Category

views_bp = Blueprint('views', __name__)


@views_bp.route('/')
def index():
    from app import db
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

    # 一次性聚合各分类文章数，避免模板中 N+1 查询
    counts = dict(
        db.session.query(Article.category_id, func.count(Article.id))
        .group_by(Article.category_id).all()
    )
    category_counts = {cat.code: counts.get(cat.id, 0) for cat in categories}

    return render_template('index.html', featured=featured,
                           categories=categories,
                           category_articles=category_articles,
                           category_counts=category_counts)


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
    Article.query.filter_by(id=art.id).update(
        {Article.local_view_count: Article.local_view_count + 1})
    db.session.commit()
    art.local_view_count += 1

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


@views_bp.route('/cover-proxy')
def cover_proxy():
    """图片代理：B站封面 CDN 会校验 Referer，带本站 Referer 直接访问会 403。
    由服务端转发并附带 B站 Referer，避开热链限制。
    仅用于代理 Article.cover_image（B站/外站封面），不开放任意 URL。
    """
    import requests as _requests
    from urllib.parse import urlparse

    url = request.args.get('url', '').strip()
    if not url:
        return Response(status=404)

    parsed = urlparse(url)
    if parsed.scheme not in ('http', 'https'):
        return Response(status=400)

    # 仅允许已知的外站图片域名（B站 CDN / 百度贴吧头像 / 官网），防止成为开放代理
    allowed_hosts = (
        'i0.hdslb.com', 'i1.hdslb.com', 'i2.hdslb.com',
        'gss0.bdstatic.com', 'gss1.bdstatic.com', 'gss2.bdstatic.com',
        'gss3.bdstatic.com',
        'glc.edu.cn', 'www.glc.edu.cn',
    )
    if parsed.hostname not in allowed_hosts:
        return Response(status=403)

    try:
        upstream = parsed.geturl()
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
                          'AppleWebKit/537.36 (KHTML, like Gecko) '
                          'Chrome/120.0 Safari/537.36',
            'Referer': 'https://www.bilibili.com/',
        }
        resp = _requests.get(upstream, headers=headers, timeout=10, stream=True)
        if resp.status_code != 200:
            return Response(status=resp.status_code)

        excluded = {'content-encoding', 'transfer-encoding', 'connection',
                    'content-length', 'keep-alive'}
        out_headers = [(k, v) for k, v in resp.headers.items()
                       if k.lower() not in excluded]
        # 缓存 7 天，减少回源
        out_headers.append(('Cache-Control', 'public, max-age=604800'))
        return Response(resp.content, status=200,
                        content_type=resp.headers.get('Content-Type', 'image/jpeg'),
                        headers=out_headers)
    except _requests.RequestException:
        return Response(status=502)
