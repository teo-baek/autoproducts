# ezmerce — 프로젝트 규칙

폐쇄형 B2B 도매 카탈로그/주문 솔루션 (고객: LALAS). 1차 백엔드 = FastAPI + Supabase(Postgres/Auth/Storage).
- 현재 작업 브랜치: `v2-dev`
- 백엔드: `backend/` (FastAPI, `.venv` = uv 관리). 테스트: `cd backend && .venv/bin/python -m pytest`
- 의존성: `backend/pyproject.toml` + `backend/uv.lock` (uv 표준). 설치/재현: `cd backend && uv sync --all-groups`. 추가는 `uv add <pkg>` (또는 dev/notebook 그룹: `uv add --group dev <pkg>`). `backend/requirements.txt`는 `uv export` **파생본**이라 직접 편집 금지.
- 설계 문서/변경이력: `docs/features/2026-06-03-ezmerce-v2-backend/`
- DB 마이그레이션: `backend/migrations/` (실행 순서: `_v2_core.sql` → `_02_price_visibility.sql` → `_03_soft_delete.sql`)
- 프론트엔드: `apps/web/` (Next.js App Router + Tailwind v4). **UI/디자인 작업 전 디자인 가이드 필독** (아래 §프론트엔드).
- **로컬 실행/포트**: 백엔드 `cd backend && .venv/bin/python -m app.main` → **:8444** (= `uvicorn app.main:app --reload --port 8444`, `PORT` env override 가능). 프론트 `cd apps/web && npm run dev` → **:3555**. 프론트→백엔드 호출 base URL = `http://localhost:8444` (env `NEXT_PUBLIC_API_BASE_URL`). CORS는 개발 중 `allow_origins=["*"]`(운영 전 화이트리스트로 좁힐 것).

## 프론트엔드 (디자인 시스템) — UI 작업 전 필독
시안 PDF에서 추출한 디자인 시스템이 있다. **임의로 색/폰트/간격을 만들지 말고 토큰·가이드를 따른다.**
- **디자인 가이드**: `apps/web/design/DESIGN-SYSTEM.md` (미감·색·타이포·컴포넌트·레이아웃 셸 A~D·범위주의).
- **토큰(소스 오브 트루스)**: `apps/web/src/styles/ezmerce-tokens.css` (Tailwind v4 `@theme`). 색/라운드/그림자/타입스케일은 여기 토큰 사용.
- **화면 명세**: `apps/web/design/SCREEN-INVENTORY.md` (36화면 + 컴포넌트 인벤토리).
- **이미지 자산**: `apps/web/public/{images,brand}/` + 인덱스 `apps/web/design/ASSET-MANIFEST.md`.
- 폰트 = **Pretendard**(본문/헤딩) + **Playfair Display 이탤릭**(로고타입). 컴포넌트는 **shadcn/ui** 기준(토큰 매핑).
- 색은 의미(시맨틱 토큰)로 쓴다: 상태 배지 = 승인 초록 / 대기 앰버 / 거절 빨강 / 정보 파랑 / 등급 연보라. **가격은 서버 권위**(아래 DB 규칙) — 프론트는 표시만.
- ⚠️ 시안 범위 ⊃ 1차 백엔드(POS·주문·분석 등 미래분 포함). 구현은 PoC 범위부터(`TODO.md`). 시안의 템플릿 잔재(`VogueCore`, 무관 로고마크)는 쓰지 말 것.

## DB 규칙

### 삭제 (soft delete) — 반드시 준수
- **hard `DELETE` 금지.** 모든 테이블에 `deleted_at TIMESTAMPTZ` (NULL = 살아있음). 삭제 = `deleted_at = now()` 세팅.
- **모든 조회는 `WHERE deleted_at IS NULL`** 필터 필수 (앱 리포지토리/쿼리 + RLS 양쪽).
- **soft-cascade**: 부모를 soft delete 하면 자식도 전파된다 — DB 트리거가 처리 (`soft_cascade_product`, `soft_cascade_wholesaler`). 앱에서 자식을 일일이 지우지 말 것.
- `ON DELETE CASCADE` FK는 **하드삭제 비상용 안전망**으로만 유지. 평상시 경로는 soft delete.
- **UNIQUE는 부분 인덱스**(`... WHERE deleted_at IS NULL`)로 둔다 → soft delete 후 같은 값 재등록 허용. 단 `products.platform_code`는 영구 식별자(QR 대상)라 전체 UNIQUE 유지(재사용 X).
- "보관(`status='archived'`)"과 "삭제(`deleted_at`)"는 **다른 개념** — archived는 진열 내림(복구 쉬움), deleted_at은 제거.

### 가격 노출
- 가격은 **서버(FastAPI) 권위**로 결정. 클라이언트가 보낸 값 신뢰 금지.
- `profiles.price_visibility`(관리자 설정, `wholesale|retail|none`) 우선, 미설정이면 `seller_type` 기본값 폴백. 로직: `app/services/pricing.py`.

### 레이어 (혼동 금지)
- **도메인 엔티티** = `app/entities/` (`models.py` = DB 테이블 1:1 Pydantic 모델, `enums.py` = DB ENUM). Supabase dict ↔ 모델 변환·검증용.
- **DTO(요청/응답 전용)** = `app/schemas/` (예: `CurrentUser`, `ProductCreate`). 엔티티와 섞지 말 것.

### 식별/구조
- **품번 정규화**: 플랫폼 글로벌 `products.platform_code`(SEQUENCE 발급) + 업체 스코프 `(wholesaler_id, source_p_number)` 유니크.
- **도매업체(`wholesalers`)와 에이전시(`agencies`)는 별개 테이블.** `products`는 `wholesaler_id`만 가리킨다(에이전시가 상품 소유 불가).
- 인증: Supabase Auth(`auth.users`) ↔ `profiles` 1:1. 역할/권한은 `profiles`.

### 1차 범위 메모
- 대상: 라이브커머스 셀러만. **에이전시는 실운영 미구현**(역할/테이블/`agency_id` 데이터 모델만 forward-compat 준비). 일반 소매업체·주문/결제/배송·정산은 Phase 2+.
