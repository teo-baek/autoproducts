-- ============================================================
-- AutoProducts B2B SaaS — 데이터베이스 통합 스키마 SQL
-- Supabase SQL Editor에서 실행해 주세요.
-- ============================================================

-- 1. 프로모션 할인 코드 (promo_codes) 테이블
CREATE TABLE IF NOT EXISTS promo_codes (
  code text PRIMARY KEY,
  discount_type text NOT NULL,                    -- 'FIXED_AMOUNT' (정액) 또는 'PERCENTAGE' (정률)
  discount_value numeric NOT NULL,                -- 할인 금액 또는 할인율
  duration text NOT NULL DEFAULT 'ONCE',          -- 'LIFETIME' (평생) / 'ONCE' (1회) / 'RECURRING' (N개월 반복)
  duration_in_months integer DEFAULT NULL,        -- 'RECURRING'인 경우 반복 적용 개월 수
  max_redemptions integer DEFAULT NULL,           -- 쿠폰 최대 발급 한도 (NULL이면 무제한)
  redemptions_count integer DEFAULT 0,            -- 현재까지 등록/사용한 횟수
  expires_at timestamp with time zone,            -- 쿠폰 코드 유효 기한
  created_at timestamp with time zone DEFAULT timezone('utc'::text, now()) NOT NULL
);

-- 2. 매장(도매상/소매상) 프로필 및 가입 정보 테이블
CREATE TABLE IF NOT EXISTS store_profiles (
  id uuid REFERENCES auth.users ON DELETE CASCADE PRIMARY KEY,
  email text NOT NULL,
  role text NOT NULL DEFAULT 'retailer',          -- 'wholesaler' 또는 'retailer'
  store_id text NOT NULL DEFAULT '',               -- 도매상 고유 코드 (예: 'dmd_kim')
  store_name text NOT NULL DEFAULT '',             -- 도매상 매장 한글명
  drive_folder_url text DEFAULT '',                -- 가입 시 연동한 구글 드라이브 폴더 주소
  plan_type text DEFAULT 'standard',               -- 'standard' (10만원) 또는 'ai_premium' (15만원)
  is_paid boolean DEFAULT false,                   -- 기본 결제 완료 여부
  has_ai_agent boolean DEFAULT false,              -- ★ AI 에이전트 활성화 여부 (+5만원 탑업 적용 여부)
  applied_promo_code text REFERENCES promo_codes(code) ON DELETE SET NULL, -- 적용된 할인 코드
  discount_until timestamp with time zone,         -- 기간 한정 할인 유효 일시
  created_at timestamp with time zone DEFAULT timezone('utc'::text, now()) NOT NULL
);

-- store_id에 대한 인덱스 (도매상 조회 최적화)
CREATE INDEX IF NOT EXISTS idx_store_profiles_store_id ON store_profiles(store_id);



-- 4. 실시간 상품 관심 로그 (product_clicks) 테이블
CREATE TABLE IF NOT EXISTS product_clicks (
  id uuid DEFAULT gen_random_uuid() PRIMARY KEY,
  store_id uuid REFERENCES store_profiles(id) ON DELETE CASCADE, -- 도매상
  p_number text NOT NULL,                                       -- 품번
  retailer_id uuid REFERENCES store_profiles(id) ON DELETE CASCADE, -- 소매상
  source text NOT NULL DEFAULT 'QR_SCAN',                       -- 'QR_SCAN' 또는 'LINK_CLICK'
  created_at timestamp with time zone DEFAULT timezone('utc'::text, now()) NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_product_clicks_store_created ON product_clicks(store_id, created_at);

-- 5. 상품 데이터 및 옵션 정보 (products) 테이블
CREATE TABLE IF NOT EXISTS products (
  store_id text NOT NULL,                        -- 도매상 고유 코드 (예: 'dmd_kim')
  p_number text NOT NULL,                        -- 품번
  item_name text NOT NULL DEFAULT '',             -- 상품명
  image_url text DEFAULT '',                     -- 구글 드라이브 썸네일 URL
  variants jsonb NOT NULL DEFAULT '[]'::jsonb,   -- 색상, 사이즈, 가격, 재고 등의 옵션 배열 (JSONB)
  is_sold_out boolean DEFAULT false,             -- 상품 품절 여부 토글
  created_at timestamp with time zone DEFAULT timezone('utc'::text, now()) NOT NULL,
  PRIMARY KEY (store_id, p_number)               -- (점포ID, 품번) 복합키를 통한 유니크 보장
);

-- 6. Supabase Storage 버킷 자동 생성 (Storage schema 권한이 있는 경우)
-- * 주의: 콘솔(Storage 메뉴)에서 'product-images' 버킷을 비공개(Private)로 생성하는 것을 권장합니다.
INSERT INTO storage.buckets (id, name, public) 
VALUES ('product-images', 'product-images', false)
ON CONFLICT (id) DO NOTHING;

-- 7. 예약 및 주문 데이터 확장 (Phase 4)
ALTER TABLE products ADD COLUMN IF NOT EXISTS reserved_quantity integer DEFAULT 0;


CREATE TABLE IF NOT EXISTS product_reservations (
    id uuid DEFAULT gen_random_uuid() PRIMARY KEY,
    store_id text NOT NULL, -- 도매상 store_id (products와 매칭용)
    retailer_email text NOT NULL, -- 소매상 식별용
    p_number text NOT NULL,
    requested_quantity integer NOT NULL DEFAULT 0,
    actual_ordered_quantity integer DEFAULT 0,
    status text DEFAULT 'PENDING', -- PENDING, CONFIRMED, COMPLETED, CANCELLED, NOSHOW
    created_at timestamp with time zone DEFAULT timezone('utc'::text, now()) NOT NULL
);

-- 8. 파트너 소매상 접근 승인 요청 (Phase 5)
-- 소매상이 도매상의 카탈로그 전체 열람 권한을 요청하는 테이블
CREATE TABLE IF NOT EXISTS partner_requests (
    id uuid DEFAULT gen_random_uuid() PRIMARY KEY,
    wholesaler_store_id text NOT NULL,              -- 도매상의 store_id (text 코드)
    retailer_email text NOT NULL,                   -- 소매상 이메일 (식별자)
    status text DEFAULT 'PENDING',                  -- PENDING, APPROVED, REJECTED
    no_show_count integer DEFAULT 0,                -- 노쇼 누적 횟수
    seller_reliability_score integer DEFAULT 100,   -- 신뢰도 점수 (100점 만점, 노쇼시 차감)
    grade text DEFAULT 'Normal',                    -- 소매상 등급 (Normal, Silver, Gold, VIP)
    created_at timestamp with time zone DEFAULT timezone('utc'::text, now()) NOT NULL,
    UNIQUE(wholesaler_store_id, retailer_email)     -- 동일 조합은 1건만 허용
);

-- ============================================================
-- 🔴 긴급 패치: Storage RLS 정책 적용 (이미지 업로드 복구)
-- ============================================================
-- product-images 버킷에 대한 RLS 정책 추가 (인증된 사용자에게 CRUD 허용)
CREATE POLICY "Allow authenticated uploads"
ON storage.objects FOR INSERT
TO authenticated
WITH CHECK (bucket_id = 'product-images');

CREATE POLICY "Allow authenticated reads"
ON storage.objects FOR SELECT
TO authenticated
USING (bucket_id = 'product-images');

CREATE POLICY "Allow authenticated updates"
ON storage.objects FOR UPDATE
TO authenticated
USING (bucket_id = 'product-images');

CREATE POLICY "Allow authenticated deletes"
ON storage.objects FOR DELETE
TO authenticated
USING (bucket_id = 'product-images');
