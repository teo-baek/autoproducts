---
commit_policy: per-task
---

# 구현계획서: 도매관리자 멀티테넌트 1차 재편

> **상위 문서**: [`requirements`](./wholesale-manager-tenancy-requirements.md)(CH-20260609-001) · [`tech-design`](./wholesale-manager-tenancy-tech-design.md)(CH-20260609-002)
> **실행 방식**: 메인 에이전트 직접 순차 구현(사장님 글로벌 규칙 "실행은 메인에서 직접" 우선 — wave-parallel 서브에이전트 미사용). TDD: 각 task = 테스트 먼저 → 구현 → `cd backend && .venv/bin/python -m pytest` 통과 → 다음.
> **DB DDL**: 마이그레이션 `_10` 은 **사용자가 Supabase SQL Editor에서 직접 실행**(앱 미실행). 백엔드 코드는 그 스키마가 적용됐다는 전제로 작성하되, 테스트는 fake repo 라 DB 없이 통과.

---

## 1. 작업 분해 (TDD bite-sized, 의존성 순)

### Phase 0 — DB 마이그레이션 (사용자 실행분)

- **T0 — 마이그레이션 `_10` SQL 파일 + 순서 문서**
  - Files: `backend/migrations/2026-06-09_v2_core_10_wholesale_manager_tenancy.sql`(신규), 마이그레이션 순서 안내(`CLAUDE.md`/README 마이그레이션 표에 10번 추가)
  - 내용: tech-design §2.3 SQL 그대로(테넌트 테이블·연결표·`profiles.manager_id`·부분 unique·트리거·RLS deny·LALAS 시드·backfill).
  - **실행 전 확인**: `_03`/`_04` 의 실제 트리거 함수명(`set_updated_at`/soft-cascade)을 마이그레이션 파일에서 읽어 SQL의 `EXECUTE FUNCTION` 이름을 일치시킴(R7).
  - Model hint: sonnet(정확성). TDD: 코드 테스트 없음 — SQL 정합은 사용자 실행 시 확인. 산출물 검증 = 파일 존재 + 컨벤션 일치.

### Phase 1 — 백엔드 기반 (모델·테넌시 헬퍼·auth)

- **T1 — 엔티티 모델 추가**
  - Files: `backend/app/entities/models.py`
  - `WholesaleManager`, `ManagerWholesaler` 모델 + `Profile.manager_id: str | None` 추가(기존 `_Entity` 공통 컬럼 패턴 따름).
  - TDD: `tests/test_entities*`(있으면) 또는 신규 — 모델이 Supabase dict 에서 생성되는지 1건.
  - Model hint: haiku(mechanical).

- **T2 — 테넌시 공용 헬퍼 신설**
  - Files: `backend/app/services/tenancy.py`(신규), `backend/tests/test_tenancy_service.py`(신규)
  - `scoped_wholesaler_ids(sb, manager_id) -> list[str]`: `manager_id` falsy → `[]`(fail-closed); 정상 → `manager_wholesalers`(alive)에서 wholesaler_id 목록.
  - TDD: fake sb 로 (a) None→`[]`, (b) 정상→id 목록, (c) deleted_at 필터 확인.
  - Model hint: sonnet. RISK(R3): 빈 리스트 fail-closed.

- **T3 — CurrentUser.manager_id resolve 주입**
  - Files: `backend/app/schemas/auth.py`, `backend/app/core/auth.py`, `backend/tests/test_auth_resolve.py`(신규)
  - `CurrentUser.manager_id: str | None = None`. `auth._resolve_manager_id(sb,row)`: 셀러/admin=`profiles.manager_id`, 도매=`manager_wholesalers` 1행. `get_current_user`/`get_current_user_optional` 매핑 직전 주입.
  - TDD: 3역할 분기 + 도매 미연결→None.
  - Model hint: sonnet. RISK(R5): 도매 로그인 +1 쿼리.

### Phase 2 — 카탈로그/공개카드 스코핑 (회귀 주의)

- **T4 — 카탈로그 테넌트 스코핑**
  - Files: `backend/app/routers/catalog.py`, `backend/tests/test_catalog_shaping.py`(보강)
  - `_query_catalog_rows(..., wholesaler_ids=None)` 추가, `list_catalog`/`export_catalog`에서 `tenancy.scoped_wholesaler_ids(sb, user.manager_id)` 주입. `wholesaler_ids=[]`→빈 결과, `None`→무필터(내부 export 재사용 등).
  - TDD: (a) 빈 스코프→빈, (b) "전체=LALAS"→무필터 동일(회귀 동일성), (c) shape/visible_price 무변경 통과.
  - Model hint: sonnet. RISK(R2/R3).

- **T5 — 공개카드 스코핑**
  - Files: `backend/app/routers/public.py`, `backend/tests/test_public_card.py`(보강)
  - 로그인+승인 뷰어일 때 상품 `wholesaler_id ∈ scoped_ids` 면 skus 부여, 아니면 공개 최소 카드만(404 아님). 비로그인 무변경.
  - TDD: 스코프 안/밖, 비로그인 3케이스.
  - Model hint: sonnet. RISK(R3).

### Phase 3 — 승인 스코프 + 합산 상품

- **T6 — 테넌트 스코프 승인 + 연결 보상**
  - Files: `backend/app/services/accounts.py`, `backend/app/routers/admin.py`, `backend/tests/test_accounts_service.py`(수정)
  - `list_by_status(status, manager_id)` 자기 테넌트+미배정(`or_`). `approve_account(..., admin_manager_id)`: 도매=`link_wholesaler_to_manager`(멱등)+보상, 셀러=`set_status(manager_id=)`. `admin.py` 호출부 `user.manager_id` 전달.
  - TDD: 도매 승인→연결+보상, 셀러 승인→manager_id, list 스코프. 기존 test 호출부 `admin_manager_id` 인자 추가.
  - Model hint: sonnet. RISK(R2/R6): 승인 누락 시 카탈로그 누락 / `or_` UUID 검증.

- **T7 — 합산 상품관리 엔드포인트**
  - Files: `backend/app/routers/admin.py`, `backend/app/services/products.py`(shape 재사용/`shape_admin_product`), `backend/tests/test_admin_products.py`(신규)
  - `GET /admin/products`: `scoped_wholesaler_ids` → `products.in_(ids)` + `wholesalers(name)` join + skus, 페이지네이션, 가격=admin 양가(visible_price). `shape_admin_product`가 `wholesaler_name` 부여.
  - TDD: shape에 wholesaler_name, 빈 스코프→빈, 가격 admin 양가.
  - Model hint: sonnet. RISK(R4): 성능/페이지네이션.

### Phase 4 — 프론트 (도매관리자 대시보드 상품관리)

- **T8 — 프론트 데이터 레이어**
  - Files: `apps/web/src/lib/products.ts`
  - `Me.manager_id` 추가, `AdminProduct = Product & { wholesaler_name: string }`, `listAdminProducts(params)` → `GET /admin/products`.
  - TDD: 타입 컴파일(`npm run build`/tsc) — UI라 단위테스트 대신 빌드 통과.
  - Model hint: sonnet.

- **T9 — 도매관리자 상품관리 화면 + 네비**
  - Files: `apps/web/src/app/admin/products/page.tsx`(신규), `apps/web/src/components/AdminShell.tsx`(NAV 항목 추가)
  - `(dash)/products/page.tsx` 참고 + **도매 출처(wholesaler_name) 컬럼**. 가격 도매가/판매가 둘 다. AdminShell NAV에 "상품 관리" 추가.
  - TDD: `npm run build` 통과 + 수동 점검(T11 가이드).
  - Model hint: sonnet.

### Phase 5 — 검증 + 사용자 가이드

- **T10 — 전체 테스트 게이트 + 마이그레이션 안내 문서**
  - `cd backend && .venv/bin/python -m pytest` 전체 통과. `apps/web` 빌드 통과. 마이그레이션 실행 순서/주의(backfill 1회) 문서화.
  - Model hint: sonnet.

- **T11 — 사용자 수동 테스트 HTML 가이드** (blocked by 전체 구현)
  - Files: `docs/features/2026-06-09-wholesale-manager-tenancy/manual-test-guide.html`(신규)
  - 사장님이 실제 서비스에서 직접 해볼 스텝(코드 테스트 아님): ① 마이그레이션 `_10` Supabase 실행 → ② `rythmn@naver.com`/`lalas2026!` admin 로그인 → ③ 도매관리자 대시보드 가입승인·합산 상품관리(도매 출처 보이는지) → ④ 도매 계정 로그인=자기 상품만 → ⑤ 셀러 로그인=카탈로그/쇼룸 상품 노출 + 가격 역할별(일반=도매가/에이전시소속=가격문의) → ⑥ 공개 QR 카드. 다크 프리미엄 톤, step-by-step 체크리스트.
  - Model hint: sonnet.

---

## 2. 위험 코드 지점 (R-N → 위치/완화)

- **R1 (회귀, breaking) — 가격 셰이핑 불변**: `app/services/pricing.py` `visible_price` 손대지 않음. catalog/public/products 호출 인자 동일 유지. 가드: `test_catalog_shaping` 통과 = 위반 신호 감지.
- **R2 (side-effect) — 카탈로그 회귀 동일성**: `catalog.py:_query_catalog_rows`/`list_catalog`, `accounts.approve_account`(신규 도매 연결). backfill+승인연결 누락 시 상품 누락. 가드: 회귀 동일성 테스트(T4) + 승인 연결 테스트(T6).
- **R3 (side-effect) — 빈 스코프 fail-closed**: `app/services/tenancy.py:scoped_wholesaler_ids`(`[]`), `catalog.py`/`public.py` `.in_([])`. 가드: 빈 리스트→빈 결과 테스트.
- **R4 (perf) — 합산 쿼리**: `admin.py:admin_products` `in_(ids)`+임베드. 가드: 페이지네이션(range) 필수, export 상한 패턴.
- **R5 (perf) — auth +1 쿼리**: `auth.py:_resolve_manager_id`(도매). 인덱스 `manager_wholesalers_wid_alive` 직격. 완화: 인덱스 존재(마이그레이션).
- **R6 (side-effect) — `or_` 필터/UUID**: `accounts.list_by_status`. manager_id UUID 형식 검증 후 삽입.
- **R7 (breaking) — 트리거 함수명**: 마이그레이션 `_10` `EXECUTE FUNCTION` 이름이 `_03`/`_04` 실제 함수명과 일치해야 함. 가드: T0에서 마이그레이션 파일 직접 확인.

---

## 변경이력
<!-- change-history skill auto-appends entries here, oldest first -->

### [2026-06-09 21:55] [구현계획서-수정]
- **id**: CH-20260609-003
- **이유**: 신규 피처 구현계획 최초 작성 — tech-design(CH-20260609-002) 기반 TDD bite-sized 분해(T0~T11) + §2 위험지점 R1~R7. 실행은 메인 직접 순차(사장님 글로벌 규칙 "실행은 메인에서 직접"). plan_byte_check·per-doc HTML 사본은 헬퍼 부재로 생략.
- **무엇이**: `wholesale-manager-tenancy-implementation-plan.md` 전체 — Phase 0~5, T0~T11, 위험 코드 지점, frontmatter `commit_policy: per-task`.
- **영향범위**: 다음 단계 구현(execute) 입력.
- **연관 항목**: CH-20260609-002

### [2026-06-09 22:30] [코드-수정] (batch: T0~T10)
- **id**: CH-20260609-004
- **이유**: 도매관리자 멀티테넌트 1차 구현 완료 — DB 마이그레이션 + 백엔드 테넌트 스코핑/승인/합산상품 + 프론트 도매관리자 상품관리 화면. **백엔드 pytest 186 passed, 프론트 tsc 0 error.**
- **무엇이**:
  - 신규: `backend/migrations/2026-06-09_v2_core_10_wholesale_manager_tenancy.sql`, `backend/app/services/tenancy.py`, `backend/tests/{test_tenancy_service,test_auth_resolve,test_catalog_scope,test_admin_products}.py`, `apps/web/src/app/admin/products/page.tsx`
  - 수정: `backend/app/entities/models.py`, `app/schemas/auth.py`, `app/core/auth.py`, `app/routers/{catalog,public,admin}.py`, `app/services/accounts.py`, `migrations/README.md`, `tests/{test_accounts_service,test_catalog_export,test_public_card}.py`, `apps/web/src/lib/products.ts`, `apps/web/src/components/AdminShell.tsx`
- **영향범위**: `GET /catalog`·`/p/{code}`·`/catalog/export.xlsx` 테넌트 스코프(1차 LALAS 단일 → 기존과 동일 결과), `GET /admin/accounts`·`/approve` 테넌트 단위, 신규 `GET /admin/products`. 가격 셰이핑(`visible_price`) 불변(FR-8). DB DDL(`_10`)은 사용자 Supabase 실행분.
- **위험 카테고리**: side-effect(스코프 fail-closed `[]`→빈 결과 / 승인 시 도매 연결 누락 시 카탈로그 누락 → 보상·테스트로 가드), breaking(트리거 함수명·마이그레이션 순서 — `set_updated_at` 실제 확인 완료)
- **변경 전/후 코드**: 생략 — 작업트리(`v2-dev`, 미커밋)가 기록. 테스트 통과로 검증.
- **연관 항목**: CH-20260609-003
