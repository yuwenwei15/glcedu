import time
import re
from datetime import datetime

import requests
from bs4 import BeautifulSoup
from flask import current_app

from app import db
from app.models import Article, Category, ScrapeLog


PDF_BASE_URL = 'https://www.glc.edu.cn'


def _pdf_absolute_url(url, base=PDF_BASE_URL):
    """Resolve a scraped URL against the GLC base URL."""
    url = url.strip()
    if url.startswith('http'):
        return url
    return base + ('' if url.startswith('/') else '/') + url


def extract_pdf_urls(content_html):
    """Return the absolute PDF URLs referenced inside article content HTML.

    GLC publishes some notices as PDFs, embedded via a JS helper
    ``showVsbpdfIframe("<url>", ...)`` and/or plain attachment ``<a>`` links.
    """
    text = content_html or ''
    urls = re.findall(r'showVsbpdfIframe\(\s*["\']([^"\']+)["\']', text)
    urls += re.findall(r'href=["\']([^"\']*\.pdf[^"\']*)["\']', text, flags=re.I)

    seen, result = set(), []
    for u in urls:
        abs_u = _pdf_absolute_url(u)
        if abs_u not in seen:
            seen.add(abs_u)
            result.append(abs_u)
    return result


def build_pdf_content(pdf_urls):
    """Build a clean 'view/download PDF' block to replace an unusable JS embed.

    The GLC PDF cannot be inline-embedded (X-Frame-Options: SAMEORIGIN) nor
    usefully text-extracted (scanned images), so we surface a direct link that
    the browser renders natively in a new tab.
    """
    if not pdf_urls:
        return ''
    primary = pdf_urls[0]
    return (
        '<div class="pdf-embed-card">'
        '<span class="pdf-embed-icon material-symbols-outlined">picture_as_pdf</span>'
        '<div class="pdf-embed-body">'
        '<p class="pdf-embed-title">本文以 PDF 附件形式发布</p>'
        '<p class="pdf-embed-desc">完整内容无法在网页内直接呈现，请点击下方按钮在新窗口查看或下载原文。</p>'
        f'<a class="pdf-embed-btn" href="{primary}" target="_blank" rel="noopener">查看 / 下载 PDF 原文</a>'
        '</div>'
        '</div>'
    )


class GLCSpider:
    def __init__(self):
        self.base_url = current_app.config['SCRAPE_BASE_URL']
        self.delay = current_app.config['SCRAPE_DELAY']
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        })

    def _fetch(self, url):
        resp = self.session.get(url, timeout=15)
        resp.encoding = 'utf-8'
        return resp.text

    def scrape_category(self, category_code, max_pages=3):
        category = Category.query.filter_by(code=category_code).first()
        if not category:
            return

        log = ScrapeLog(category_id=category.id, started_at=datetime.now())
        db.session.add(log)
        db.session.commit()

        total_found = 0
        total_new = 0

        try:
            for page_num in range(1, max_pages + 1):
                url = self._build_list_url(category, page_num)
                if not url:
                    break

                html = self._fetch(url)
                articles = self._parse_list_page(html)

                if not articles:
                    break

                total_found += len(articles)

                for item in articles:
                    item_url = item['url']
                    if item_url.startswith('http') and 'glc.edu.cn' not in item_url:
                        continue

                    if item_url.startswith('http'):
                        full_url = item_url
                    else:
                        full_url = self.base_url + item_url

                    exists = Article.query.filter_by(original_url=full_url).first()
                    if exists:
                        continue

                    time.sleep(self.delay)
                    try:
                        article_html = self._fetch(full_url)
                        article_data = self._parse_article_page(article_html)
                    except Exception:
                        continue

                    if not article_data:
                        continue

                    summary = item.get('summary', '')
                    if not summary and article_data.get('is_pdf'):
                        summary = '本文为 PDF 附件公告'

                    article = Article(
                        category_id=category.id,
                        title=item['title'],
                        summary=summary,
                        content=article_data['content'],
                        author=article_data.get('author', ''),
                        source=article_data.get('source', ''),
                        original_url=full_url,
                        cover_image=article_data.get('cover_image', ''),
                        published_at=item.get('date'),
                        view_count=0,
                    )
                    db.session.add(article)
                    total_new += 1

                db.session.commit()
                time.sleep(self.delay)

            log.status = 'success'
        except Exception as e:
            log.status = 'failed'
            log.error_message = str(e)
            db.session.rollback()
        finally:
            log.finished_at = datetime.now()
            log.articles_found = total_found
            log.articles_new = total_new
            db.session.merge(log)
            db.session.commit()

        return {'found': total_found, 'new': total_new}

    def scrape_all(self, max_pages=3):
        categories = Category.query.order_by(Category.sort_order).all()
        results = {}
        for cat in categories:
            results[cat.code] = self.scrape_category(cat.code, max_pages)
        return results

    def _build_list_url(self, category, page_num):
        if page_num == 1:
            return self.base_url + category.url_path

        path = category.url_path
        base_path = path.rsplit('.', 1)[0]

        if not hasattr(self, '_page_totals'):
            self._page_totals = {}

        if category.code not in self._page_totals:
            html = self._fetch(self.base_url + category.url_path)
            total = self._extract_total_pages(html)
            self._page_totals[category.code] = total

        total = self._page_totals[category.code]
        page_val = total - page_num
        if page_val < 1:
            return None
        return f"{self.base_url}{base_path}/{page_val}.htm"

    def _extract_total_pages(self, html):
        match = re.search(r'/(\d+)页', html)
        if match:
            return int(match.group(1))
        return 10  # fallback

    def _parse_list_page(self, html):
        soup = BeautifulSoup(html, 'lxml')
        items = []

        for li in soup.select('li[id^="line_u10_"]'):
            link = li.select_one('a.block')
            if not link:
                continue

            href = link.get('href', '')
            if href.startswith('..'):
                href = href.replace('..', '', 1)

            title_el = link.select_one('h2')
            title = title_el.get_text(strip=True) if title_el else ''

            summary_el = link.select_one('.zhai')
            summary = summary_el.get_text(strip=True) if summary_el else ''

            date_div = li.select_one('.date3')
            pub_date = None
            if date_div:
                day_el = date_div.select_one('p')
                month_el = date_div.select_one('div')
                if day_el and month_el:
                    try:
                        date_str = f"{month_el.get_text(strip=True)}-{day_el.get_text(strip=True)}"
                        pub_date = datetime.strptime(date_str, '%Y-%m-%d')
                    except ValueError:
                        pass

            if title and href:
                items.append({
                    'title': title,
                    'url': href,
                    'summary': summary,
                    'date': pub_date,
                })

        return items

    def _parse_article_page(self, html):
        soup = BeautifulSoup(html, 'lxml')

        content_div = soup.select_one('[id*="vsb_content"]') or soup.select_one('.v_news_content')
        if not content_div:
            content_div = soup.select_one('#content') or soup.find('div', class_='content')

        if not content_div:
            return None

        # Fix image URLs
        for img in content_div.find_all('img'):
            src = img.get('src', '')
            if src and not src.startswith('http'):
                img['src'] = self.base_url + (src if src.startswith('/') else '/' + src)

        content_html = str(content_div)

        # PDF notices: GLC embeds the PDF via JS (showVsbpdfIframe) which renders
        # blank on our site, and the PDF cannot be inline-embedded (X-Frame-Options:
        # SAMEORIGIN) nor usefully text-extracted (scanned images). Replace the
        # broken embed with a clean view/download block.
        pdf_urls = extract_pdf_urls(content_html)
        is_pdf = bool(pdf_urls)
        if is_pdf:
            content_html = build_pdf_content(pdf_urls)

        # Extract metadata
        author = ''
        source = ''
        meta_text = soup.get_text()

        author_match = re.search(r'作者[：:]\s*([^\s]+)', meta_text)
        if author_match:
            author = author_match.group(1).strip()

        source_match = re.search(r'来源[：:]\s*([^\s]+)', meta_text)
        if source_match:
            source = source_match.group(1).strip()

        # Extract first image as cover (PDF notices carry no usable image)
        cover_image = ''
        if not is_pdf:
            first_img = content_div.find('img')
            if first_img:
                cover_image = first_img.get('src', '')

        return {
            'content': content_html,
            'author': author,
            'source': source,
            'cover_image': cover_image,
            'is_pdf': is_pdf,
        }
