"""前端页面视图测试：验证各页面能正常渲染。"""


class TestViewPages:
    def test_index_page(self, client):
        resp = client.get('/')
        assert resp.status_code == 200
        assert '桂林学院' in resp.data.decode('utf-8')

    def test_category_page(self, client):
        resp = client.get('/category/xxxw')
        assert resp.status_code == 200
        assert '桂院要闻' in resp.data.decode('utf-8')

    def test_category_not_found(self, client):
        resp = client.get('/category/nonexist')
        assert resp.status_code == 404

    def test_article_page(self, client, sample_article):
        resp = client.get(f'/article/{sample_article}')
        assert resp.status_code == 200
        content = resp.data.decode('utf-8')
        assert '测试新闻标题' in content

    def test_article_increments_view_count(self, client, sample_article):
        client.get(f'/article/{sample_article}')
        client.get(f'/article/{sample_article}')
        resp = client.get(f'/api/news/{sample_article}')
        data = resp.get_json()
        assert data['data']['view_count'] >= 2

    def test_search_page(self, client):
        resp = client.get('/search')
        assert resp.status_code == 200
        assert '搜索' in resp.data.decode('utf-8')

    def test_search_with_query(self, client, sample_article):
        resp = client.get('/search?q=测试')
        assert resp.status_code == 200
        assert '测试新闻标题' in resp.data.decode('utf-8')
