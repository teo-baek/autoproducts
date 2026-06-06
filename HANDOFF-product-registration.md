# HANDOFF — 도매상 상품 등록 (apps/web)

> 다음 세션은 이 파일 경로로 시작: `HANDOFF-product-registration.md`
> 작성: 2026-06-06 / 브랜치: `v2-dev` / 백엔드 상태=[HANDOFF.md](HANDOFF.md) · 디자인=[apps/web/design/DESIGN-SYSTEM.md](apps/web/design/DESIGN-SYSTEM.md) · 할 일=[TODO.md](TODO.md)
>
> 🔜 **다음 작업 = 도매상(wholesaler) 입장의 "상품 등록" 화면 구현.** 사용자가 **상품등록 관련 PDF 시안**을 다음 세션에 줄 예정 → 그 스펙 + 아래 백엔드/디자인 기반으로 구현.

---

## 🎯 Goal
도매상이 로그인 후 **상품을 등록·관리**하는 프론트(apps/web) 화면 구현:
- **단일 상품 등록 폼** (`POST /products`)
- **표준 엑셀 대량 등록 마법사** (`POST /uploads/excel` → 이미지 업로드/매칭 → 검증 → 완료)
- **상품 관리 목록**(수정/삭제/보관) + 이미지 매칭
백엔드 API·데이터모델은 **이미 완성·라이브 검증**됨. 프론트만 얹으면 됨.

---

## ✅ 직전까지 된 것 (이번까지)
- **인증 완료**: `/login`·`/register`(3유형+서류 모달)·`AuthGuard`(미로그인→/login)·로그인후 홈. Supabase publishable(anon) 키 연동됨.
- **디자인 시스템**: 토큰(`apps/web/src/styles/ezmerce-tokens.css`) + 폰트(Pretendard/Playfair, layout `<link>`) + **UI 프리미티브**(`src/components/ui.tsx`): `Button`·`TextField`·`Checkbox`·`SegTabs`·`Alert`·`FileRow`·`Modal`, `AuthShell`, `icons.tsx`.
- **연동 헬퍼**: `src/lib/supabase.ts`(브라우저 클라), `src/lib/api.ts`(`api(path,{auth,body})` — FormData면 멀티파트, auth면 Bearer 자동).
- **포트/실행**: 루트 `make dev`(프론트:3555+백엔드:8444) · `make web`/`make api`/`make stop`. `NEXT_PUBLIC_API_BASE_URL=http://localhost:8444`.
- 백엔드 **70 tests passed**.

---

## 🔌 백엔드 API (이미 구현·정확한 계약)
인증: 모든 product 경로 = **`require_approved` + `require_role("wholesaler")`**, `wholesaler_id`는 JWT에서. 가격은 도매 본인 = 관리뷰(도매가+판매가 둘 다).

### 단일 등록 — `POST /products`
요청 = `ProductCreate` (`app/schemas/product.py`):
```jsonc
{
  "source_p_number": "업체 품번(필수)",
  "item_name": "상품명(필수)",
  "fabric_composition": "혼용률(선택)",
  "origin": "원산지(선택)",
  "lead_time_days": "리드타임(선택, 문자열)",
  "description": "설명(선택)",
  "skus": [                         // 1개 이상
    { "color":"BLACK", "size":"FREE", "wholesale_price": 18000, "retail_price": 29000, "stock": 12 }
  ]
}
```
- `wholesale_price` 필수(int≥0), `retail_price`/`stock` 선택(int≥0). **platform_code 는 서버가 SEQUENCE로 자동 발급**(프론트가 만들지 말 것).

### 수정/삭제
- `PATCH /products/{pid}` — body=부분 dict. 불변컬럼(`id/platform_code/wholesaler_id/created_by/created_at/deleted_at`) 자동 제거, **소유자 스코프**(타 도매 상품이면 404). **보관(archive)** = `{"status":"archived"}` PATCH.
- `DELETE /products/{pid}` — **soft delete**(`deleted_at`), 자식(skus/images) DB 트리거 cascade, 소유자 스코프(404).

### 엑셀 대량 등록 + 이미지
- `POST /uploads/excel` (multipart `file`) — **표준 템플릿** 파싱 → 품번별 상품 1 + SKU N 생성, `upload_job` 기록. 품번 단위 에러 격리(UNIQUE 충돌 시 해당 품번만 error). 입력 행 컬럼 ≈ `source_p_number, item_name, color, size, wholesale_price, retail_price, stock`.
- `POST /uploads/images` — 프론트가 **Storage에 직접 업로드** 후 `{original_filename, storage_path}` 매니페스트 전달 → 품번 자동매칭 → `product_images` 기록.
- `GET /uploads/{job}/unmatched` — 미매칭 이미지 목록.
- `POST /uploads/{job}/match` — 수동 매칭(이미지 ↔ source_p_number).

### ⚠️ 백엔드 갭 (구현 필요할 수 있음)
- **상품 목록/상세 조회 엔드포인트가 없음** — 현재 product 라우터는 `POST/PATCH/DELETE`만. "상품 관리 목록"·수정폼 프리필용 데이터는 **`GET /catalog`(역할 셰이핑된 목록)** 뿐. 도매 본인 관리뷰 목록/상세가 필요하면 **`GET /products`(+`/{id}`) 신규 추가** 검토. → 다음 세션 첫 결정거리.
- **product-images Storage 버킷 미생성**(TODO.md) — 이미지 대량 업로드 화면 붙일 때 필요(비공개 버킷+RLS, 사용자가 SQL/대시보드로 생성).

---

## 🎨 디자인 (시안 화면 매핑)
상세: `apps/web/design/SCREEN-INVENTORY.md`. 상품 등록 관련:
- **셸-B (다크 사이드바 백오피스)** — p8~26 공통. 좌측 다크 네이비 사이드바(로고·네비: 대시보드/상품관리/고객/주문/카탈로그, 하단 설정/지원/로그아웃) + 상단 검색바/알림/POS. **⚠️ 이 셸 컴포넌트는 아직 미구현** — 상품 화면 전에 만들어야 함(`AuthShell`은 인증 전용).
- **p7 커스텀 상품 추가 모달** — 단건 입력(상품명·품번·도매가/소매가·색상/사이즈·혼용률·재고 스텝퍼·설명) → `POST /products` 매핑 참고.
- **p11~15 대량 등록 마법사 4스텝** — ①파일 업로드(드롭존, 샘플 템플릿 다운로드 링크) ②이미지 업로드+진행/실패 ③데이터 검증(에러 테이블) ④완료(요약). 스텝퍼 컴포넌트 필요.
- **p16 미매칭 상품 데이터 관리**(드래그&드롭 매칭), **p17 상품 목록**, **p18 업로드 팝오버**.
- 데모 상품 사진: `apps/web/public/images/products/*`.
- ⚠️ 시안 잔재 `VogueCore`/`voguecore.com`·무관 로고 쓰지 말 것. POS·주문은 Phase 2(상품등록과 분리).

---

## 📐 지켜야 할 규칙 (루트 `CLAUDE.md`)
- **soft delete**(hard DELETE 금지), 조회 `deleted_at IS NULL`.
- **platform_code 는 서버 권위**(프론트 생성 금지), 품번=`source_p_number`(업체 스코프).
- **가격 노출**: 도매 본인 상품은 관리뷰(도매가+판매가). 프론트는 서버 준 필드만. (등록 시엔 둘 다 입력)
- **소유권(IDOR)**: 백엔드가 wholesaler_id 스코프 처리 — 프론트는 신경 X, 단 타 상품 접근 시 404 처리 UI.
- 토큰·컴포넌트(ui.tsx) 재사용, 임의 색/폰트 금지. **엑셀=표준 템플릿만**(1차).

---

## 🛠 What Worked (이 프로젝트에서 통한 방식)
- 토큰으로 직접 빌드한 UI 프리미티브 재사용(shadcn 미설치). `api()` 헬퍼로 백엔드 호출(Bearer 자동).
- 페이지 보호 = `AuthGuard`로 감싸기(+역할 게이트 추가하면 됨).
- dev 검증 = `make web` 후 playwright 스크린샷.
- 커밋은 논리 단위로 자주(푸시는 사용자가 직접 — **절대 `git push` 하지 말 것**).

## ❌ What Didn't Work / 함정 (반복 금지)
- **Tailwind v4 globals.css 에서 `@import url()` 폰트** → 순서 충돌. 폰트는 `layout.tsx <link>` 로.
- **createClient 빈 키 → throw** → placeholder 폴백 둠. `.env.local` 변경 시 **dev 재시작 필요**(Next는 시작 시 env 읽음).
- **file input `hidden`+`<label>` 트리거 → 일부 브라우저 다이얼로그 안 열림** → `useRef`+`<button type=button>`에서 `inputRef.click()`. (FileRow에 이미 적용)
- **백엔드 미처리 gotrue 에러 → 500(메시지X)** → 서비스에서 잡아 친화 400으로. (register 중복이메일에 적용)
- playwright file-chooser 큐가 꼬이면 `browser_close`로 리셋.

---

## 🔜 Next Steps (다음 세션 — PDF 받은 뒤)
1. **상품등록 PDF 시안 정독** + 위 백엔드 계약과 매핑.
2. **결정**: 상품 목록/상세 = `GET /catalog` 재사용 vs `GET /products` 신규(권장 — 도매 관리뷰). 정하고 필요하면 백엔드 먼저.
3. **셸-B(다크 사이드바) 레이아웃 컴포넌트** 구현 + `AuthGuard`+wholesaler 역할 게이트. (이후 상품/주문 화면 공통 사용)
4. **단일 상품 등록 폼** → `POST /products` (동적 SKU 행 추가: 색상/사이즈/도매가/소매가/재고).
5. **대량 등록 마법사**(4스텝) → `/uploads/excel` → (Storage 직접 업로드)+`/uploads/images`·`/unmatched`·`/match` → 검증/완료. 샘플 템플릿 다운로드 제공.
6. **상품 관리 목록** + 보관(`PATCH status=archived`)·삭제(`DELETE` soft)·수정.
7. (사용자) **product-images 버킷 생성**(비공개+RLS) — 이미지 업로드 화면 붙기 전.

---

## 검증/실행
```bash
make dev            # 프론트 :3555 + 백엔드 :8444 (Ctrl+C 둘 다 종료)
make api / make web # 개별
cd backend && .venv/bin/python -m pytest -q   # 70 passed
```
- 도매 계정으로 로그인해야 product API 접근 가능(`require_role("wholesaler")` + 승인). 테스트 계정은 Supabase 대시보드 Auth + profiles(role=wholesaler, status=approved, wholesaler_id 세팅)로 준비하거나, 가입→관리자 승인 흐름 사용.
