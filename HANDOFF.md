# HANDOFF — ezmerce v2 백엔드 (1차)

> 새 세션은 이 파일 경로만 주고 시작하면 됩니다: `HANDOFF.md`
> 작성 시점: 2026-06-03 / 브랜치: **`v2-dev`** (feature/dev 기준 38 commits) / 테스트: **36 passed**

## 🎯 Goal
**ezmerce** = 폐쇄형 B2B 도매 카탈로그·주문 솔루션 (고객: **LALAS** 동대문 도매상인연합).
1차 백엔드 = **FastAPI + Supabase(Postgres/Auth/Storage)**. 범위: 상품등록·엑셀출력·QR + 역할기반 폐쇄형 카탈로그(가격 차등 노출).
설계/계획/변경이력 문서: `docs/features/2026-06-03-ezmerce-v2-backend/` (requirements / tech-design / implementation-plan + ERD/overview HTML).
프로젝트 규칙: 루트 **`CLAUDE.md`** (DB 삭제 정책·레이어 규칙 등 — 꼭 읽기).

## ✅ Current Progress (된 것)
- **백엔드 전체 구현 + 36 tests 통과** (`cd backend && .venv/bin/python -m pytest`). 단위테스트는 fake repo 기반이라 라이브 DB 없이 통과.
- **DB 스키마 라이브 적용 완료** — Supabase 프로젝트(`ezjgnmbuheheytcyibmx`)에 v1 리셋 후 v2 적용. **7개 테이블 + 핵심 컬럼 REST로 검증됨**(v1 잔재 0).
- 라우터(14 routes): `/health`, `/admin/accounts(+approve/reject/price-visibility)`, `/products(+PATCH/DELETE)`, `/catalog`, `/p/{code}`, `/qr/{code}.png`.
- js-super 파이프라인 산출물(요구사항→설계→계획) + 변경이력 CH-001~019 누적.

### 핵심 설계 결정 (이번 세션에서 확정 — 다 반영됨)
1. **도매업체 ≠ 에이전시 = 별도 테이블** (`wholesalers`/`agencies`). `organizations+type` 단일테이블 폐기. `products.wholesaler_id`는 도매만 가리킴(타입안전).
2. **모든 사람 계정 = `profiles` 한 테이블**(`role`로 구분: admin/wholesaler/retail_seller/agency). **소매셀러도 profiles 행**(개인계정). 조직만 테이블.
3. **가격 노출 = 서버 권위 셰이핑** (`pricing.py`). `profiles.price_visibility`(관리자 설정, wholesale|retail|none) 우선, 미설정 시 seller_type 기본값. 라이브셀러→도매가/에이전시→판매가/에이전시소속셀러→미노출.
4. **soft delete 전면** — 전 테이블 `deleted_at`(hard DELETE 금지). 부분 유니크 + soft-cascade 트리거(`_03`). 조회는 `deleted_at IS NULL`.
5. **감사 컬럼** — `created_by`/`updated_by`(FK profiles) + `updated_at` 자동 트리거(`_04`). products 경로엔 wiring 완료(register=created_by, patch/delete=updated_by).
6. **JWT = JWKS 공개키(ES256) 검증** (`auth.py verify_supabase_jwt`, PyJWKClient). 신규 Supabase 비대칭 키 대응. `SUPABASE_JWT_SECRET` 불필요(HS256 `decode_jwt`는 레거시 폴백).
7. **품번 정규화** = `platform_code`(글로벌, SEQUENCE) + `(wholesaler_id, source_p_number)` 유니크. `EZM-000001` 형식.
8. **레이어**: 도메인 엔티티 = `app/entities/`(models+enums), DTO = `app/schemas/`. (혼동 금지)
9. **에이전시는 1차 미운영** — 역할/테이블/agency_id 데이터모델만 forward-compat(§5). 동작하는 건 "에이전시 소속 셀러 가격 미노출"뿐.

### 빌드/환경
- backend = **정식 uv 프로젝트** (`backend/pyproject.toml` + `backend/uv.lock`). 재현: `cd backend && uv sync --all-groups`. `requirements.txt`는 `uv export` 파생본(직접 편집 금지).
- 루트의 옛 Streamlit pyproject/uv.lock/requirements.txt는 **삭제됨**(Python 프로젝트는 backend 단독).
- `backend/.env` 존재(gitignore됨). 사용자가 SUPABASE_URL + SUPABASE_SERVICE_KEY 채움. `.env.example` 참고.

## ⚠️ 발견한 버그/함정 (반복 금지)
- **supabase-py 가 backend/.venv에 실제로는 미설치였음** → 한 서브에이전트가 스텁을 만들어 라이브러리를 가렸던 적 있음. 진짜 설치로 교체 완료. (find_spec OK ≠ import OK)
- **`auth.decode_jwt` HS256** 은 신규 Supabase(비대칭) 토큰 검증 불가 → **JWKS로 전환 완료**.
- **`platform_code.next_platform_code` 가 `rpc("nextval", ...)` 호출** → PostgREST로 호출 불가(pg_catalog 함수). **`public.next_platform_seq()` RPC(`_05`)로 교체 완료**. ⬅️ 단, **`_05` 마이그레이션은 아직 SQL Editor에서 실행 안 됨!** (Next Steps 참고)

## 🔜 Next Steps (이어서 할 일)
1. **[즉시] `_05` 마이그레이션 실행** — `backend/migrations/2026-06-03_v2_core_05_platform_code_fn.sql`을 Supabase SQL Editor에 붙여 실행. (안 하면 상품 등록 시 platform_code 발급 실패)
   - 실행 후 RPC 동작 확인: 서비스키로 `POST {SUPABASE_URL}/rest/v1/rpc/next_platform_seq` → 숫자 반환되면 OK.
2. **엔드포인트 동작 확인** (사용자 요청) — `cd backend && .venv/bin/uvicorn app.main:app --reload` → `/docs`(Swagger)로 확인. 라이브 DB 연결됨. (단위테스트는 이미 green, 여기선 실제 Supabase 연동 동작 검증)
   - 스모크: wholesaler 1행 insert → profile(role=wholesaler, wholesaler_id) → 상품 등록 → platform_code/updated_at 트리거/soft delete cascade 동작 확인.
3. **갭 엔드포인트 빌드** (사용자가 선택한 방향, TDD/fake repo로 DB없이도 가능):
   - `POST /auth/register` — Supabase Auth 가입 후 `profiles`(status=pending) 생성. **추천: 백엔드 엔드포인트 방식**(role/seller_type 받아 service key로 insert).
   - `GET /catalog/export.xlsx` — `excel_export` 서비스 이미 있음, 라우트만.
   - `POST /uploads/excel`·`/uploads/images`·`GET /uploads/{job}/unmatched`·`POST /uploads/{job}/match` + `upload_jobs` 영속화. (`excel_parse`·`image_match` 로직 완성됨)
4. **이미지 스토리지 결정/구현** — `product_images.storage_path` = Supabase Storage 버킷(`product-images`). **추천: v1처럼 프론트가 Storage 직접 업로드**, 백엔드는 경로 기록+매칭. 버킷+RLS 생성 필요(아직 없음).
5. (이후) 프론트(apps/web·mobile) ↔ FastAPI 연동, Phase 2(주문/배송).

## 미해결 결정 (다음 세션에서 확정 필요)
- 회원가입 profiles 생성: 백엔드 `/auth/register`(추천) vs DB 트리거(auth.users→profiles).
- 이미지 업로드: 프론트 직접 Storage(추천, v1 방식) vs 백엔드 프록시(multipart).

## 참고 위치
- 마이그레이션 + 실행순서: `backend/migrations/README.md` (리셋 `_RESET_public.sql` → `_v2_core` → `_02` → `_03` → `_04` → `_05`)
- 변경이력(감사 추적): 각 `docs/features/2026-06-03-ezmerce-v2-backend/*.md` 의 `## 변경이력` (CH-YYYYMMDD-NNN)
- 가격 로직: `app/services/pricing.py` / 인증: `app/core/auth.py` / 설정: `app/core/config.py`
- 워크플로: js-super 스킬(brainstorm→tech-design→write-plan→execute-plan, change-history, change-propagation). 변경 시 change-history 기록 규율 유지.

## 검증 명령
```bash
cd backend && .venv/bin/python -m pytest -q          # 36 passed 기대
cd backend && .venv/bin/python -c "from app.main import app; print(sorted({r.path for r in app.routes}))"
# 라이브 스키마 점검(읽기전용, 시크릿 비노출)은 이 세션에서 쓴 PostgREST OpenAPI 조회 방식 재사용
```
