-- ==============================================================================
-- AutoProducts DB & Storage 통합 보안 정책 해결 스크립트
-- ==============================================================================
-- 이 스크립트는 다음 두 가지 문제를 해결합니다.
-- 1. Storage 403 에러 해결: upsert 동작에 필요한 SELECT, UPDATE 권한 추가
-- 2. Advisor 에러 해결: store_profiles 테이블의 RLS 활성화 스위치 ON
-- ==============================================================================

-- ------------------------------------------------------------------------------
-- [1] Storage 권한 업데이트 ('product-images' 버킷 전체 공개)
-- ------------------------------------------------------------------------------
-- 기존에 만들었던 단일 INSERT 정책이 있다면 삭제하여 충돌을 방지합니다.
DROP POLICY IF EXISTS "Allow public uploads to product-images" ON storage.objects;

-- 덮어쓰기(Upsert)와 읽기에 필요한 권한들을 각각 생성합니다.
CREATE POLICY "Allow public select for product-images" 
ON storage.objects FOR SELECT TO public 
USING (bucket_id = 'product-images');

CREATE POLICY "Allow public insert for product-images" 
ON storage.objects FOR INSERT TO public 
WITH CHECK (bucket_id = 'product-images');

CREATE POLICY "Allow public update for product-images" 
ON storage.objects FOR UPDATE TO public 
USING (bucket_id = 'product-images');

-- ------------------------------------------------------------------------------
-- [2] Database 테이블 권한 경고 해결
-- ------------------------------------------------------------------------------
-- 이미 만들어진 권한 정책들이 올바르게 작동하도록 테이블의 RLS를 활성화합니다.
ALTER TABLE public.store_profiles ENABLE ROW LEVEL SECURITY;
