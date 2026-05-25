-- 1. Products Table (불변 정보)
CREATE TABLE products (
  id BIGSERIAL PRIMARY KEY,
  p_number VARCHAR(50) UNIQUE NOT NULL, -- 상품 품번 (예: SKU-123456)
  name VARCHAR(255) NOT NULL, -- 상품명
  price INTEGER NOT NULL, -- 도매 단가
  description TEXT,
  retail_price INTEGER, -- 권장 소비자가
  material VARCHAR(255), -- 혼용률
  origin VARCHAR(255), -- 제조국
  reorder_period VARCHAR(255), -- 리오더 기간
  main_image_url TEXT,
  image_urls TEXT[], -- 다중 이미지 (디테일 컷 등)
  created_at TIMESTAMP WITH TIME ZONE DEFAULT timezone('utc'::text, now()) NOT NULL
);

-- 2. Product SKUs Table (가변 정보: 재고 및 색상/사이즈, Row-level Lock 적용 대상)
CREATE TABLE product_skus (
  id BIGSERIAL PRIMARY KEY,
  product_id BIGINT REFERENCES products(id) ON DELETE CASCADE,
  color VARCHAR(50) NOT NULL,
  size VARCHAR(50) NOT NULL,
  allocated_stock INTEGER NOT NULL DEFAULT 0, -- 라이브 방송을 위해 할당된 가상 재고 (Lock)
  sold_stock INTEGER NOT NULL DEFAULT 0, -- 실제 판매(차감)된 재고
  created_at TIMESTAMP WITH TIME ZONE DEFAULT timezone('utc'::text, now()) NOT NULL,
  UNIQUE(product_id, color, size)
);

-- Row-level Security (RLS) 설정 (로컬 테스트를 위해 일단 모두에게 허용)
ALTER TABLE products ENABLE ROW LEVEL SECURITY;
ALTER TABLE product_skus ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Allow public read access to products" ON products FOR SELECT USING (true);
CREATE POLICY "Allow public insert to products" ON products FOR INSERT WITH CHECK (true);
CREATE POLICY "Allow public update to products" ON products FOR UPDATE USING (true);

CREATE POLICY "Allow public read access to product_skus" ON product_skus FOR SELECT USING (true);
CREATE POLICY "Allow public insert to product_skus" ON product_skus FOR INSERT WITH CHECK (true);
CREATE POLICY "Allow public update to product_skus" ON product_skus FOR UPDATE USING (true);

-- 3. 안전한 재고 차감을 위한 RPC (PostgreSQL 함수) - 동시성 제어 (Row-level Lock)
CREATE OR REPLACE FUNCTION decrement_stock(sku_id BIGINT)
RETURNS void
LANGUAGE plpgsql
AS $$
BEGIN
  -- FOR UPDATE를 통해 해당 row를 잠금(Lock)하여 동시성 충돌 방지
  UPDATE product_skus
  SET allocated_stock = allocated_stock - 1,
      sold_stock = sold_stock + 1
  WHERE id = sku_id AND allocated_stock > 0;
END;
$$;

-- 4. 재고 락(Stock-Lock) 부여를 위한 RPC
CREATE OR REPLACE FUNCTION increment_allocated_stock(p_sku_id BIGINT, qty INTEGER)
RETURNS void
LANGUAGE plpgsql
AS $$
BEGIN
  UPDATE product_skus
  SET allocated_stock = allocated_stock + qty
  WHERE id = p_sku_id;
END;
$$;

-- 5. Storage 버킷 및 권한 설정
INSERT INTO storage.buckets (id, name, public) VALUES ('product_images', 'product_images', true)
ON CONFLICT (id) DO NOTHING;

CREATE POLICY "Public Access"
ON storage.objects FOR SELECT
USING ( bucket_id = 'product_images' );

CREATE POLICY "Public Upload"
ON storage.objects FOR INSERT
WITH CHECK ( bucket_id = 'product_images' );
