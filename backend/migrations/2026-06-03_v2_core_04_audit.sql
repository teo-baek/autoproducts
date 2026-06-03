-- ezmerce v2 — 델타 마이그레이션 04: 감사 컬럼 (누가 만들/고쳤나)
-- created_by/updated_by 는 앱이 현재 사용자(profiles.id)로 채운다. FK → profiles.
-- updated_at 은 BEFORE UPDATE 트리거로 자동 갱신.
-- 실행 순서: base → _02 → _03 → 본 파일

-- 1) updated_at 없는 테이블에 추가 (products 는 이미 보유)
ALTER TABLE public.wholesalers    ADD COLUMN updated_at TIMESTAMPTZ NOT NULL DEFAULT now();
ALTER TABLE public.agencies       ADD COLUMN updated_at TIMESTAMPTZ NOT NULL DEFAULT now();
ALTER TABLE public.profiles       ADD COLUMN updated_at TIMESTAMPTZ NOT NULL DEFAULT now();
ALTER TABLE public.product_skus   ADD COLUMN updated_at TIMESTAMPTZ NOT NULL DEFAULT now();
ALTER TABLE public.product_images ADD COLUMN updated_at TIMESTAMPTZ NOT NULL DEFAULT now();
ALTER TABLE public.upload_jobs    ADD COLUMN updated_at TIMESTAMPTZ NOT NULL DEFAULT now();

-- 2) created_by / updated_by (FK → profiles). upload_jobs.created_by 는 이미 존재.
ALTER TABLE public.wholesalers    ADD COLUMN created_by UUID REFERENCES public.profiles(id) ON DELETE SET NULL,
                                  ADD COLUMN updated_by UUID REFERENCES public.profiles(id) ON DELETE SET NULL;
ALTER TABLE public.agencies       ADD COLUMN created_by UUID REFERENCES public.profiles(id) ON DELETE SET NULL,
                                  ADD COLUMN updated_by UUID REFERENCES public.profiles(id) ON DELETE SET NULL;
ALTER TABLE public.profiles       ADD COLUMN created_by UUID REFERENCES public.profiles(id) ON DELETE SET NULL,
                                  ADD COLUMN updated_by UUID REFERENCES public.profiles(id) ON DELETE SET NULL;
ALTER TABLE public.products       ADD COLUMN created_by UUID REFERENCES public.profiles(id) ON DELETE SET NULL,
                                  ADD COLUMN updated_by UUID REFERENCES public.profiles(id) ON DELETE SET NULL;
ALTER TABLE public.product_skus   ADD COLUMN created_by UUID REFERENCES public.profiles(id) ON DELETE SET NULL,
                                  ADD COLUMN updated_by UUID REFERENCES public.profiles(id) ON DELETE SET NULL;
ALTER TABLE public.product_images ADD COLUMN created_by UUID REFERENCES public.profiles(id) ON DELETE SET NULL,
                                  ADD COLUMN updated_by UUID REFERENCES public.profiles(id) ON DELETE SET NULL;
ALTER TABLE public.upload_jobs    ADD COLUMN updated_by UUID REFERENCES public.profiles(id) ON DELETE SET NULL;

-- 3) updated_at 자동 갱신 트리거 (행 UPDATE 시 now())
CREATE OR REPLACE FUNCTION public.set_updated_at() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
  NEW.updated_at = now();
  RETURN NEW;
END $$;

CREATE TRIGGER trg_set_updated_at_wholesalers    BEFORE UPDATE ON public.wholesalers    FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();
CREATE TRIGGER trg_set_updated_at_agencies       BEFORE UPDATE ON public.agencies       FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();
CREATE TRIGGER trg_set_updated_at_profiles       BEFORE UPDATE ON public.profiles       FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();
CREATE TRIGGER trg_set_updated_at_products       BEFORE UPDATE ON public.products       FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();
CREATE TRIGGER trg_set_updated_at_product_skus   BEFORE UPDATE ON public.product_skus   FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();
CREATE TRIGGER trg_set_updated_at_product_images BEFORE UPDATE ON public.product_images FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();
CREATE TRIGGER trg_set_updated_at_upload_jobs    BEFORE UPDATE ON public.upload_jobs    FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();
