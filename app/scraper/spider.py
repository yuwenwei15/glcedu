import time
import re
from datetime import datetime

import requests
from bs4 import BeautifulSoup
from flask import current_app

from app import db
from app.models import Article, Category, ScrapeLog


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

                    article = Article(
                        category_id=category.id,
                        title=item['title'],
                        summary=item.get('summary', ''),
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

        # Extract first image as cover
        cover_image = ''
        first_img = content_div.find('img')
        if first_img:
            cover_image = first_img.get('src', '')

        return {
            'content': content_html,
            'author': author,
            'source': source,
            'cover_image': cover_image,
        }
