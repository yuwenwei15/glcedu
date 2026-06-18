from flask_apscheduler import APScheduler

scheduler = APScheduler()


def init_scheduler(app):
    scheduler.init_app(app)

    @scheduler.task('cron', id='daily_scrape', hour=6, minute=0,
                    timezone='Asia/Shanghai')
    def daily_scrape():
        with app.app_context():
            from app.scraper.spider import GLCSpider
            spider = GLCSpider()
            spider.scrape_all(max_pages=3)

    scheduler.start()
