-- ezmerce v2 — 델타 마이그레이션 02: 관리자 설정형 가격 노출 권한
-- (개발 정의서: "도소매 관리자 → 권한 관리 → 소매 업체별 가격 정보 보기 접근 권한 설정")
-- base(2026-06-03_v2_core.sql) 실행 후 이어서 실행.

CREATE TYPE price_visibility AS ENUM ('wholesale', 'retail', 'none');

-- 관리자가 셀러별로 설정. NULL = 미설정 → 앱에서 seller_type 기준 기본값으로 폴백
ALTER TABLE public.profiles ADD COLUMN price_visibility price_visibility;
