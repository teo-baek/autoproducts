-- AutoProducts V2 Core Database Schema
-- Run this script in the Supabase SQL Editor.

-- 1. products (부모 테이블: 변하지 않는 마스터 데이터)
CREATE TABLE IF NOT EXISTS public.products (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    p_number TEXT NOT NULL,
    store_id TEXT NOT NULL,
    item_name TEXT NOT NULL,
    fabric_composition TEXT,
    origin TEXT,
    lead_time_days TEXT,
    description TEXT,
    image_url TEXT,
    is_sold_out BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    UNIQUE(store_id, p_number)
);

-- 2. product_skus (자식 테이블: 옵션, 단가, 실시간 재고 - Race Condition 방지용)
CREATE TABLE IF NOT EXISTS public.product_skus (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    product_id UUID REFERENCES public.products(id) ON DELETE CASCADE,
    color TEXT NOT NULL,
    size TEXT NOT NULL,
    wholesale_price INTEGER NOT NULL,
    retail_price INTEGER,
    stock INTEGER DEFAULT 0,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    UNIQUE(product_id, color, size)
);

-- 3. Row Level Security (RLS) 활성화
ALTER TABLE public.products ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.product_skus ENABLE ROW LEVEL SECURITY;

-- 4. 정책(Policies) 설정 (MVP 단계에서는 모두 접근 허용하여 UI 개발 속도 극대화)
-- 향후 안정화 단계에서 auth.uid() 정책으로 변경됩니다.
CREATE POLICY "Enable read access for all users" ON public.products FOR SELECT USING (true);
CREATE POLICY "Enable insert access for all users" ON public.products FOR INSERT WITH CHECK (true);
CREATE POLICY "Enable update access for all users" ON public.products FOR UPDATE USING (true);
CREATE POLICY "Enable delete access for all users" ON public.products FOR DELETE USING (true);

CREATE POLICY "Enable read access for all users" ON public.product_skus FOR SELECT USING (true);
CREATE POLICY "Enable insert access for all users" ON public.product_skus FOR INSERT WITH CHECK (true);
CREATE POLICY "Enable update access for all users" ON public.product_skus FOR UPDATE USING (true);
CREATE POLICY "Enable delete access for all users" ON public.product_skus FOR DELETE USING (true);
