import os
from pathlib import Path

from dotenv import load_dotenv


CURRENT_FILE = Path(__file__).resolve()
BACKEND_DIR = CURRENT_FILE.parents[1]
PROJECT_ROOT = CURRENT_FILE.parents[2]

# Prefer the project root .env when present, but keep backend/.env working too.
load_dotenv(PROJECT_ROOT / ".env")
load_dotenv(BACKEND_DIR / ".env")


class BaseConfig:
    SECRET_KEY = os.getenv("SECRET_KEY", "dev-secret-key-change-me-1234567890")
    JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY", "dev-jwt-secret-key-change-me-1234567890")
    SQLALCHEMY_DATABASE_URI = os.getenv(
        "DATABASE_URL",
        "postgresql+psycopg://prognose:prognose@localhost:5432/prognose",
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
    APP_VERSION = os.getenv("APP_VERSION", "0.1.0")
    STRIPE_SECRET_KEY = os.getenv("STRIPE_SECRET_KEY", "")
    STRIPE_WEBHOOK_SECRET = os.getenv("STRIPE_WEBHOOK_SECRET", "")
    STRIPE_SUCCESS_URL = os.getenv("STRIPE_SUCCESS_URL", "http://localhost:3000/billing/success")
    STRIPE_CANCEL_URL = os.getenv("STRIPE_CANCEL_URL", "http://localhost:3000/billing/cancel")
    OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
    OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-5-mini")
    AI_EVENT_GENERATION_MAX_COUNT = int(os.getenv("AI_EVENT_GENERATION_MAX_COUNT", "5"))
    AI_MIN_CLOSE_HOURS = int(os.getenv("AI_MIN_CLOSE_HOURS", "24"))
    AI_MAX_SOURCE_URLS = int(os.getenv("AI_MAX_SOURCE_URLS", "5"))
    AI_SOURCE_TIMEOUT_SECONDS = int(os.getenv("AI_SOURCE_TIMEOUT_SECONDS", "8"))
    AI_SOURCE_TEXT_CHAR_LIMIT = int(os.getenv("AI_SOURCE_TEXT_CHAR_LIMIT", "3000"))
    MAX_CONTENT_LENGTH = int(os.getenv("MAX_CONTENT_LENGTH", "1048576"))
    AI_DEFAULT_SOURCE_URLS = [
        value.strip()
        for value in os.getenv("AI_DEFAULT_SOURCE_URLS", "").split(",")
        if value.strip()
    ]
    AI_BOT_EMAIL = os.getenv("AI_BOT_EMAIL", "ai-bot@prognose.local")
    AI_BOT_HANDLE = os.getenv("AI_BOT_HANDLE", "ai_liquidity_bot")
    MARKET_DATA_SEARCH_LIMIT = int(os.getenv("MARKET_DATA_SEARCH_LIMIT", "8"))
    MARKET_DATA_TRACKED_SYMBOL_LIMIT = int(os.getenv("MARKET_DATA_TRACKED_SYMBOL_LIMIT", "24"))
    MARKET_DATA_WEBSOCKET_ENABLED = os.getenv("MARKET_DATA_WEBSOCKET_ENABLED", "true").strip().lower() == "true"
    JSON_SORT_KEYS = False
    CORS_ORIGINS = [
        origin.strip()
        for origin in os.getenv("CORS_ORIGINS", "http://localhost:3000").split(",")
        if origin.strip()
    ]
    CELERY = {
        "broker_url": REDIS_URL,
        "result_backend": REDIS_URL,
        "task_ignore_result": True,
    }


class DevelopmentConfig(BaseConfig):
    DEBUG = True


class TestingConfig(BaseConfig):
    TESTING = True
    SQLALCHEMY_DATABASE_URI = os.getenv("TEST_DATABASE_URL", "sqlite+pysqlite:///:memory:")
    MARKET_DATA_WEBSOCKET_ENABLED = False
    CELERY = {
        "broker_url": "memory://",
        "result_backend": "cache+memory://",
        "task_ignore_result": True,
    }


class ProductionConfig(BaseConfig):
    DEBUG = False


CONFIG_MAP = {
    "development": DevelopmentConfig,
    "testing": TestingConfig,
    "production": ProductionConfig,
}


def get_config(config_name: str | None = None) -> type[BaseConfig]:
    env_name = config_name or os.getenv("FLASK_ENV", "development")
    return CONFIG_MAP.get(env_name, DevelopmentConfig)
