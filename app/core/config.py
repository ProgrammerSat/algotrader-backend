import os
from pydantic_settings import BaseSettings
from functools import lru_cache

# Resolve the absolute path to the backend folder (two levels up from this file)
BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DB_PATH = os.path.join(BASE_DIR, "algotrader.db")


class Settings(BaseSettings):
    fyers_app_id: str = ""
    fyers_secret_key: str = ""
    fyers_redirect_uri: str = "http://localhost:8000/api/auth/fyers/callback"

    secret_key: str = "changeme_secret"
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 1440

    database_url: str = f"sqlite:///{DB_PATH}"
    app_env: str = "development"

    gemini_api_key: str = ""  # Google Gemini API key for AI screener
    cors_origins: str = "http://localhost:5173,http://localhost:3000"

    class Config:
        env_file = ".env"
        extra = "ignore"


@lru_cache()
def get_settings() -> Settings:
    return Settings()
