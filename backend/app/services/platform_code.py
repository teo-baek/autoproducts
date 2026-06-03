def format_platform_code(seq: int, prefix: str = "EZM") -> str:
    return f"{prefix}-{seq:06d}"


def next_platform_code(supabase, prefix: str = "EZM") -> str:
    # RISK(race): 반드시 Postgres SEQUENCE(nextval)로 발급 — 앱 카운터 금지
    seq = supabase.rpc("nextval", {"seq_name": "platform_code_seq"}).execute().data
    return format_platform_code(int(seq), prefix)
