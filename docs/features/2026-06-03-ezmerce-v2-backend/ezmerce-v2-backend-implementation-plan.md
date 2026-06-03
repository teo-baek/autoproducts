---
commit_policy: per-task
---

# ezmerce v2 백엔드 (1차) 구현계획서

> **다음 단계 안내**: 이 계획을 task-by-task 로 실행하려면 `subagent-driven-development`(보조 에이전트 강제 모드, 13+ task 권장) 또는 `executing-plans`(인라인 모드)를 사용하세요. 각 step 은 체크박스(`- [ ]`)라 진행 추적이 가능합니다.

**Goal:** LALAS용 폐쇄형 B2B 카탈로그의 1차 백엔드(FastAPI + Supabase)를 구축한다 — 상품등록·엑셀출력·QR + 역할기반 폐쇄형 카탈로그(가격 차등 노출).

**Architecture:** 프론트(Next.js/Expo) → **FastAPI**(인증검증·RBAC·엑셀/QR·가격권위) → Supabase(Postgres + Auth + Storage). 프론트는 Supabase 직결하지 않고 FastAPI를 경유한다. 가격 노출은 서버에서 역할 기준으로 결정한다.

**Tech Stack:** Python 3.12, FastAPI, Supabase(supabase-py), Postgres, pandas/openpyxl(엑셀), qrcode/Pillow(QR), pytest.

**Spec inputs:**
- `ezmerce-v2-backend-requirements.md` — FR-1(RBAC/승인), FR-2(상품 CRUD/품번정규화), FR-3(엑셀출력+QR), FR-4(QR), FR-5(폐쇄형 카탈로그+가격차등)
- `ezmerce-v2-backend-tech-design.md` — §3 DB 스키마/DDL, §3.10 가격 리졸버, §6 핵심결정(platform_code SEQUENCE, FastAPI 가격권위)

**실행 메모:** 외부 의존(Supabase)을 끊고 TDD하기 위해 **순수 로직(가격 리졸버·platform_code·엑셀 파서·QR URL)** 은 단위테스트로 강제하고, DB 접근은 `Repository` 프로토콜로 추상화해 가짜(fake) 구현으로 라우터를 테스트한다.

---

## 1. 단계별 작업

### Task 1: 프로젝트 부트스트랩 (FastAPI 스켈레톤 + 설정)

**Files:**
- Create: `backend/app/__init__.py`
- Create: `backend/app/core/config.py`
- Create: `backend/app/main.py`
- Test: `backend/tests/test_health.py`

**Model**: haiku

- [ ] **Step 1: 실패 테스트 작성** — `backend/tests/test_health.py`

```python
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

def test_health_ok():
    res = client.get("/health")
    assert res.status_code == 200
    assert res.json() == {"status": "ok"}
```

- [ ] **Step 2: 실패 확인**

Run: `cd backend && source .venv/bin/activate && pytest tests/test_health.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.main'`

- [ ] **Step 3: 설정 모듈 작성** (new file: `backend/app/core/config.py`)

```python
from functools import lru_cache
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    supabase_url: str = ""
    supabase_service_key: str = ""
    supabase_jwt_secret: str = ""
    public_base_url: str = "http://localhost:3000"  # QR 카드 URL prefix
    platform_code_prefix: str = "EZM"

    class Config:
        env_file = ".env"
        extra = "ignore"


@lru_cache
def get_settings() -> Settings:
    return Settings()
```

- [ ] **Step 4: 앱 진입점 작성** (new file: `backend/app/main.py`)

```python
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(title="ezmerce API", version="0.2.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # RISK(breaking): 운영 전 화이트리스트로 좁힐 것
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health():
    return {"status": "ok"}
```

- [ ] **Step 5: 통과 확인**

Run: `cd backend && source .venv/bin/activate && pytest tests/test_health.py -v`
Expected: PASS

- [ ] **Step 6: 커밋**

```bash
git add backend/app backend/tests/test_health.py
git commit -m "feat(api): FastAPI 스켈레톤 + health 엔드포인트"
```

---

### Task 2: DB 마이그레이션 (v2 코어 스키마)

**Files:**
- Create: `backend/migrations/2026-06-03_v2_core.sql`
- Modify: `setup_v2_schema.sql:1-48` (구버전 표시 — deprecate 주석)

**Model**: sonnet

> tech-design §3 의 전체 DDL을 마이그레이션 파일로 확정한다. SQL은 Supabase SQL Editor에서 실행하므로 자동 테스트 대신 **검증 체크리스트**로 수용한다(코드 로직 아님).

- [ ] **Step 1: 마이그레이션 파일 작성** (new file: `backend/migrations/2026-06-03_v2_core.sql`)

```sql
-- ezmerce v2 core schema (1차) — Supabase SQL Editor에서 실행
-- ENUM
CREATE TYPE user_role      AS ENUM ('admin','wholesaler','retail_seller','agency');
CREATE TYPE account_status AS ENUM ('pending','approved','rejected','suspended');
CREATE TYPE seller_type    AS ENUM ('agency_affiliated','independent');
CREATE TYPE org_type       AS ENUM ('wholesaler','agency');
CREATE TYPE product_status AS ENUM ('active','archived');
CREATE TYPE image_match    AS ENUM ('matched','unmatched');
CREATE TYPE upload_status  AS ENUM ('uploaded','parsing','needs_matching','completed','failed');

-- platform_code 발급 시퀀스 (원자적)
CREATE SEQUENCE IF NOT EXISTS public.platform_code_seq START 1;

CREATE TABLE public.organizations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name TEXT NOT NULL,
    type org_type NOT NULL,
    biz_number TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE public.profiles (
    id UUID PRIMARY KEY REFERENCES auth.users(id) ON DELETE CASCADE,
    role user_role NOT NULL,
    status account_status NOT NULL DEFAULT 'pending',
    full_name TEXT,
    phone TEXT,
    organization_id UUID REFERENCES public.organizations(id) ON DELETE SET NULL,
    seller_type seller_type,
    approved_at TIMESTAMPTZ,
    approved_by UUID REFERENCES public.profiles(id),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT seller_type_only_for_retail CHECK (
        (role = 'retail_seller' AND seller_type IS NOT NULL)
        OR (role <> 'retail_seller' AND seller_type IS NULL)
    )
);
CREATE INDEX idx_profiles_role_status ON public.profiles(role, status);
CREATE INDEX idx_profiles_org ON public.profiles(organization_id);

CREATE TABLE public.products (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    wholesaler_org_id UUID NOT NULL REFERENCES public.organizations(id) ON DELETE CASCADE,
    platform_code TEXT NOT NULL UNIQUE,
    source_p_number TEXT NOT NULL,
    item_name TEXT NOT NULL,
    fabric_composition TEXT, origin TEXT, lead_time_days TEXT, description TEXT,
    representative_image_url TEXT,
    status product_status NOT NULL DEFAULT 'active',
    is_sold_out BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (wholesaler_org_id, source_p_number)
);
CREATE INDEX idx_products_org_status ON public.products(wholesaler_org_id, status);

CREATE TABLE public.product_skus (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    product_id UUID NOT NULL REFERENCES public.products(id) ON DELETE CASCADE,
    color TEXT NOT NULL, size TEXT NOT NULL,
    wholesale_price INTEGER NOT NULL,
    retail_price INTEGER,
    stock INTEGER NOT NULL DEFAULT 0,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (product_id, color, size)
);

CREATE TABLE public.product_images (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    product_id UUID REFERENCES public.products(id) ON DELETE CASCADE,
    wholesaler_org_id UUID NOT NULL REFERENCES public.organizations(id) ON DELETE CASCADE,
    storage_path TEXT NOT NULL,
    original_filename TEXT,
    match_status image_match NOT NULL DEFAULT 'unmatched',
    is_representative BOOLEAN NOT NULL DEFAULT FALSE,
    sort_order INTEGER NOT NULL DEFAULT 0,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_images_unmatched ON public.product_images(wholesaler_org_id, match_status);

CREATE TABLE public.upload_jobs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    wholesaler_org_id UUID NOT NULL REFERENCES public.organizations(id) ON DELETE CASCADE,
    created_by UUID REFERENCES public.profiles(id),
    file_path TEXT,
    status upload_status NOT NULL DEFAULT 'uploaded',
    total_rows INTEGER DEFAULT 0, matched_rows INTEGER DEFAULT 0, error_rows INTEGER DEFAULT 0,
    error_detail JSONB,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    completed_at TIMESTAMPTZ
);

-- RLS (방어선) — tech-design §3.11
CREATE OR REPLACE FUNCTION public.current_profile()
RETURNS public.profiles LANGUAGE sql STABLE AS $$
  SELECT * FROM public.profiles WHERE id = auth.uid();
$$;

ALTER TABLE public.organizations  ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.profiles       ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.products       ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.product_skus   ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.product_images ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.upload_jobs    ENABLE ROW LEVEL SECURITY;

CREATE POLICY profiles_self_select ON public.profiles FOR SELECT USING (id = auth.uid());
CREATE POLICY profiles_self_update ON public.profiles FOR UPDATE USING (id = auth.uid());
CREATE POLICY products_read_approved ON public.products FOR SELECT
  USING (status = 'active' AND (SELECT status FROM public.profiles WHERE id = auth.uid()) = 'approved');
CREATE POLICY products_owner_write ON public.products FOR ALL
  USING (wholesaler_org_id = (SELECT organization_id FROM public.profiles WHERE id = auth.uid()));
```

- [ ] **Step 2: 구버전 스키마 deprecate 표시**

**원본** (`setup_v2_schema.sql:1-2`):
```sql
-- AutoProducts V2 Core Database Schema
-- Run this script in the Supabase SQL Editor.
```

**수정 후**:
```sql
-- [DEPRECATED 2026-06-03] backend/migrations/2026-06-03_v2_core.sql 로 대체됨.
-- AutoProducts V2 Core Database Schema (구버전 — products/product_skus only)
-- Run this script in the Supabase SQL Editor.
```

- [ ] **Step 3: 수용 체크리스트 검증** (Supabase SQL Editor 실행 후)

```
[ ] 7개 ENUM 생성됨
[ ] 6개 테이블 생성됨 (organizations/profiles/products/product_skus/product_images/upload_jobs)
[ ] platform_code_seq 시퀀스 존재
[ ] seller_type_only_for_retail CHECK 동작 (retail_seller 외 seller_type 입력 시 거부)
[ ] RLS 6개 테이블 활성
```

- [ ] **Step 4: 커밋**

```bash
git add backend/migrations setup_v2_schema.sql
git commit -m "feat(db): v2 코어 스키마 마이그레이션 (계정/조직/상품/이미지/업로드잡 + RLS)"
```

---

### Task 3: Supabase 클라이언트 + Repository 프로토콜

**Files:**
- Create: `backend/app/core/supabase.py`
- Create: `backend/app/repositories/base.py`
- Test: `backend/tests/test_supabase_client.py`

**Model**: sonnet

- [ ] **Step 1: 실패 테스트 작성** — `backend/tests/test_supabase_client.py`

```python
from app.core.supabase import get_supabase

def test_get_supabase_is_singleton(monkeypatch):
    monkeypatch.setenv("SUPABASE_URL", "https://x.supabase.co")
    monkeypatch.setenv("SUPABASE_SERVICE_KEY", "svc")
    get_supabase.cache_clear()
    a = get_supabase()
    b = get_supabase()
    assert a is b
```

- [ ] **Step 2: 실패 확인** — Run: `pytest tests/test_supabase_client.py -v` → FAIL (모듈 없음)

- [ ] **Step 3: 클라이언트 작성** (new file: `backend/app/core/supabase.py`)

```python
from functools import lru_cache
from supabase import create_client, Client
from app.core.config import get_settings


@lru_cache
def get_supabase() -> Client:
    s = get_settings()
    # service role 키 — 서버 전용. RISK(side-effect): 절대 프론트 노출 금지
    return create_client(s.supabase_url, s.supabase_service_key)
```

- [ ] **Step 4: Repository 프로토콜** (new file: `backend/app/repositories/base.py`)

```python
from typing import Protocol, Any


class ProductRepository(Protocol):
    def next_platform_code(self) -> int: ...
    def insert_product(self, data: dict) -> dict: ...
    def insert_skus(self, rows: list[dict]) -> list[dict]: ...
    def get_product(self, product_id: str) -> dict | None: ...
    def update_product(self, product_id: str, patch: dict) -> dict: ...
    def list_active(self, limit: int, cursor: str | None) -> list[dict]: ...
```

- [ ] **Step 5: 통과 확인** — Run: `pytest tests/test_supabase_client.py -v` → PASS

- [ ] **Step 6: 커밋**

```bash
git add backend/app/core/supabase.py backend/app/repositories/base.py backend/tests/test_supabase_client.py
git commit -m "feat(api): Supabase 클라이언트 + Repository 프로토콜"
```

---

### Task 4: 인증 의존성 (Supabase JWT 검증 → 현재 프로필)

**Files:**
- Create: `backend/app/core/auth.py`
- Create: `backend/app/schemas/auth.py`
- Test: `backend/tests/test_auth_dep.py`

**Model**: sonnet

- [ ] **Step 1: 실패 테스트 작성** — `backend/tests/test_auth_dep.py`

```python
import jwt
import pytest
from app.core.auth import decode_jwt, AuthError

SECRET = "test-secret"

def test_decode_valid_jwt():
    token = jwt.encode({"sub": "user-123"}, SECRET, algorithm="HS256")
    assert decode_jwt(token, SECRET)["sub"] == "user-123"

def test_decode_invalid_jwt_raises():
    with pytest.raises(AuthError):
        decode_jwt("garbage", SECRET)
```

- [ ] **Step 2: 실패 확인** — Run: `pytest tests/test_auth_dep.py -v` → FAIL

- [ ] **Step 3: 인증 스키마** (new file: `backend/app/schemas/auth.py`)

```python
from pydantic import BaseModel


class CurrentUser(BaseModel):
    id: str
    role: str
    status: str
    seller_type: str | None = None
    organization_id: str | None = None
```

- [ ] **Step 4: 인증 모듈** (new file: `backend/app/core/auth.py`)

```python
import jwt
from fastapi import Depends, Header
from app.core.config import get_settings
from app.core.supabase import get_supabase
from app.schemas.auth import CurrentUser


class AuthError(Exception):
    pass


def decode_jwt(token: str, secret: str) -> dict:
    try:
        return jwt.decode(token, secret, algorithms=["HS256"], audience="authenticated")
    except Exception as e:  # noqa: BLE001
        raise AuthError(str(e))


def get_current_user(authorization: str = Header(default="")) -> CurrentUser:
    from fastapi import HTTPException
    if not authorization.startswith("Bearer "):
        raise HTTPException(401, "missing bearer token")
    token = authorization.split(" ", 1)[1]
    try:
        payload = decode_jwt(token, get_settings().supabase_jwt_secret)
    except AuthError:
        raise HTTPException(401, "invalid token")
    uid = payload["sub"]
    sb = get_supabase()
    row = sb.table("profiles").select("*").eq("id", uid).single().execute().data
    if not row:
        raise HTTPException(403, "no profile")
    return CurrentUser(**{k: row.get(k) for k in CurrentUser.model_fields})
```

- [ ] **Step 5: 통과 확인** — Run: `pytest tests/test_auth_dep.py -v` → PASS

- [ ] **Step 6: 커밋**

```bash
git add backend/app/core/auth.py backend/app/schemas/auth.py backend/tests/test_auth_dep.py
git commit -m "feat(auth): Supabase JWT 검증 + current_user 의존성"
```

---

### Task 5: RBAC 가드 (역할/승인 요구)

**Files:**
- Create: `backend/app/core/rbac.py`
- Test: `backend/tests/test_rbac.py`

**Model**: sonnet

- [ ] **Step 1: 실패 테스트 작성** — `backend/tests/test_rbac.py`

```python
import pytest
from fastapi import HTTPException
from app.core.rbac import require_role, require_approved
from app.schemas.auth import CurrentUser

def cu(**kw):
    base = dict(id="u", role="wholesaler", status="approved")
    base.update(kw)
    return CurrentUser(**base)

def test_require_role_pass():
    require_role("wholesaler", "admin")(cu(role="wholesaler"))  # no raise

def test_require_role_block():
    with pytest.raises(HTTPException) as e:
        require_role("admin")(cu(role="wholesaler"))
    assert e.value.status_code == 403

def test_require_approved_blocks_pending():
    with pytest.raises(HTTPException):
        require_approved(cu(status="pending"))
```

- [ ] **Step 2: 실패 확인** — Run: `pytest tests/test_rbac.py -v` → FAIL

- [ ] **Step 3: RBAC 모듈** (new file: `backend/app/core/rbac.py`)

```python
from fastapi import HTTPException
from app.schemas.auth import CurrentUser


def require_approved(user: CurrentUser) -> CurrentUser:
    if user.status != "approved":
        raise HTTPException(403, "account not approved")
    return user


def require_role(*roles: str):
    def _dep(user: CurrentUser) -> CurrentUser:
        if user.role not in roles:
            raise HTTPException(403, f"requires role in {roles}")
        return user
    return _dep
```

- [ ] **Step 4: 통과 확인** — Run: `pytest tests/test_rbac.py -v` → PASS

- [ ] **Step 5: 커밋**

```bash
git add backend/app/core/rbac.py backend/tests/test_rbac.py
git commit -m "feat(auth): RBAC require_role/require_approved 가드"
```

---

### Task 6: 가입 + 관리자 계정 승인 (FR-1.3)

**Files:**
- Create: `backend/app/routers/admin.py`
- Create: `backend/app/services/accounts.py`
- Test: `backend/tests/test_accounts_service.py`

**Model**: sonnet

- [ ] **Step 1: 실패 테스트 작성** — `backend/tests/test_accounts_service.py`

```python
from app.services.accounts import approve_account

class FakeProfiles:
    def __init__(self): self.updated = {}
    def set_status(self, uid, status, by):
        self.updated = {"id": uid, "status": status, "approved_by": by}
        return self.updated

def test_approve_sets_status_approved():
    repo = FakeProfiles()
    out = approve_account(repo, target_id="seller-1", admin_id="admin-1")
    assert out["status"] == "approved"
    assert out["approved_by"] == "admin-1"
```

- [ ] **Step 2: 실패 확인** — Run: `pytest tests/test_accounts_service.py -v` → FAIL

- [ ] **Step 3: 서비스 작성** (new file: `backend/app/services/accounts.py`)

```python
def approve_account(repo, target_id: str, admin_id: str) -> dict:
    return repo.set_status(target_id, "approved", admin_id)

def reject_account(repo, target_id: str, admin_id: str) -> dict:
    return repo.set_status(target_id, "rejected", admin_id)
```

- [ ] **Step 4: 라우터 작성** (new file: `backend/app/routers/admin.py`)

```python
from fastapi import APIRouter, Depends
from app.core.auth import get_current_user
from app.core.rbac import require_role
from app.core.supabase import get_supabase
from app.schemas.auth import CurrentUser

router = APIRouter(prefix="/admin", tags=["admin"])
_admin = require_role("admin")


def _set_status(uid: str, status: str, by: str):
    sb = get_supabase()
    return sb.table("profiles").update(
        {"status": status, "approved_by": by, "approved_at": "now()"}
    ).eq("id", uid).execute().data


@router.get("/accounts")
def list_accounts(status: str = "pending", user: CurrentUser = Depends(get_current_user)):
    _admin(user)
    sb = get_supabase()
    return sb.table("profiles").select("*").eq("status", status).execute().data


@router.post("/accounts/{uid}/approve")
def approve(uid: str, user: CurrentUser = Depends(get_current_user)):
    _admin(user)
    return _set_status(uid, "approved", user.id)


@router.post("/accounts/{uid}/reject")
def reject(uid: str, user: CurrentUser = Depends(get_current_user)):
    _admin(user)
    return _set_status(uid, "rejected", user.id)
```

- [ ] **Step 5: main.py 라우터 등록**

**원본** (`backend/app/main.py:1-6`):
```python
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(title="ezmerce API", version="0.2.0")
```

**수정 후**:
```python
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.routers import admin

app = FastAPI(title="ezmerce API", version="0.2.0")
app.include_router(admin.router)
```

- [ ] **Step 6: 통과 확인** — Run: `pytest tests/test_accounts_service.py -v` → PASS

- [ ] **Step 7: 커밋**

```bash
git add backend/app/routers/admin.py backend/app/services/accounts.py backend/app/main.py backend/tests/test_accounts_service.py
git commit -m "feat(admin): 계정 승인/거절/목록 (FR-1.3)"
```

---

### Task 7: platform_code 생성기 (품번 정규화, FR-2.5)

**Files:**
- Create: `backend/app/services/platform_code.py`
- Test: `backend/tests/test_platform_code.py`

**Model**: haiku

- [ ] **Step 1: 실패 테스트 작성** — `backend/tests/test_platform_code.py`

```python
from app.services.platform_code import format_platform_code

def test_format_zero_pads_with_prefix():
    assert format_platform_code(1, prefix="EZM") == "EZM-000001"
    assert format_platform_code(123456, prefix="EZM") == "EZM-123456"

def test_format_overflow_keeps_full_number():
    assert format_platform_code(12345678, prefix="EZM") == "EZM-12345678"
```

- [ ] **Step 2: 실패 확인** — Run: `pytest tests/test_platform_code.py -v` → FAIL

- [ ] **Step 3: 생성기 작성** (new file: `backend/app/services/platform_code.py`)

```python
def format_platform_code(seq: int, prefix: str = "EZM") -> str:
    return f"{prefix}-{seq:06d}"


def next_platform_code(supabase, prefix: str = "EZM") -> str:
    # RISK(race): 반드시 Postgres SEQUENCE(nextval)로 발급 — 앱 카운터 금지
    seq = supabase.rpc("nextval", {"seq_name": "platform_code_seq"}).execute().data
    return format_platform_code(int(seq), prefix)
```

- [ ] **Step 4: 통과 확인** — Run: `pytest tests/test_platform_code.py -v` → PASS

- [ ] **Step 5: 커밋**

```bash
git add backend/app/services/platform_code.py backend/tests/test_platform_code.py
git commit -m "feat(products): platform_code 생성기 (품번 정규화)"
```

---

### Task 8: 상품 단건 등록 (FR-2.1)

**Files:**
- Create: `backend/app/schemas/product.py`
- Create: `backend/app/services/products.py`
- Create: `backend/app/routers/products.py`
- Test: `backend/tests/test_products_service.py`

**Model**: sonnet

- [ ] **Step 1: 실패 테스트 작성** — `backend/tests/test_products_service.py`

```python
from app.services.products import register_product
from app.schemas.product import ProductCreate, SkuCreate

class FakeRepo:
    def __init__(self): self.products=[]; self.skus=[]; self.seq=0
    def next_platform_code(self):
        self.seq += 1; return f"EZM-{self.seq:06d}"
    def insert_product(self, d): d={**d,"id":"p1"}; self.products.append(d); return d
    def insert_skus(self, rows): self.skus.extend(rows); return rows

def test_register_assigns_platform_code_and_skus():
    repo = FakeRepo()
    payload = ProductCreate(
        source_p_number="1001", item_name="린넨 셔츠",
        skus=[SkuCreate(color="화이트", size="F", wholesale_price=12000, retail_price=29000)],
    )
    out = register_product(repo, org_id="org-1", payload=payload)
    assert out["platform_code"] == "EZM-000001"
    assert repo.skus[0]["wholesale_price"] == 12000
    assert repo.products[0]["wholesaler_org_id"] == "org-1"
```

- [ ] **Step 2: 실패 확인** — Run: `pytest tests/test_products_service.py -v` → FAIL

- [ ] **Step 3: 스키마 작성** (new file: `backend/app/schemas/product.py`)

```python
from pydantic import BaseModel, Field


class SkuCreate(BaseModel):
    color: str
    size: str
    wholesale_price: int = Field(ge=0)
    retail_price: int | None = Field(default=None, ge=0)
    stock: int = Field(default=0, ge=0)


class ProductCreate(BaseModel):
    source_p_number: str
    item_name: str
    fabric_composition: str | None = None
    origin: str | None = None
    lead_time_days: str | None = None
    description: str | None = None
    skus: list[SkuCreate]
```

- [ ] **Step 4: 서비스 작성** (new file: `backend/app/services/products.py`)

```python
from app.schemas.product import ProductCreate


def register_product(repo, org_id: str, payload: ProductCreate) -> dict:
    code = repo.next_platform_code()
    product = repo.insert_product({
        "wholesaler_org_id": org_id,
        "platform_code": code,
        "source_p_number": payload.source_p_number,
        "item_name": payload.item_name,
        "fabric_composition": payload.fabric_composition,
        "origin": payload.origin,
        "lead_time_days": payload.lead_time_days,
        "description": payload.description,
    })
    repo.insert_skus([{**s.model_dump(), "product_id": product["id"]} for s in payload.skus])
    return product
```

- [ ] **Step 5: 라우터 작성** (new file: `backend/app/routers/products.py`)

```python
from fastapi import APIRouter, Depends, HTTPException
from app.core.auth import get_current_user
from app.core.rbac import require_role, require_approved
from app.core.supabase import get_supabase
from app.schemas.auth import CurrentUser
from app.schemas.product import ProductCreate
from app.services.products import register_product
from app.services.platform_code import next_platform_code

router = APIRouter(prefix="/products", tags=["products"])


class SupabaseProductRepo:
    def __init__(self): self.sb = get_supabase()
    def next_platform_code(self): return next_platform_code(self.sb)
    def insert_product(self, d): return self.sb.table("products").insert(d).execute().data[0]
    def insert_skus(self, rows): return self.sb.table("product_skus").insert(rows).execute().data


@router.post("")
def create_product(payload: ProductCreate, user: CurrentUser = Depends(get_current_user)):
    require_approved(user); require_role("wholesaler")(user)
    if not user.organization_id:
        raise HTTPException(400, "no organization")
    return register_product(SupabaseProductRepo(), user.organization_id, payload)
```

- [ ] **Step 6: main.py 라우터 등록**

**원본** (`backend/app/main.py:3`):
```python
from app.routers import admin
```

**수정 후**:
```python
from app.routers import admin, products
```

(그리고 `app.include_router(admin.router)` 다음 줄에 `app.include_router(products.router)` 추가)

- [ ] **Step 7: 통과 확인** — Run: `pytest tests/test_products_service.py -v` → PASS

- [ ] **Step 8: 커밋**

```bash
git add backend/app/schemas/product.py backend/app/services/products.py backend/app/routers/products.py backend/app/main.py backend/tests/test_products_service.py
git commit -m "feat(products): 상품 단건 등록 (FR-2.1)"
```

---

### Task 9: 상품 수정/삭제/보관 (FR-2.4)

**Files:**
- Modify: `backend/app/services/products.py`
- Modify: `backend/app/routers/products.py`
- Test: `backend/tests/test_product_archive.py`

**Model**: sonnet

- [ ] **Step 1: 실패 테스트 작성** — `backend/tests/test_product_archive.py`

```python
from app.services.products import archive_product

class FakeRepo:
    def __init__(self): self.patch=None
    def update_product(self, pid, patch): self.patch={"id":pid, **patch}; return self.patch

def test_archive_sets_status_archived():
    repo = FakeRepo()
    out = archive_product(repo, "p1")
    assert out["status"] == "archived"
```

- [ ] **Step 2: 실패 확인** — Run: `pytest tests/test_product_archive.py -v` → FAIL

- [ ] **Step 3: 서비스 확장** — `backend/app/services/products.py` 끝에 추가

**수정 후**:
```python
def update_product(repo, product_id: str, patch: dict) -> dict:
    return repo.update_product(product_id, patch)


def archive_product(repo, product_id: str) -> dict:
    return repo.update_product(product_id, {"status": "archived"})
```

- [ ] **Step 4: 라우터 확장 + repo update 메서드** — `SupabaseProductRepo`에 메서드 추가 + 엔드포인트

**수정 후**:
```python
    def update_product(self, pid, patch):
        return self.sb.table("products").update(patch).eq("id", pid).execute().data[0]


@router.patch("/{pid}")
def patch_product(pid: str, patch: dict, user: CurrentUser = Depends(get_current_user)):
    require_approved(user); require_role("wholesaler")(user)
    return SupabaseProductRepo().update_product(pid, patch)  # RISK(side-effect): 소유 org 검증 필요


@router.delete("/{pid}")
def delete_product(pid: str, user: CurrentUser = Depends(get_current_user)):
    require_approved(user); require_role("wholesaler")(user)
    return SupabaseProductRepo().update_product(pid, {"status": "archived"})
```

- [ ] **Step 5: 통과 확인** — Run: `pytest tests/test_product_archive.py -v` → PASS

- [ ] **Step 6: 커밋**

```bash
git add backend/app/services/products.py backend/app/routers/products.py backend/tests/test_product_archive.py
git commit -m "feat(products): 수정/삭제/보관 (FR-2.4)"
```

---

### Task 10: 표준 엑셀 템플릿 파서 (FR-2.2)

**Files:**
- Create: `backend/app/services/excel_parse.py`
- Create: `backend/tests/fixtures/template_sample.xlsx` (테스트 픽스처)
- Test: `backend/tests/test_excel_parse.py`

**Model**: sonnet

- [ ] **Step 1: 실패 테스트 작성** — `backend/tests/test_excel_parse.py`

```python
import openpyxl
from app.services.excel_parse import parse_template_rows, TEMPLATE_COLUMNS

def _make_xlsx(tmp_path, rows):
    wb = openpyxl.Workbook(); ws = wb.active
    ws.append(TEMPLATE_COLUMNS)
    for r in rows: ws.append(r)
    p = tmp_path / "t.xlsx"; wb.save(p); return p

def test_parse_valid_rows(tmp_path):
    p = _make_xlsx(tmp_path, [["1001","린넨셔츠","화이트","F","12000","29000"]])
    parsed = parse_template_rows(str(p))
    assert parsed.rows[0]["source_p_number"] == "1001"
    assert parsed.rows[0]["wholesale_price"] == 12000
    assert parsed.errors == []

def test_parse_missing_price_is_error(tmp_path):
    p = _make_xlsx(tmp_path, [["1002","바지","블랙","L","","20000"]])
    parsed = parse_template_rows(str(p))
    assert parsed.errors and parsed.errors[0]["row"] == 2
```

- [ ] **Step 2: 실패 확인** — Run: `pytest tests/test_excel_parse.py -v` → FAIL

- [ ] **Step 3: 파서 작성** (new file: `backend/app/services/excel_parse.py`)

```python
from dataclasses import dataclass, field
import openpyxl

TEMPLATE_COLUMNS = ["품번", "상품명", "색상", "사이즈", "도매가", "판매가"]
_KEY = {"품번": "source_p_number", "상품명": "item_name", "색상": "color",
        "사이즈": "size", "도매가": "wholesale_price", "판매가": "retail_price"}


@dataclass
class ParseResult:
    rows: list[dict] = field(default_factory=list)
    errors: list[dict] = field(default_factory=list)


def parse_template_rows(path: str) -> ParseResult:
    wb = openpyxl.load_workbook(path, read_only=True)
    ws = wb.active
    res = ParseResult()
    for i, row in enumerate(ws.iter_rows(min_row=2, values_only=True), start=2):
        rec = {_KEY[c]: (row[j] if j < len(row) else None) for j, c in enumerate(TEMPLATE_COLUMNS)}
        try:
            rec["wholesale_price"] = int(rec["wholesale_price"])
            rec["retail_price"] = int(rec["retail_price"]) if rec["retail_price"] not in (None, "") else None
            if not rec["source_p_number"] or not rec["item_name"]:
                raise ValueError("필수값 누락")
            res.rows.append(rec)
        except (TypeError, ValueError) as e:
            res.errors.append({"row": i, "reason": str(e), "raw": list(row)})
    return res
```

- [ ] **Step 4: 통과 확인** — Run: `pytest tests/test_excel_parse.py -v` → PASS

- [ ] **Step 5: 커밋**

```bash
git add backend/app/services/excel_parse.py backend/tests/test_excel_parse.py
git commit -m "feat(upload): 표준 엑셀 템플릿 파서 + 행 검증 (FR-2.2)"
```

---

### Task 11: 이미지 자동 매칭 로직 (FR-2.3)

**Files:**
- Create: `backend/app/services/image_match.py`
- Test: `backend/tests/test_image_match.py`

**Model**: sonnet

- [ ] **Step 1: 실패 테스트 작성** — `backend/tests/test_image_match.py`

```python
from app.services.image_match import match_filename_to_product

def test_match_by_source_p_number():
    products = {"1001": "p1", "1002": "p2"}
    assert match_filename_to_product("1001.jpg", products) == "p1"
    assert match_filename_to_product("1001_main.png", products) == "p1"

def test_no_match_returns_none():
    assert match_filename_to_product("zzz.jpg", {"1001": "p1"}) is None
```

- [ ] **Step 2: 실패 확인** — Run: `pytest tests/test_image_match.py -v` → FAIL

- [ ] **Step 3: 매칭 로직 작성** (new file: `backend/app/services/image_match.py`)

```python
import re
from pathlib import Path


def match_filename_to_product(filename: str, products_by_pnum: dict[str, str]) -> str | None:
    """파일명에서 품번 토큰을 추출해 products_by_pnum(source_p_number -> product_id)와 매칭."""
    stem = Path(filename).stem
    tokens = re.split(r"[_\-\s]", stem)
    for tok in [stem, *tokens]:
        if tok in products_by_pnum:
            return products_by_pnum[tok]
    return None
```

- [ ] **Step 4: 통과 확인** — Run: `pytest tests/test_image_match.py -v` → PASS

- [ ] **Step 5: 커밋**

```bash
git add backend/app/services/image_match.py backend/tests/test_image_match.py
git commit -m "feat(upload): 이미지 파일명→품번 자동 매칭 (FR-2.3)"
```

---

### Task 12: 가격 노출 리졸버 (FR-5.2, 핵심)

**Files:**
- Create: `backend/app/services/pricing.py`
- Test: `backend/tests/test_pricing.py`

**Model**: sonnet

- [ ] **Step 1: 실패 테스트 작성** — `backend/tests/test_pricing.py`

```python
import pytest
from app.services.pricing import visible_price, PriceForbidden

SKU = {"wholesale_price": 12000, "retail_price": 29000, "product_org": "org-1"}

def test_independent_seller_sees_wholesale():
    assert visible_price("retail_seller", "independent", SKU)["price"] == 12000

def test_agency_affiliated_seller_sees_none():
    assert visible_price("retail_seller", "agency_affiliated", SKU)["price"] is None

def test_agency_sees_retail():
    assert visible_price("agency", None, SKU)["price"] == 29000

def test_wholesaler_owner_sees_both():
    out = visible_price("wholesaler", None, SKU, viewer_org="org-1")
    assert out["wholesale_price"] == 12000 and out["retail_price"] == 29000

def test_unknown_role_gets_none():
    assert visible_price("guest", None, SKU)["price"] is None
```

- [ ] **Step 2: 실패 확인** — Run: `pytest tests/test_pricing.py -v` → FAIL

- [ ] **Step 3: 리졸버 작성** (new file: `backend/app/services/pricing.py`)

```python
class PriceForbidden(Exception):
    pass


def visible_price(role: str, seller_type: str | None, sku: dict, viewer_org: str | None = None) -> dict:
    """역할×seller_type 기준 노출 가격 결정 — tech-design §3.10."""
    if role == "retail_seller" and seller_type == "independent":
        return {"price": sku["wholesale_price"]}
    if role == "retail_seller" and seller_type == "agency_affiliated":
        return {"price": None}  # 가격 미노출
    if role == "agency":
        return {"price": sku["retail_price"]}
    if role == "wholesaler" and viewer_org == sku.get("product_org"):
        return {"wholesale_price": sku["wholesale_price"], "retail_price": sku["retail_price"]}
    if role == "admin":
        return {"wholesale_price": sku["wholesale_price"], "retail_price": sku["retail_price"]}
    return {"price": None}
```

- [ ] **Step 4: 통과 확인** — Run: `pytest tests/test_pricing.py -v` → PASS

- [ ] **Step 5: 커밋**

```bash
git add backend/app/services/pricing.py backend/tests/test_pricing.py
git commit -m "feat(catalog): 역할별 가격 노출 리졸버 (FR-5.2)"
```

---

### Task 13: QR 생성 + 공개 카드 데이터 (FR-4)

**Files:**
- Create: `backend/app/services/qr.py`
- Create: `backend/app/routers/public.py`
- Test: `backend/tests/test_qr.py`

**Model**: sonnet

- [ ] **Step 1: 실패 테스트 작성** — `backend/tests/test_qr.py`

```python
from app.services.qr import qr_target_url, generate_qr_png

def test_qr_target_url():
    assert qr_target_url("EZM-000001", "https://shop.ezmerce.io") == "https://shop.ezmerce.io/p/EZM-000001"

def test_generate_qr_png_returns_png_bytes():
    data = generate_qr_png("https://x/p/EZM-1")
    assert data[:8] == b"\x89PNG\r\n\x1a\n"  # PNG 시그니처
```

- [ ] **Step 2: 실패 확인** — Run: `pytest tests/test_qr.py -v` → FAIL

- [ ] **Step 3: QR 서비스 작성** (new file: `backend/app/services/qr.py`)

```python
import io
import qrcode


def qr_target_url(platform_code: str, base_url: str) -> str:
    return f"{base_url.rstrip('/')}/p/{platform_code}"


def generate_qr_png(url: str) -> bytes:
    img = qrcode.make(url)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()
```

- [ ] **Step 4: 공개 라우터 작성** (new file: `backend/app/routers/public.py`)

```python
from fastapi import APIRouter, HTTPException
from fastapi.responses import Response
from app.core.config import get_settings
from app.core.supabase import get_supabase
from app.services.qr import qr_target_url, generate_qr_png

router = APIRouter(tags=["public"])


@router.get("/qr/{platform_code}.png")
def qr_png(platform_code: str):
    url = qr_target_url(platform_code, get_settings().public_base_url)
    return Response(content=generate_qr_png(url), media_type="image/png")


@router.get("/p/{platform_code}")
def product_card(platform_code: str):
    sb = get_supabase()
    row = sb.table("products").select(
        "platform_code,item_name,fabric_composition,origin,representative_image_url"
    ).eq("platform_code", platform_code).eq("status", "active").single().execute().data
    if not row:
        raise HTTPException(404, "not found")
    return row  # RISK(side-effect): 공개 링크 — 가격 필드 절대 포함 금지
```

- [ ] **Step 5: main.py 등록** — `from app.routers import admin, products, public` + `app.include_router(public.router)`

- [ ] **Step 6: 통과 확인** — Run: `pytest tests/test_qr.py -v` → PASS

- [ ] **Step 7: 커밋**

```bash
git add backend/app/services/qr.py backend/app/routers/public.py backend/app/main.py backend/tests/test_qr.py
git commit -m "feat(qr): QR 생성 + 공개 상품 카드(가격 비노출) (FR-4)"
```

---

### Task 14: 엑셀 출력 + QR 이미지 삽입 (FR-3)

**Files:**
- Create: `backend/app/services/excel_export.py`
- Test: `backend/tests/test_excel_export.py`

**Model**: sonnet

- [ ] **Step 1: 실패 테스트 작성** — `backend/tests/test_excel_export.py`

```python
import openpyxl
from app.services.excel_export import build_catalog_xlsx

def test_export_has_qr_column_last(tmp_path):
    items = [{"platform_code": "EZM-000001", "item_name": "린넨셔츠", "price": 12000}]
    out = tmp_path / "out.xlsx"
    build_catalog_xlsx(items, str(out), base_url="https://x")
    wb = openpyxl.load_workbook(out)
    ws = wb.active
    headers = [c.value for c in ws[1]]
    assert headers[-1] == "QR"            # 최우측 열이 QR (FR-3.2)
    assert ws.cell(row=2, column=1).value == "EZM-000001"
    assert len(ws._images) == 1           # QR 이미지 1개 삽입됨
```

- [ ] **Step 2: 실패 확인** — Run: `pytest tests/test_excel_export.py -v` → FAIL

- [ ] **Step 3: 출력 서비스 작성** (new file: `backend/app/services/excel_export.py`)

```python
import io
import openpyxl
from openpyxl.drawing.image import Image as XLImage
from app.services.qr import qr_target_url, generate_qr_png

HEADERS = ["품번", "상품명", "가격", "QR"]


def build_catalog_xlsx(items: list[dict], out_path: str, base_url: str) -> str:
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.append(HEADERS)
    for i, it in enumerate(items, start=2):
        ws.cell(row=i, column=1, value=it["platform_code"])
        ws.cell(row=i, column=2, value=it["item_name"])
        ws.cell(row=i, column=3, value=it.get("price"))
        png = generate_qr_png(qr_target_url(it["platform_code"], base_url))
        img = XLImage(io.BytesIO(png)); img.width = img.height = 64
        ws.add_image(img, f"D{i}")        # 최우측 열(QR)에 삽입
        ws.row_dimensions[i].height = 50
    wb.save(out_path)
    return out_path
```

- [ ] **Step 4: 통과 확인** — Run: `pytest tests/test_excel_export.py -v` → PASS

- [ ] **Step 5: 커밋**

```bash
git add backend/app/services/excel_export.py backend/tests/test_excel_export.py
git commit -m "feat(export): QR 삽입 카탈로그 엑셀 출력 (FR-3)"
```

---

### Task 15: 폐쇄형 카탈로그 엔드포인트 (FR-5.1/5.3 통합)

**Files:**
- Create: `backend/app/routers/catalog.py`
- Test: `backend/tests/test_catalog_shaping.py`

**Model**: sonnet

- [ ] **Step 1: 실패 테스트 작성** — `backend/tests/test_catalog_shaping.py`

```python
from app.routers.catalog import shape_catalog_item
from app.schemas.auth import CurrentUser

ROW = {"platform_code":"EZM-1","item_name":"셔츠",
       "skus":[{"color":"화이트","size":"F","wholesale_price":12000,"retail_price":29000,"product_org":"org-9"}]}

def test_agency_affiliated_seller_item_has_no_price():
    u = CurrentUser(id="u", role="retail_seller", status="approved", seller_type="agency_affiliated")
    item = shape_catalog_item(ROW, u)
    assert item["skus"][0]["price"] is None

def test_independent_seller_sees_wholesale():
    u = CurrentUser(id="u", role="retail_seller", status="approved", seller_type="independent")
    item = shape_catalog_item(ROW, u)
    assert item["skus"][0]["price"] == 12000
```

- [ ] **Step 2: 실패 확인** — Run: `pytest tests/test_catalog_shaping.py -v` → FAIL

- [ ] **Step 3: 카탈로그 라우터 작성** (new file: `backend/app/routers/catalog.py`)

```python
from fastapi import APIRouter, Depends, Query
from app.core.auth import get_current_user
from app.core.rbac import require_approved
from app.core.supabase import get_supabase
from app.schemas.auth import CurrentUser
from app.services.pricing import visible_price

router = APIRouter(prefix="/catalog", tags=["catalog"])


def shape_catalog_item(row: dict, user: CurrentUser) -> dict:
    shaped_skus = []
    for sku in row.get("skus", []):
        price = visible_price(user.role, user.seller_type, sku, viewer_org=user.organization_id)
        shaped_skus.append({"color": sku["color"], "size": sku["size"], **price})
    return {"platform_code": row["platform_code"], "item_name": row["item_name"], "skus": shaped_skus}


@router.get("")
def list_catalog(
    user: CurrentUser = Depends(get_current_user),
    limit: int = Query(default=30, le=100),
    cursor: str | None = None,
):
    require_approved(user)  # 미승인 → 403 (FR-5.1 / AC-6)
    sb = get_supabase()
    q = sb.table("products").select(
        "platform_code,item_name,product_skus(color,size,wholesale_price,retail_price,wholesaler_org_id)"
    ).eq("status", "active").order("created_at").limit(limit)
    if cursor:
        q = q.gt("created_at", cursor)
    rows = q.execute().data
    return {"items": [shape_catalog_item(_normalize(r), user) for r in rows]}


def _normalize(r: dict) -> dict:
    skus = [{**s, "product_org": s.get("wholesaler_org_id")} for s in r.get("product_skus", [])]
    return {"platform_code": r["platform_code"], "item_name": r["item_name"], "skus": skus}
```

- [ ] **Step 4: main.py 등록** — `from app.routers import admin, products, public, catalog` + `app.include_router(catalog.router)`

- [ ] **Step 5: 통과 확인** — Run: `pytest tests/test_catalog_shaping.py -v` → PASS

- [ ] **Step 6: 전체 테스트 회귀**

Run: `cd backend && source .venv/bin/activate && pytest -v`
Expected: 전체 PASS

- [ ] **Step 7: 커밋**

```bash
git add backend/app/routers/catalog.py backend/app/main.py backend/tests/test_catalog_shaping.py
git commit -m "feat(catalog): 폐쇄형 카탈로그 + 역할별 가격 셰이핑 (FR-5)"
```

---

## 2. 위험 코드 지점

- `backend/app/core/supabase.py:get_supabase` — **side-effect**: service role 키로 RLS 전면 우회. mitigation: 키는 백엔드 env only, 프론트 전달 절대 금지(Task 1 CORS도 운영 시 화이트리스트).
- `backend/app/services/platform_code.py:next_platform_code` — **race**: 동시 등록 시 품번 중복. mitigation: Postgres SEQUENCE `nextval` 사용(앱 카운터 금지).
- `backend/app/services/pricing.py:visible_price` — **breaking**: 분기 누락 시 가격 오노출(특히 agency_affiliated). mitigation: 역할×seller_type 전수 테스트(Task 12) + 기본 반환 `{"price": None}` 안전값.
- `backend/app/routers/public.py:product_card` — **side-effect**: 공개 링크에 가격 노출 위험. mitigation: select 컬럼에서 가격 필드 원천 제외.
- `backend/app/routers/products.py:patch_product` — **side-effect**: 타 조직 상품 수정 가능. mitigation: 소유 `organization_id` 일치 검증 추가(실행 시 보강).
- `backend/app/routers/catalog.py:list_catalog` — **breaking**: 미승인 접근 차단 실패 시 폐쇄성 훼손. mitigation: `require_approved` 최상단 + AC-6 테스트.

## 3. 롤백 전략

- **Code**: `commit_policy: per-task` — task 단위 원자 커밋. 문제 task는 `git revert <SHA>`.
- **DB**: 마이그레이션 역방향 스크립트 `backend/migrations/2026-06-03_v2_core_down.sql`(DROP TABLE/TYPE/SEQUENCE)를 실행 시 함께 작성. PoC는 Supabase 프로젝트 리셋도 가능.
- **Config**: CORS/키는 env 토글. 카탈로그 노출은 `require_approved`로 사실상 기능 플래그 역할.

---
## 변경이력
<!-- change-history skill auto-appends entries here, oldest first -->

### [2026-06-03 17:25] [구현계획서-수정]
- **id**: CH-20260603-003
- **이유**: tech-design 기반 1차 백엔드 구현계획서 최초 작성 (15 task TDD)
- **무엇이**: ezmerce-v2-backend-implementation-plan.md 전체 (Task 1~15, §2 위험 6건, §3 롤백)
- **영향범위**: backend/ 신규 구축 예정, setup_v2_schema.sql deprecate 예정. 빌드 선행: backend/.venv에 PyJWT·pydantic-settings 설치 완료
- **연관 항목**: CH-20260603-001(requirements), CH-20260603-002(tech-design)

### [2026-06-03 17:42] [코드-수정] (batch: tasks 1..15)
- **id**: CH-20260603-004
- **이유**: 1차 백엔드 전체 구현 (js-super-sub-driven 서브에이전트 wave 실행 — Wave1 Foundation+순수서비스, Wave2 상품/QR/관리자/카탈로그, Finalize 라우터 와이어링)
- **무엇이**: backend/app/(core/{config,supabase,auth,rbac}, schemas/{auth,product}, services/{platform_code,excel_parse,image_match,pricing,products,accounts,qr,excel_export}, routers/{admin,products,public,catalog}, main.py), backend/migrations/2026-06-03_v2_core.sql, backend/conftest.py, backend/tests/(11개), setup_v2_schema.sql(deprecate)
- **영향범위**: backend/ 전부 신규(깨질 호출부 없음). setup_v2_schema.sql deprecate 주석. 프론트(apps/*)는 미연동(다음 Phase).
- **위험 카테고리**: side-effect(service role 키 RLS 우회·공개카드 가격노출·patch 소유검증 미비), breaking(CORS 와일드카드), race(platform_code → SEQUENCE로 완화)
- **task별 세부 (15건, 코드는 git show로 조회)**:
  - T1 FastAPI 스켈레톤+health — `16c6fa3`
  - T3 Supabase 클라이언트+Repository — `1b6e87b`
  - T4 JWT 인증 (verify_aud=False 보정) — `1de4f44`
  - T5 RBAC 가드 — `a9b914f`
  - T7 platform_code 생성기 — `7a8fe22`
  - T10 엑셀 파서 — `af7a6c4`
  - T11 이미지 매칭 — `ea04323`
  - T12 가격 리졸버 — `8d40a01`
  - T2 DB 마이그레이션 — `8c6937e`
  - T6 관리자 승인 — `b0ed0b7`
  - T8+T9 상품 CRUD — `bab826e`
  - T13 QR+공개카드 — `1c69191`
  - T14 엑셀 출력 — `319b3e0`
  - T15 카탈로그 — `daeb360`
  - 라우터 와이어링 — `c9309df`
- **빌드 중 보정 (plan deviation)**:
  - `auth.py` decode_jwt: `audience="authenticated"` → `options={"verify_aud": False}` (단위테스트 토큰에 aud 없음)
  - backend/.venv에 supabase-py 실제 설치 (find_spec 오탐 → 서브에이전트가 스텁 생성했던 것을 제거하고 진짜 라이브러리로 교체)
- **미구현 갭 (계획 §4 고지대로)**: 업로드 오케스트레이션 엔드포인트(POST /uploads/excel·/images, /uploads/{job}/match + upload_jobs 영속화), POST /auth/register, GET /catalog/export.xlsx 라우트. 서비스/순수로직은 구현됨(excel_parse·image_match·excel_export), 라우트 와이어링만 미완.
- **연관 commits**: 16c6fa3..c9309df (15 commits)
- **연관 항목**: CH-20260603-003(구현계획서)
- **변경 전/후 코드**: 생략 — `git show <SHA>` 로 조회

### [2026-06-03 20:59] [코드-수정] (propagation: price_visibility)
- **id**: CH-20260603-007
- **이유**: 관리자 설정형 가격 노출(price_visibility) 도입 — 개발 정의서 "소매 업체별 가격 보기 권한 설정" 의도 반영
- **무엇이**: migrations/2026-06-03_v2_core_02_price_visibility.sql(신규), app/services/pricing.py(리졸버+_default_visibility), app/schemas/auth.py(CurrentUser.price_visibility), app/routers/catalog.py(셰이핑에 전달), app/routers/admin.py(set price-visibility 엔드포인트), tests/test_pricing.py(override 4건)
- **영향범위**: 가격 노출 경로 전반. 기존 동작은 price_visibility=None 폴백으로 보존(기존 26 테스트 무변경) → 신규 4건 추가 → **30 passed**
- **위험 카테고리**: side-effect (가격 노출 정책 변경 — 폴백으로 하위호환 유지)
- **변경 전/후 코드**: 생략 — `git show` 로 조회
- **연관 항목**: CH-20260603-005 (요구사항), CH-20260603-006 (개발방향)

### [2026-06-03 21:14] [코드-수정] (organizations → wholesalers/agencies 분리)
- **id**: CH-20260603-009
- **이유**: 도매업체/에이전시 별도 테이블 분리 반영 (CH-008 개발방향). FK 타입 안전화.
- **무엇이**: migrations/2026-06-03_v2_core.sql(organizations→wholesalers+agencies, org_type 제거, profiles organization_id→wholesaler_id+agency_id, products/images/jobs wholesaler_org_id→wholesaler_id, RLS), app/schemas/auth.py(CurrentUser wholesaler_id+agency_id), app/routers/catalog.py·products.py, app/services/products.py, tests/test_products_service.py
- **영향범위**: 상품 소유/카탈로그/가격 경로. 앱 14 라우트 정상, **30 passed** 유지. Task 2의 구 DDL(organizations)은 본 변경으로 supersede.
- **위험 카테고리**: breaking (스키마 컬럼/테이블명 변경 — 단, DB 미적용 상태라 base 마이그레이션 직접 정리. 라이브 적용본 없었음)
- **변경 전/후 코드**: 생략 — `git show` 로 조회
- **연관 항목**: CH-20260603-008 (개발방향)

### [2026-06-03 21:52] [코드-수정] (soft delete 전면 도입)
- **id**: CH-20260603-012
- **이유**: hard DELETE 대신 soft delete (deleted_at) 전 테이블 도입 + soft-cascade 트리거로 CASCADE 대체
- **무엇이**: migrations/2026-06-03_v2_core_03_soft_delete.sql(신규 — deleted_at 7테이블, 부분 유니크, soft_cascade_product/wholesaler 트리거, RLS 필터), app/services/products.py(soft_delete_product), app/routers/products.py(DELETE→deleted_at), app/routers/catalog.py(조회 deleted_at 필터), tests/test_product_archive.py(soft delete 테스트), **루트 CLAUDE.md 신규(DB 규칙 — 삭제 정책 문서화)**
- **영향범위**: 삭제/조회 경로 전반. 앱 14 라우트 정상, **31 passed**. products UNIQUE → 부분 인덱스 전환.
- **위험 카테고리**: breaking (UNIQUE→부분 인덱스), side-effect (트리거 cascade — 부모 삭제 시 자식 전파)
- **변경 전/후 코드**: 생략 — `git show` 로 조회
- **연관 항목**: CH-20260603-010 (요구사항), CH-20260603-011 (개발방향)

### [2026-06-03 21:58] [코드-수정] (엔티티 모델 레이어 추가)
- **id**: CH-20260603-013
- **이유**: 테이블당 엔티티 모델이 없어 dict 로만 다루던 것을 타입 안전 Pydantic 모델로 보강 (tech-design §5 schemas 자리 채움)
- **무엇이**: app/schemas/enums.py(신규 — 7 ENUM), app/schemas/entities.py(신규 — Wholesaler/Agency/Profile/Product/ProductSku/ProductImage/UploadJob, deleted_at·wholesaler_id/agency_id·price_visibility 반영), tests/test_entities.py(신규 4건)
- **영향범위**: additive — 기존 코드/동작 무변경(서비스·라우터의 dict 사용은 그대로). 전체 **35 passed**. 서비스/응답에서 모델 채택은 후속 점진 적용.
- **위험 카테고리**: none (순수 추가)
- **변경 전/후 코드**: 생략 — `git show` 로 조회
- **연관 항목**: CH-20260603-008 (도매/에이전시 분리), CH-20260603-012 (soft delete)

### [2026-06-03 22:04] [코드-수정] (엔티티 → app/entities/ 분리)
- **id**: CH-20260603-014
- **이유**: `schemas`는 DTO 개념 — 도메인 엔티티/ENUM 을 `app/entities/`로 분리 (레이어 혼동 방지)
- **무엇이**: app/entities/{__init__,enums,models}.py 신규(schemas/enums.py + entities.py 이동), app/schemas/에서 제거(이제 DTO만: auth/product), tests/test_entities.py import 갱신, CLAUDE.md 레이어 규칙 추가
- **영향범위**: move/additive — 동작 무변경, **35 passed**. 사용처는 test_entities.py뿐이라 안전.
- **위험 카테고리**: none
- **연관 항목**: CH-20260603-013 (엔티티 모델 최초 추가)

### [2026-06-03 22:15] [코드-수정] (감사 컬럼 + 루트 uv 정리)
- **id**: CH-20260603-017
- **이유**: created_by/updated_by + updated_at 자동갱신(핵심 도메인) 도입, 루트 Streamlit 시절 uv 잔재 정리
- **무엇이**: migrations/2026-06-03_v2_core_04_audit.sql(신규 — 감사 컬럼 + set_updated_at 트리거 7테이블), app/entities/models.py(감사 필드 추가), app/services/products.py + app/routers/products.py(register→created_by, patch/delete→updated_by wiring), tests/test_products_service.py·test_product_archive.py(감사 assert); **루트 pyproject.toml/uv.lock/requirements.txt 삭제**(Python 프로젝트는 backend 단독)
- **영향범위**: 앱 14 라우트 정상, **35 passed**. created_by/updated_by FK→profiles, updated_at 트리거 전 테이블. 루트 Python 매니페스트 제거.
- **위험 카테고리**: side-effect (updated_at 트리거), breaking (루트 deps 매니페스트 제거 — backend로 일원화됨)
- **변경 전/후 코드**: 생략 — `git show` 로 조회
- **연관 항목**: CH-20260603-015 (요구사항), CH-20260603-016 (개발방향)

### [2026-06-03 22:38] [코드-수정] (JWT 검증 JWKS 전환)
- **id**: CH-20260603-019
- **이유**: Supabase 비대칭 JWT(ES256) 대응 — JWKS 공개키 검증 도입(HS256은 레거시 폴백 유지)
- **무엇이**: app/core/auth.py(verify_supabase_jwt + PyJWKClient, get_current_user 가 사용), app/core/config.py(supabase_jwks_url 파생, jwt_secret 선택), backend/pyproject.toml(pyjwt→pyjwt[crypto]) + uv.lock, tests/test_auth_dep.py(JWKS garbage 테스트), backend/.env.example 문구 갱신
- **영향범위**: 인증 경로. **36 passed**. decode_jwt(HS256)은 레거시 헬퍼로 유지.
- **위험 카테고리**: breaking (검증 알고리즘 변경 — 신규 Supabase 프로젝트 정합)
- **변경 전/후 코드**: 생략 — `git show` 로 조회
- **연관 항목**: CH-20260603-018 (개발방향)

### [2026-06-04 00:10] [코드-수정] (갭 A: 카탈로그 엑셀 출력 라우트 와이어링, Task 14/15 잔여)
- **id**: CH-20260604-020
- **이유**: 계획 §4 미구현 갭 — excel_export 서비스는 있으나 라우트 미연결. `GET /catalog/export.xlsx` 추가(FR-3).
- **무엇이**: app/services/excel_export.py(_build_workbook 추출 + catalog_xlsx_bytes 메모리 생성 추가, build_catalog_xlsx 동작 유지), app/routers/catalog.py(_query_catalog_rows 공용화, _export_row, GET /catalog/export.xlsx — 승인가드+역할별 가격 셰이핑+QR), tests/test_catalog_export.py(신규 3)
- **영향범위**: 카탈로그 경로. **39 passed**(+3). 라우트 16개. 엑셀 출력은 _EXPORT_MAX=1000 상한(페이지네이션 미적용, 위험 주석).
- **위험 카테고리**: scale (대량 카탈로그 시 상한 누락), non-breaking
- **변경 전/후 코드**: 생략 — `git show` 로 조회
- **연관 항목**: CH-20260603-019 (직전 코드 변경), 계획 Task 14(엑셀출력)·Task 15(카탈로그)
