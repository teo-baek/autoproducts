-- ezmerce v2 — 델타 마이그레이션 03: soft delete (hard DELETE 금지)
-- 정책: 모든 테이블에 deleted_at TIMESTAMPTZ (NULL = 살아있음). 삭제는 deleted_at 세팅으로.
-- base(_v2_core.sql) → _02_price_visibility.sql → 본 파일 순서로 실행.

-- 1) 전 테이블 deleted_at
ALTER TABLE public.wholesalers    ADD COLUMN deleted_at TIMESTAMPTZ;
ALTER TABLE public.agencies       ADD COLUMN deleted_at TIMESTAMPTZ;
ALTER TABLE public.profiles       ADD COLUMN deleted_at TIMESTAMPTZ;
ALTER TABLE public.products       ADD COLUMN deleted_at TIMESTAMPTZ;
ALTER TABLE public.product_skus   ADD COLUMN deleted_at TIMESTAMPTZ;
ALTER TABLE public.product_images ADD COLUMN deleted_at TIMESTAMPTZ;
ALTER TABLE public.upload_jobs    ADD COLUMN deleted_at TIMESTAMPTZ;

-- 2) UNIQUE → 부분 유니크(살아있는 행끼리만). 소프트 삭제 후 같은 값 재등록 허용.
--    platform_code 는 영구 식별자(QR 대상)라 전체 UNIQUE 유지 — 손대지 않음.
ALTER TABLE public.products     DROP CONSTRAINT IF EXISTS products_wholesaler_id_source_p_number_key;
CREATE UNIQUE INDEX products_wholesaler_source_alive
  ON public.products (wholesaler_id, source_p_number) WHERE deleted_at IS NULL;

ALTER TABLE public.product_skus DROP CONSTRAINT IF EXISTS product_skus_product_id_color_size_key;
CREATE UNIQUE INDEX product_skus_option_alive
  ON public.product_skus (product_id, color, size) WHERE deleted_at IS NULL;

-- 3) 살아있는 행 조회 가속(선택)
CREATE INDEX idx_products_alive ON public.products (wholesaler_id) WHERE deleted_at IS NULL;

-- 4) soft-cascade: 부모 deleted_at 세팅 시 자식 전파 (ON DELETE CASCADE 의 soft 버전)
CREATE OR REPLACE FUNCTION public.soft_cascade_product() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
  IF NEW.deleted_at IS NOT NULL AND OLD.deleted_at IS NULL THEN
    UPDATE public.product_skus   SET deleted_at = NEW.deleted_at WHERE product_id = NEW.id AND deleted_at IS NULL;
    UPDATE public.product_images SET deleted_at = NEW.deleted_at WHERE product_id = NEW.id AND deleted_at IS NULL;
  END IF;
  RETURN NEW;
END $$;
CREATE TRIGGER trg_soft_cascade_product
  AFTER UPDATE OF deleted_at ON public.products
  FOR EACH ROW EXECUTE FUNCTION public.soft_cascade_product();

CREATE OR REPLACE FUNCTION public.soft_cascade_wholesaler() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
  IF NEW.deleted_at IS NOT NULL AND OLD.deleted_at IS NULL THEN
    -- products 전파 → 그 products 의 trg_soft_cascade_product 가 skus/images 까지 연쇄
    UPDATE public.products       SET deleted_at = NEW.deleted_at WHERE wholesaler_id = NEW.id AND deleted_at IS NULL;
    UPDATE public.product_images SET deleted_at = NEW.deleted_at WHERE wholesaler_id = NEW.id AND deleted_at IS NULL;
    UPDATE public.upload_jobs    SET deleted_at = NEW.deleted_at WHERE wholesaler_id = NEW.id AND deleted_at IS NULL;
  END IF;
  RETURN NEW;
END $$;
CREATE TRIGGER trg_soft_cascade_wholesaler
  AFTER UPDATE OF deleted_at ON public.wholesalers
  FOR EACH ROW EXECUTE FUNCTION public.soft_cascade_wholesaler();

-- 5) 읽기 정책에 삭제 필터 추가 (RLS 방어선)
DROP POLICY IF EXISTS products_read_approved ON public.products;
CREATE POLICY products_read_approved ON public.products FOR SELECT
  USING (
    status = 'active' AND deleted_at IS NULL
    AND (SELECT status FROM public.profiles WHERE id = auth.uid()) = 'approved'
  );
