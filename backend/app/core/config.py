from pydantic_settings import BaseSettings
from functools import lru_cache

class Settings(BaseSettings):
    app_name: str = "FeedPilot API"
    app_version: str = "0.1.0"
    debug: bool = False
    anthropic_api_key: str = ""
    database_url: str = ""

    class Config:
        env_file = ".env"

@lru_cache()
def get_settings():
    return Settings()