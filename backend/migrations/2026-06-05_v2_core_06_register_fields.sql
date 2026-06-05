-- 2026-06-05_v2_core_06_register_fields.sql
-- 회원가입 확장: 회사명 + 사업자 서류 경로 + 비공개 Storage 버킷.
-- 실행: Supabase SQL Editor. 실행순서상 _05 다음.

-- 1) profiles 컬럼 추가 ---------------------------------------------------------
ALTER TABLE public.profiles
  ADD COLUMN IF NOT EXISTS company_name       TEXT,  -- 회사명/상호 (소매·도매·에이전시 공통)
  ADD COLUMN IF NOT EXISTS business_cert_path TEXT,  -- 사업자등록증 (business-docs 버킷 내 경로)
  ADD COLUMN IF NOT EXISTS id_doc_path        TEXT;  -- 신분증 (민감 PII)

COMMENT ON COLUMN public.profiles.id_doc_path IS
  '신분증 경로 — 민감 PII(주민등록번호 포함 가능). 비공개 버킷 전용. 마스킹/최소수집/보존정책 필요(개인정보보호법).';

-- 2) 비공개 Storage 버킷 -------------------------------------------------------
--    public=false. 업로드는 백엔드(service key)만 수행하므로 클라이언트용 RLS 정책은 두지 않는다.
--    (절대 public read 또는 anon insert 정책을 추가하지 말 것 — 민감 서류 노출 방지.)
INSERT INTO storage.buckets (id, name, public)
VALUES ('business-docs', 'business-docs', false)
ON CONFLICT (id) DO NOTHING;

-- 참고: service_role 키는 RLS 를 우회하므로 백엔드 업로드/조회는 정책 없이 동작.
-- 클라이언트 직접 접근은 차단된 상태가 안전한 기본값(폐쇄형 정책).
