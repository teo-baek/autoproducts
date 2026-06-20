-- _SEED_reset_to_admin.sql
-- ============================================================================
-- 시드/리셋: "도매관리자(admin) 만 남기고 소매·도매(그 외 전부) 하드 삭제"
--   - 남기는 것 : role='admin' 계정 전부 + 그 admin 들이 가리키는 테넌트(wholesale_managers) + LALAS 시드 테넌트.
--   - 지우는 것 : 그 외 모든 계정(wholesaler/retail_seller/agency + 무프로필 auth 계정) ·
--                 모든 도매업체/상품/SKU/이미지/업로드잡 · 모든 에이전시 ·
--                 테스트 테넌트 · 도매상↔관리자 연결 · 승인/거절 로그.
--   - ⚠️ 하드 DELETE(soft delete 아님) — 되돌릴 수 없음. auth.users 까지 지워 이메일 재가입 가능(=깨끗한 시드).
--
-- 실행 위치: Supabase SQL Editor.  ★ 반드시 "맞는 프로젝트(보통 개발/스테이징)" 인지 먼저 확인 ★
-- 멱등: 재실행 안전(이미 비어 있으면 0건 삭제).
--
-- 권장 절차:
--   1) 백업: 대시보드 Database → Backups(또는 PITR) 로 스냅샷 확보.
--   2) §0 검증 SELECT 만 먼저 실행 → "남길 admin/테넌트" 가 맞는지 눈으로 확인.
--   3) §1 끝의 COMMIT 을 ROLLBACK 으로 바꿔 1회 실행(드라이런) → 카운트가 기대대로인지 확인.
--   4) 맞으면 다시 COMMIT 으로 바꿔 실행 → 확정 삭제.
--
-- 보존 기준(knob): 기본은 role='admin' 전부 보존(다중 admin·이메일 변경에도 안전).
--   ↳ 특정 1명만 남기려면 §1 의 두 군데 `WHERE role = 'admin'` 를 `WHERE id = '<admin uuid>'` 로 바꾸세요.
--   LALAS 시드 테넌트 id = 1a1a0000-0000-0000-0000-00000000a1a5 (admin.manager_id 가 비어도 보호됨).
--
-- FK 처리 메모(왜 이 순서인가):
--   · profiles.approved_by  → ON DELETE 절 없음(NO ACTION). 남길 admin 이 "삭제될 계정" 을 승인했으면
--     삭제가 막힘 → §1-(1) 에서 먼저 NULL 로 끊는다.
--   · upload_jobs.created_by → 역시 NO ACTION. 도매업체를 먼저 지우면(CASCADE) upload_jobs 가 함께
--     사라져 계정 삭제 시 충돌 없음 → 그래서 "도매업체 → 계정" 순서.
--   · 그 외 created_by/updated_by(감사) = SET NULL, manager_wholesalers/manager_rejections·products·
--     skus·images = CASCADE, profiles.id→auth.users = CASCADE → 순서만 맞으면 자동 정리.
-- ============================================================================


-- ── §0. 검증: 무엇이 "남는지" 먼저 확인 (이 블록만 따로 실행) ─────────────────────
SELECT u.id, u.email, p.role, p.status, p.manager_id
  FROM public.profiles p JOIN auth.users u ON u.id = p.id
 WHERE p.role = 'admin';                                  -- 남길 관리자(들)

SELECT id, name FROM public.wholesale_managers
 WHERE id IN (SELECT manager_id FROM public.profiles WHERE role = 'admin' AND manager_id IS NOT NULL)
    OR id = '1a1a0000-0000-0000-0000-00000000a1a5';       -- 남길 테넌트(들)


-- ── §1. 삭제 (트랜잭션) — 끝의 COMMIT/ROLLBACK 으로 확정/취소 ──────────────────────
BEGIN;

-- (1) NO ACTION 지뢰 해소: 남길 admin 이 "삭제될 계정" 을 approved_by 로 참조하면 먼저 끊는다.
--     (admin↔admin 승인 이력은 보존 — 삭제 대상(비-admin)을 가리키는 참조만 NULL)
UPDATE public.profiles
   SET approved_by = NULL
 WHERE approved_by IS NOT NULL
   AND approved_by NOT IN (SELECT id FROM public.profiles WHERE role = 'admin');

-- (2) 승인/거절 로그 전체 비우기(신청자 전원 삭제 → CASCADE 로도 사라지지만 명시적 정리)
DELETE FROM public.manager_rejections;

-- (3) 도매업체 전체 → FK ON DELETE CASCADE 로 함께 삭제:
--     products → product_skus / product_images, upload_jobs, manager_wholesalers
DELETE FROM public.wholesalers;

-- (4) 에이전시 전체
DELETE FROM public.agencies;

-- (5) 테스트 테넌트 삭제 — 남길 admin 의 테넌트 + LALAS 시드만 보존
DELETE FROM public.wholesale_managers
 WHERE id NOT IN (
         SELECT manager_id FROM public.profiles
          WHERE role = 'admin' AND manager_id IS NOT NULL
       )
   AND id <> '1a1a0000-0000-0000-0000-00000000a1a5';      -- LALAS 시드 보호

-- (6) 계정: admin 빼고 전부 → auth.users 삭제(무프로필 orphan 계정 포함).
--     profiles 는 FK ON DELETE CASCADE 로 자동 삭제(+ 세션/identity 정리)
DELETE FROM auth.users
 WHERE id NOT IN (SELECT id FROM public.profiles WHERE role = 'admin');

-- 검증 카운트 — 기대: auth.users=profiles=admin 수, wholesale_managers≥1(LALAS), 나머지 0
SELECT 'auth.users'          AS t, count(*) FROM auth.users
UNION ALL SELECT 'profiles',            count(*) FROM public.profiles
UNION ALL SELECT 'wholesale_managers',  count(*) FROM public.wholesale_managers
UNION ALL SELECT 'manager_wholesalers', count(*) FROM public.manager_wholesalers
UNION ALL SELECT 'manager_rejections',  count(*) FROM public.manager_rejections
UNION ALL SELECT 'wholesalers',         count(*) FROM public.wholesalers
UNION ALL SELECT 'products',            count(*) FROM public.products
UNION ALL SELECT 'product_skus',        count(*) FROM public.product_skus
UNION ALL SELECT 'product_images',      count(*) FROM public.product_images
UNION ALL SELECT 'upload_jobs',         count(*) FROM public.upload_jobs
UNION ALL SELECT 'agencies',            count(*) FROM public.agencies
ORDER BY t;

COMMIT;
-- ROLLBACK;   -- ← 드라이런/카운트 이상 시: 위 COMMIT 을 지우고 이 줄로 실행 → 아무것도 안 지워짐


-- ── §2. (선택) Storage 파일 정리 ────────────────────────────────────────────────
-- 위 §1 은 DB 의 이미지/서류 "기록" 만 지운다. 실제 업로드 파일은 버킷에 남는다.
-- 파일은 GCS 버킷에 있음(Supabase Storage 아님). 완전 비우려면 gsutil 로:
--   gsutil -m rm -r gs://ezmerce-product-images/** gs://ezmerce-business-docs/**
