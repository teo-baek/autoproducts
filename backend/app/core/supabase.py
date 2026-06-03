from functools import lru_cache
from supabase import create_client, Client
from app.core.config import get_settings


@lru_cache
def get_supabase() -> Client:
    s = get_settings()
    # service role 키 — 서버 전용. RISK(side-effect): 절대 프론트 노출 금지
    return create_client(s.supabase_url, s.supabase_service_key)
