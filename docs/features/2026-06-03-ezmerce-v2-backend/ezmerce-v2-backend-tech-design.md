# 기술 설계서: ezmerce v2 백엔드 (1차 — 상품·권한 코어)

> **상위 문서**: [ezmerce-v2-backend-requirements.md](./ezmerce-v2-backend-requirements.md) (승인됨, CH-20260603-001)
> **다음 단계**: `writing-plans` (`/write-plan`) — 본 설계를 단계별 TDD 구현계획서로 분해.
> **본 문서 범위**: 백엔드 아키텍처 + **DB 스키마(데이터 모델)가 핵심 산출물** + API 윤곽 + 핵심 결정/대안 + 위험 + 테스트 전략.

---

## 1. 아키텍처 개요

```
[apps/web (Next.js)]   [apps/mobile (Expo)]
          \                 /
           \   HTTPS/JWT   /
            v             v
        ┌──────────────────────────┐
        │   FastAPI (backend/)      │  ← 인증 검증, RBAC, 가격노출 결정(권위),
        │   Python 3.12             │    엑셀 파싱/출력, QR 생성, 이미지 매칭
        └──────────────────────────┘
              │ service role        │ verify JWT
              v                     v
   ┌─────────────────┐   ┌──────────────────┐   ┌──────────────┐
   │ Supabase Postgres│   │ Supabase Auth     │   │ Supabase     │
   │ (스키마 + RLS)   │   │ (이메일 로그인)   │   │ Storage      │
   └─────────────────┘   └──────────────────┘   │ (이미지/엑셀) │
                                                 └──────────────┘
```

- **프론트엔드는 Supabase에 직접 붙지 않고 FastAPI를 경유**한다. 이유: 엑셀 파싱(`pandas`/`openpyxl`)·QR 생성(`qrcode`/`Pillow`)·엑셀 QR 삽입은 서버에서만 가능하고, **가격 노출 결정(NFR-2)은 반드시 서버 권위**여야 하기 때문.
- **인증**: 프론트가 Supabase Auth로 로그인 → JWT 획득 → FastAPI 호출 시 `Authorization: Bearer <jwt>` → FastAPI가 JWT 검증 + `profiles`에서 역할/승인상태 조회.
- **DB 접근**: FastAPI는 Supabase **service role 키**로 Postgres 접근(RLS 우회). RLS는 직접 접근 대비 **방어선(defense-in-depth)**으로 유지.

## 2. 영향 컴포넌트

| 컴포넌트 | 현재 | 1차 작업 |
|---|---|---|
| `backend/` (FastAPI) | 비어있음(`__pycache__`만) | **신규 구축** — 라우터(auth/products/uploads/catalog/qr/export), 서비스 계층, Supabase 클라이언트, Pydantic 스키마 |
| `setup_v2_schema.sql` | products/product_skus 2개 + 전체허용 RLS | **전면 확장** → 본 문서 §3의 마이그레이션으로 대체 (계정/조직/이미지/업로드잡 추가, 품번 정규화, 가격 2종, RLS 재설계) |
| Supabase Storage | 미설정 | 버킷 2개: `product-images`, `excel-uploads` |
| `apps/web`, `apps/mobile` | v1 로그인리스 UI | (다음 Phase에서 FastAPI 연동 — 본 1차는 백엔드 중심) |

## 3. 데이터 모델 (DB 스키마) — 핵심 산출물

### 3.1 ER 관계 요약

```
auth.users ─1:1─ profiles ─*:1─ wholesalers   (도매 직원)
                    └──────────*:1─ agencies   (에이전시 직원 / 에이전시 소속 셀러를 관리)

wholesalers ─1:*─ products ─1:*─ product_skus (도매가/판매가/재고)
                     │
                     └─1:*─ product_images (matched|unmatched)

wholesalers ─1:*─ upload_jobs (엑셀 대량업로드 + 매칭 상태)
```

### 3.2 ENUM 타입

```sql
CREATE TYPE user_role        AS ENUM ('admin', 'wholesaler', 'retail_seller', 'agency');
CREATE TYPE account_status   AS ENUM ('pending', 'approved', 'rejected', 'suspended');
CREATE TYPE seller_type      AS ENUM ('agency_affiliated', 'independent'); -- retail_seller 전용
CREATE TYPE product_status   AS ENUM ('active', 'archived');
CREATE TYPE image_match      AS ENUM ('matched', 'unmatched');
CREATE TYPE upload_status    AS ENUM ('uploaded', 'parsing', 'needs_matching', 'completed', 'failed');
```

### 3.3 wholesalers / agencies (도매업체 · 에이전시 — 분리)

도매업체(상품을 *파는* 쪽)와 에이전시(셀러를 *관리하는* 쪽)는 다른 주체 → **별도 테이블**로 분리해 FK 타입 안전성과 의도를 확보한다.

```sql
CREATE TABLE public.wholesalers (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name        TEXT NOT NULL,
    biz_number  TEXT,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE public.agencies (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name        TEXT NOT NULL,
    biz_number  TEXT,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);
```

### 3.4 profiles (auth.users 1:1 확장 — 역할/승인)

```sql
CREATE TABLE public.profiles (
    id              UUID PRIMARY KEY REFERENCES auth.users(id) ON DELETE CASCADE,
    role            user_role NOT NULL,
    status          account_status NOT NULL DEFAULT 'pending',
    full_name       TEXT,
    phone           TEXT,
    wholesaler_id   UUID REFERENCES public.wholesalers(id) ON DELETE SET NULL,
        -- wholesaler 직원 → 소속 도매업체
    agency_id       UUID REFERENCES public.agencies(id) ON DELETE SET NULL,
        -- agency 직원 → 소속 에이전시 / retail_seller(agency_affiliated) → 자신을 관리하는 에이전시
        -- admin / independent seller → 둘 다 NULL
    seller_type     seller_type,              -- role='retail_seller' 일 때만 채움
    price_visibility price_visibility,        -- 관리자 설정형 가격 노출(NULL=미설정→seller_type 기본값 폴백). 델타 마이그레이션 02
    approved_at     TIMESTAMPTZ,
    approved_by     UUID REFERENCES public.profiles(id),
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),

    CONSTRAINT seller_type_only_for_retail CHECK (
        (role = 'retail_seller' AND seller_type IS NOT NULL)
        OR (role <> 'retail_seller' AND seller_type IS NULL)
    )
);
CREATE INDEX idx_profiles_role_status ON public.profiles(role, status);
CREATE INDEX idx_profiles_wholesaler ON public.profiles(wholesaler_id);
CREATE INDEX idx_profiles_agency ON public.profiles(agency_id);
```

### 3.5 products (상품 마스터 + 품번 정규화)

```sql
CREATE TABLE public.products (
    id                UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    wholesaler_id UUID NOT NULL REFERENCES public.wholesalers(id) ON DELETE CASCADE,
    platform_code     TEXT NOT NULL UNIQUE,    -- 품번 정규화: 플랫폼 글로벌 식별자 (예: EZM-000123)
    source_p_number   TEXT NOT NULL,           -- 도매업체 원본 품번 (보존)
    item_name         TEXT NOT NULL,
    fabric_composition TEXT,
    origin            TEXT,
    lead_time_days    TEXT,
    description       TEXT,
    representative_image_url TEXT,             -- 대표 이미지(매칭 후 채움)
    status            product_status NOT NULL DEFAULT 'active',  -- active|archived(보관)
    is_sold_out       BOOLEAN NOT NULL DEFAULT FALSE,
    created_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at        TIMESTAMPTZ NOT NULL DEFAULT now(),

    UNIQUE (wholesaler_id, source_p_number)  -- 같은 업체 내 원본품번 중복 방지
);
CREATE INDEX idx_products_org_status ON public.products(wholesaler_id, status);
```

> **품번 정규화(FR-2.5) 해법**: 충돌 위험은 두 축으로 차단 — ① 전 플랫폼 유니크인 `platform_code`(플랫폼이 발급, QR·카탈로그·엑셀의 기준 키), ② 업체 스코프 유니크 `UNIQUE(wholesaler_id, source_p_number)`. 서로 다른 업체가 같은 원본품번(예: "1001")을 써도 `platform_code`가 다르므로 섞이지 않는다. 발급 방식은 §6 핵심결정-2 참조.

### 3.6 product_skus (옵션·가격 2종·재고)

```sql
CREATE TABLE public.product_skus (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    product_id      UUID NOT NULL REFERENCES public.products(id) ON DELETE CASCADE,
    color           TEXT NOT NULL,
    size            TEXT NOT NULL,
    wholesale_price INTEGER NOT NULL,          -- 도매가 (라이브셀러 노출)
    retail_price    INTEGER,                   -- 판매가 (에이전시 노출)
    stock           INTEGER NOT NULL DEFAULT 0,-- 1차엔 차감 로직 없음(필드만 보유, Phase2 대비)
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),

    UNIQUE (product_id, color, size)
);
```

### 3.7 product_images (대량 업로드 + 매칭 보조)

```sql
CREATE TABLE public.product_images (
    id                UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    product_id        UUID REFERENCES public.products(id) ON DELETE CASCADE, -- NULL=미매칭
    wholesaler_id UUID NOT NULL REFERENCES public.wholesalers(id) ON DELETE CASCADE,
    storage_path      TEXT NOT NULL,           -- Supabase Storage 경로
    original_filename TEXT,                    -- 품번/이미지명 매칭 기준
    match_status      image_match NOT NULL DEFAULT 'unmatched',
    is_representative BOOLEAN NOT NULL DEFAULT FALSE,
    sort_order        INTEGER NOT NULL DEFAULT 0,
    created_at        TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_images_unmatched ON public.product_images(wholesaler_id, match_status);
```

> **매칭 흐름(FR-2.3)**: 업로드 시 `original_filename` ↔ `source_p_number`(또는 platform_code)로 자동 매칭 → 성공 시 `product_id` 연결 + `match_status='matched'`. 실패 건은 `unmatched`로 남아 **수작업 매칭 UI**가 `idx_images_unmatched`로 조회해 보정.

### 3.8 upload_jobs (엑셀 대량 업로드 잡)

```sql
CREATE TABLE public.upload_jobs (
    id                UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    wholesaler_id UUID NOT NULL REFERENCES public.wholesalers(id) ON DELETE CASCADE,
    created_by        UUID REFERENCES public.profiles(id),
    file_path         TEXT,                    -- 업로드된 엑셀 Storage 경로
    status            upload_status NOT NULL DEFAULT 'uploaded',
    total_rows        INTEGER DEFAULT 0,
    matched_rows      INTEGER DEFAULT 0,
    error_rows        INTEGER DEFAULT 0,
    error_detail      JSONB,                   -- 불일치/누락 상세(수작업 매칭 UI 입력)
    created_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
    completed_at      TIMESTAMPTZ
);
```

### 3.9 QR 코드 (FR-4) — 테이블 없이 규칙으로

- QR이 인코딩하는 대상 = **공개 상품 카드 URL**: `https://<domain>/p/<platform_code>`
- QR 이미지는 **요청 시 생성**(`qrcode`+`Pillow`). 엑셀 출력(FR-3.2) 시점에도 동일 함수로 생성해 셀에 삽입.
- 캐시가 필요하면 `products.qr_image_url`(생성본 Storage 경로)를 선택적으로 추가 — 1차는 온디맨드로 충분.
- `/p/<platform_code>` 공개 카드 페이지는 **가격 비노출**(공개 링크이므로 제품 정보만), 인스타 비율 카드.

### 3.10 가격 노출 결정 (FR-5.2) — 서버 권위 로직

DB 컬럼 자체를 숨기기보다 **FastAPI 응답 셰이핑**으로 처리(테스트·제어 용이). 노출 가격은 **관리자 설정 `price_visibility` 우선**, 미설정 시 `seller_type` 기준 기본값으로 폴백:

| 역할 | 기준 | 노출 가격 필드 |
|---|---|---|
| `wholesaler`(자기 조직) / `admin` | 관리뷰(고정) | 도매가 + 판매가 모두 |
| `retail_seller` / `agency` | `price_visibility`='wholesale' | `wholesale_price` |
| 〃 | ='retail' | `retail_price` |
| 〃 | ='none' 또는 미설정+기본 none | **없음 (price=null)** |
| 미승인/비로그인 | — | **접근 거부(403)** |

기본값 `_default_visibility`: independent→wholesale · agency_affiliated→none · agency→retail. 관리자가 `price_visibility`로 셀러별 override (FR-1.5).

의사코드:
```python
def visible_price(role, seller_type, sku, viewer_org=None, price_visibility=None):
    if role == 'wholesaler' and viewer_org == sku['product_org']:
        return {'wholesale_price': ..., 'retail_price': ...}   # 관리뷰
    if role == 'admin':
        return {'wholesale_price': ..., 'retail_price': ...}
    vis = price_visibility or _default_visibility(role, seller_type)   # 관리자 설정 우선
    if vis == 'wholesale': return {'price': sku['wholesale_price']}
    if vis == 'retail':    return {'price': sku['retail_price']}
    return {'price': None}
```

### 3.11 RLS 정책 (방어선)

FastAPI가 service role로 접근하므로 런타임 권위는 앱 계층이지만, 직접 접근 차단을 위해 RLS를 켠다. 헬퍼:

```sql
-- 현재 로그인 사용자의 역할/승인 조회 헬퍼
CREATE OR REPLACE FUNCTION public.current_profile()
RETURNS public.profiles LANGUAGE sql STABLE AS $$
  SELECT * FROM public.profiles WHERE id = auth.uid();
$$;

ALTER TABLE public.wholesalers    ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.agencies       ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.profiles       ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.products       ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.product_skus   ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.product_images ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.upload_jobs    ENABLE ROW LEVEL SECURITY;

-- profiles: 본인 행만 조회/수정
CREATE POLICY profiles_self_select ON public.profiles FOR SELECT USING (id = auth.uid());
CREATE POLICY profiles_self_update ON public.profiles FOR UPDATE USING (id = auth.uid());

-- products/skus/images: 승인된 사용자만 active 상품 조회
CREATE POLICY products_read_approved ON public.products FOR SELECT
  USING (status = 'active' AND (SELECT status FROM public.profiles WHERE id = auth.uid()) = 'approved');

-- products: 도매업체는 자기 조직 상품 CRUD
CREATE POLICY products_owner_write ON public.products FOR ALL
  USING (wholesaler_id = (SELECT wholesaler_id FROM public.profiles WHERE id = auth.uid()));
-- (skus/images/upload_jobs 도 동일 패턴 + 관리자 전체 권한 정책)
```

> 가격 컬럼 숨김은 RLS로 불가하므로 **반드시 FastAPI 응답 셰이핑(§3.10)으로 보장**. RLS는 "미승인 차단/타조직 쓰기 차단"의 보조선.

## 4. 외부 인터페이스 (API 윤곽)

> 상세 요청/응답 스키마는 write-plan에서 확정. 1차 엔드포인트 윤곽만.

| 메서드 | 경로 | 역할 | 설명 |
|---|---|---|---|
| POST | `/auth/register` | public | 가입 요청(상태 pending) |
| POST | `/admin/accounts/{id}/approve` `/reject` | admin | 계정 승인/거절 (FR-1.3) |
| POST | `/admin/accounts/{id}/price-visibility` | admin | 소매 셀러 가격 노출 설정 (FR-1.5) |
| GET | `/admin/accounts?status=pending` | admin | 승인 대기 목록 |
| POST | `/products` | wholesaler | 단건 등록 (FR-2.1) |
| PATCH/DELETE | `/products/{id}` | wholesaler | 수정/삭제/보관 (FR-2.4) |
| POST | `/uploads/excel` | wholesaler | 표준 템플릿 업로드→파싱 잡 생성 (FR-2.2) |
| POST | `/uploads/images` | wholesaler | 이미지 대량 업로드 (FR-2.2) |
| GET | `/uploads/{job}/unmatched` · POST `/uploads/{job}/match` | wholesaler | 수작업 매칭 (FR-2.3) |
| GET | `/catalog` | seller/agency(approved) | 폐쇄형 카탈로그 + 역할별 가격 (FR-5) |
| GET | `/catalog/export.xlsx` | seller/agency | QR 삽입 엑셀 다운로드 (FR-3) |
| GET | `/p/{platform_code}` | public | QR 카드 페이지 데이터(가격 비노출, FR-4.2) |
| GET | `/qr/{platform_code}.png` | public | QR 이미지 생성 (FR-4.1) |

## 5. 백엔드 구조(디렉터리 제안)

```
backend/
├── app/
│   ├── main.py                # FastAPI 앱 + 라우터 등록 + CORS
│   ├── core/ (config, supabase client, auth deps, rbac)
│   ├── schemas/ (pydantic)
│   ├── routers/ (auth, admin, products, uploads, catalog, qr, export)
│   └── services/ (excel_parse, excel_export, qr, image_match, pricing, platform_code)
├── migrations/2026-06-03_v2_core.sql   # §3 전체 DDL
└── tests/
```

## 6. 핵심 결정 (+대안)

1. **API 계층 = FastAPI 경유** (vs 프론트→Supabase 직결). 채택: 엑셀/QR Python 라이브러리 + 가격 권위가 서버 필수. 대안(직결+Edge Function) 기각: Python 라이브러리 활용 불가, 가격 권위 분산.
2. **품번 정규화 = 글로벌 `platform_code` + 업체 스코프 원본품번**. 발급: Postgres `SEQUENCE` 기반 `EZM-` 접두 zero-pad (원자적, 동시성 안전). 대안(복합키만) 기각: QR/카탈로그에 단일 글로벌 키 필요.
3. **가격 노출 = FastAPI 앱 계층 셰이핑** (vs Postgres 역할별 뷰/SECURITY DEFINER). 채택: PoC에서 테스트·제어 단순. RLS는 보조선.
4. **인증 = Supabase Auth + profiles 미러 테이블**. 대안(자체 인증) 기각: 재발명.
5. **wholesalers / agencies 테이블 분리** (vs 단일 organizations+type). 채택: 도매업체(상품 소유)와 에이전시(셀러 관리)는 다른 주체 + 관계·향후 기능(에이전시 슈퍼관리자/정산 vs 도매 주문/배송)이 발산 → FK 타입 안전(`products.wholesaler_id`→`wholesalers`만) + 의도 명확. `profiles`는 `wholesaler_id`/`agency_id`로 소속 구분.
6. **이미지 매칭 = product_images(match_status) + upload_jobs 영속화**. 대안(업로드 시 인메모리 매칭) 기각: 수작업 매칭 UI에 영속 상태 필요.

## 7. 예비 위험

| 위험 | 영향 | 완화 |
|---|---|---|
| service role 키 노출 | RLS 전면 우회 | 키는 백엔드 환경변수 only, 프론트 절대 노출 금지 |
| 가격 컬럼 누출(에이전시 소속 셀러) | 정책 위반(AC-5) | 모든 가격 경로 §3.10 셰이핑 통과 + 전용 테스트 |
| platform_code 동시 발급 충돌 | 중복 품번 | SEQUENCE 원자성 사용(애플리케이션 카운터 금지) |
| 표준 템플릿이어도 엑셀 변형 | 파싱 실패 | 엄격 검증 + error_detail → 수작업 매칭 UI |
| 공개 QR 카드에 가격 노출 | 폐쇄성 훼손 | `/p/{code}`는 가격 필드 자체를 미포함 |

## 8. 테스트 전략

- **단위**: 가격 노출 리졸버(역할×seller_type 매트릭스 전수), `platform_code` 생성기, 엑셀 파서, QR URL/이미지.
- **통합**: 업로드→파싱→매칭→등록 / 카탈로그 역할별 가격 / 관리자 승인 게이트 / 미승인 403.
- **수용**: AC-1~6 1:1 매핑 (특히 AC-5 가격 매트릭스, AC-6 승인 게이트).
- 도구: `pytest`(backend/tests), 이후 `/api-test` 파이프라인 연계.

---
## 변경이력
<!-- change-history skill auto-appends entries here, oldest first -->

### [2026-06-03 16:17] [개발방향-수정]
- **id**: CH-20260603-002
- **이유**: 승인된 requirements.md 기반 기술 설계서 최초 작성 (백엔드 DB 스키마 우선)
- **무엇이**: ezmerce-v2-backend-tech-design.md 전체 (§1 아키텍처 ~ §8 테스트 전략, §3 전체 DDL 포함)
- **영향범위**: setup_v2_schema.sql 대체 예정, backend/ 신규 구축 예정 (현재 비어있어 깨질 호출부 없음)
- **연관 항목**: CH-20260603-001 (requirements)

### [2026-06-03 20:59] [개발방향-수정]
- **id**: CH-20260603-006
- **이유**: FR-1.5(관리자 가격 노출 설정) 반영 — price_visibility 도입 (change-propagation)
- **무엇이**: §3.4 profiles에 `price_visibility` 컬럼, §3.10 리졸버 규칙/의사코드(관리자 설정 우선 + seller_type 폴백), §4 `/admin/accounts/{id}/price-visibility` 엔드포인트
- **영향범위**: implementation-plan, code(pricing.py/catalog.py/admin.py/schemas/migration delta 02)
- **연관 항목**: CH-20260603-005 (요구사항), CH-20260603-007 (코드)

### [2026-06-03 21:14] [개발방향-수정]
- **id**: CH-20260603-008
- **이유**: 도매업체와 에이전시는 다른 주체 — 단일 `organizations`+type 를 `wholesalers`/`agencies` 별도 테이블로 분리 (FK 타입 안전 + 의도 명확, 향후 기능 발산 대비)
- **무엇이**: §3.1 ER, §3.2 ENUM(org_type 제거), §3.3 wholesalers/agencies, §3.4 profiles(organization_id → wholesaler_id+agency_id), §3.5/3.7/3.8 wholesaler_org_id → wholesaler_id, §3.11 RLS, §6 핵심결정-5
- **영향범위**: code(migration base 재작성, schemas/auth.py, routers/catalog·products, services/products), implementation-plan Task 2 DDL은 본 마이그레이션으로 supersede
- **연관 항목**: CH-20260603-009 (코드)
