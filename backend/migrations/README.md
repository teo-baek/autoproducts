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
7. `2026-06-06_v2_core_07_product_category.sql` — 상품 분류 `products.category`(의류/잡화 등) + 부분 인덱스. 도매 상품관리 목록 필터·단일 등록 모달용. **(상품관리 화면의 카테고리 기능에 필요)**

## Storage 버킷 (대시보드 또는 SQL)
- **`product-images`** — 상품 이미지 업로드용. **공개(public) 권장**(상품 사진은 카탈로그 노출이 목적). 프론트가 직접 업로드 → `representative_image_url`(public URL) 저장 + 매니페스트 매칭. 미생성 시 단일/대량 등록의 이미지 업로드만 실패(상품 데이터 등록은 정상).
  - 대시보드: Storage → New bucket → name `product-images`, Public ✓.

## 주의
- `_RESET_public.sql`은 **비가역**(데이터 영구 삭제). 올바른 프로젝트인지 확인 후 실행.
- 1~4는 리셋 후 깨끗한 public 위에서 순서대로 실행하면 충돌 없이 끝납니다.
- `auth.users`(로그인 계정)와 storage 버킷/이미지는 reset이 건드리지 않음.
- 적용 후: 백엔드는 `backend/.env`(SUPABASE_URL + SUPABASE_SERVICE_KEY)로 접속. JWT는 JWKS 공개키로 검증.
