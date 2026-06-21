"""API 接口测试：验证新闻列表、详情、搜索、分类等接口的返回格式与状态码。"""


class TestNewsAPI:
    def test_list_news(self, client, sample_article):
        resp = client.get('/api/news')
        assert resp.status_code == 200
        data = resp.get_json()
        assert data['success'] is True
        assert 'data' in data
        assert 'pagination' in data
        assert isinstance(data['data'], list)

    def test_list_news_with_category(self, client, sample_article):
        resp = client.get('/api/news?category=xxxw')
        assert resp.status_code == 200
        data = resp.get_json()
        assert data['success'] is True
        assert len(data['data']) >= 1

    def test_get_news_detail(self, client, sample_article):
        resp = client.get(f'/api/news/{sample_article}')
        assert resp.status_code == 200
        data = resp.get_json()
        assert data['success'] is True
        assert data['data']['title'] == '测试新闻标题'
        assert 'content' in data['data']

    def test_get_news_not_found(self, client):
        resp = client.get('/api/news/99999')
        assert resp.status_code == 404

    def test_search_news(self, client, sample_article):
        resp = client.get('/api/news/search?q=测试')
        assert resp.status_code == 200
        data = resp.get_json()
        assert data['success'] is True
        assert len(data['data']) >= 1

    def test_search_empty_query(self, client):
        resp = client.get('/api/news/search?q=')
        assert resp.status_code == 200
        data = resp.get_json()
        assert data['data'] == []

    def test_list_categories(self, client):
        resp = client.get('/api/categories')
        assert resp.status_code == 200
        data = resp.get_json()
        assert data['success'] is True
        assert len(data['data']) >= 5

    def test_get_stats(self, client, sample_article):
        resp = client.get('/api/stats')
        assert resp.status_code == 200
        data = resp.get_json()
        assert data['success'] is True
        assert data['data']['total_articles'] >= 1


class TestAdminAuth:
    def test_scrape_without_token(self, client):
        resp = client.post('/api/admin/scrape')
        assert resp.status_code == 401
        data = resp.get_json()
        assert data['success'] is False

    def test_scrape_with_wrong_token(self, client):
        resp = client.post('/api/admin/scrape',
                           headers={'X-Admin-Token': 'wrong-token'})
        assert resp.status_code == 401
        data = resp.get_json()
        assert data['success'] is False

    def test_scrape_with_valid_token(self, client):
        resp = client.post('/api/admin/scrape',
                           headers={'X-Admin-Token': 'test-token'})
        assert resp.status_code == 200
        data = resp.get_json()
        assert data['success'] is True
        assert 'task_id' in data
