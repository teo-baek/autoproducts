# ezmerce QA 2차 — Fast tasks (3개)

출처: `~/Downloads/ezmerce QA.pdf` (3페이지). 작업 브랜치: `v2-dev`.

---

## Task 1: 엑셀 카탈로그 — QR 이미지 열 신규 추가 (전체 적용)
- **명세**: 스타일 렌더 엑셀(`build_render_xlsx`, 11열)에서 기존 **K열 "QR 링크"(URL 텍스트) 그대로 유지**하고, **우측에 L열 "QR 이미지"(QR PNG 임베드) 신규 추가** → 12열로 확장. 역할 구분 없이 **모든 export에 적용**(사용자 결정: "지금 전체 적용"). 나중에 '도매만'으로 좁히면 역할 게이트만 추가.
- **현황(이미 있음)**: `generate_qr_png()`(PNG bytes), `_embed_image()`, openpyxl Image 인프라 전부 존재.
- **영향 파일**:
  - `backend/app/services/excel_export.py` — `RENDER_HEADERS`(L=`"QR 이미지"` 추가), `_write_render_rows`(K=링크 텍스트 항상, L=QR PNG 임베드 항상), 컬럼 너비(L 이미지폭, K 링크폭)
  - `backend/app/routers/catalog.py` — 호출부(`qr_as_link` 의미 변경/유지 정리)
  - `backend/tests/test_excel_export.py` · `backend/tests/test_catalog_export.py` — 12열/L열 검증으로 업데이트
- **검증**: `cd backend && .venv/bin/python -m pytest tests/test_excel_export.py tests/test_catalog_export.py tests/test_qr.py`

## Task 2: 단일 상품 등록 모달 — 제품 상세 설명 입력 추가
- **명세**: `SingleProductModal` 폼에 **"제품 상세 설명" textarea** 추가. 등록/수정 시 `description` payload 포함. 시안 위치 = 우측(이미지 업로드 아래) 또는 '혼용률' 아래. **DB/백엔드는 이미 완비**(products.description 컬럼, ProductCreate, register_product insert, 응답 셰이핑, ProductDetailModal 표시까지 전부 존재) → **프론트만**.
- **공개 카드(/p)에는 미노출**(현 정책 유지).
- **영향 파일**:
  - `apps/web/src/components/SingleProductModal.tsx` — `description` state, prefill(`editing.description`), reset, createProduct/updateProduct payload, textarea UI
  - `apps/web/src/lib/products.ts` — `ProductUpdatePayload`에 `description` 있는지 확인, 없으면 추가(`ProductCreatePayload`엔 이미 있음)

## Task 3: 미매칭 상품 데이터 관리 — UX 4개 개선
- **명세**: `(dash)/products/unmatched/page.tsx` 4건.
  1. **스크롤바**: 우측 "연결되지 않은 이미지" 그리드 컨테이너에 좌측 테이블과 동일하게 `max-h-[34rem] overflow-y-auto` 추가.
  2. **연속 드래그앤드롭 버그**: "1개 매칭 후 드롭 안 먹음" — `onDropImage`에서 `load()` 비동기 미대기/레이스 + drag state 정리 문제 추정. 파일 전체 읽고 근본원인 진단 → `committing` 가드, `await load()`, `dragId/overPid` 확실 리셋, drop target(`<tr>`)의 `onDragOver` `preventDefault` 보장.
  3. **미매칭만 표시**: 상품 테이블을 `!productThumb(p)`(미매칭)만 필터링 → 매칭되면 목록에서 사라짐.
  4. **취소 버튼**: 헤더 '저장' 옆에 '취소' 추가 → `router.push("/products")` (자동 저장이므로 단순 뒤로가기). `useRouter` import 필요.
- **영향 파일**: `apps/web/src/app/(dash)/products/unmatched/page.tsx` (단일)

---

## 병렬화 계획 (DAG)

- **Independent: 1, 2, 3** — 서로 다른 파일, 의존 없음.
  - Task 1 = 백엔드(`excel_export.py` + 테스트).
  - Task 2 = 프론트(`SingleProductModal.tsx` + `lib/products.ts`).
  - Task 3 = 프론트(`unmatched/page.tsx`).
  - Task 2·3 모두 프론트지만 파일이 겹치지 않음(`lib/products.ts`는 Task2만 건드림) → 충돌 없음.
- → 3개 보조 에이전트 **동시 dispatch**, 각자 task 단위 commit.
