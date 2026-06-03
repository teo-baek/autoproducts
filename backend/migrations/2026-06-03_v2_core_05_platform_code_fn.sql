-- ezmerce v2 — 델타 마이그레이션 05: platform_code 시퀀스 RPC 함수
-- 이유: 앱(supabase-py)은 PostgREST RPC 로만 함수 호출 가능. nextval(pg_catalog)은 직접 호출 불가
--       → public 래퍼 함수를 만들어 RPC 로 노출. base(_v2_core)에서 만든 platform_code_seq 사용.
-- 실행 순서: base → _02 → _03 → _04 → 본 파일

CREATE OR REPLACE FUNCTION public.next_platform_seq()
RETURNS BIGINT
LANGUAGE sql VOLATILE AS $$
  SELECT nextval('public.platform_code_seq');
$$;

GRANT EXECUTE ON FUNCTION public.next_platform_seq() TO anon, authenticated, service_role;
