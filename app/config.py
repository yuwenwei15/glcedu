import os
from dotenv import load_dotenv

load_dotenv()


class Config:
    SECRET_KEY = os.getenv('SECRET_KEY', 'dev-secret-key')
    SQLALCHEMY_DATABASE_URI = os.getenv('DATABASE_URI')
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    SCHEDULER_API_ENABLED = True
    SCHEDULER_TIMEZONE = 'Asia/Shanghai'

    # Scraper settings
    SCRAPE_BASE_URL = 'https://www.glc.edu.cn'
    SCRAPE_DELAY = 1.5  # seconds between requests
    SCRAPE_MAX_PAGES = 3  # pages per category per run
