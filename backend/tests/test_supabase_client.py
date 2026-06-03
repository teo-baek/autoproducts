from app.core.supabase import get_supabase

def test_get_supabase_is_singleton(monkeypatch):
    monkeypatch.setenv("SUPABASE_URL", "https://x.supabase.co")
    monkeypatch.setenv("SUPABASE_SERVICE_KEY", "svc")
    get_supabase.cache_clear()
    a = get_supabase()
    b = get_supabase()
    assert a is b
