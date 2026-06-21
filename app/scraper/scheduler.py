import os
import logging

from flask_apscheduler import APScheduler

logger = logging.getLogger(__name__)

scheduler = APScheduler()


def init_scheduler(app):
    # 多 worker 部署时只在 ENABLE_SCHEDULER=true 的那个进程启动，避免重复抓取
    if not app.config.get('ENABLE_SCHEDULER', True):
        logger.info('调度器已禁用（ENABLE_SCHEDULER=false），跳过启动')
        return

    # 开发模式下 Flask reloader 会起父子两个进程，只在真正服务请求的子进程
    # （WERKZEUG_RUN_MAIN=true）里启动，避免定时任务跑两遍
    if app.debug and not os.environ.get('WERKZEUG_RUN_MAIN'):
        return

    scheduler.init_app(app)

    @scheduler.task('cron', id='daily_scrape', hour=6, minute=0,
                    timezone='Asia/Shanghai')
    def daily_scrape():
        with app.app_context():
            from app.scraper.spider import GLCSpider
            spider = GLCSpider()
            spider.scrape_all(max_pages=3)

    @scheduler.task('cron', id='daily_social_scrape', hour=6, minute=30,
                    timezone='Asia/Shanghai')
    def daily_social_scrape():
        with app.app_context():
            from app.scraper.mediacrawler_adapter import MediaCrawlerAdapter
            adapter = MediaCrawlerAdapter()
            adapter.run(platform='bilibili')
            adapter.run(platform='tieba')

    scheduler.start()
