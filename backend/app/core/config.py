from functools import lru_cache
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    supabase_url: str = ""
    supabase_service_key: str = ""
    supabase_jwt_secret: str = ""
    public_base_url: str = "http://localhost:3000"  # QR 카드 URL prefix
    platform_code_prefix: str = "EZM"

    class Config:
        env_file = ".env"
        extra = "ignore"


@lru_cache
def get_settings() -> Settings:
    return Settings()
