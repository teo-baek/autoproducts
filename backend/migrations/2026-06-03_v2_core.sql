-- ezmerce v2 core schema (1차) — Supabase SQL Editor에서 실행
-- ENUM
CREATE TYPE user_role      AS ENUM ('admin','wholesaler','retail_seller','agency');
CREATE TYPE account_status AS ENUM ('pending','approved','rejected','suspended');
CREATE TYPE seller_type    AS ENUM ('agency_affiliated','independent');
CREATE TYPE org_type       AS ENUM ('wholesaler','agency');
CREATE TYPE product_status AS ENUM ('active','archived');
CREATE TYPE image_match    AS ENUM ('matched','unmatched');
CREATE TYPE upload_status  AS ENUM ('uploaded','parsing','needs_matching','completed','failed');

-- platform_code 발급 시퀀스 (원자적)
CREATE SEQUENCE IF NOT EXISTS public.platform_code_seq START 1;

CREATE TABLE public.organizations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name TEXT NOT NULL,
    type org_type NOT NULL,
    biz_number TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE public.profiles (
    id UUID PRIMARY KEY REFERENCES auth.users(id) ON DELETE CASCADE,
    role user_role NOT NULL,
    status account_status NOT NULL DEFAULT 'pending',
    full_name TEXT,
    phone TEXT,
    organization_id UUID REFERENCES public.organizations(id) ON DELETE SET NULL,
    seller_type seller_type,
    approved_at TIMESTAMPTZ,
    approved_by UUID REFERENCES public.profiles(id),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT seller_type_only_for_retail CHECK (
        (role = 'retail_seller' AND seller_type IS NOT NULL)
        OR (role <> 'retail_seller' AND seller_type IS NULL)
    )
);
CREATE INDEX idx_profiles_role_status ON public.profiles(role, status);
CREATE INDEX idx_profiles_org ON public.profiles(organization_id);

CREATE TABLE public.products (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    wholesaler_org_id UUID NOT NULL REFERENCES public.organizations(id) ON DELETE CASCADE,
    platform_code TEXT NOT NULL UNIQUE,
    source_p_number TEXT NOT NULL,
    item_name TEXT NOT NULL,
    fabric_composition TEXT, origin TEXT, lead_time_days TEXT, description TEXT,
    representative_image_url TEXT,
    status product_status NOT NULL DEFAULT 'active',
    is_sold_out BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (wholesaler_org_id, source_p_number)
);
CREATE INDEX idx_products_org_status ON public.products(wholesaler_org_id, status);

CREATE TABLE public.product_skus (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    product_id UUID NOT NULL REFERENCES public.products(id) ON DELETE CASCADE,
    color TEXT NOT NULL, size TEXT NOT NULL,
    wholesale_price INTEGER NOT NULL,
    retail_price INTEGER,
    stock INTEGER NOT NULL DEFAULT 0,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (product_id, color, size)
);

CREATE TABLE public.product_images (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    product_id UUID REFERENCES public.products(id) ON DELETE CASCADE,
    wholesaler_org_id UUID NOT NULL REFERENCES public.organizations(id) ON DELETE CASCADE,
    storage_path TEXT NOT NULL,
    original_filename TEXT,
    match_status image_match NOT NULL DEFAULT 'unmatched',
    is_representative BOOLEAN NOT NULL DEFAULT FALSE,
    sort_order INTEGER NOT NULL DEFAULT 0,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_images_unmatched ON public.product_images(wholesaler_org_id, match_status);

CREATE TABLE public.upload_jobs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    wholesaler_org_id UUID NOT NULL REFERENCES public.organizations(id) ON DELETE CASCADE,
    created_by UUID REFERENCES public.profiles(id),
    file_path TEXT,
    status upload_status NOT NULL DEFAULT 'uploaded',
    total_rows INTEGER DEFAULT 0, matched_rows INTEGER DEFAULT 0, error_rows INTEGER DEFAULT 0,
    error_detail JSONB,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    completed_at TIMESTAMPTZ
);

-- RLS (방어선) — tech-design §3.11
CREATE OR REPLACE FUNCTION public.current_profile()
RETURNS public.profiles LANGUAGE sql STABLE AS $$
  SELECT * FROM public.profiles WHERE id = auth.uid();
$$;

ALTER TABLE public.organizations  ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.profiles       ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.products       ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.product_skus   ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.product_images ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.upload_jobs    ENABLE ROW LEVEL SECURITY;

CREATE POLICY profiles_self_select ON public.profiles FOR SELECT USING (id = auth.uid());
CREATE POLICY profiles_self_update ON public.profiles FOR UPDATE USING (id = auth.uid());
CREATE POLICY products_read_approved ON public.products FOR SELECT
  USING (status = 'active' AND (SELECT status FROM public.profiles WHERE id = auth.uid()) = 'approved');
CREATE POLICY products_owner_write ON public.products FOR ALL
  USING (wholesaler_org_id = (SELECT organization_id FROM public.profiles WHERE id = auth.uid()));
