# HANDOFF — ezmerce v2 백엔드 (1차)

> 🔭 **다음 작업 = 상품등록 엑셀/이미지 파이프라인 고도화(jinsup_dev 흡수)** → [HANDOFF-product-pipeline-upgrade.md](HANDOFF-product-pipeline-upgrade.md) 로 시작.
> ✅ 도매상 상품 등록(프론트+백엔드) 구현 완료 (2026-06-06) → [HANDOFF-product-registration.md](HANDOFF-product-registration.md). 사용자 액션 2개 남음: **마이그레이션 `_07`** + **`product-images` 버킷(공개)** 생성. (인증·디자인시스템도 완료 — [HANDOFF-frontend-design-system.md](HANDOFF-frontend-design-system.md). 이 문서는 백엔드 상태/인계)
> 새 세션은 이 파일 경로만 주고 시작하면 됩니다: `HANDOFF.md`
> 최종 갱신: 2026-06-04 / 브랜치: **`v2-dev`** / 단위 **65 passed** / **라이브 스모크 24 PASS·0 FAIL** / `_05` 적용됨 / 비즈니스 라우트 **16개**(+health)

## 🎯 Goal
**ezmerce** = 폐쇄형 B2B 도매 카탈로그·주문 솔루션 (고객: **LALAS** 동대문 도매상인연합).
1차 백엔드 = **FastAPI + Supabase(Postgres/Auth/Storage)**. 범위: 상품등록·엑셀출력·QR + 역할기반 폐쇄형 카탈로그(가격 차등 노출).
설계/계획/변경이력 문서: `docs/features/2026-06-03-ezmerce-v2-backend/` (requirements / tech-design / implementation-plan + ERD/overview HTML).
프로젝트 규칙: 루트 **`CLAUDE.md`** (DB 삭제 정책·레이어 규칙 등 — 꼭 읽기).

## ✅ Current Progress (된 것)
- **백엔드 전체 구현 + 58 tests 통과** (`cd backend && .venv/bin/python -m pytest`). 단위테스트는 fake repo 기반이라 라이브 DB 없이 통과. uvicorn 부팅 스모크 OK(/health 200, OpenAPI 16라우트).
- **DB 스키마 라이브 적용 완료** — Supabase 프로젝트(`ezjgnmbuheheytcyibmx`)에 v1 리셋 후 v2 적용. **7개 테이블 + 핵심 컬럼 REST로 검증됨**(v1 잔재 0). ⚠️ **단 `_05`(platform_code RPC)는 아직 미적용** — 라이브 RPC 호출이 404(아래 Next Steps 1).
- **갭 엔드포인트 3그룹 완성**(이전 세션 §4 미구현분):
  - `GET /catalog/export.xlsx` — 역할별 가격 셰이핑 + QR 삽입 엑셀 다운로드 (CH-020)
  - `POST /auth/register` — 백엔드 회원가입(자가가입 retail_seller/agency 화이트리스트, status=pending, price_visibility 시드) (CH-021)
  - `POST /uploads/excel`·`/images`·`GET /{job}/unmatched`·`POST /{job}/match` + upload_jobs 영속화 (CH-022)
- 라우터(16 routes): `/health`, `/auth/register`, `/admin/accounts(+approve/reject/price-visibility)`, `/products(+PATCH/DELETE)`, `/catalog(+export.xlsx)`, `/p/{code}`, `/qr/{code}.png`, `/uploads/{excel,images,{job}/unmatched,{job}/match}`.
- js-super 파이프라인 산출물(요구사항→설계→계획) + 변경이력 CH-001~022 누적.

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

## ✅ 라이브 검증 완료 (2026-06-04)
- `_05` 적용됨(RPC 정상). **라이브 스모크 24 PASS / 0 FAIL** — 가입·승인 → 상품 CRUD·platform_code·보관·soft delete → 엑셀 대량등록·자동매칭·수동매칭 → IDOR 404 → 카탈로그(도매가 노출)·export.xlsx·QR·공개카드(가격 미포함)·미승인 403, cleanup까지. gotrue `res.user.id` 형태도 라이브 확인(이전 RISK 해소).
- **재검토로 보안/잠복 버그 수정**: uploads IDOR(CH-023), products IDOR+mass-assignment·공개카드 deleted_at 누락(CH-024), catalog 가 SKU에 없는 wholesaler_id 임베드 조회로 라이브 500(CH-025) — 모두 수정·검증.

## 🔜 Next Steps (이어서 할 일)
1. **[사용자] `product-images` Storage 버킷 + RLS 생성** — 이미지 업로드 모델=프론트 직접 Storage(확정). 버킷 생성(비공개) + storage.objects RLS(SQL Editor). 실제 프론트 이미지 업로드 전까지는 미사용이라 급하진 않음. (현재 uploads 매칭은 매니페스트만으로 동작 — 실파일 불필요)
2. (권장) 남은 should-fix 정리 — uploads #3 트랜잭션 부재(부분실패 시 job-first), #6 export 대표가격 폴백, #8 error_detail JSONB 날짜셀 직렬화. (라이브 동작엔 지장 없음)
3. (이후) 프론트(apps/web·mobile) ↔ FastAPI 연동, Phase 2(주문/배송).

## 검증/테스트 도구
- 단위테스트: `cd backend && .venv/bin/python -m pytest -q` (65 passed). notebook 도구 포함 재현: `uv sync --all-groups`.
- **API 라이브 통합 노트북**: `backend/notebooks/ezmerce_v2_api_tests.ipynb` — Jupyter로 Run All 하면 1차 API 전체를 실 Supabase에 대고 검증(시드→흐름→cleanup). 비정형 엑셀은 1차 비범위(표준 템플릿만, 확정).

## 확정된 결정 (이번 세션)
- 회원가입 = **백엔드 `/auth/register`** (자가가입 role 화이트리스트로 권한상승 차단). → CH-021
- 이미지 업로드 = **프론트 직접 Storage** (v1 방식, 백엔드는 경로 기록+품번 자동매칭). → CH-022

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
