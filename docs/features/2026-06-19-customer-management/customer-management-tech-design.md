# 기술설계: 고객 관리 (Customer Management) — 1차

> **상위 문서**: `customer-management-requirements.md` (PRD). **다음 단계**: `write-plan` (`/write-plan`) 으로 `customer-management-implementation-plan.md` 작성.
> 본 문서는 **기술 설계만** 담는다(아키텍처/데이터모델/API/결정/리스크/테스트). 작업 분해는 다음 단계.

## 0. 핵심 결정 요약 (먼저 읽기)

| # | 결정 | 값 | 근거 |
|---|---|---|---|
| D1 | 소매↔도매 연결 모델 | **기본 전부 연결 + 관리자가 취소(opt-out)** | 사장님 결정 2026-06-20 — 그룹 안 소매는 도매를 다 봄, 취소만 예외 (배정[opt-in]에서 반전) |
| D2 | 취소 저장 구조 | 신규 테이블 `wholesaler_customer_exclusions` | 취소된 (도매,소매) 쌍만 기록. 빈 표 = 전부 연결. `(도매,소매)` 부분 unique |
| D3 | 등급 | **1차 제외(화면 숨김)** — `profiles.tier` 칸은 보존 | 주문 없어 기준·기능 없음. 2차 자동등급으로 부활 (사장님 결정 2026-06-20) |
| D4 | ~~등급 값~~ | (1차 제외) | D3 참조 |
| D5 | 도매관리자 화면 위치 | `/admin/customers` (AdminShell) | admin 은 `(dash)`에서 `/admin`으로 리다이렉트됨 → admin 콘솔에 둠 |
| D6 | 도매 화면 위치 | `/customers` (Shell, 기존 ComingSoon 교체) | 기존 라우트·메뉴 재사용 |
| D7 | 취소/복원 주체 | **도매관리자(admin)만** | 1차 통제. 도매 셀프는 Phase 2 |
| D8 | 가격노출 설정 주체 | admin(테넌트 전체) + 도매(연결된 소매만, 취소분 제외) | 도매가 연결 고객 관리 |
| D9 | (등급의 가격 영향) | 등급 1차 제외 — 가격은 price_visibility/visible_price() 만 | — |

---

## 1. 아키텍처 개요

기존 멀티테넌트 구조(`도매관리자 > 도매업체 > 소매`) 위에 **"소매↔도매 배정" n:m 관계**와 **역할별 스코프 조회/관리 경로**를 얹는다.

```
[프론트]
  도매(wholesaler) → /customers (Shell)            → GET /customers           → 자기 배정 소매만
  도매관리자(admin) → /admin/customers (AdminShell) → GET /customers (admin분기) + GET /customers/wholesalers
                                                     → 테넌트 전체 소매 + 도매업체 목록 + 배정

[백엔드] 신규 라우터 app/routers/customers.py — 한 라우터에서 role 분기 + 스코프 강제
  GET  /customers                      목록(역할별 스코프)
  GET  /customers/wholesalers          도매업체 목록(admin 전용 — 도매 탭 + 배정 드롭다운)
  POST /customers/{uid}/tier           등급 설정(admin 전체 / 도매 자기배정분)
  POST /customers/{uid}/price-visibility  가격노출 설정(admin 전체 / 도매 자기배정분)
  POST /customers/{uid}/assign         배정(admin 전용) {wholesaler_id}
  POST /customers/{uid}/unassign       배정해제(admin 전용) {wholesaler_id}

[DB] 신규 테이블 wholesaler_customers(n:m) + profiles.tier 컬럼
```

**스코프 강제(앱레이어 책임)** — service-key 가 RLS 를 우회하므로 모든 조회/쓰기에서 **뷰어 역할로 직접 필터**한다([[wholesaler-image-isolation]] 동일 클래스):
- admin → `manager_id`(테넌트) 스코프. 도매업체 = `scoped_wholesaler_ids(manager_id)`. 소매 = 테넌트 소속 소매.
- wholesaler → `wholesaler_customers.wholesaler_id == viewer.wholesaler_id` 인 소매만. 다른 도매 고객 접근 시 404/403.

## 2. 영향 받는 컴포넌트

### 신규
- `backend/migrations/2026-06-20_v2_core_11_customer_assignment_tier.sql` — `wholesaler_customers` 테이블 + `profiles.tier` 컬럼. (※ 일련번호 `_11` 은 실행 전 `backend/migrations/` 최신번호 확인 후 확정)
- `backend/app/routers/customers.py` — 신규 라우터(위 6 엔드포인트). `app/main.py` 에 include.
- `apps/web/src/app/(dash)/customers/page.tsx` — ComingSoon 교체(도매용 화면).
- `apps/web/src/app/admin/customers/page.tsx` — 신규(도매관리자용 화면, 탭).
- `apps/web/src/components/CustomerTable.tsx` (가칭) — 두 화면 공용 소매 테이블/상세.

### 수정
- `backend/app/entities/models.py` — `Profile.tier` 필드 추가, `WholesalerCustomer` 엔티티 신규.
- `backend/app/entities/enums.py` — `CustomerTier(new|regular)` 추가.
- `backend/app/schemas/` — `Customer` 응답 DTO(= Account + tier + assigned_wholesalers).
- `backend/app/services/tenancy.py` 또는 신규 `services/customers.py` — 배정/스코프 헬퍼.
- `apps/web/src/components/Shell.tsx` — NAV 에서 `주문 관리`·`카탈로그 관리` 제거(L24-30), 헤더 `POS` 버튼 제거(L131-134).
- `apps/web/src/components/AdminShell.tsx` — `고객 관리`(`/admin/customers`) 메뉴 추가.
- `apps/web/src/lib/products.ts` — `Customer` 타입 + API 함수(listCustomers/listWholesalers/assign/unassign/setTier/setPriceVisibility).

### 재사용(수정 없음)
- `services/tenancy.py:scoped_wholesaler_ids()`, `admin.py:list_approved_for_manager()`, `shape_account_rows()` — 셰이핑/스코프.
- `core/auth.py:get_current_user` + `_resolve_manager_id()` — CurrentUser(`role`,`manager_id`,`wholesaler_id`).
- `core/rbac.py:require_role` — 가드.
- 프론트 `admin/page.tsx` 탭/테이블 패턴, `ui`(Card/Badge/Button/Spinner), `lib/api.ts:api()`.

## 3. 데이터 모델

### 3.1 신규 테이블 `wholesaler_customers` (n:m 배정)

```sql
CREATE TABLE public.wholesaler_customers (
  id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  wholesaler_id UUID NOT NULL REFERENCES public.wholesalers(id) ON DELETE CASCADE,
  customer_id   UUID NOT NULL REFERENCES public.profiles(id)    ON DELETE CASCADE,
  created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
  created_by    UUID REFERENCES public.profiles(id),
  deleted_at    TIMESTAMPTZ            -- soft delete
);
-- 살아있는 배정은 (도매,소매) 1쌍만 (soft delete 후 재배정 허용)
CREATE UNIQUE INDEX uq_wholesaler_customers_alive
  ON public.wholesaler_customers (wholesaler_id, customer_id) WHERE deleted_at IS NULL;
CREATE INDEX idx_wc_wholesaler ON public.wholesaler_customers (wholesaler_id) WHERE deleted_at IS NULL;
CREATE INDEX idx_wc_customer   ON public.wholesaler_customers (customer_id)   WHERE deleted_at IS NULL;
```
- soft delete 규칙 준수(hard delete 금지, 조회는 `deleted_at IS NULL`). `ON DELETE CASCADE` 는 하드삭제 비상망.
- soft-cascade: 도매/소매가 soft delete 되면 배정도 정리되는 게 이상적 — 1차는 **조회 시 양쪽 살아있음 필터**로 충분(트리거는 Phase 2 선택). 

### 3.2 `profiles.tier` 컬럼

```sql
ALTER TABLE public.profiles
  ADD COLUMN IF NOT EXISTS tier TEXT CHECK (tier IN ('new','regular'));
CREATE INDEX IF NOT EXISTS idx_profiles_tier ON public.profiles (tier) WHERE deleted_at IS NULL;
```
- nullable. **null = 신규(new) 로 취급**(백필 불필요). 값 = `new`(신규)/`regular`(일반).
- **소매당 1개**(도매 공유) — D3. 도매별 차등 등급은 Phase 2(필요 시 `wholesaler_customers.tier` 로 이동).

### 3.3 엔티티/DTO
- `Profile.tier: str | None` 추가. `CustomerTier(str,Enum){new,regular}` 신규.
- `WholesalerCustomer` 엔티티(테이블 1:1).
- 응답 `Customer` = 기존 Account 필드 + `tier` + `assigned_wholesalers: [{id,name}]`(admin 뷰의 `소속 도매` 컬럼용; 도매 뷰는 자기 자신이라 생략 가능).

## 4. 외부 인터페이스 (API)

공통: `Depends(get_current_user)`. 응답 가격 관련은 **셰이핑 우회 금지**(가격노출은 기존 `visible_price()`/price_visibility 모델 그대로, 본 기능은 노출 *설정*만 건드림).

| 메서드·경로 | 권한 | 동작 | 스코프 강제 |
|---|---|---|---|
| `GET /customers` | admin / wholesaler | 소매 목록 | admin=테넌트 전체 소매 / wholesaler=`wc.wholesaler_id==viewer.wholesaler_id` |
| `GET /customers/wholesalers` | admin | 테넌트 도매업체 목록(+배정 소매 수) | `scoped_wholesaler_ids(manager_id)` |
| `POST /customers/{uid}/tier` | admin / wholesaler | `{tier:new\|regular}` 설정 | admin=테넌트 내 / wholesaler=해당 uid 가 자기 배정분일 때만, 아니면 403 |
| `POST /customers/{uid}/price-visibility` | admin / wholesaler | `{price_visibility:wholesale\|retail\|none}` | 동일 스코프 강제. 검증은 기존 admin 엔드포인트 로직 재사용 |
| `POST /customers/{uid}/assign` | **admin only** | `{wholesaler_id}` → wc 행 upsert(살아있는 중복 무시) | wholesaler_id 가 `scoped_wholesaler_ids` 에 속해야 함 |
| `POST /customers/{uid}/unassign` | **admin only** | `{wholesaler_id}` → wc 행 soft delete | 동일 |

- 기존 `POST /admin/accounts/{uid}/price-visibility`(admin.py:284) 는 **유지**(admin UI 호환). 신규 `/customers/...` 는 도매도 쓸 수 있는 스코프판. 프론트 고객관리는 `/customers/...` 사용.
- 에러: 스코프 위반 = 403, 없는 uid = 404, 잘못된 enum = 400. (기존 패턴)

## 5. 핵심 결정 (대안 비교)

- **D1/D2 n:m 연결표** — (택) `wholesaler_customers`. 대안: profiles 단일컬럼(1:1) = 사장님 요구(여러 도매) 불충족. 대안: 배열컬럼 = 조회/격리/유니크 어려움. → 조인테이블이 표준.
- **D3 등급=소매 속성(profiles.tier)** — (택) price_visibility 와 같은 레벨이라 일관, 구현 단순. 대안: `wholesaler_customers.tier`(도매별 차등) = 더 정확하나 admin 전체뷰에서 한 소매가 여러 등급 → UI 복잡. 1차 보류, Phase 2 이전 경로 명시. **트레이드오프: 같은 소매를 여러 도매가 보면 등급이 공유됨(last-write-wins)** — 1차 허용.
- **D5/D6 화면 2곳** — (택) admin=`/admin/customers`, 도매=`/customers`. 대안: `/customers` 하나를 admin 도 통과시키게 WholesalerGate 변경 = 기존 리다이렉트(admin→/admin) 흐름을 깨고 회귀위험. → 콘솔별 분리 + 공용 컴포넌트.
- **D7 배정 admin 전용** — (택) 1차 통제 단순. 대안: 도매 셀프배정 = 권한·악용 고려 필요 → Phase 2.
- **D8 도매도 등급/가격노출 설정** — (택) "도매가 자기 고객 관리" 요구 충족. 단 **스코프 강제가 보안 핵심**(아래 리스크). 대안: 도매 read-only = 더 안전하지만 요구 미충족.

## 6. 예비 리스크

- ⚠️ **도매↔도매 격리(최우선).** `GET /customers` 및 `tier`/`price-visibility` 쓰기에서 wholesaler 가 **자기 배정분이 아닌 소매**를 보거나 수정하면 치명적 누출/변조. service-key 가 RLS 우회 → **앱레이어에서 `wholesaler_customers` 조인으로 명시 검증**. 테스트로 못박기([[wholesaler-image-isolation]] 전례).
- ⚠️ **테넌트 격리.** admin 조회는 반드시 `manager_id` 스코프. 미스코프 시 타 테넌트 노출.
- ⚠️ **가격노출 서버 권위 유지.** 본 기능은 price_visibility *값 설정*만. `visible_price()`·카탈로그/엑셀 셰이핑 로직은 **건드리지 않음**. 등급은 가격에 영향 0(D9).
- ⚠️ **마이그레이션은 DDL** → 사장님이 Supabase SQL Editor 에서 실행. 일련번호/실행순서 README 갱신.
- soft delete/부분 유니크 준수 — 재배정(해제 후 재배정) 정상 동작 확인.
- WholesalerGate/AdminShell 라우팅 회귀 — admin 이 `/customers`(도매용) 로 새지 않게, 도매가 `/admin/customers` 못 보게.

## 7. 테스트 전략

**백엔드 (pytest, `backend/tests/`)**
- 격리: wholesaler A 가 `GET /customers` 시 자기 배정 소매만(타 도매 배정분 0건). A 가 B의 소매 `tier`/`price-visibility` POST → 403.
- admin: 테넌트 전체 소매 + 도매업체 목록. 타 테넌트 0건.
- 배정: assign → `GET /customers`(도매) 에 반영. unassign → 사라짐. n:m: 한 소매를 A·B 에 배정 시 둘 다 조회됨. 해제 후 재배정(soft delete 재사용) 정상.
- tier/price-visibility enum 검증(400), 없는 uid(404).
- 회귀: 기존 `/admin/accounts`·`visible_price`·카탈로그 export 영향 없음.

**프론트 (typecheck + 수동)**
- `npm run typecheck` 0. 도매 화면=자기 고객만, admin 화면=탭(도매업체/소매)+배정. 메뉴에서 주문/카탈로그/POS 사라짐.

---
## 변경이력
<!-- change-history skill auto-appends entries here, oldest first -->

### CH-0001 · 2026-06-20 · [개발방향-수정]
- **이유**: PRD(customer-management-requirements.md) 승인 후 기술설계 최초 작성. 코드베이스 정밀 조사 + 사장님 결정 반영.
- **무엇이**: `customer-management-tech-design.md` 최초 생성 — §0 결정요약(D1~D9), §1 아키텍처, §2 영향 컴포넌트, §3 데이터모델(`wholesaler_customers` n:m + `profiles.tier`), §4 API(6 엔드포인트), §5 결정/대안, §6 리스크, §7 테스트.
- **반영된 사장님 결정**: 배정 카디널리티 = **n:m(연결표)**; 등급 = **소매당 1개(도매 공유)**; 화면 2곳(도매 `/customers`·관리자 `/admin/customers`).
- **영향범위**: 요구사항 FR-2b 의 "데이터 구조는 기술설계에서 확정" → 본 문서에서 n:m 연결표로 확정. 다음 단계 write-plan 에서 작업 분해.

### CH-0002 · 2026-06-20 · [개발방향-수정]
- **이유**: 사장님 결정 2건(2026-06-20) — 등급 1차 제외 + 매칭 모델 반전(배정→취소). 코드 = 단일 진실(본 문서 §0 표 갱신, 본문 일부는 옛 '배정' 서술 잔존 — §0 표·변경이력 우선).
- **무엇이**:
  - **D1/D2 반전**: `wholesaler_customers`(배정·n:m) → **`wholesaler_customer_exclusions`(취소)**. 기본 전부 연결, 취소된 쌍만 기록. 빈 표 = 전부 연결.
  - **D3/D4 등급 1차 제외**: `profiles.tier` 칸·엔드포인트는 잠자는 상태로 보존(2차 자동등급).
  - **§4 API**: `assign`/`unassign` → **`disconnect`/`reconnect`**. `tier` 엔드포인트는 잠자는 상태 유지.
  - **마이그레이션 §0**: 옛 `wholesaler_customers` 테이블 `DROP ... CASCADE`(테스트 잔재 정리).
- **영향범위**: 백엔드(엔티티/서비스/라우터/마이그레이션/테스트)·프론트(타입/CustomerTable/페이지) 전면 반영 완료. 백엔드 224 passed, 프론트 tsc/eslint 0.
