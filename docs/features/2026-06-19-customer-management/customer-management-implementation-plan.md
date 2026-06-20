# 구현계획: 고객 관리 (Customer Management) — 1차

> **상위 문서**: `customer-management-requirements.md`(PRD) · `customer-management-tech-design.md`(설계). **다음 단계**: `execute-plan`(`/execute-plan`).
> 각 작업은 bite-sized + TDD(테스트 우선). 격리/스코프 지점에는 실행 시 `# ⚠️ RISK(...)` 주석 부착(§3).

## 1. 작업 순서 (의존 DAG)

```
T1(마이그레이션 SQL) ─ 사용자 실행 ─┐
                                    ├→ T2(엔티티/enum) → T3(서비스·격리) ──┬→ T4 GET /customers
                                    │                                      ├→ T5 GET /customers/wholesalers
                                    │                                      ├→ T6 assign·unassign
                                    │                                      ├→ T7 tier
                                    │                                      └→ T8 price-visibility
                                    │   (T4~T8: 라우터 + pytest)
T9(lib API/타입) ← (백엔드 계약 확정 후) → T10(CustomerTable 공용) →┬→ T11 도매 /customers
                                                                    └→ T12 관리자 /admin/customers + AdminShell 메뉴
T13(Shell 버튼 숨기기) — 독립 (병렬 가능)
T14(전체 검증: pytest + typecheck)
```
- **백엔드(T1~T8)** 와 **버튼 숨기기(T13)** 는 독립 → 병렬 가능. 프론트 화면(T11/T12) 은 T9·T10 + 백엔드 계약 확정 후.

## 2. 작업 목록

### T1 · DB 마이그레이션 SQL 작성 (사용자가 실행)
- **목표**: `wholesaler_customers`(n:m) 테이블 + `profiles.tier` 컬럼.
- **파일**: `backend/migrations/2026-06-20_v2_core_NN_customer_assignment_tier.sql` (NN = `backend/migrations/` 최신 일련번호+1, 작성 직전 `ls` 로 확인). `backend/migrations/README.md` 실행순서 추가.
- **내용**: 설계 §3.1/§3.2 SQL 그대로 — 테이블(+`gen_random_uuid()`, `ON DELETE CASCADE`, `deleted_at`), 살아있는 `(wholesaler_id, customer_id)` 부분 유니크, 인덱스 2개; `ALTER profiles ADD tier TEXT CHECK (tier IN ('new','regular'))` + 부분 인덱스. 멱등(`IF NOT EXISTS`).
- **완료조건**: SQL 파일·README 갱신 완료. ⚠️ **DDL 이라 사장님이 Supabase SQL Editor 에서 실행** — 실행 안내 출력. (앱은 실행 후 동작)

### T2 · 엔티티 / enum 추가
- **목표**: 도메인 모델에 tier·배정 반영.
- **파일**: `backend/app/entities/enums.py`, `backend/app/entities/models.py`.
- **구현**: `class CustomerTier(str,Enum){new,regular}`; `Profile.tier: str | None = None`; `class WholesalerCustomer(_Entity){id,wholesaler_id,customer_id,created_at,created_by,deleted_at}`.
- **테스트**: `tests/test_entities.py`(있으면) 또는 신규 — Profile dict→모델 라운드트립에 tier 포함, WholesalerCustomer 매핑.
- **완료조건**: import·검증 통과.

### T3 · 고객 서비스 + 리포지토리 (스코프·격리 핵심)
- **목표**: 역할별 스코프 조회·배정·해제·설정 로직을 한 곳에. **격리는 여기서 못박는다.**
- **파일**: 신규 `backend/app/services/customers.py` (+ repo 메서드는 `admin.py:SupabaseAdminRepo` 패턴 재사용 또는 신규 `SupabaseCustomersRepo`).
- **구현 요점**:
  - `list_customers(viewer)` — admin: `manager_id` 테넌트 소매(기존 `list_approved_for_manager` 확장, role in retail_seller/agency) + 각 소매의 `assigned_wholesalers`; wholesaler: `wholesaler_customers` 조인으로 `wc.wholesaler_id == viewer.wholesaler_id AND deleted_at IS NULL` 인 소매만.
  - `list_wholesalers(viewer)` — admin: `scoped_wholesaler_ids(manager_id)` → wholesalers + 배정 소매 수.
  - `assign(admin, customer_id, wholesaler_id)` — wholesaler_id ∈ scoped 검증 후 wc upsert(살아있는 중복이면 no-op).
  - `unassign(admin, customer_id, wholesaler_id)` — wc 행 soft delete.
  - `set_tier(viewer, uid, tier)` / `set_price_visibility(viewer, uid, vis)` — `_assert_can_manage(viewer, uid)`: admin=테넌트 내 uid, wholesaler=uid 가 자기 배정분일 때만(아니면 403).
  - `_assert_can_manage` / 도매 스코프 조인 = **단일 격리 게이트**(중복 구현 금지).
- **테스트(TDD 우선)** `tests/test_customers_service.py`:
  - 도매 A 조회 = 자기 배정만, B 배정 소매 0건.
  - 도매 A 가 B 배정 소매 set_tier/set_price_visibility → 권한오류.
  - admin = 테넌트 전체, 타 테넌트 0건.
  - assign/unassign 반영, n:m(소매 1개 → A·B 둘 다), soft delete 후 재배정.
- **완료조건**: 위 테스트 green.

### T4 · `GET /customers` 라우터
- **파일**: 신규 `backend/app/routers/customers.py`; `app/main.py` include.
- **구현**: `get_current_user` 의존 → `customers.list_customers(user)`. 응답 = `Customer[]`(Account 필드 + tier + assigned_wholesalers).
- **테스트** `tests/test_customers_routes.py`: admin/wholesaler 각 200·스코프, 비인증 401, 미승인 도매 거부.
- **완료조건**: 테스트 green.

### T5 · `GET /customers/wholesalers` (admin 전용)
- **구현**: `_admin(user)` 가드 → `list_wholesalers(user)`.
- **테스트**: admin 200(테넌트 도매 + 배정 수), 도매 호출 403, 타 테넌트 0건.

### T6 · `POST /customers/{uid}/assign` · `/unassign` (admin 전용)
- **구현**: `{wholesaler_id}` 검증 → service. 400(누락)/403(스코프 밖 wholesaler)/404(없는 uid).
- **테스트**: assign→GET 도매뷰 반영, unassign→사라짐, scoped 밖 wholesaler_id 403, 재배정 정상.

### T7 · `POST /customers/{uid}/tier`
- **구현**: enum 검증(`new|regular`, 400) → `set_tier(user, uid, tier)`(스코프 강제).
- **테스트**: admin 전체 OK, 도매 자기배정 OK / 타 도매 고객 403, 잘못된 값 400.

### T8 · `POST /customers/{uid}/price-visibility`
- **구현**: 검증(`wholesale|retail|none`, 기존 로직 재사용) → `set_price_visibility(user, uid, vis)`(스코프 강제). 기존 `/admin/accounts/{uid}/price-visibility` 는 그대로 둠.
- **테스트**: 스코프 강제 동일 패턴. **회귀**: `visible_price()`·카탈로그/엑셀 가격 셰이핑 영향 없음(설정값만 변경) — 기존 테스트 green 유지.

### T9 · 프론트 lib 타입·API
- **파일**: `apps/web/src/lib/products.ts`.
- **구현**: `Customer = Account & { tier: string|null; assigned_wholesalers?: {id,name}[] }`; `listCustomers()`, `listWholesalers()`, `assignCustomer(uid,wid)`, `unassignCustomer(uid,wid)`, `setCustomerTier(uid,tier)`, `setCustomerPriceVisibility(uid,vis)` — 모두 `api(..., {auth:true})`.
- **완료조건**: `npm run typecheck` 0.

### T10 · 공용 `CustomerTable` 컴포넌트
- **파일**: 신규 `apps/web/src/components/CustomerTable.tsx`.
- **구현**: props `{ rows, role, wholesalers?, onAssign?, onTier, onPriceVis }`. 디자인(Admin.dc.html 고객관리) 레이아웃 — 컬럼 `거래처명(아바타)|담당자|등급|가격노출|가입상태|[상세]`, admin 이면 `소속 도매` 컬럼 추가. 필터 탭(전체/일반/신규) + 검색. 상세 패널(기본정보+등급·가격노출 드롭다운+메모, 주문/미수금 없음). 빈 상태. **디자인 토큰/시맨틱 배지 사용**(임의 색 금지).
- **완료조건**: typecheck 0, 디자인 가이드 준수.

### T11 · 도매 화면 `/customers` 교체
- **파일**: `apps/web/src/app/(dash)/customers/page.tsx` (ComingSoon 제거).
- **구현**: `listCustomers()` → `<CustomerTable role="wholesaler" .../>`. 등급/가격노출만(배정·도매탭 없음).
- **완료조건**: typecheck 0, 도매 로그인 시 자기 고객만.

### T12 · 관리자 화면 `/admin/customers` 신규 + 메뉴
- **파일**: 신규 `apps/web/src/app/admin/customers/page.tsx`; `apps/web/src/components/AdminShell.tsx` 메뉴 `고객 관리` 추가.
- **구현**: 탭 `[도매업체 | 소매 거래처]`. 소매 탭 = `<CustomerTable role="admin" wholesalers onAssign .../>`(배정 드롭다운). 도매업체 탭 = `listWholesalers()` 목록(이름/담당자/배정 소매 수/[상세]).
- **완료조건**: typecheck 0, admin 로그인 시 도매+소매 둘 다·배정 동작.

### T13 · Shell 버튼 숨기기 (독립)
- **파일**: `apps/web/src/components/Shell.tsx`.
- **구현**: NAV(L24-30)에서 `주문 관리`·`카탈로그 관리` 항목 제거(주석 아닌 제거 — 라우트/페이지 파일은 남김). 헤더 `POS` 버튼(L131-134) 제거.
- **완료조건**: typecheck 0, 좌측 메뉴에 주문/카탈로그 없음, 헤더에 POS 없음.

### T14 · 전체 검증
- **구현**: `cd backend && .venv/bin/python -m pytest`(전부 green, 신규 포함) + `cd apps/web && npm run typecheck`(0).
- **완료조건**: 둘 다 통과. 회귀 0.

## 3. 위험 주석(RISK) 부착 지점 — 실행 시 필수

- **T3/T4/T7/T8 격리 게이트** — `# ⚠️ RISK(side-effect): service-key가 RLS 우회 — 도매는 wholesaler_customers 조인으로 자기 배정분만. 누출/변조 치명 — by customer-management` 를 도매 스코프 필터·`_assert_can_manage` 에 부착.
- **T6 배정** — `# ⚠️ RISK(breaking): wholesaler_id는 scoped_wholesaler_ids 내에서만 — 타 테넌트 도매에 배정 금지`.
- **T8 price-visibility** — `# ⚠️ RISK(breaking): 설정값만 변경, visible_price()/카탈로그 셰이핑 불변 — 우회 금지`.
- **T1 마이그레이션** — DDL, 사용자 실행. 부분 유니크(`WHERE deleted_at IS NULL`) 누락 시 재배정 불가.

## 4. 검증 전략 요약
- 백엔드: 격리(도매↔도매·테넌트) 테스트가 1순위 게이트. assign/unassign/n:m/재배정, enum 400, 스코프 403, 회귀(visible_price·export) 보존.
- 프론트: typecheck 0 + 역할별 화면 수동 확인(도매=자기 고객 / admin=도매+소매·배정 / 메뉴 정리).

---
## 변경이력
<!-- change-history skill auto-appends entries here, oldest first -->

### CH-0001 · 2026-06-20 · [구현계획-수정]
- **이유**: 기술설계(customer-management-tech-design.md) 승인 후 구현계획 최초 작성.
- **무엇이**: `customer-management-implementation-plan.md` 최초 생성 — §1 의존 DAG, §2 작업 T1~T14(마이그레이션·엔티티·서비스(격리)·라우터6·프론트API/컴포넌트/화면2·버튼숨김·검증), §3 RISK 부착지점, §4 검증전략.
- **영향범위**: 없음(최초 생성). 다음 단계 execute-plan 에서 T1부터 구현. T1(DDL)은 사장님 Supabase 실행.

### CH-0002 · 2026-06-20 · [코드-수정] (batch: T1~T14)
- **이유**: 구현계획 실행(인라인, memory-fallback/무커밋 — 사장님 커밋 요청 전).
- **무엇이 (신규)**:
  - `backend/migrations/2026-06-20_v2_core_12_customer_assignment_tier.sql` — `wholesaler_customers`(n:m) + `profiles.tier`. README 갱신(_11·_12).
  - `backend/app/entities/enums.py` `CustomerTier(new|regular)`; `models.py` `Profile.tier` + `WholesalerCustomer`.
  - `backend/app/services/customers.py` — 역할별 스코프 조회/배정/해제/등급·가격노출 + 격리 게이트(`assert_can_manage`).
  - `backend/app/routers/customers.py` — `SupabaseCustomersRepo` + 6 엔드포인트; `main.py` include.
  - `backend/tests/test_customers_service.py`(12) + `test_customers_routes.py`(5).
  - `apps/web/src/lib/products.ts` — `Customer`/`ManagedWholesaler` 타입 + 6 API 함수.
  - `apps/web/src/components/CustomerTable.tsx` — 공용 목록/탭/검색/상세(등급·가격노출·배정).
  - `apps/web/src/app/(dash)/customers/page.tsx`(도매) 교체; `apps/web/src/app/admin/customers/page.tsx`(관리자, 탭) 신규.
- **무엇이 (수정)**: `Shell.tsx`(주문·카탈로그 메뉴 + POS 버튼 제거), `AdminShell.tsx`(고객 관리 메뉴 추가).
- **위험 주석(RISK)**: 도매↔도매 격리(side-effect) — `customers.py` 의 wholesaler 조회 필터·`assert_can_manage`·`_assert_scoped_wholesaler`(breaking). 가격노출은 값 설정만(visible_price 불변).
- **검증**: 백엔드 pytest **222 passed**(기존 205 + 신규 17), 회귀 0. 프론트 `tsc --noEmit` 0, `eslint` 0.
- **잔여(사장님 액션)**: T1 마이그레이션(`_12`)을 Supabase SQL Editor 에서 1회 실행해야 운영 동작. 커밋 미실행(요청 시).

### CH-0003 · 2026-06-20 · [코드-수정] (등급 제외 + 매칭 모델 반전)
- **이유**: 사장님 결정(2026-06-20) — ① 등급 1차 화면 제외 ② 매칭 '배정→취소' 반전.
- **무엇이**:
  - 등급: `CustomerTable`·`page` 에서 등급 컬럼·필터·설정 제거. lib 의 tier API/라벨 제거. (DB 칸·서비스/라우터 `tier`는 잠자는 상태 보존)
  - 매칭 반전: 마이그레이션 테이블 `wholesaler_customers`→`wholesaler_customer_exclusions`(+ §0 옛 테이블 DROP CASCADE), 엔티티 `WholesalerCustomerExclusion`, 서비스 `list_customers`(전체−취소)·`disconnect`/`reconnect`·`assert_can_manage`(취소 격리), 라우터 엔드포인트 `disconnect`/`reconnect`, 테스트 14건 재작성.
  - 프론트: `Customer.excluded_wholesaler_ids`, `ManagedWholesaler.connected_count`, `disconnectCustomer`/`reconnectCustomer`, `CustomerTable` 상세 = 도매별 `연결됨/취소됨` 토글, 컬럼 `연결 도매 수`.
- **검증**: 백엔드 **224 passed**, 프론트 `tsc`/`eslint` 0, 옛 '배정' 명칭 잔재 0.
- **잔여(사장님 액션)**: **마이그레이션(`_12`) 갱신본을 다시 실행** — 옛 테이블+테스트 배정 데이터 자동 정리 + 새 취소 테이블 생성. 재실행 안전(멱등).
