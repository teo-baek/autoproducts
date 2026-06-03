from functools import lru_cache
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    supabase_url: str = ""
    supabase_service_key: str = ""
    supabase_jwt_secret: str = ""  # (레거시 HS256 — JWKS 검증 사용 시 불필요)
    public_base_url: str = "http://localhost:3000"  # QR 카드 URL prefix
    platform_code_prefix: str = "EZM"

    @property
    def supabase_jwks_url(self) -> str:
        # Supabase 비대칭 JWT 공개키(ES256) 엔드포인트 — SUPABASE_URL 에서 파생
        return f"{self.supabase_url.rstrip('/')}/auth/v1/.well-known/jwks.json"

    class Config:
        env_file = ".env"
        extra = "ignore"


@lru_cache
def get_settings() -> Settings:
    return Settings()
