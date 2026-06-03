-- ⚠️⚠️⚠️ DESTRUCTIVE — public 스키마의 모든 테이블·데이터·타입·함수·트리거를 통째로 삭제합니다.
-- v1 → v2 전환(리셋) 할 때 "딱 한 번", Supabase SQL Editor 에서 실행하세요.
-- 실행 직후 같은 에디터에서: _v2_core.sql → _02_price_visibility.sql → _03_soft_delete.sql → _04_audit.sql 순서로 실행.
--
-- 건드리지 않는 것: auth 스키마(로그인 계정 auth.users), storage 스키마(버킷·이미지) — 그대로 유지됩니다.
--   (storage 의 v1 버킷도 비우려면 Dashboard → Storage 에서 따로 삭제)
-- 되돌릴 수 없습니다. 올바른 프로젝트인지 반드시 확인 후 실행.

drop schema public cascade;
create schema public;

-- PostgREST/Supabase 역할들에 public 권한 복구 (이거 안 하면 API가 깨짐)
grant usage on schema public to postgres, anon, authenticated, service_role;
grant all on all tables    in schema public to postgres, anon, authenticated, service_role;
grant all on all routines  in schema public to postgres, anon, authenticated, service_role;
grant all on all sequences in schema public to postgres, anon, authenticated, service_role;
alter default privileges in schema public grant all on tables    to postgres, anon, authenticated, service_role;
alter default privileges in schema public grant all on routines  to postgres, anon, authenticated, service_role;
alter default privileges in schema public grant all on sequences to postgres, anon, authenticated, service_role;
