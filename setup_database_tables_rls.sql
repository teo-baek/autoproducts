-- ==============================================================================
-- AutoProducts Database Tables RLS Policy Configuration (개발 및 테스트용 v2)
-- ==============================================================================
-- 이 스크립트는 향후 개발 시 마주할 수 있는 모든 주요 테이블의 접근 권한 에러를 
-- 미연에 방지하기 위해, 개발용 전체 공개(Public ALL) 권한 정책을 일괄 생성합니다.
-- ==============================================================================

-- 1. 테이블 RLS 활성화
ALTER TABLE public.products ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.partner_requests ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.product_reservations ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.store_profiles ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.product_clicks ENABLE ROW LEVEL SECURITY;

-- 2. 기존 개발용 정책 삭제 (충돌 방지)
DROP POLICY IF EXISTS "Enable all for public on products" ON public.products;
DROP POLICY IF EXISTS "Enable all for public on partner_requests" ON public.partner_requests;
DROP POLICY IF EXISTS "Enable all for public on product_reservations" ON public.product_reservations;
DROP POLICY IF EXISTS "Enable all for public on store_profiles" ON public.store_profiles;
DROP POLICY IF EXISTS "Enable all for public on product_clicks" ON public.product_clicks;

-- 3. 전체 공개 CRUD(읽기/쓰기/수정/삭제) 허용 정책 생성
CREATE POLICY "Enable all for public on products" 
ON public.products FOR ALL TO public USING (true) WITH CHECK (true);

CREATE POLICY "Enable all for public on partner_requests" 
ON public.partner_requests FOR ALL TO public USING (true) WITH CHECK (true);

CREATE POLICY "Enable all for public on product_reservations" 
ON public.product_reservations FOR ALL TO public USING (true) WITH CHECK (true);

CREATE POLICY "Enable all for public on store_profiles" 
ON public.store_profiles FOR ALL TO public USING (true) WITH CHECK (true);

CREATE POLICY "Enable all for public on product_clicks" 
ON public.product_clicks FOR ALL TO public USING (true) WITH CHECK (true);

-- 4. DB 테이블 스키마 업데이트 (추가 컬럼)
ALTER TABLE public.products ADD COLUMN IF NOT EXISTS description TEXT DEFAULT '';
