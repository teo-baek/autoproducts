-- ezmerce — 테스트 상품 데이터 정리 (soft delete)
-- ──────────────────────────────────────────────────────────────────────────
-- 용도: 대량등록 마법사를 중간까지만 진행하다 중단하는 사이 DB 에 쌓인 '테스트 상품'을 깨끗이 비운다.
-- 안전: hard DELETE 가 아니라 soft delete(deleted_at=now()) — 실수해도 복구 가능. (ezmerce 삭제 정책 준수)
-- 카스케이드: products 를 soft delete 하면 트리거(soft_cascade_product)가 SKU·이미지까지 전파한다.
--            → 자식 테이블을 따로 지울 필요 없음.
-- 실행 위치: Supabase 대시보드 → SQL Editor. 아래 STEP 순서대로.
-- ⚠️ 운영 데이터가 아니라 '내 테스트 도매업체'인지 STEP 1 으로 꼭 확인하고 진행할 것.
-- ──────────────────────────────────────────────────────────────────────────

-- STEP 1) 어느 도매업체에 살아있는 상품이 몇 개 있는지 본다. (지울 대상 식별)
SELECT w.id AS wholesaler_id, w.name, count(*) AS 살아있는_상품수
FROM public.products pr
JOIN public.wholesalers w ON w.id = pr.wholesaler_id
WHERE pr.deleted_at IS NULL
GROUP BY w.id, w.name
ORDER BY 살아있는_상품수 DESC;

-- (참고) 내 로그인 이메일로 연결된 도매업체 id 를 바로 찾고 싶으면:
-- SELECT p.wholesaler_id
-- FROM public.profiles p
-- JOIN auth.users u ON u.id = p.id
-- WHERE u.email = 'admin@jinju-ict.com';   -- ← 본인 이메일로 교체


-- STEP 2) 지우기 전 '몇 개가 지워질지' 미리 확인. 아래 :WID 를 STEP 1 에서 고른 UUID 로 교체.
-- (작은따옴표 유지: '...uuid...')
SELECT count(*) AS 지울_상품수
FROM public.products
WHERE wholesaler_id = 'PASTE-WHOLESALER-UUID-HERE'
  AND deleted_at IS NULL;


-- STEP 3) 실제 정리(soft delete). 위 개수가 맞으면 실행. UUID 를 동일하게 교체.
UPDATE public.products
SET deleted_at = now()
WHERE wholesaler_id = 'PASTE-WHOLESALER-UUID-HERE'
  AND deleted_at IS NULL;

-- (선택) 업로드 작업 이력(upload_jobs)도 같이 비우려면 — 화면의 '업로드 내역'이 깔끔해짐:
-- UPDATE public.upload_jobs
-- SET deleted_at = now()
-- WHERE wholesaler_id = 'PASTE-WHOLESALER-UUID-HERE'
--   AND deleted_at IS NULL;


-- STEP 4) 검증 — 0 이면 정리 완료.
SELECT count(*) AS 남은_상품수
FROM public.products
WHERE wholesaler_id = 'PASTE-WHOLESALER-UUID-HERE'
  AND deleted_at IS NULL;


-- ──────────────────────────────────────────────────────────────────────────
-- (비상) 방금 정리를 되돌리고 싶다면 — soft delete 라 복구 가능.
-- 단, 카스케이드로 같이 지워진 자식도 되살리려면 시점이 맞아야 하니 가급적 바로 실행.
-- UPDATE public.products SET deleted_at = NULL
-- WHERE wholesaler_id = 'PASTE-WHOLESALER-UUID-HERE'
--   AND deleted_at >= now() - interval '10 minutes';
-- ──────────────────────────────────────────────────────────────────────────
