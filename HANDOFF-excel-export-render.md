# HANDOFF — 카탈로그 엑셀 "출력물" 렌더 (사진·QR 박은 A~K 엑셀) ✅ 완료(2026-06-06)

> ✅ **구현 완료(2026-06-06, 백엔드 138 passed). jinsup 예시 `2026-05-31_방송제품목록.xlsx` 와 구조 동일 확인.** 무엇이 들어갔나:
> - `app/services/excel_export.py` → **`build_render_xlsx(rows, base_url)`**(순수 빌더, I/O 없음) + **`cell_image_bytes(sb, path)`**(Storage 다운로드→`process_image_bytes` 셀 썸네일) + `_p_code`.
> - `app/services/pricing.py` → **`visible_price_columns(...)`**(visible_price 재사용, 도매가/판매가 2칸으로 정규화·미노출=None).
> - 라우트 **둘 다 전환**: `/products/export.xlsx`(도매 본인=관리뷰, 도매가+판매가) · `/catalog/export.xlsx`(셀러/에이전시=역할별 셰이핑, `_query_catalog_export_rows`+`_styled_export_rows`).
> - 테스트: `tests/test_excel_export.py`(레이아웃·반복·이미지·P CODE·`visible_price_columns`), `tests/test_catalog_export.py`/`tests/test_products_list.py` 라우트 갱신.
> **최종 결정(사용자 확정 2026-06-06):** ① **A~K 11열**(예시 동일): A 사진·B 품번·C 상품명·D 색상·E 상세사이즈·F 혼용률·G 도매가·H 판매가·I 재고·**J P CODE**·**K QR 링크**. *(처음 'P CODE 제거'로 갔다가, 예시 파일 보고 복원으로 번복)* ② **SKU당 1행, 셀 병합 없이 매 행 독립**(같은 사진/품번/상품명/QR도 매 행 반복 — jinsup `_write_rows` 방식). ③ **역할별 `visible_price` 셰이핑**(G/H 칸 고정, 값만 역할로 결정 — FR-3+FR-5.2). ④ **P CODE=`도매//1000_소매//1000`은 도매가·판매가 둘 다 보일 때만** 생성(한쪽만/미노출=빈칸 → 가격코드 유출 방지). 관리뷰=항상, 셀러 카탈로그=빈칸. ⑤ 도매가/판매가는 **숫자 + `#,##0` 콤마서식**(예시는 텍스트 '18,000'였으나 합계 가능하도록 숫자 유지). ⑥ 메모리: 대표이미지 한 장씩 다운로드→`EXCEL_CELL_PX=110` 축소(원본 즉시 회수).
>
> ─────────────────── 이하 원본 인계 내용(참고) ───────────────────
> 작성: 2026-06-06 / 브랜치: `v2-dev`
> 같이 보기: [HANDOFF-product-pipeline-upgrade.md](HANDOFF-product-pipeline-upgrade.md) · [HANDOFF.md](HANDOFF.md) · 규칙 [CLAUDE.md](CLAUDE.md)
> ⚠️ 이건 이전에 "가져오지 않음"으로 미뤄둔 **jinsup `excel_builder`(사진/QR 박은 엑셀 렌더)** 를 구현하는 작업이었다.

## 🎯 목표
상품 카탈로그를 **사진·QR이 셀에 박힌 스타일 엑셀**로 출력. 컬럼 레이아웃(A~K):

| 열 | 헤더 | 내용 | 정렬 |
|----|------|------|------|
| A | 사진 | 제품 이미지(실물) 셀에 삽입 | 가운데 |
| B | 품번 | 품번 | |
| C | 상품명 | 상품명 | **좌정렬** |
| D | 색상 | 색상 | |
| E | 상세사이즈 | 사이즈 | **좌정렬** |
| F | 혼용률 | 혼용률 | **좌정렬** |
| G | 도매가 | 도매가 | |
| H | 판매가 | 판매가 | |
| I | 재고 | 재고 | |
| J | P CODE | (아래 ⚠️ 결정) | |
| K | QR 링크 | QR 코드 이미지(100×100) 삽입 | 가운데 |

## ⚠️⚠️ 키값은 jinsup 예시 — 우리 실제 필드로 매핑할 것 (절대 혼동 금지)
사용자가 준 표의 "내용" 칸(`p_number`, `mix_ratio`, `wholesale`, `retail`, `p_code`…)은 **jinsup_dev 예시 키**다. **우리 스키마 필드명은 다르다.** 매핑:

| 열 | jinsup 예시 키 | **우리 실제 필드** (entities/models.py) |
|----|----------------|------------------------------------------|
| A 사진 | (이미지) | `products.representative_image_url` 또는 `product_images.storage_path` (Storage 다운로드) |
| B 품번 | `p_number` | **`product.source_p_number`** |
| C 상품명 | `item_name` | `product.item_name` |
| D 색상 | `color` | **`sku.color`** (product_skus) |
| E 상세사이즈 | `size` | **`sku.size`** |
| F 혼용률 | `mix_ratio` | **`product.fabric_composition`** ← 이름 완전 다름 주의 |
| G 도매가 | `wholesale` | **`sku.wholesale_price`** (⚠️ `visible_price()` 통과) |
| H 판매가 | `retail` | **`sku.retail_price`** (⚠️ `visible_price()` 통과) |
| I 재고 | `stock` | **`sku.stock`** |
| J P CODE | `p_code` | **결정 필요** (아래) |
| K QR | (QR) | `product.platform_code` → `qr_target_url()` → `/p/{platform_code}` |

## ⚠️ 결정 필요 (다음 세션 시작 시 사용자에게 확인)
1. **J열 "P CODE" 정의** — 두 후보:
   - (a) **jinsup 가격코드** `compute_p_code(도매, 소매) = f"{도매//1000}_{소매//1000}"` (jinsup `parsing.py`). 가격을 코드로 숨겨 표기하던 용도.
   - (b) **우리 `platform_code`**(EZM-000001, 영구 식별자).
   - → 둘은 완전히 다른 것. **어느 쪽인지 물어보고 진행.** (QR(K)은 platform_code 라서, J가 (a)일 가능성 있음)
2. **행 단위(granularity)** — 한 상품에 색상×사이즈 SKU가 여러 개. 표는 색상/사이즈/재고가 행마다 다르므로 **SKU당 1행**이 맞아 보임. 그러면 **사진·QR·품번·상품명·P CODE는 같은 상품 행들에 걸쳐 병합(merge)할지 / 매 행 반복할지** 결정. (jinsup `_write_rows`는 행 단위로 이미지 삽입 — 참고)
3. **export 대상/가격 셰이핑 범위** — 이 출력물이
   - 도매 본인/admin **관리뷰**(도매가+판매가 둘 다)용인지,
   - 아니면 카탈로그처럼 **역할별 셰이핑**(셀러는 단일가/미노출)도 필요한지.
   - → **무조건 `visible_price()` 경유**(CLAUDE.md §가격 노출). 대상에 맞는 viewer 역할로 호출.
4. **대량 이미지 메모리** — 수백 장 이미지를 한 xlsx에 임베드 = 메모리 큼(운영 Cloud Run **512Mi**). 한 번에 다운로드/임베드하면 OOM 위험 → 배치/상한/스트리밍 고려. (클라 리사이즈 TODO가 적용되면 원본이 가벼워져 유리)

## 📚 참조 원본 (읽고 흡수 — 출력 로직만)
```bash
git show jinsup_dev:backend/app/excel_builder.py
#   _write_rows(L38): A열 제품이미지 add_image, K열 QR 100×100 add_image
#   _apply_styles(L86): 헤더행 height 28, 데이터행 height 95, A/K 열 width 16, 나머지 자동폭, 좌정렬 처리
#   build_workbook(L122) / build_excel_bytes(L133) / output_filename(L141)
git show jinsup_dev:backend/app/parsing.py   # compute_p_code(가격코드), strip_trailing_zero
```
- 흡수: openpyxl `Image(io.BytesIO(...))` 셀 삽입, 행높이/열폭/정렬 스타일, QR 100×100.
- **제외**: jinsup `drive.py`(구글드라이브/GAS 이미지 소싱). 우리는 이미지가 **Supabase Storage**에 있으니 거기서 다운로드.

## ✅ 현재 코드 상태 (이 위에 얹기)
- `backend/app/services/excel_export.py`:
  - `catalog_xlsx_bytes(items, base_url)` — **이미 QR 임베드**(4열: 품번/상품명/가격/QR, QR 64px, 행높이 50). ← A~K 풀 레이아웃 + 사진까지 확장 대상.
  - `products_xlsx_bytes(products)` — 도매 관리뷰 10열 **평문**(사진/QR 없음).
  - QR 헬퍼는 `app/services/qr.py`: `qr_target_url(platform_code, base_url)`, `generate_qr_png(url)` **이미 존재**(jinsup `qr.py` 흡수 불필요).
- 라우트:
  - `GET /catalog/export.xlsx`(`routers/catalog.py`) — 역할별 `visible_price()` 셰이핑 + `catalog_xlsx_bytes`.
  - `GET /products/export.xlsx`(`routers/products.py`) — 도매 관리뷰, `visible_price()` 통과 + `products_xlsx_bytes`.
- 의존성: `openpyxl`·`pillow`·`qrcode` 전부 설치됨. **새 의존성 불필요.**

## 🛠 작업 개요 (제안)
1. `excel_export.py`에 **스타일 렌더 빌더** 추가(예: `build_render_xlsx(rows, base_url, ...)`):
   - 헤더 A~K, 좌정렬(C/E/F), 행높이~95, A/K 열폭~16.
   - 행 = SKU 단위(결정 #2 반영). 가격은 호출부에서 `visible_price()`로 이미 셰이핑된 값을 받는다(빌더는 셰이핑 안 함 — 우회 금지).
   - A열: 상품 이미지 Storage 다운로드 → (PIL로 셀 크기 리사이즈) → `XLImage` 삽입. 이미지 없으면 빈 칸.
   - K열: `generate_qr_png(qr_target_url(platform_code))` → 100×100 삽입.
   - J열: 결정 #1.
2. 라우트 연결 — 기존 `/products/export.xlsx`(관리뷰)와/또는 `/catalog/export.xlsx`를 스타일 렌더로 전환할지, 별도 `?style=render` 옵션/새 엔드포인트로 둘지 결정.
3. 이미지 다운로드 = `SupabaseUploadRepo.download_object` 재사용 또는 storage 클라이언트 직접. 대량 시 배치/상한(결정 #4).
4. 테스트: 헤더/열순서, QR·이미지 add_image 호출, 가격이 `visible_price()` 경유, 이미지 없는 행 처리, (선택) P CODE 값.

## 📐 지켜야 할 규칙
- **가격 출력은 반드시 `visible_price()` 경유** — 빌더에서 직접 컬럼 조회/가공 금지(CLAUDE.md §가격 노출). 소매업체 유형별 차등이 이 출력물에도 적용돼야 함.
- soft delete: 조회는 `deleted_at IS NULL`.
- 저장키 ASCII 규칙은 업로드 쪽 얘기(읽기엔 무관). 원본 한글 파일명은 표시용.
- 새 의존성은 uv로만(`requirements.txt` 직접편집 금지). 끝나면 `cd backend && .venv/bin/python -m pytest -q` 통과.

## 검증
```bash
cd backend && .venv/bin/python -m pytest -q
git show jinsup_dev:backend/app/excel_builder.py   # 이미지/QR/스타일 흡수
```
