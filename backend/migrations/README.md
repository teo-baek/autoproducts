# ezmerce v2 — DB 마이그레이션 실행 순서

Supabase **SQL Editor**에 아래 파일들을 **순서대로** 붙여넣어 실행합니다. (raw SQL — 현재 CLI 미사용)

## 신규/리셋 적용 (v1 → v2 덮어쓰기)

0. **`_RESET_public.sql`** — ⚠️ **딱 한 번**, v1을 전부 날릴 때만. (public 스키마 전체 삭제 후 재생성. auth·storage는 유지)
1. `2026-06-03_v2_core.sql` — ENUM 6종 + wholesalers/agencies/profiles/products/product_skus/product_images/upload_jobs + RLS + platform_code 시퀀스
2. `2026-06-03_v2_core_02_price_visibility.sql` — 관리자 설정형 가격 노출(`price_visibility`)
3. `2026-06-03_v2_core_03_soft_delete.sql` — soft delete(`deleted_at`) + 부분 유니크 + soft-cascade 트리거 + RLS 필터
4. `2026-06-03_v2_core_04_audit.sql` — 감사 컬럼(`created_by`/`updated_by`/`updated_at`) + `set_updated_at` 트리거
5. `2026-06-03_v2_core_05_platform_code_fn.sql` — `public.next_platform_seq()` RPC 함수(상품 등록 시 platform_code 발급용)
6. `2026-06-05_v2_core_06_register_fields.sql` — 회원가입 확장: `profiles.company_name`/`business_cert_path`/`id_doc_path` + 비공개 `business-docs` 버킷

## 주의
- `_RESET_public.sql`은 **비가역**(데이터 영구 삭제). 올바른 프로젝트인지 확인 후 실행.
- 1~4는 리셋 후 깨끗한 public 위에서 순서대로 실행하면 충돌 없이 끝납니다.
- `auth.users`(로그인 계정)와 storage 버킷/이미지는 reset이 건드리지 않음.
- 적용 후: 백엔드는 `backend/.env`(SUPABASE_URL + SUPABASE_SERVICE_KEY)로 접속. JWT는 JWKS 공개키로 검증.
