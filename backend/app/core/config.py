from functools import lru_cache
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    supabase_url: str = ""
    supabase_service_key: str = ""
    supabase_jwt_secret: str = ""  # (레거시 HS256 — JWKS 검증 사용 시 불필요)
    public_base_url: str = "http://localhost:3555"  # 프론트 공개 카드 prefix({base}/p?code=…). dev=프론트 포트
    platform_code_prefix: str = "EZM"

    # ── GCS(파일 저장소) — Supabase Storage 대체. ⚠️ DB/Auth/JWT 는 계속 Supabase(위 SUPABASE_*) ──
    gcs_project: str = ""            # GCP 프로젝트 ID(예: ezmerce). 빈값이면 ADC 기본 프로젝트
    gcs_product_bucket: str = ""     # 공개 버킷(상품 이미지)
    gcs_doc_bucket: str = ""         # 비공개 버킷(가입 서류 PII, 서비스계정 전용)
    gcs_public_base: str = ""        # 공개 read URL prefix. 빈값이면 storage.googleapis.com/{버킷} 으로 파생(CDN 쓰면 여기 지정)
    gcs_signing_sa: str = ""         # 키리스 V4 서명용 서비스계정 이메일(런타임 SA). 빈값이면 ADC 자격증명으로 직접 서명 시도

    @property
    def supabase_jwks_url(self) -> str:
        # Supabase 비대칭 JWT 공개키(ES256) 엔드포인트 — SUPABASE_URL 에서 파생
        return f"{self.supabase_url.rstrip('/')}/auth/v1/.well-known/jwks.json"

    @property
    def gcs_public_base_url(self) -> str:
        # 공개 이미지 URL prefix. 명시값 우선, 없으면 공개 버킷 표준 호스트로 파생.
        base = self.gcs_public_base.rstrip("/")
        return base or f"https://storage.googleapis.com/{self.gcs_product_bucket}"

    class Config:
        env_file = ".env"
        extra = "ignore"


@lru_cache
def get_settings() -> Settings:
    return Settings()
