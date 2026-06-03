def format_platform_code(seq: int, prefix: str = "EZM") -> str:
    return f"{prefix}-{seq:06d}"


def next_platform_code(supabase, prefix: str = "EZM") -> str:
    # RISK(race): Postgres SEQUENCE 로 원자 발급 — public.next_platform_seq() RPC (마이그레이션 _05)
    seq = supabase.rpc("next_platform_seq", {}).execute().data
    return format_platform_code(int(seq), prefix)
