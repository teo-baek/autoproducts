-- _PRELAUNCH_wipe_test_data.sql
-- ============================================================================
-- ⚠️⚠️ 운영 오픈 전 "테스트 데이터 전체 하드 삭제" 1회용 스크립트 ⚠️⚠️
--   - 되돌릴 수 없음(soft delete 아님 — 진짜 DELETE).
--   - 남기는 것: 관리자(LALAS) 계정 1개 + LALAS 테넌트(wholesale_managers) 1행. 그 외 전부 삭제.
--   - 삭제 대상: 모든 상품/SKU/이미지/업로드잡 · 모든 도매업체 · 모든 도매상↔관리자 연결 ·
--                모든 승인/거절 이력 · 관리자 1명 빼고 모든 계정(profiles + auth.users) · 에이전시 전부.
--
-- 실행 위치: Supabase SQL Editor.  ★ 반드시 "운영 프로젝트"가 맞는지 먼저 확인하고 실행 ★
--
-- 권장 순서:
--   1) 백업: 대시보드 Database → Backups(또는 PITR) 로 스냅샷 확보.
--   2) 아래 §0(검증 SELECT)만 먼저 실행 → 남길 관리자/테넌트가 맞는지 눈으로 확인.
--   3) §1 을 "끝의 COMMIT 을 지우고 ROLLBACK 으로" 한 번 실행(드라이런) → 카운트가 기대대로인지 확인.
--   4) 맞으면 §1 의 끝을 다시 COMMIT 으로 바꿔 실행 → 확정 삭제.
--
-- 남길 고정값(2026-06-09 시드 기준):
--   관리자 id (profiles=auth.users 동일) = f50945ce-0fec-4241-96ed-29e3dc97bade  (로그인 rythmn@naver.com)
--   LALAS 테넌트 id                       = 1a1a0000-0000-0000-0000-00000000a1a5
-- ============================================================================


-- ── §0. 검증: 남길 대상이 맞는지 먼저 확인 (이 블록만 따로 실행) ───────────────────
SELECT id, email FROM auth.users
 WHERE id = 'f50945ce-0fec-4241-96ed-29e3dc97bade';            -- 1행(라라스 관리자 이메일)이어야 함

SELECT id, role, status, company_name, manager_id FROM public.profiles
 WHERE id = 'f50945ce-0fec-4241-96ed-29e3dc97bade';            -- role='admin', manager_id=1a1a...a1a5

SELECT id, name FROM public.wholesale_managers
 WHERE id = '1a1a0000-0000-0000-0000-00000000a1a5';            -- 'LALAS' 1행


-- ── §1. 삭제 (트랜잭션) — 끝의 COMMIT/ROLLBACK 으로 확정/취소 ──────────────────────
BEGIN;

-- 1) 승인/거절 이력 전체
DELETE FROM public.manager_rejections;

-- 2) 도매업체 전체 → FK ON DELETE CASCADE 로 아래가 함께 삭제됨:
--    products → product_skus / product_images, upload_jobs, manager_wholesalers
DELETE FROM public.wholesalers;

-- 3) 에이전시(테스트분) 전체
DELETE FROM public.agencies;

-- 4) 테넌트: LALAS 하나만 남기고(혹시 모를 테스트 테넌트) 삭제
DELETE FROM public.wholesale_managers
 WHERE id <> '1a1a0000-0000-0000-0000-00000000a1a5';

-- 5) 남길 관리자가 (삭제될) 타 계정을 approved_by 로 참조하면 제약 위반 → 먼저 끊는다
UPDATE public.profiles SET approved_by = NULL
 WHERE id = 'f50945ce-0fec-4241-96ed-29e3dc97bade';

-- 6) 계정: 관리자(LALAS) 한 명만 남기고 전부 삭제.
--    auth.users 삭제 → profiles 가 FK ON DELETE CASCADE 로 자동 삭제(+ 로그인 세션/identity 도 정리)
DELETE FROM auth.users
 WHERE id <> 'f50945ce-0fec-4241-96ed-29e3dc97bade';

-- 검증 카운트 — 기대: auth.users=1, profiles=1, wholesale_managers=1, 나머지 전부 0
SELECT 'auth.users'          AS t, count(*) FROM auth.users
UNION ALL SELECT 'profiles',            count(*) FROM public.profiles
UNION ALL SELECT 'wholesale_managers',  count(*) FROM public.wholesale_managers
UNION ALL SELECT 'wholesalers',         count(*) FROM public.wholesalers
UNION ALL SELECT 'products',            count(*) FROM public.products
UNION ALL SELECT 'product_skus',        count(*) FROM public.product_skus
UNION ALL SELECT 'product_images',      count(*) FROM public.product_images
UNION ALL SELECT 'upload_jobs',         count(*) FROM public.upload_jobs
UNION ALL SELECT 'manager_wholesalers', count(*) FROM public.manager_wholesalers
UNION ALL SELECT 'manager_rejections',  count(*) FROM public.manager_rejections
UNION ALL SELECT 'agencies',            count(*) FROM public.agencies
ORDER BY t;

COMMIT;
-- ROLLBACK;   -- ← 드라이런(테스트) 또는 카운트 이상 시: 위 COMMIT 줄을 지우고 이 줄로 실행 → 아무것도 안 지워짐


-- ── §2. (선택) Storage 파일 정리 ────────────────────────────────────────────────
-- 위 §1 은 DB 의 이미지 "기록"만 지운다. 실제 업로드된 사진/서류 파일은 버킷에 남는다.
-- 파일은 GCS 버킷에 있음(Supabase Storage 아님). 완전 비우려면 gsutil 로:
--   gsutil -m rm -r gs://ezmerce-product-images/** gs://ezmerce-business-docs/**
