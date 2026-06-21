import os
from dotenv import load_dotenv

load_dotenv()


class Config:
    SECRET_KEY = os.getenv('SECRET_KEY', 'dev-secret-key')
    SQLALCHEMY_DATABASE_URI = os.getenv('DATABASE_URI')
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # MySQL 默认 8 小时断开空闲连接；pool_recycle 在到点前主动回收，
    # pool_pre_ping 取连接前先探活，避免半夜空闲后报 "MySQL server has gone away"。
    SQLALCHEMY_ENGINE_OPTIONS = {
        'pool_recycle': 280,
        'pool_pre_ping': True,
    }

    # 是否生产环境：生产下禁止沿用弱默认密钥（见 app/__init__.py 启动校验）
    IS_PRODUCTION = os.getenv('APP_ENV', '').lower() == 'production'

    SCHEDULER_API_ENABLED = True
    SCHEDULER_TIMEZONE = 'Asia/Shanghai'
    # 调度器开关：多 worker 部署时只在一个进程设为 true，避免每个进程都跑一遍定时抓取
    ENABLE_SCHEDULER = os.getenv('ENABLE_SCHEDULER', 'true').lower() in ('1', 'true', 'yes')

    # Scraper settings
    SCRAPE_BASE_URL = 'https://www.glc.edu.cn'
    SCRAPE_DELAY = 1.5  # seconds between requests
    SCRAPE_MAX_PAGES = 3  # pages per category per run

    # MediaCrawler settings (B站 新媒体动态分类)
    MEDIACRAWLER_DIR = os.getenv('MEDIACRAWLER_DIR', r'D:\ai\MediaCrawler')
    # MediaCrawler 自带依赖较重（playwright/typer 等），用它自己的 venv 解释器运行 main.py；
    # 留空则回退到当前 Python 解释器。
    MEDIACRAWLER_PYTHON = os.getenv('MEDIACRAWLER_PYTHON', r'D:\ai\MediaCrawler\venv\Scripts\python.exe')
    MEDIACRAWLER_OUTPUT_DIR = os.getenv('MEDIACRAWLER_OUTPUT_DIR', '')  # 留空则自动探测 data/bili/json
    MEDIACRAWLER_KEYWORD = os.getenv('MEDIACRAWLER_KEYWORD', '桂林学院')
    MEDIACRAWLER_TIMEOUT = int(os.getenv('MEDIACRAWLER_TIMEOUT', '600'))  # 单次最长秒数
    MEDIACRAWLER_CATEGORY_CODE = os.getenv('MEDIACRAWLER_CATEGORY_CODE', 'xmtx')

    # 贴吧
    MEDIACRAWLER_CATEGORY_CODE_TIEBA = os.getenv('MEDIACRAWLER_CATEGORY_CODE_TIEBA', 'tbtl')
    MEDIACRAWLER_TIEBA_NAME = os.getenv('MEDIACRAWLER_TIEBA_NAME', '桂林学院')
    MEDIACRAWLER_TIEBA_COOKIE = os.getenv('MEDIACRAWLER_TIEBA_COOKIE', '')

    # Admin
    ADMIN_TOKEN = os.getenv('ADMIN_TOKEN', 'glcedu-admin-2024')

    # AI 新闻总结（OpenAI 兼容接口 / 商汤 SenseNova）
    AI_API_KEY = os.getenv('AI_API_KEY', '')
    AI_BASE_URL = os.getenv('AI_BASE_URL', 'https://token.sensenova.cn/v1')
    AI_MODEL = os.getenv('AI_MODEL', 'sensenova-6.7-flash-lite')
    AI_TEMPERATURE = float(os.getenv('AI_TEMPERATURE', '0.6'))
    AI_MAX_TOKENS = int(os.getenv('AI_MAX_TOKENS', '600'))
    AI_TIMEOUT = int(os.getenv('AI_TIMEOUT', '60'))
