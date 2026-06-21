"""爬虫解析逻辑测试：验证列表页和文章页的 HTML 解析。"""
from app.scraper.spider import GLCSpider, extract_pdf_urls, build_pdf_content


SAMPLE_LIST_HTML = '''
<ul>
  <li id="line_u10_0">
    <a class="block" href="../info/1001/12345.htm">
      <h2>桂林学院召开2025年工作会议</h2>
      <div class="zhai">会议总结了过去一年的成绩...</div>
    </a>
    <div class="date3">
      <div>2025-03</div>
      <p>15</p>
    </div>
  </li>
  <li id="line_u10_1">
    <a class="block" href="../info/1001/12346.htm">
      <h2>我校学生获全国大赛一等奖</h2>
      <div class="zhai">在近日举办的比赛中...</div>
    </a>
    <div class="date3">
      <div>2025-03</div>
      <p>14</p>
    </div>
  </li>
</ul>
'''

SAMPLE_ARTICLE_HTML = '''
<html><body>
<div id="vsb_content_2">
  <p>作者：张三</p>
  <p>来源：新闻中心</p>
  <p><img src="/images/news/photo.jpg"/>这是正文内容。</p>
</div>
</body></html>
'''


class TestListPageParsing:
    def test_parse_list_page(self, app):
        with app.app_context():
            spider = GLCSpider()
            items = spider._parse_list_page(SAMPLE_LIST_HTML)
            assert len(items) == 2
            assert items[0]['title'] == '桂林学院召开2025年工作会议'
            assert '/info/1001/12345.htm' in items[0]['url']
            assert items[0]['summary'] == '会议总结了过去一年的成绩...'

    def test_parse_empty_page(self, app):
        with app.app_context():
            spider = GLCSpider()
            items = spider._parse_list_page('<html><body></body></html>')
            assert items == []


class TestArticlePageParsing:
    def test_parse_article_page(self, app):
        with app.app_context():
            spider = GLCSpider()
            result = spider._parse_article_page(SAMPLE_ARTICLE_HTML)
            assert result is not None
            assert '正文内容' in result['content']
            assert result['author'] == '张三'
            assert result['source'] == '新闻中心'
            assert 'https://www.glc.edu.cn/images/news/photo.jpg' in result['cover_image']

    def test_parse_no_content(self, app):
        with app.app_context():
            spider = GLCSpider()
            result = spider._parse_article_page('<html><body><p>no content div</p></body></html>')
            assert result is None


class TestPDFExtraction:
    def test_extract_pdf_urls(self):
        html = '''<script>showVsbpdfIframe("/docs/notice.pdf", "100%")</script>
                  <a href="/attachment/report.pdf">下载</a>'''
        urls = extract_pdf_urls(html)
        assert len(urls) == 2
        assert 'https://www.glc.edu.cn/docs/notice.pdf' in urls[0]

    def test_build_pdf_content(self):
        urls = ['https://www.glc.edu.cn/docs/test.pdf']
        html = build_pdf_content(urls)
        assert 'test.pdf' in html
        assert 'target="_blank"' in html

    def test_no_pdf(self):
        assert extract_pdf_urls('<p>normal content</p>') == []
        assert build_pdf_content([]) == ''
