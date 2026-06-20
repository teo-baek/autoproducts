-- ============================================================================
-- ezmerce — "전체 상품 초기화" 리셋 시드 스크립트
-- ----------------------------------------------------------------------------
-- 실행 위치 : Supabase 대시보드 → SQL Editor (이 파일 전체 붙여넣고 Run)
-- 목적      : 모든 상품 + 그 자식(SKU·이미지) 데이터를 통째로 비운다. (개발/시연 초기화용)
--
-- ⚠️ 이 파일은 soft delete 가 아니라 "진짜 DELETE" 다 — 되돌릴 수 없음.
--    앱 정상 경로는 soft delete(deleted_at) 지만, 여기는 "싹 비우고 새로 시드"하는
--    개발/프리런치 전용 리셋이므로 하드 삭제를 쓴다(기존 _PRELAUNCH_wipe_test_data.sql 과 동일 철학).
--
-- 지우는 것 : public.products 전부 + product_skus + product_images (FK CASCADE).
-- 남기는 것 : 계정(profiles/auth.users) · 도매업체(wholesalers) · 관리자/테넌트 · 에이전시
--             · upload_jobs(잡 이력) — 전부 그대로. "상품 데이터만" 초기화한다.
--
-- 권장 순서 : 1) 백업(대시보드 Database → Backups/PITR) 확보.
--            2) §0 먼저 실행 → 지워질 건수 눈으로 확인.
--            3) §1 을 "끝의 COMMIT 을 지우고 ROLLBACK 으로" 한 번 실행(드라이런) → 카운트 확인.
--            4) 맞으면 §1 끝을 다시 COMMIT 으로 바꿔 실행 → 확정 삭제.
-- ============================================================================


-- ── §0. (확인) 지금 상품이 몇 건인지 먼저 본다 ─────────────────────────────────
SELECT 'products(전체)'             AS t, count(*) FROM public.products
UNION ALL SELECT 'products(살아있음)',         count(*) FROM public.products      WHERE deleted_at IS NULL
UNION ALL SELECT 'product_skus',               count(*) FROM public.product_skus
UNION ALL SELECT 'product_images',             count(*) FROM public.product_images
ORDER BY t;


-- ── §1. 삭제 (트랜잭션) — 끝의 COMMIT/ROLLBACK 으로 확정/취소 ──────────────────────
BEGIN;

-- 자식 먼저(명시적). products 에 ON DELETE CASCADE 가 걸려 있어 사실 parent 만 지워도 따라 지워지지만,
-- 의도를 분명히 하려고 자식→부모 순으로 직접 비운다.
DELETE FROM public.product_images;
DELETE FROM public.product_skus;
DELETE FROM public.products;

-- 검증 카운트 — 기대: 셋 다 0
SELECT 'products'       AS t, count(*) FROM public.products
UNION ALL SELECT 'product_skus',   count(*) FROM public.product_skus
UNION ALL SELECT 'product_images', count(*) FROM public.product_images
ORDER BY t;

COMMIT;
-- ROLLBACK;   -- ← 드라이런/카운트 이상 시: 위 COMMIT 을 지우고 이 줄로 실행 → 아무것도 안 지워짐


-- ── §2. (선택) platform_code 시퀀스 1번부터 다시 ──────────────────────────────────
-- ⚠️ platform_code 는 원래 "영구 식별자(재사용 X, QR 대상)" 라 운영에선 절대 되돌리면 안 된다.
--    아래는 "상품을 전부 비우고 1번부터 새로 시드"하는 개발 초기화일 때만 켠다.
--    (이미 인쇄/배포된 QR 이 있으면 절대 실행 금지 — 코드가 겹쳐 엉뚱한 상품을 가리킴.)
-- ALTER SEQUENCE public.platform_code_seq RESTART WITH 1;


-- ── §3. (선택) Storage 실제 이미지 파일 정리 ──────────────────────────────────────
-- §1 은 DB 의 이미지 "기록"만 지운다. 버킷에 업로드된 실제 사진 파일은 남는다.
-- 파일은 GCS 버킷에 있음(Supabase Storage 아님). 완전히 비우려면 gsutil 로:
--   gsutil -m rm -r gs://ezmerce-product-images/**


-- ── (대안) 하드 삭제가 부담되면: soft delete 로 "내리기"만 ─────────────────────────
-- 진짜로 지우지 않고 앱 화면에서만 안 보이게(deleted_at 세팅) 하려면 §1 대신 아래를 쓴다.
-- soft-cascade 트리거(soft_cascade_product)가 자식 SKU/이미지까지 전파한다.
--   BEGIN;
--   UPDATE public.products SET deleted_at = now() WHERE deleted_at IS NULL;
--   COMMIT;
