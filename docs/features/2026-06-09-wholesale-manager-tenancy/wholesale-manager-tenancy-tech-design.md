# 기술설계: 도매관리자 멀티테넌트 1차 재편

> **상위 문서**: [`wholesale-manager-tenancy-requirements.md`](./wholesale-manager-tenancy-requirements.md) (PRD, CH-20260609-001).
> **다음 단계**: 이 문서를 입력으로 `writing-plans`(`/write-plan`)가 `wholesale-manager-tenancy-implementation-plan.md`(단계별 TDD 구현계획)를 작성한다.
> 범위: 1차 = 단일 테넌트 LALAS. forward-compat(테넌트 N개·도매상↔관리자 n:m) 1순위. **1차 동작 결과는 기존과 동일해야 함(회귀 금지).** 과설계(RLS 전환·에이전시 실운영·둘째 테넌트 UI) 제외.

---

## 1. 아키텍처 개요

### 테넌트 스코프 강제 위치 — 앱레이어(쿼리 필터)

현재 시스템은 service-key 단일 클라이언트(`app/core/supabase.py`)로 PostgREST에 접속하며, RLS는 정의돼 있으나 service_role이 우회하므로 **격리는 전적으로 앱레이어 책임**이다(NFR-3). 기존에 이미 동일 패턴이 자리잡혀 있다:

- `products.py` `SupabaseProductRepo(owner_wid=...)` — `.eq("wholesaler_id", owner_wid)`로 IDOR 차단 (products.py:98-99, 107-108).
- `admin.py` — `require_role("admin")` 후 service-key로 전역 조회.

테넌트 스코프도 **같은 레이어(라우터/리포지토리의 쿼리 필터)** 에 끼운다. 미들웨어 방식은 채택하지 않는다(이유: §6-c). 핵심은 "스코프 키를 `CurrentUser`에 한 번 실어두고, 데이터를 만지는 모든 조회가 그 키로 필터를 건다"이다.

### 스코프 키 = `manager_id` (테넌트 식별자)

- **도매상(wholesaler)**: `manager_wholesalers` 연결표 → 자신이 소속된 `manager_id`.
- **셀러(retail_seller)**: `profiles.manager_id` → 자신이 연계된 도매관리자.
- **admin(대표 관리자)**: `profiles.manager_id` → 자기 테넌트(자기 도매연합).

`CurrentUser.manager_id`를 `auth.py`의 프로필 조회 시점에 1회 해석(resolve)해 적재한다(§3.2).

### 데이터 흐름 (1차, LALAS 단일)

```
셀러 로그인 → CurrentUser.manager_id = (profiles.manager_id = LALAS)
  GET /catalog        → products where wholesaler_id IN (manager_wholesalers of LALAS)
  GET /p/{code}       → 위 동일 스코프 + platform_code 단건
도매 로그인 → CurrentUser.manager_id = (manager_wholesalers → LALAS), wholesaler_id = 본인 업체
  GET /products       → 기존대로 본인 wholesaler_id 만 (FR-6, 변경 없음)
admin 로그인 → CurrentUser.manager_id = (profiles.manager_id = LALAS)
  GET /admin/accounts → 자기 테넌트의 도매/셀러만 (FR-7)
  GET /admin/products → 소속 도매 합산 (FR-5, 행마다 wholesaler 이름)
```

> **1차 불변식**: LALAS가 유일 테넌트이고 **모든 기존 wholesaler/seller가 LALAS에 backfill**되므로, `wholesaler_id IN (LALAS 소속 전체)` = `현존 전체 도매상` → **카탈로그 결과가 기존 "전체 노출"과 동일**(NFR-1 회귀 안전). 둘째 테넌트가 생기는 순간에만 결과가 갈라진다(스키마 변경 없음).

---

## 2. 데이터 모델

### 2.1 신규 테이블 / 컬럼

| 객체 | 형태 | 목적 |
|---|---|---|
| `wholesale_managers` | 테이블(테넌트 엔티티) | 도매관리자(도매연합). 1차 = LALAS 1행 |
| `manager_wholesalers` | 연결표 | 도매상↔관리자 소속. 단일 `manager_id` 칸 금지(NFR-2), n:m 대비 |
| `profiles.manager_id` | 컬럼(FK) | 셀러→관리자 연계 + admin→자기 테넌트 매핑 |

설계 결정 요약(상세 §6):
- **셀러→관리자**: `profiles.manager_id` 단일 FK **채택**(연결표 아님). 셀러는 1차·중기 모두 관리자 1개에만 연계(PRD: 셀러↔관리자 1:1 연계). admin도 같은 칸 재사용(§6-d).
- **도매상↔관리자**: `manager_wholesalers` 연결표 **채택**. PRD가 명시적으로 단일 칸 금지. 1차 1:n은 "도매상당 살아있는 행 1개"를 **부분 unique 인덱스**로 강제(§6-b).

### 2.2 기존 테이블과의 관계

- `wholesalers` / `products` / `product_skus` 는 **건드리지 않는다**. 상품 스코프는 항상 `products.wholesaler_id`를 통해, `manager_wholesalers`를 한 단계 거쳐 해석한다(상품 자체에 manager_id 비정규화 안 함 → 재소속 시 일관성 깨질 위험 제거).
- `visible_price()`는 `viewer_org = user.wholesaler_id` / `product_org = products.wholesaler_id`로 동작 — 테넌트 도입과 **무관**(FR-8 불변). 시그니처 변경 없음(§3.6).

### 2.3 마이그레이션 파일 (실행 가능, 1파일)

파일명: `backend/migrations/2026-06-09_v2_core_10_wholesale_manager_tenancy.sql`
실행: **사용자가 Supabase SQL Editor에서 직접 실행**(DDL, 앱 미실행). `_09` 다음 순번. README/마이그레이션 표에 10번 항목 추가 필요(§7).

컨벤션 반영: `_v2_core`의 테이블 스타일(UUID PK, `gen_random_uuid()`, `created_at DEFAULT now()`), `_03`의 `deleted_at`·부분 unique(`WHERE deleted_at IS NULL`)·soft-cascade 트리거, `_04`의 `updated_at`+트리거 재사용 / `created_by`·`updated_by` FK, `_07`/`_09`의 멱등(`IF NOT EXISTS`)·부분 인덱스 패턴.

> ⚠️ **구현 시 확정 필요**: `_04`의 updated_at 트리거 함수 실제 이름과 `_03`의 soft-cascade 함수 패턴을 마이그레이션 파일에서 직접 확인해 정확히 재사용할 것(아래 SQL은 `set_updated_at`/`soft_cascade_*` 관례명을 가정). 시드 UUID(`1a1a0000-…-a1a5`)는 backfill이 같은 파일에서 참조하기 위한 **고정 유효-hex UUID** — 임의 교체 가능하나 파일 내 일관 유지.

```sql
-- ezmerce v2 — _10 도매관리자(도매연합) 멀티테넌트 1차 재편
-- 테넌트 엔티티(wholesale_managers) + 도매상 소속 연결표(manager_wholesalers)
--   + 셀러/admin → 관리자 연계(profiles.manager_id).
-- 격리는 앱레이어 스코프(service-key 일관). RLS 전환은 범위 밖 — 새 테이블도 정책은 기본 deny 최소만.
-- 컨벤션: _03(soft delete/부분 unique/soft-cascade), _04(audit/updated_at 트리거) 준수.
-- 실행 순서: _09 다음. Supabase SQL Editor 직접 실행(DDL). 멱등 지향(IF NOT EXISTS) — 재실행 안전.

-- ── 1) 테넌트 엔티티 ───────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS public.wholesale_managers (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name        TEXT NOT NULL,
    biz_number  TEXT,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    created_by  UUID REFERENCES public.profiles(id) ON DELETE SET NULL,
    updated_by  UUID REFERENCES public.profiles(id) ON DELETE SET NULL,
    deleted_at  TIMESTAMPTZ
);

-- ── 2) 도매상 ↔ 관리자 소속 연결표 (단일 manager_id 칸 금지 — n:m forward-compat) ──
CREATE TABLE IF NOT EXISTS public.manager_wholesalers (
    id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    manager_id    UUID NOT NULL REFERENCES public.wholesale_managers(id) ON DELETE CASCADE,
    wholesaler_id UUID NOT NULL REFERENCES public.wholesalers(id)        ON DELETE CASCADE,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    created_by    UUID REFERENCES public.profiles(id) ON DELETE SET NULL,
    updated_by    UUID REFERENCES public.profiles(id) ON DELETE SET NULL,
    deleted_at    TIMESTAMPTZ
);

-- 1:n 강제 — 1차엔 도매상당 (살아있는) 소속 1행만. 같은 도매상 중복 소속 차단.
-- n:m 로 풀 때 이 부분 unique 만 드롭하면 됨(스키마 변경 최소). _09 의 부분 unique 패턴과 동형.
CREATE UNIQUE INDEX IF NOT EXISTS manager_wholesalers_wid_alive
  ON public.manager_wholesalers (wholesaler_id) WHERE deleted_at IS NULL;
-- (manager, wholesaler) 살아있는 쌍 중복 방지 + 조회 가속
CREATE UNIQUE INDEX IF NOT EXISTS manager_wholesalers_pair_alive
  ON public.manager_wholesalers (manager_id, wholesaler_id) WHERE deleted_at IS NULL;
CREATE INDEX IF NOT EXISTS idx_manager_wholesalers_manager
  ON public.manager_wholesalers (manager_id) WHERE deleted_at IS NULL;

-- ── 3) 셀러/admin → 관리자 연계 (단일 FK; 셀러는 관리자 1개 연계, admin 은 자기 테넌트) ──
ALTER TABLE public.profiles
  ADD COLUMN IF NOT EXISTS manager_id UUID REFERENCES public.wholesale_managers(id) ON DELETE SET NULL;
CREATE INDEX IF NOT EXISTS idx_profiles_manager ON public.profiles (manager_id);

-- ── 4) audit: updated_at 자동 갱신 트리거 (_04 패턴 재사용 — 함수명 _04 확인 후 일치) ──
DROP TRIGGER IF EXISTS trg_set_updated_at_wholesale_managers ON public.wholesale_managers;
CREATE TRIGGER trg_set_updated_at_wholesale_managers
  BEFORE UPDATE ON public.wholesale_managers FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();
DROP TRIGGER IF EXISTS trg_set_updated_at_manager_wholesalers ON public.manager_wholesalers;
CREATE TRIGGER trg_set_updated_at_manager_wholesalers
  BEFORE UPDATE ON public.manager_wholesalers FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();

-- ── 5) soft-cascade: 테넌트 soft-delete 시 소속 연결행 전파 (_03 패턴) ──
CREATE OR REPLACE FUNCTION public.soft_cascade_manager() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
  IF NEW.deleted_at IS NOT NULL AND OLD.deleted_at IS NULL THEN
    UPDATE public.manager_wholesalers SET deleted_at = NEW.deleted_at
      WHERE manager_id = NEW.id AND deleted_at IS NULL;
  END IF;
  RETURN NEW;
END $$;
DROP TRIGGER IF EXISTS trg_soft_cascade_manager ON public.wholesale_managers;
CREATE TRIGGER trg_soft_cascade_manager
  AFTER UPDATE OF deleted_at ON public.wholesale_managers
  FOR EACH ROW EXECUTE FUNCTION public.soft_cascade_manager();

-- ── 6) RLS (방어선 최소 — service-key 우회, 기본 deny. RLS 전환은 범위 밖) ──
ALTER TABLE public.wholesale_managers ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.manager_wholesalers ENABLE ROW LEVEL SECURITY;
-- (정책 미추가 = 기본 deny. 앱은 service_role 로 우회. anon/authenticated 직접 접근 차단)

-- ── 7) LALAS 시드 + 기존 단일 admin 연결 ──
--   대표 admin = 기존 단일 admin 계정(이미 존재). id = f50945ce-0fec-4241-96ed-29e3dc97bade
--   고정 시드 UUID(유효 hex): 1a1a0000-0000-0000-0000-00000000a1a5
INSERT INTO public.wholesale_managers (id, name, created_by)
VALUES (
  '1a1a0000-0000-0000-0000-00000000a1a5'::uuid,
  'LALAS',
  'f50945ce-0fec-4241-96ed-29e3dc97bade'
)
ON CONFLICT (id) DO NOTHING;

-- 대표 admin → LALAS 테넌트 매핑
UPDATE public.profiles
  SET manager_id = '1a1a0000-0000-0000-0000-00000000a1a5'::uuid
  WHERE id = 'f50945ce-0fec-4241-96ed-29e3dc97bade';

-- ── 8) backfill: 기존 도매상 전부 LALAS 소속으로, 기존 셀러 전부 LALAS 연계로 ──
--   (1차 회귀 안전 핵심 — 기존 '전체 노출' 결과를 스코프 도입 후에도 동일하게 유지)
INSERT INTO public.manager_wholesalers (manager_id, wholesaler_id, created_by)
SELECT '1a1a0000-0000-0000-0000-00000000a1a5'::uuid, w.id,
       'f50945ce-0fec-4241-96ed-29e3dc97bade'
  FROM public.wholesalers w
 WHERE w.deleted_at IS NULL
   AND NOT EXISTS (
     SELECT 1 FROM public.manager_wholesalers mw
      WHERE mw.wholesaler_id = w.id AND mw.deleted_at IS NULL
   );

UPDATE public.profiles
   SET manager_id = '1a1a0000-0000-0000-0000-00000000a1a5'::uuid
 WHERE role = 'retail_seller' AND deleted_at IS NULL AND manager_id IS NULL;
```

> `wholesale_managers.created_by`가 `profiles(id)` FK라 admin 프로필이 먼저 존재해야 한다 — 기존 admin은 이미 존재하므로 안전.

---

## 3. 백엔드 변경 지점

### 3.1 `app/entities/models.py` (ENUM 불필요)

신규 ENUM 없음(`enums.py` 무변경 — 테넌트는 엔티티지 enum 아님). 모델 2종 추가 + `Profile`에 1칸:

```python
class WholesaleManager(_Entity):
    id: str
    name: str
    biz_number: str | None = None
    # + 공통 감사/생명주기 컬럼(created_at/updated_at/created_by/updated_by/deleted_at)

class ManagerWholesaler(_Entity):
    id: str
    manager_id: str
    wholesaler_id: str
    # + 공통 감사/생명주기 컬럼

class Profile(_Entity):
    ...
    manager_id: str | None = None   # 셀러→관리자 연계 / admin→자기 테넌트 (신규)
```

### 3.2 `app/schemas/auth.py` + `app/core/auth.py` — CurrentUser에 `manager_id` 주입

`CurrentUser`에 `manager_id: str | None = None` 추가. 단, **`profiles.manager_id`는 셀러/admin에만 채워지고 도매상은 `manager_wholesalers`에 있다** → `auth.py`에서 역할별 resolve가 필요하다. 현재 `get_current_user`/`get_current_user_optional`는 `CurrentUser(**{k: row.get(k) ...})`로 평면 매핑만 한다(auth.py:56, 82) → 도매상 manager_id는 이 매핑으로 안 채워짐.

해결: 평면 매핑 직전 도매상이면 1쿼리로 보강하는 헬퍼를 추가.

```python
def _resolve_manager_id(sb, row: dict) -> str | None:
    # 셀러/admin: profiles.manager_id 직접. 도매상: manager_wholesalers 1:n(1차 1행) 에서 해석.
    if row.get("manager_id"):
        return row["manager_id"]
    if row.get("role") == "wholesaler" and row.get("wholesaler_id"):
        link = sb.table("manager_wholesalers").select("manager_id").eq(
            "wholesaler_id", row["wholesaler_id"]).is_("deleted_at", "null").limit(1).execute().data
        return link[0]["manager_id"] if link else None
    return None
```

두 의존성(`get_current_user`, `get_current_user_optional`)에서 `CurrentUser` 생성 직전에 `row["manager_id"] = _resolve_manager_id(sb, row)`로 덮어쓴 뒤 매핑. **시그니처 변경 없음**(반환형 그대로 `CurrentUser`). 비용: 도매상 로그인당 +1 쿼리(인덱스 `manager_wholesalers_wid_alive` 직격, 무시 가능).

### 3.3 `app/routers/catalog.py` — 카탈로그 스코핑 (FR-4, 회귀 주의)

스코프를 `_query_catalog_rows`에 주입한다. PostgREST는 부분쿼리 IN을 직접 못 받으므로 **2-step**: ① 뷰어의 `manager_id`로 소속 도매상 id 목록을 먼저 조회 → ② `.in_("wholesaler_id", ids)`.

```python
def _scoped_wholesaler_ids(sb, manager_id: str | None) -> list[str]:
    # 셀러가 연계된 도매관리자에 소속된 도매상 id. manager_id 없으면 [] (=빈 스코프, fail-closed).
    if not manager_id:
        return []
    rows = sb.table("manager_wholesalers").select("wholesaler_id").eq(
        "manager_id", manager_id).is_("deleted_at", "null").execute().data or []
    return [r["wholesaler_id"] for r in rows]

def _query_catalog_rows(sb, limit, cursor=None, wholesaler_ids: list[str] | None = None):
    q = sb.table("products").select(...).eq("status","active").is_("deleted_at","null")...
    if wholesaler_ids is not None:
        q = q.in_("wholesaler_id", wholesaler_ids)   # [] → 빈 결과(연계 없는 셀러는 아무것도 못 봄)
    ...
```

`list_catalog`/`export_catalog`에서 `ids = _scoped_wholesaler_ids(sb, user.manager_id)` 후 전달. export rows 쿼리도 동일 인자.

- **회귀 안전**: 1차엔 LALAS 소속 = 전체 도매상이라 `in_(전체 id)` = 무필터와 동일 결과.
- **빈 스코프 경계**: backfill로 모든 기존 셀러는 `manager_id`를 갖지만, 혹시 누락 시 `[]` → 빈 카탈로그(과노출보다 안전한 fail-closed). admin 직접 카탈로그 호출 시 admin도 `manager_id` 보유 → 자기 테넌트 스코프.
- `shape_catalog_item`/`shape_owner_product`/`visible_price` **무변경**(가격 셰이핑 불변, FR-8) → `test_catalog_shaping`/`test_pricing` 그대로 통과.

### 3.4 `app/routers/public.py` — 공개카드 스코핑 (FR-4)

`product_card`는 ① 비로그인 = 공개 최소 응답(가격 없음), ② 로그인 셀러 = 스코프 내에서만 skus 노출. 현재 단건 조회에 뷰어가 로그인+승인이고 `manager_id`가 있을 때 **해당 상품의 `wholesaler_id`가 뷰어 스코프에 속하는지 검사**를 추가:

```python
row = res.data ...
if not row: raise HTTPException(404, "not found")
card = { ...공개 최소... }   # 비로그인/미승인은 여기까지 (변경 없음)
if viewer and viewer.status == "approved":
    ids = _scoped_wholesaler_ids(sb, viewer.manager_id)   # 공용 tenancy 헬퍼 재사용
    if row["wholesaler_id"] in ids:
        card["skus"] = shape_card_skus(row, viewer)
    # 스코프 밖이면 skus 미부여(가격/재고 없이 공개 카드만) — 404 아님, 카드 자체는 공개 링크
```

- 1차 회귀: LALAS 셀러 + LALAS 도매상 상품 → 항상 스코프 내 → 기존과 동일하게 skus 노출.
- `_scoped_wholesaler_ids`는 공용 모듈(`app/services/tenancy.py` 신설)로 빼서 `catalog.py`/`public.py`가 공유(중복 방지).

### 3.5 `app/routers/admin.py` + `app/services/accounts.py` — 테넌트 스코프 승인 (FR-7)

**list 스코프**: `SupabaseAdminRepo.list_by_status`는 현재 `status`만 필터(admin.py:35-37). admin의 `manager_id`로 자기 테넌트만 보이게 한다. 단 셀러는 `profiles.manager_id`로 직접 필터되지만 **pending 신규 가입자는 아직 manager_id가 없다**(자가가입 시 미설정).

1차 단일 테넌트에선 "manager_id IS NULL(미배정 신규) OR manager_id = 내 테넌트"를 함께 본다(미배정분을 유일 테넌트가 흡수). 도매 pending도 아직 `manager_wholesalers` 없음 → 동일 규칙.

```python
def list_by_status(self, status, manager_id):
    q = self.sb.table("profiles").select("*").eq("status", status).is_("deleted_at","null")
    # 1차: 자기 테넌트 + 미배정(신규 가입) 을 함께. (둘째 테넌트 등장 시 라우팅 규칙 정교화 — 범위 밖)
    q = q.or_(f"manager_id.eq.{manager_id},manager_id.is.null")
    return q.order("created_at", desc=True).execute().data or []
```

`list_accounts`에서 `repo.list_by_status(status, user.manager_id)`로 전달.

**approve 스코프 + 자동 연결 보상 패턴 유지**: `approve_account`(accounts.py:24-42)의 도매 자동 wholesaler 생성·보상(A-4)을 **그대로 유지**하되, 승인 시 **테넌트 연결**을 추가한다:

- 도매 승인: wholesaler 생성 → `set_status`로 `wholesaler_id` 연결 → **`manager_wholesalers` 행 생성**(승인한 admin의 `manager_id`로).
- 셀러 승인: `profiles.manager_id`를 admin의 `manager_id`로 설정.

보상 체인 확장(현 A-4 패턴 연장): wholesaler 생성 성공 → `set_status` 성공 → `link_wholesaler_to_manager` 실패 시 **방금 만든 wholesaler를 soft-delete**(고아 방지). `approve_account` 시그니처에 `admin_manager_id: str` 인자를 추가하고, `admin.py`의 `approve`에서 `user.manager_id` 전달.

```python
def approve_account(repo, target_id, admin_id, admin_manager_id):
    prof = repo.get_profile(target_id)
    wholesaler_id = None
    if prof.role == "wholesaler" and not prof.wholesaler_id:
        wholesaler_id = repo.create_wholesaler(name)["id"]
    try:
        result = repo.set_status(target_id, "approved", admin_id,
                                 wholesaler_id=wholesaler_id,
                                 manager_id=(admin_manager_id if prof.role=="retail_seller" else None))
        if prof.role == "wholesaler":
            wid = wholesaler_id or prof.wholesaler_id
            repo.link_wholesaler_to_manager(wid, admin_manager_id, by=admin_id)  # 멱등(이미 있으면 skip)
        return result
    except Exception:
        if wholesaler_id is not None:
            repo.soft_delete_wholesaler(wholesaler_id)   # 보상(A-4 연장)
        raise
```

`set_status`에 `manager_id` 인자 추가(셀러일 때만 patch에 포함). `link_wholesaler_to_manager`는 `manager_wholesalers`에 멱등 insert(부분 unique 충돌 시 무시 — 재승인 안전). `reject_account` 무변경.

### 3.6 `app/services/pricing.py` — 손대지 않음 (FR-8)

`visible_price`/`visible_price_columns` 시그니처·로직 **변경 없음**. `viewer_org`/`product_org`는 여전히 `wholesaler_id` 기준이며 테넌트와 무관. 호출부(`catalog`/`public`/`products`)도 인자 전달 동일 → `test_pricing` 영향 없음. (점검 결과: manager_id가 가격 결정에 끼어들 여지 없음 — 확인 완료.)

### 3.7 `app/routers/products.py` — FR-6 유지 + FR-5 합산 조회 신설

- **FR-6(단일 도매업체)**: 기존 `/products` 전부 **무변경**. `SupabaseProductRepo(owner_wid=user.wholesaler_id)`로 본인 상품만(products.py:107-108). 회귀 없음.
- **FR-5(합산 상품관리)**: 도매관리자용 신규 조회. **별도 엔드포인트**(admin 전용, 스코프·권한이 도매 본인용과 다름). `admin.py`에 `GET /admin/products` 추가가 자연스럽다(admin 콘솔 소속).

```python
# admin.py — 소속 도매 합산 상품관리 (행마다 도매 출처)
@router.get("/products")
def admin_products(user, limit=30, offset=0, search=None, status=None):
    _admin(user)
    sb = get_supabase()
    ids = _scoped_wholesaler_ids(sb, user.manager_id)          # 자기 테넌트 소속 도매 전체
    if not ids: return {"items": [], "total": 0, "limit": limit, "offset": offset}
    q = sb.table("products").select(
        "id,platform_code,source_p_number,item_name,category,status,is_sold_out,created_at,"
        "wholesaler_id,representative_image_url,"
        "wholesalers(name),"                                    # ← 도매 출처 이름 join (FR-5)
        "product_skus(color,size,wholesale_price,retail_price,stock,deleted_at)",
        count="exact"
    ).in_("wholesaler_id", ids).is_("deleted_at","null").is_("product_skus.deleted_at","null")
    ... 필터/페이지네이션(range) ...
    # 가격: admin 역할 → visible_price 가 {wholesale_price, retail_price} 둘 다 반환(기존 규칙)
```

셰이핑은 `shape_owner_product`를 재사용하되 `wholesaler_name`(`row["wholesalers"]["name"]`)을 추가하는 `shape_admin_product(row)` 신설. 가격은 `visible_price("admin", ...)` 통과(FR-8).

---

## 4. API 인터페이스 변화

기존 응답 형태는 유지하고 **추가 필드만**(프론트 회귀 최소).

| 엔드포인트 | 변화 | 호환성 |
|---|---|---|
| `GET /auth/me` | `manager_id` 필드 추가(`CurrentUser`에 들어감) | 기존 필드 유지, 추가만 |
| `GET /catalog`, `/catalog/export.xlsx` | 응답 형태 동일. 내부적으로 뷰어 테넌트 스코프 적용 | 1차 결과 동일(회귀 없음) |
| `GET /p/{code}` | 응답 동일. 스코프 밖 상품은 로그인 셀러여도 `skus` 미부여 | 1차 결과 동일 |
| `GET /admin/accounts` | 자기 테넌트+미배정만 반환. 행 형태 동일(`email`/`agency_name` 유지) | 행 스키마 동일, 모수만 축소 |
| `POST /admin/accounts/{uid}/approve` | 승인 시 테넌트 연결(도매=연결표, 셀러=manager_id) 부수효과 추가 | 응답 형태 동일 |
| **`GET /admin/products`** (신규) | 소속 도매 합산 상품. 각 item에 `wholesaler_id` + `wholesaler_name` | 신규 — `ProductList` 형태 + 출처 필드 |

신규 엔드포인트 응답 예:

```json
{ "items": [ { "id":"...", "platform_code":"EZM-1", "item_name":"셔츠",
  "wholesaler_id":"w-1", "wholesaler_name":"라라스도매A", "status":"active",
  "skus":[{"color":"화이트","size":"F","wholesale_price":12000,"retail_price":29000,"stock":7}] } ],
  "total": 1, "limit": 30, "offset": 0 }
```

---

## 5. 프론트 변경 지점

### 5.1 `lib/products.ts` — 타입/호출 확장
- `Me` 타입에 `manager_id: string | null` 추가(getMe 응답 1:1).
- 신규 호출 `listAdminProducts(params)` → `GET /admin/products`. `AdminProduct = Product & { wholesaler_name: string }` 타입 추가.
- `Account` 타입에 `manager_id` 추가(선택).

### 5.2 `/admin` 도매관리자 대시보드 — 탭 구조화 (FR-5)
현재 `admin/page.tsx`는 가입승인 단일 화면. **상품관리 탭 추가**(권장안):
- `app/admin/products/page.tsx` 신규 라우트 + `AdminShell` NAV에 "상품 관리" 항목 추가(`AdminShell.tsx`의 `NAV` 배열에 `{ href:"/admin/products", label:"상품 관리", icon: Box }`). 기존 `/admin`(가입 승인)은 그대로.
- 합산 상품 테이블은 `(dash)/products/page.tsx`를 참고하되 **행마다 "도매 출처"(`wholesaler_name`) 컬럼**을 추가. 가격은 admin이라 도매가/판매가 둘 다 표시.

### 5.3 `(dash)` 단일 도매업체 유지 (FR-6)
- `(dash)/layout.tsx` + `WholesalerGate.tsx` **무변경**. 도매상은 자기 상품만(`/products`). `Shell.tsx` NAV 그대로.
- `WholesalerGate`는 이미 admin→`/admin`, seller→`/seller/showroom` 리다이렉트, 승인 도매만 통과(WholesalerGate.tsx:31-41) → 분리 완성돼 있음.

### 5.4 게이트/네비 분기
- `AdminGate.tsx` 무변경(admin만 `/admin` 통과). admin 콘솔 NAV만 확장.
- `AdminShell.tsx`: 기존 "가격·권한 설정 soon" 자리 위/옆에 "상품 관리" 활성 항목 추가.

### 5.5 `lib/catalog.ts` 호출 변화
- **변화 없음**. `getCatalog`/`getAllCatalog`/`toShowroomCards`는 백엔드가 스코프를 적용하므로 클라이언트 코드 동일. 셀러 쇼룸은 자동으로 연계 테넌트 상품만 받게 됨(1차엔 전체와 동일).

---

## 6. 핵심 설계 결정 (대안 비교 + 추천)

### (a) 셀러→관리자 연계: 단일 FK vs 연결표
- **A. `profiles.manager_id` 단일 FK** — 셀러 1명이 관리자 1개에 연계. 조회 1홉, auth resolve 단순, admin도 같은 칸 재사용.
- B. `manager_sellers` 연결표 — n:m 확장 자유, 그러나 셀러는 PRD상 1:1 연계라 현실적 n:m 시나리오 없음. resolve에 +1 join.
- **추천: A**. PRD가 셀러↔관리자를 1:1로 정의. forward-compat이 필요한 축은 **도매상↔관리자**(PRD가 명시적으로 단일 칸 금지한 쪽)이지 셀러가 아니다. 셀러가 미래에 다중 연계가 필요해지면 그때 연결표로 승격(스코프 헬퍼만 교체, 호출부 무변경). 과설계 회피.

### (b) 도매상↔관리자 1:n 강제 방법
- A. 연결표 + 앱레이어에서 "1행만" 검사 — 동시성 race로 중복 가능.
- **B. 연결표 + 부분 unique 인덱스 `(wholesaler_id) WHERE deleted_at IS NULL`** — DB가 도매상당 살아있는 소속 1행을 강제. soft-delete 후 재소속 허용(`_03`/`_09`와 동형 패턴).
- C. `wholesalers.manager_id` 칸 — PRD가 단일 칸 금지(n:m 대비) → 탈락.
- **추천: B**. PRD의 "연결표 형태" + "1:n 강제"를 동시 만족. n:m 전환은 이 부분 unique **드롭 한 줄**(`manager_wholesalers_pair_alive`는 유지)로 끝나 스키마 변경 최소(NFR-1).

### (c) 테넌트 스코프 강제 위치: 쿼리 필터 vs 미들웨어
- A. FastAPI 미들웨어/전역 의존성에서 강제 — 엔드포인트마다 스코프 키·테이블이 달라(catalog=products.wholesaler_id, accounts=profiles.manager_id) 일괄 주입이 어렵고, service-key 단일 클라이언트라 "쿼리에 자동 WHERE 삽입"이 불가(ORM 아님).
- **B. 라우터/리포지토리 쿼리 필터** — 기존 `owner_wid` IDOR 가드(products.py)와 **동일 패턴**. 명시적·국소적·테스트 용이.
- **추천: B**. 코드베이스가 이미 앱레이어 명시 필터로 통일돼 있고(NFR-3), RLS 전환은 범위 밖. 공용 헬퍼 `_scoped_wholesaler_ids`로 중복만 통제.

### (d) admin 역할의 테넌트 매핑: `profiles.manager_id` 재사용 vs 신규 컬럼
- **A. `profiles.manager_id` 재사용** — admin도 셀러처럼 "어느 테넌트에 속하나"를 같은 칸으로 표현. 컬럼 1개로 셀러+admin 둘 다 커버.
- B. `wholesale_managers.owner_admin_id` 역방향 FK — 대표 admin 1명만 표현 가능, "테넌트에 admin 여럿"으로 못 늘어남.
- **추천: A**. 시드에서 기존 admin의 `manager_id=LALAS`로 세팅(§2.3-7). 미래에 테넌트당 admin 여럿도 같은 칸으로 자연 확장. `auth._resolve_manager_id`가 admin/셀러/도매 3역할을 한 함수로 처리.

---

## 7. 예비 위험

1. **마이그레이션 순서 + backfill 누락** — `_10`은 반드시 `_09` 이후, 그리고 **기존 admin 프로필이 존재한 뒤** 실행(시드의 `created_by` FK 때문). backfill(§2.3-8)을 빠뜨리면 기존 셀러 `manager_id=NULL` → 카탈로그가 **빈 결과(fail-closed)**로 회귀. 마이그레이션 표에 10번 추가 + "backfill 포함, 1회 실행" 명시 필요.

2. **카탈로그 회귀(전체 노출 동일성)** — 1차 핵심 불변식은 "LALAS 소속 = 전체 도매상". backfill이 **모든 살아있는 wholesaler**를 LALAS에 묶어야 `in_(전체)` = 무필터와 동일. 신규 도매 승인 시 `link_wholesaler_to_manager`가 빠지면 그 도매 상품이 카탈로그에서 누락 → 승인 보상 체인(§3.5)에 반드시 포함. 회귀 테스트로 "스코프 적용 전후 카탈로그 item 수 동일" 검증(§8).

3. **빈 스코프 경계 처리** — `_scoped_wholesaler_ids`가 `[]` 반환 시 `.in_("wholesaler_id", [])`는 PostgREST에서 빈 결과를 줘야 한다(과노출 금지). 빈 리스트 IN 동작을 테스트로 고정. `manager_id=None` 셀러(backfill 누락분)는 의도적으로 빈 카탈로그 — 과노출보다 안전.

4. **합산 쿼리 성능** — `GET /admin/products`가 `in_(도매 id 목록)` + `wholesalers(name)` + `product_skus` 임베드. 1차 LALAS는 도매 수 적어 무탈. 테넌트·도매가 커지면 `in_` 목록이 길어짐 → `idx_products_wholesaler_status`/alive 인덱스 활용. 페이지네이션(`range`) 필수, export는 기존 상한(`_EXPORT_MAX=1000`) 패턴 준수.

5. **auth resolve 추가 쿼리** — 도매상 로그인마다 `manager_wholesalers` +1 쿼리. `manager_wholesalers_wid_alive` 인덱스 직격이라 비용 미미하나, `get_current_user_optional`(공개카드)도 도매상 토큰이면 동일 비용 발생 — 공개 트래픽 많으면 캐시 고려(범위 밖).

6. **`or_` 필터 안전성(accounts)** — `list_by_status`의 `manager_id.eq.{id},manager_id.is.null`에서 `manager_id`가 신뢰된 서버 값(JWT→profiles)이라 인젝션 위험 낮으나, UUID 형식 검증 후 삽입 권장.

7. **트리거 함수명 불일치** — §2.3 SQL의 `set_updated_at`/`soft_cascade_*` 는 관례명 가정. 구현 시 `_04`/`_03` 실제 함수명을 확인해 일치시킬 것(불일치 시 마이그레이션 실패).

---

## 8. 테스트 전략

기존 pytest 정합(모두 service 단/셰이핑 단 순수함수 테스트 — DB 미접속 fake repo 패턴) 유지.

**기존 테스트 영향(회귀 가드)**
- `test_catalog_shaping.py` — `shape_catalog_item`/`visible_price` 무변경이므로 **그대로 통과해야 함**(가격 셰이핑 불변 증명). 변경 시 설계 위반 신호.
- `test_pricing.py`(있으면) — `visible_price` 무변경 → 통과.
- `test_accounts_service.py` — `approve_account` 시그니처에 `admin_manager_id` 추가됨 → **기존 테스트 호출부 수정 필요**(인자 추가). `FakeProfiles`에 `link_wholesaler_to_manager`/`set_status(manager_id=)` 추가. 기존 A-4 보상 테스트는 wholesaler 생성→연결 실패 경로 유지 확인.
- `test_public_card.py` — viewer를 스코프 내로 가정하는 fake 보강 후 통과.

**신규 테스트 포인트**
- **테넌트 스코핑(catalog)**: `_scoped_wholesaler_ids`가 manager_id→도매 id 목록을 정확히 반환. `manager_id=None`→`[]`. `_query_catalog_rows(wholesaler_ids=[])`가 빈 결과. fake sb로 검증.
- **회귀 동일성**: "LALAS 소속=전체"일 때 스코프 적용 결과 == 무스코프 결과(item 수/순서 동일).
- **공개카드 스코프**: 스코프 밖 상품 → 로그인 셀러여도 `skus` 미부여, 공개 카드 필드는 유지(404 아님).
- **승인 스코프**: `approve_account`가 도매 승인 시 `link_wholesaler_to_manager` 호출(멱등), 셀러 승인 시 `set_status(manager_id=admin_manager_id)`. 연결 실패 시 wholesaler soft-delete 보상.
- **accounts list 스코프**: `list_by_status(status, manager_id)`가 자기 테넌트+미배정만(`or_` 필터) 구성.
- **합산 상품(admin)**: `shape_admin_product`가 `wholesaler_name`을 부여, 가격은 admin→도매가+판매가 둘 다.
- **auth resolve**: `_resolve_manager_id` 3역할(셀러=profiles.manager_id, 도매=연결표, admin=profiles.manager_id) 분기.
- **backfill SQL**: 별도 검증은 SQL 수동 실행 후 "셀러 manager_id 채워짐 / 도매 연결행 생성됨 / 카탈로그 item 수 불변" 스모크(통합 테스트는 범위 밖, 수동 체크리스트로).

---

## 변경이력
<!-- change-history skill auto-appends entries here, oldest first -->

### [2026-06-09 21:50] [개발방향-수정]
- **id**: CH-20260609-002
- **이유**: 신규 피처 tech-design 최초 작성 — 도매관리자 멀티테넌트 1차 재편 기술설계. PRD(CH-20260609-001) 기반, Plan 서브에이전트가 실제 코드(마이그레이션 컨벤션·auth·catalog·admin·accounts·pricing·products·프론트 shell/gate) 읽고 설계, 시드 UUID hex 버그(`…lala` → 유효 hex `1a1a0000-…-a1a5`) 수정 후 확정.
- **무엇이**: `wholesale-manager-tenancy-tech-design.md` 전체 — 아키텍처, 데이터모델+마이그레이션 SQL(`_10`), 백엔드 변경지점(auth/catalog/public/admin/accounts/products), API 델타, 프론트 변경지점, 설계결정 4건, 위험 7, 테스트 전략.
- **영향범위**: 다음 단계 writing-plans 입력. 구현 시 신규=`backend/migrations/2026-06-09_v2_core_10_wholesale_manager_tenancy.sql`·`app/services/tenancy.py` / 수정=auth.py, catalog.py, public.py, admin.py, accounts.py, products.py, entities/models.py, schemas/auth.py + 프론트 admin/*, lib/products.ts. 기존 테스트 `test_accounts_service` 시그니처 수정 필요.
- **연관 항목**: CH-20260609-001
