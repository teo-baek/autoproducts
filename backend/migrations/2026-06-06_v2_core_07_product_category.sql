-- ezmerce v2 — _07 상품 카테고리
-- 도매 상품관리 화면의 분류 필터(전체/의류/잡화)용. NULL = 미분류.
-- 시안 단일 등록 모달의 '카테고리' 셀렉트 + 목록 필터 탭에 대응.
-- 멱등(IF NOT EXISTS) — 재실행 안전.

ALTER TABLE products ADD COLUMN IF NOT EXISTS category TEXT;

-- 분류 필터 조회 가속(살아있는 행만).
CREATE INDEX IF NOT EXISTS idx_products_category
  ON products (wholesaler_id, category)
  WHERE deleted_at IS NULL;

COMMENT ON COLUMN products.category IS '상품 분류(의류|잡화 등). 도매 관리 목록 필터/단일 등록 모달용. NULL=미분류.';
