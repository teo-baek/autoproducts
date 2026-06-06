# HANDOFF — 상품등록 엑셀/이미지 파이프라인 고도화 (jinsup_dev 흡수)

> ✅ **3파트 + ZIP + 커밋시점 리팩터 완료 (2026-06-06)** — 백엔드 **130 passed**, 프론트 build·lint OK.
> ⚠️ **사용자 잔여 액션(SQL Editor)**: ① `_07` ② `_08`(thumbnail_path) ③ **`_09`(품번 유일성 제거 — 새 흐름 필수)** ④ `product-images` 버킷(공개) 생성. 테스트 데이터 정리는 `backend/seeds/cleanup_test_products.sql`.
>
> ### 🔧 추가 변경 (이 세션 후반, 위 "완료 내역" 외)
> - **파일명 매칭 보강**: 숫자런 추출 + 경계가드 부분일치(글자+숫자 붙은 파일명도 매칭, `상품5015.jpg`/`셔츠ABC123.jpg`). 품번은 유일키 아님.
> - **ZIP 업로드**: 서버 staging 방식 — `POST /uploads/zip/stage`(압축해제+썸네일→Storage staging, manifest 반환). Cloud Run 512Mi 대비 **배치+워커 제한+크기 100MB 가드**. (시안 2p UI: 진행바/용량)
> - **빈 품번 행 = 폐기**(상품명 대용 안 함, `ParseResult.dropped`).
> - **품번 유일성 제거(`_09`)** + **연속 (품번,상품명) 블록 그룹핑**(`_group_rows`) — 같은 품번의 다른 상품 허용.
> - **에러 메시지 친화화**: raw DB/버킷명 노출 제거(서버 로그로만). 중복=「이미 등록된 품번입니다」.
> - **커밋 시점 = 4단계**: `POST /uploads/excel/validate`(드라이런)→`/zip/stage`→`/uploads/commit`(상품 생성+이미지 매칭 한 번에). 마법사가 1·2단계에선 DB 미기록, 마지막 "상품 등록"에서 저장. **옛 `/uploads/excel`·`/images`·`/images/zip` 라우트 제거.**
> 다음 세션 시작 경로: `HANDOFF-product-pipeline-upgrade.md`
> 작성: 2026-06-06 / 브랜치: `v2-dev` / 백엔드 **93→115 passed**
> 같이 보기: [HANDOFF-product-registration.md](HANDOFF-product-registration.md)(상품등록 구현분) · [HANDOFF.md](HANDOFF.md)(백엔드 전반) · 규칙 [CLAUDE.md](CLAUDE.md)

---

## ✅ 완료 내역 (2026-06-06 이 세션)
**① 엑셀 동의어/필수컬럼/stock·혼용률** — `services/excel_parse.py`
- `_ALIASES` 를 jinsup `SYNONYMS_POOL` 기준 병합 확장(모델명·물품명·색상명·상세사이즈·도매단가·입고가·매장판매가 등). 우선순위 = 목록 순서(⚠️ `도매가`를 `입고가`/`도매Sale` 보다 앞에 둬 실제 POS에서 올바른 열 선택).
- 선택 컬럼 `fabric_composition`(혼용률/혼방률/소재)·`stock`(재고정상/재고/현재고/매장량/수량) 신규 매핑. `재고`는 관대 파싱(비숫자→0, 행 안 죽임). 혼용률은 자유 텍스트.
- 필수 논리컬럼(품번·상품명·도매가) 헤더 미발견 → **`ExcelFormatError`(파일 단위)**. 위치 폴백 제거. 라우트 `upload_excel`이 → 400 친화 메시지.
- `ingest_excel`: `stock`→SKU, `fabric_composition`→Product(그룹 첫 유효값) 인입.

**② 이미지 서버측 가공** — 신규 `services/image_process.py` + `services/uploads.py`
- `process_image_bytes()`: EXIF 정면보정(`exif_transpose`)→RGB→**웹 800px 상한**(`WEB_MAX_BOX`, 확대 안 함)→JPEG. 실패는 예외 대신 `status='error'`.
- `attach_images()`: repo 가 `download_object`/`upload_object` 를 가질 때만(capability 감지) 가공 — 원본 다운로드→리사이즈→`thumbs/...` 업로드→`thumbnail_path` 기록. **none/ok/error 3-상태 + `ThreadPoolExecutor`(max 8) 이미지 단위 격리**. 미매칭 이미지도 가공. 응답에 `processed` 카운트 추가.
- `SupabaseUploadRepo.download_object/upload_object`(service key, `upsert`). 엔티티 `ProductImage.thumbnail_path` 추가. 마이그레이션 `_08`.

**③ 파일명→품번 매칭** — `services/image_match.py`
- 정규화: 확장자 제거→끝 `.0` 제거→trim. 후보 `[정규화 전체, *(_-공백 토큰), *숫자런(\\d+)]`. 정확 일치 먼저(전체→토큰→숫자런)→대소문자 무시→**경계 가드 부분일치**(긴 품번 우선).
- ⚠️ "숫자만 뽑는" 게 아니라 **실제 품번(영숫자 포함)과 대조**. 숫자런 후보로 `상품5015.jpg`(글자+숫자 붙음)도 잡고, 부분일치로 `셔츠ABC123.jpg`도 잡되, `5015`에 `501`이 박히는 식의 오매칭은 경계 가드로 차단.

**④ ZIP 일괄 업로드 (추가 요청 — 2026-06-06)** — `services/uploads.py` + `routers/uploads.py` + 프론트
- `extract_zip_images()`(stdlib `zipfile`, 이미지 확장자 필터, `__MACOSX`/`._`/`.DS_Store` 제외, **Windows cp437 한글 파일명 복구**, 최대 1000장), `ingest_image_zip()`(원본 Storage 업로드+썸네일 가공+품번 매칭+job 갱신, `ThreadPoolExecutor`). `_process_one_image`→`_thumbnail_from_bytes` 리팩터로 ZIP은 재다운로드 없이 처리.
- 라우터 `POST /uploads/images/zip`(multipart, `Form` job_id). 의존성 추가 없음(stdlib).
- 프론트: `lib/products.ts` `uploadImagesZip()`(XHR 업로드 진행률), `bulk` 2단계 UI를 **시안 2페이지**대로 — 드롭존 "JPG · PNG · ZIP 지원 · ZIP 1개당 최대 1,000장"(시안의 "500MB"는 강제값이 아니라 실제 강제 기준=1000장으로 문구 교체), 업로드 행에 진행바/`loaded MB / total MB`/`%`, ZIP=아카이브 아이콘. `goAttach`가 개별 이미지(attachImages)+ZIP 서버결과 병합.

테스트: `test_image_process.py`(신규), `test_image_match.py`·`test_excel_parse.py`·`test_uploads_service.py`(확장, ZIP/매칭 포함). 백엔드 **125 passed**, 프론트 **build·lint 통과**.

### 후속 메모(범위 밖, 필요 시)
- 대량(수백 장) 시 동기 가공이 길면 `upload_job` 에 `processing` 상태 + 백그라운드 잡으로(현재 MVP=병렬+격리 동기).
- 프론트가 `thumbnail_path` 를 카탈로그/미매칭 프리뷰에 사용하도록 연동(현재 백엔드만 기록).
- 썸네일 2종(카드용 소형)·`representative_image_url` 자동 세팅은 미구현.

---

## 📦 (이하 원본 작업지시 — 보존)

## 🎯 목표
v2-dev 상품등록 파이프라인의 **① 엑셀 컬럼 흡수 ② 이미지 서버측 가공 ③ 파일명 매칭**을 `jinsup_dev` 수준으로 끌어올린다.
**가져오지 않음**: 출력물(사진/QR 박은 엑셀 렌더), 구글드라이브/GAS 소싱.
**유지**: v2 모델 — 프론트→Storage 직접 업로드, 필드단위 검증, platform_code 서버발급(SEQUENCE), soft delete, 도매업체 소유 스코프(IDOR).

## 📚 참조 원본 (읽기만 — 흡수 대상)
```bash
git show jinsup_dev:backend/app/parsing.py   # SYNONYMS_POOL(L18), get_column_value_by_synonyms(L53), strip_trailing_zero(L68)
git show jinsup_dev:backend/app/drive.py     # _to_excel_thumbnail(L112), process_single_row_image(L123, 3-state), process_images(L155, ThreadPoolExecutor)
```
⚠️ `clean_and_parse_price`(parsing.py L38, "가격 깨지면 조용히 0") **이식 금지**. drive.py 의 구글드라이브/GAS/urllib 소싱 **전부 제외**.

---

## ✅ 이번 세션까지 된 것 (이미 일부 ①·③ 진행됨 — 그 위에 얹기)
실제 LALAS POS `.xls`(21열) 업로드를 디버깅하며 파이프라인을 이미 한 단계 올려놨다. **다음 세션은 백지가 아니라 아래를 확장**한다.

### `backend/app/services/excel_parse.py` (현재 163줄) — ① 부분 완료
- **헤더 기반 컬럼 매칭** 이미 구현: `_ALIASES`(품번/상품명/색상/사이즈/도매가/판매가 + 일부 별칭) + `_header_index()`(별칭으로 위치 탐색, 못 찾으면 **위치 기반 폴백**).
- **`.xlsx/.xls/.csv` 3형식** 모두 `_read_all_rows()`로 읽음(헤더 포함). CSV 인코딩 자동(utf-8-sig→cp949→euc-kr).
- **통화 허용** `_to_int()`: `₩280,000원`→280000, float/`1001.0` 보정. **비숫자는 여전히 "숫자 형식이 아닙니다" 오류**(jinsup의 조용한 0 흡수 안 함 — 이 원칙 유지).
- **필드단위 검증**: `(행·필드·사유)` + 오류 행 제외 (시안 데이터검증 표와 1:1).
- **빈 품번 → 상품명 대용**(사용자 결정): `source_p_number` 비면 `item_name`으로. 둘 다 없으면 오류로 제외.

### `backend/app/services/image_match.py` (현재 12줄) — ③ 베이스
- 현재: `Path(stem)` → `[_\-\s]` 토큰분리 → `[stem, *tokens]` 순으로 pmap(정확) 일치.
- **미구현**: `.0` 제거, 대소문자 무시 폴백.

### `backend/app/services/uploads.py` `attach_images` — ② 미착수
- 현재: 매니페스트(`{original_filename, storage_path}`)만 받아 품번 자동매칭 + `product_images` 기록. **서버가 바이트를 안 만짐**(가공 없음).

---

## 🛠 다음 세션 작업 (3파트)

### ① 엑셀 동의어 헤더 매칭 강화 — `excel_parse.py`
현재 `_ALIASES`를 **jinsup `SYNONYMS_POOL` 기준으로 확장**(순서=우선순위):
```
품번:   품번 / 상품코드 / 품목코드 / 모델명
상품명: 상품명 / 품목명 / 물품명 / 제품명
색상:   색상 / 컬러 / 색상명
사이즈: 상세사이즈 / 사이즈 / 규격
도매가: 도매가 / 도매단가 / 입고가 / 공급가
판매가: 소매가 / 판매가 / 소비자가 / 매장판매가
(선택) 혼용률: 혼용률 / 혼방률 / 소재      재고: 재고정상 / 재고 / 현재고 / 매장량 / 수량
```
- 헤더 trim 후 비교, 한 필드에 여러 헤더 매칭 시 **우선순위 첫 번째**. (현 `_norm`+`_header_index` 확장)
- **(신규)** 선택 컬럼 `fabric_composition`(혼용률)·`stock`(재고)도 매핑 → SkuCreate.stock / Product.fabric_composition 으로 인입. *(현재 ingest_excel 은 stock/fabric 미인입 — 흡수 시 같이 추가)*
- **(신규) 필수 논리컬럼(품번·상품명·도매가)이 헤더에 아예 없으면 → 파일 단위 오류**로 명확히 리턴(어떤 컬럼이 없는지 표기). 현재는 위치 폴백/행별 오류로 흐려짐 → 깔끔한 파일오류로.
  - 라우트(`uploads.upload_excel`)에서 이 파일오류 → 400 친화 메시지. (이미 전역 ACAO 안전망 있음 — main.py)
- **검증 원칙 유지**: 비숫자 가격은 0 흡수 금지, 필드오류로.
- 테스트(`test_excel_parse.py` 확장): (a) `상품코드/공급가` 동의어 정상 (b) 필수컬럼 누락→파일오류 (c) 비숫자 가격 여전히 필드오류.

### ② 이미지 서버측 가공 — 신규 `backend/app/services/image_process.py` + `uploads.py`
- **`uv add pillow`** (backend). drive.py의 urllib/Drive/GAS는 제외.
- jinsup `_to_excel_thumbnail` 로직 이식: `Image.open` → `ImageOps.exif_transpose`(EXIF 정면보정) → `convert("RGB")` → `thumbnail(box)` → JPEG bytes.
  - ⚠️ 크기는 **엑셀셀용 90×110 쓰지 말 것** → **웹 카탈로그용**(예: 긴변 800px, 필요시 카드용 작은 것 1종). **상수/설정으로**.
- `attach_images` 흐름에 경로(b) 추가: 매니페스트 수신 → 이미지별로
  (1) Storage(`product-images`, service key)에서 **원본 다운로드** → (2) 가공 → (3) 파생 썸네일을 **`thumbs/...` 경로 업로드** → (4) `product_images` 행에 **원본+썸네일 경로 기록**.
  - `SupabaseUploadRepo` 에 storage download/upload 메서드 추가 필요(현재 바이트 안 만짐).
- **3-상태(ok/none/error) + `ThreadPoolExecutor` 병렬**(jinsup `process_images`): 깨진 이미지 1장이 배치 전체를 안 죽이게 **이미지 단위 격리**, `max_workers` 제한.
- **순서**: 먼저 파일명→품번 매칭, 그다음 **전 이미지 가공(미매칭 이미지도 썸네일 생성** → 수동매칭 UI 프리뷰 깔끔).
- **⚠️ DB**: 썸네일 경로 저장 컬럼 필요 → **마이그레이션 `_08`** 추가(`product_images.thumbnail_path TEXT`). 엔티티 `ProductImage` 에도 필드 추가. (멱등 `ADD COLUMN IF NOT EXISTS`)
- 대량(수백 장): 동기 엔드포인트가 길어지면 `upload_job` 에 `processing` 상태 추가해 백그라운드 잡으로. **MVP=병렬+격리로 동기 처리**, 비동기는 후속 메모만.
- 테스트(신규 `test_image_process.py`): EXIF 회전 보정 / 썸네일 크기 상한 / 깨진 바이트→error 상태(예외 전파 X).

### ③ 파일명→품번 매칭 고도화 — `image_match.py`
- 정규화: 확장자 제거 → **끝의 `.0` 제거**(`5015.0.jpg`→`5015`) → 앞뒤 공백 제거. (jinsup `strip_trailing_zero` 참고)
- 후보 = `[정규화 전체, *(_ - 공백 토큰)]`, **각 토큰도 끝 `.0` 제거**.
- 대조: **정확 일치 먼저 → 실패 시 대소문자 무시 폴백**(거짓충돌 방지로 순서 지킴). **전체 정규화 문자열을 토큰보다 먼저**.
- 매칭 점수/신뢰도는 MVP 범위 밖(이진 매칭 유지).
- 테스트(`test_image_match.py` 확장): `.0` 케이스, 대소문자, 멀티토큰(`5015_blue.jpg`), 미매칭.

---

## 🚫 가져오지 않는 것 (명시)
- `excel_builder.py`(사진/QR 박은 엑셀 렌더), `qr.py` — v2 `GET /catalog/export.xlsx`·`/products/export.xlsx`(가격 셰이핑)는 **그대로**.
- `drive.py` 의 구글드라이브/GAS 소싱 전부. (셀러가 실제 드라이브 폴더 운영이 확인되면 그때 '옵션 소스'로 별도 검토)
- jinsup `clean_and_parse_price` 의 "가격 깨지면 0" 동작.

## 📐 지켜야 할 v2 규칙
- soft delete / 모든 조회 `deleted_at IS NULL`, platform_code 서버 SEQUENCE 발급, 도매업체 소유 스코프(IDOR) — 기존대로.
- 가격 출력은 `visible_price()` 경유(인입 단계는 도매가+판매가 둘 다 저장 — 유지).
- 새 의존성은 **uv로만**(`uv add pillow`), `requirements.txt` 직접편집 금지(`uv export` 파생본 — 끝나고 재생성).
- 끝나면 `cd backend && .venv/bin/python -m pytest -q` 통과 확인.

## 🔌 현재 관련 계약/파일 (출발점)
- `services/excel_parse.py`(파서) · `services/uploads.py`(ingest_excel/attach_images + `SupabaseUploadRepo`) · `services/image_match.py`(매칭) · `routers/uploads.py`(`POST /uploads/excel`·`/images`, `GET /uploads/jobs`·`/{job}/unmatched`·`POST /{job}/match`).
- 엔티티 `entities/models.py`: `ProductImage`(storage_path/original_filename/match_status/is_representative/sort_order…) — 썸네일 컬럼 추가 대상. `ProductSku`(stock), `Product`(fabric_composition) — ① 인입 확장 대상.
- 마이그레이션 순서: `backend/migrations/README.md`(현재 `_07`까지) → `_08` 추가.
- 사용자 액션(기존): `product-images` 버킷(공개) 생성 — ② 가공이 이 버킷에서 원본 read/썸네일 write.

## 검증
```bash
cd backend && uv add pillow && .venv/bin/python -m pytest -q   # 통과 확인(현재 93 → 확장 후 증가)
git show jinsup_dev:backend/app/parsing.py   # 동의어/정규화 참조
git show jinsup_dev:backend/app/drive.py     # 썸네일/병렬 참조
```
