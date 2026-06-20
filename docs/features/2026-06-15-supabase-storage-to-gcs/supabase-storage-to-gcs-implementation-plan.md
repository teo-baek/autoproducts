# Supabase Storage → Google Cloud Storage 이전 — 구현계획서

- 작성일: 2026-06-15
- 브랜치: `v2-dev`
- 상태: **계획 (구현 전)** — 아래 §3 열린 결정 확정 후 §5 작업 착수

---

## 1. 개요 · 범위

**Storage(파일 저장소)만** Supabase → GCS로 이전한다.

### 1-1. 범위 (IN)
- 상품 이미지 버킷 `product-images`(공개) → GCS
- 가입 서류 버킷 `business-docs`(비공개, PII) → GCS
- 프론트 직접 업로드 모델 → **백엔드 서명(signed) URL 발급 모델**로 재설계
- 백엔드 스토리지 읽기/쓰기/URL 생성·파싱 전부 GCS로 치환
- 관련 테스트·환경변수·배포(Makefile/deploy.env/DEPLOY.md)·문서·ops SQL 갱신

### 1-2. 비범위 (OUT) — **절대 건드리지 않음**
- **Postgres DB · Auth(GoTrue) · JWT(JWKS) = Supabase 유지.** `SUPABASE_URL` / `SUPABASE_SERVICE_KEY` / `supabase_jwks_url`는 그대로 살아있어야 한다.
- DB 스키마(DDL) 변경 없음 — `storage_path` / `thumbnail_path` / `representative_image_url` / `*_path` 컬럼은 그대로 두고 **값의 의미(호스트)만** 바뀐다.
- **데이터 이전·백필 없음** — 프리런치 단계 결정. 기존 객체 복사 ❌, `representative_image_url` 호스트 재작성 ❌. Supabase 버킷은 컷오버 시 그냥 비운다.
- 프론트 `@supabase/supabase-js` 제거 ❌ — 로그인/세션(auth)에 계속 필요.

### 1-3. 확정된 결정 (사용자 승인 완료)
| # | 결정 | 값 |
|---|---|---|
| D1 | 업로드 방식 | **백엔드 서명 URL 발급** (브라우저 → 백엔드에 요청 → V4 signed PUT URL → 브라우저가 GCS로 직접 PUT → 백엔드가 경로 DB 기록) |
| D2 | 기존 데이터 | **프리런치, 이전 불필요** (백필·객체복사 없음) |
| D3 | GCS 인프라 | **기존 GCP 프로젝트 재사용** (Cloud Run 배포에 쓰는 그 프로젝트/서비스계정) |
| D4 | 객체 경로 규칙 | **그대로 유지** (`{wholesaler_id}/...`, `staging/`, `thumbs/...`) — `storage_path`·manifest·`thumb_path` 로직 무변경 |

---

## 2. 목표 아키텍처

### 2-1. 버킷
| 버킷(논리) | GCS 접근모델 | 용도 |
|---|---|---|
| product-images | **공개 read** (`allUsers:objectViewer`, uniform bucket-level access) + 브라우저 PUT용 CORS | 상품 원본·썸네일(`thumbs/`)·ZIP staging |
| business-docs | **비공개** (서비스계정 전용, 공개 액세스 차단) | 가입 서류(PII) |

> 버킷 이름은 GCS 전역 유니크 → 잠정 `ezmerce-product-images` / `ezmerce-business-docs` (§3-D 확정). **하드코딩 상수를 env/config로 이동**한다.

### 2-2. 업로드 흐름 (D1, 상품 이미지)
```
브라우저  ──(1) POST /uploads/sign {경로, content-type}──▶  백엔드
백엔드    ──(2) 도매 스코프 경로 검증 + V4 signed PUT URL 발급 ──▶  브라우저
브라우저  ──(3) PUT 파일 ──────────────────────────────────────▶  GCS
브라우저  ──(4) 기존대로 commit/manifest(storage_path 포함) ───▶  백엔드 → DB 기록
```
- ZIP staging(`/zip/stage`)은 **현재도 서버 경유**라 백엔드-only 치환(서명 URL 불필요).
- 가입 서류는 **현재도 서버 경유**(`/auth/register/documents`) — 백엔드가 GCS 비공개 버킷에 직접 쓰기.

### 2-3. URL 생성
- 공개 이미지 URL = `{GCS_PUBLIC_BASE}/{path}` (기본 `https://storage.googleapis.com/{bucket}`). env로 빼서 추후 CDN/커스텀 도메인 교체 가능.
- `representative_image_url`은 계속 **완전 URL** 저장(이제 GCS 주소). DB 의미 무변경.

### 2-4. 자격증명
- 기존 Cloud Run 전용 **서비스계정 키 재사용**(권장). 두 버킷에 `Storage Object Admin` 부여. 이 키로 V4 서명 가능.
- 로컬: 키 파일 경로(ADC `GOOGLE_APPLICATION_CREDENTIALS` 또는 config). Cloud Run: Secret Manager(현 `SUPABASE_SERVICE_KEY`와 동일 패턴).

### 2-5. business-docs 읽기 (Phase 2 의존성 메모)
- 현재 코드는 **write-only** (관리자 열람 엔드포인트 없음). GCS 비공개라 공개 URL 없음 → 추후 열람은 **백엔드가 단기 signed GET URL 발급**. 1차는 **쓰기만** 이전, 읽기는 Phase 2 설계.

---

## 3. 열린 결정 / 확인 필요 (⚠️ 착수 전 확정)

> 아래는 잠정 기본값(권장). 대부분 코드로 기본값 채택 가능하나, **D-A(공개버킷 org 정책)와 D-E(자격증명)**는 사용자/GCP 확인이 필요.

| ID | 항목 | 권장 기본값 | 비고 |
|---|---|---|---|
| **D-A** | product-images **공개 버킷 허용 여부** | 공개 버킷 사용 | ⚠️ GCP 조직정책 `공개 액세스 방지(public access prevention)`가 켜져 있으면 **불가** → 상품 이미지도 전부 **서명 read URL**로 가야 함(프론트/백엔드 URL 생성부 전체 파급). **GCP에서 확인 필요.** |
| **D-B** | 공개 URL 형식 | `https://storage.googleapis.com/{bucket}/{path}` | env `GCS_PUBLIC_BASE`로 분리 → 추후 Cloud CDN/커스텀 도메인 교체 용이 |
| **D-C** | 버킷 이름 | `ezmerce-product-images` / `ezmerce-business-docs` | 전역 유니크 필요. 상수 → env 이동 (`images.py:8`, `auth.py:13`, `products.ts:82`) |
| **D-D** | CORS(브라우저 PUT) | product-images 버킷에 `gsutil cors set` (origin=프론트 도메인, method PUT/GET) | 서명URL 모델에서 브라우저가 GCS로 직접 PUT → **GCS 버킷 CORS 필수**. FastAPI CORS와 무관 |
| **D-E** | 자격증명 방식 | 기존 SA 키 재사용(Secret Manager) | 대안: Cloud Run 런타임 SA + `iam.signBlob`(`serviceAccountTokenCreator`). 서명 URL 발급에 둘 중 하나 필요 |
| **D-F** | business-docs 읽기 | 1차 write-only 유지, 읽기는 Phase 2 signed GET | 현재 열람 코드 없음 |

---

## 4. 완전 표면 인벤토리 (전수 — "하나도 빠짐없이")

> 레포 전체 5각도 스윕 + gap-critic 교차검증 결과. `변경` = 이전 위해 손대야 함 / `유지` = 무변경(완전성 위해 기록).

### 4-A. 백엔드 코드 (변경)
| 위치 | 종류 | 작업 |
|---|---|---|
| `app/core/supabase.py:6-10` | client | 유지(DB/Auth) + **병렬 GCS 클라이언트 신설** 필요 |
| `app/core/config.py:6-15` | env | GCS 필드 추가. `SUPABASE_*`·`jwks` 유지 |
| `app/services/images.py:8` | bucket-const | `IMAGE_BUCKET` → env/config |
| `app/services/images.py:11-14` | url-build | `public_image_url` GCS 형식으로 |
| `app/services/images.py:17-31` | url-parse | `storage_path_from_public_url` GCS 마커로(또는 제거 검토) |
| `app/services/images.py:34-42` | url-build | `representative_image_url` 폴백 — 위 함수 의존, 동반 점검 |
| `app/routers/uploads.py:28-30` | client | `SupabaseUploadRepo` → GCS repo |
| `app/routers/uploads.py:79-80` | download | `download_object` GCS 읽기로 (**백엔드 핵심 읽기 primitive**) |
| `app/routers/uploads.py:82-86` | upload | `upload_object` GCS 쓰기로(upsert 의미 유지=동일키 덮어쓰기) |
| `app/routers/uploads.py:88-90` | db | `list_unmatched_images` = DB 조회, **무변경** |
| `app/services/uploads.py:175-186` | upload | `_thumbnail_from_bytes` — repo 통해 동작(치환 흡수) |
| `app/services/uploads.py:188-203` | download | `_process_one_image` 원본 다운로드 — **(1차 매핑 누락분)** repo 통해 흡수, 검증 |
| `app/services/uploads.py:206-256` | up+down | `attach_images` 배치(4 workers×16) — repo 치환, 동시성 유지 |
| `app/services/uploads.py:317-366` | upload | `stage_zip_to_manifest` 서버측 staging 업로드 |
| `app/services/uploads.py:27-37` | path | `_safe_object_name`(md5[:16]) — **유지**(경로 규칙 보존) |
| `app/services/image_process.py:49-55` | path | `thumb_path`(`thumbs/...jpg`) — **유지** |
| `app/services/excel_export.py:148-167` | download | `cell_image_bytes` GCS 다운로드로(10분 TTL 캐시 유지) |
| `app/services/excel_export.py:108-117` | path | `cell_image_path`(thumb→storage 폴백) — **유지** |
| `app/routers/catalog.py:9,119,154` | url-parse/build | `storage_path_from_public_url`/`representative_image_url` 의존 — 함수 교체로 반영, 검증 |
| `app/routers/products.py:12,191-192` | url-parse | 위와 동일(엑셀 export 폴백) |
| `app/routers/admin.py:12,335` | url-parse | 위와 동일(관리자 export 폴백) |
| `app/routers/public.py:5,7,17` | url-build | 공개 QR 카드 이미지 URL — 함수 교체로 반영 |
| `app/routers/auth.py:13` | bucket-const | `_DOC_BUCKET` → env/config |
| `app/routers/auth.py:38-47` | upload | `upload_document` GCS 비공개 업로드로 |
| **신규** `POST /uploads/sign` | endpoint | **V4 signed PUT URL 발급**(도매 스코프 경로 검증) |
| `app/services/accounts.py` | other | 계정 보상흐름 — 스토리지 직접접근 없음, **무변경** |

### 4-B. 프론트엔드 (변경)
| 위치 | 종류 | 작업 |
|---|---|---|
| `apps/web/src/lib/products.ts:82` | bucket-const | `PRODUCT_BUCKET` → 불필요/env |
| `apps/web/src/lib/products.ts:323-336` | upload | `uploadProductImage` — 서명URL 요청 후 GCS PUT |
| `apps/web/src/lib/products.ts:338-340` | url-build | `publicImageUrl` — `getPublicUrl` → GCS URL 빌더(env base) |
| `apps/web/src/lib/products.ts:342-347` | url-build | `productThumb` — 위 빌더 의존 |
| `apps/web/src/lib/products.ts:26-32,215` | type/plumbing | `ProductImage.storage_path` + manifest — 경로 규칙 유지(무변경 예상, 확인) |
| `apps/web/src/app/(dash)/products/bulk/page.tsx:141,155,177-178` | upload | 새 업로드 흐름 반영(키 `{wid}/bulk/{stamp}-{i}` 유지) |
| `apps/web/src/components/SingleProductModal.tsx:11,123-124` | upload | 새 흐름 + `representative_image_url` 세팅 |
| `apps/web/src/components/ProductDetailModal.tsx:30,81-103` | url-build | 갤러리 URL 빌더 교체로 반영 |
| `apps/web/src/app/(dash)/products/unmatched/page.tsx:13,284,383` | url-build | staged/미매칭 표시 — 빌더 교체로 반영 |

### 4-C. 프론트엔드 (유지 — 완전성 기록)
- `lib/supabase.ts:22-26` 브라우저 클라이언트 = **auth 전용 유지** (로그인/세션). `:23` placeholder `.supabase.co`는 사소(선택 정리).
- `app/p/page.tsx:144-150` `<img src=representative_image_url>` = 서버 URL 그대로 → **무변경**. 단 `:144` "external(Supabase Storage)" **주석 스테일** → 공급자 중립으로 수정.
- `lib/catalog.ts:22,118` `representative_image_url` 패스스루 → **무변경**.
- `app/register/page.tsx:84-88` 서류 업로드는 **백엔드 API 경유**(직접 storage 아님) → 프론트 무변경.
- `next.config.ts` `images.unoptimized` + static export → plain `<img>`라 **remotePatterns 불필요(무변경 확정)**.
- `package.json:12` `@supabase/supabase-js` → **auth용 유지(제거 금지)**.
- `apps/web/.env*` `NEXT_PUBLIC_SUPABASE_*` → auth용 **유지**. (D-B 채택 시 `NEXT_PUBLIC_GCS_PUBLIC_BASE` 1개 추가 가능)

### 4-D. 테스트 (변경) — ⚠️ 안 고치면 깨짐
| 위치 | 작업 |
|---|---|
| `tests/test_public_card.py:27,40-42` | `/storage/v1/object/public/product-images/...` 단언 → GCS URL 형식으로 |
| `tests/test_excel_export.py:116-144` | `_FakeStorage`(from_/download) → GCS 다운로드 추상화에 맞춤, 캐시 call-count 단언 유지 |
| `tests/test_uploads_service.py:248-262,272-286,337-349` | `FakeStorageRepo`(bucket 기본값) → 새 repo 시그니처. `thumbnail_path`/manifest 경로 단언은 유지(경로 규칙 불변) |
| `tests/conftest.py` | 스토리지 참조 없음 — **무변경** |

### 4-E. 설정/환경변수
| 위치 | 작업 |
|---|---|
| `backend/.env` / `.env.example` | GCS 변수 추가(`GCS_PROJECT`, `GCS_PRODUCT_BUCKET`, `GCS_DOC_BUCKET`, `GCS_PUBLIC_BASE`, 자격증명). `SUPABASE_*`·`PUBLIC_BASE_URL` 유지 |
| `apps/web/.env*` | (선택) `NEXT_PUBLIC_GCS_PUBLIC_BASE`. `NEXT_PUBLIC_SUPABASE_*` 유지 |

### 4-F. 인프라/배포 (변경)
| 위치 | 작업 |
|---|---|
| `Makefile:60-66, 115-127` (`deploy-api`) | GCS env/secret 와이어링 추가(`--set-env-vars`/`--set-secrets`) |
| `deploy.env` / `deploy.env.example` (루트) | GCS 버킷·public-base·자격증명 변수 추가 |
| `backend/DEPLOY.md:86-100` | GCS 자격증명/버킷/CORS 문서화. 기존 CORS·동기 이미지처리 경고 유지 |
| `backend/app/main.py:9-14` (CORS) | API용 FastAPI CORS는 유지. **브라우저→GCS PUT은 GCS 버킷 CORS(D-D)**가 담당 |
| `Dockerfile`/`.dockerignore`/`cloudbuild.yaml` | 스토리지 참조 없음 — `uv`로 GCS 의존성 자동 설치, **무변경** |
| `firebase.json` | 프론트 호스팅 전용 — **무변경** |

### 4-G. 의존성
| 위치 | 작업 |
|---|---|
| `backend/pyproject.toml` + `uv.lock` | `uv add google-cloud-storage` → `uv export`로 `requirements.txt` 재생성(**직접 편집 금지**). `supabase` 의존은 DB/Auth용 **유지** |
| `apps/web/package.json` | `@supabase/supabase-js` **유지(auth)** |

### 4-H. SQL / 마이그레이션
| 위치 | 작업 |
|---|---|
| `migrations/2026-06-05_v2_core_06_register_fields.sql:14-22` | `storage.buckets`(business-docs) INSERT + "RLS 금지" 보안주석 → GCS에선 의미 없음. **GCS 비공개 버킷+IAM**으로 재현. SQL은 보존하되 주석에 "Storage=GCS로 이전, 이 INSERT는 레거시" 명기 |
| `migrations/_PRELAUNCH_wipe_test_data.sql:82` | `DELETE FROM storage.objects WHERE bucket_id IN (...)` → GCS에선 무의미(메타만 정리). 주석/대체: `gsutil rm -r gs://bucket/...` 안내 |
| `migrations/_SEED_reset_to_admin.sql:97` | 동일(현 untracked 파일) |
| `migrations/_RESET_public.sql:5-6` | "storage 스키마 그대로 유지" 계약 주석 → GCS 정리로 문구 갱신 |
| `migrations/README.md:7,13-15,19-21,26` | 수동 버킷 셋업 런북(Supabase Dashboard) → **GCS(gsutil/console)**로 재작성 |
| 경로 컬럼들(`*_path`, `representative_image_url`, `storage_path`, `thumbnail_path`) | **DDL 무변경** — 프리런치라 값 백필도 없음 |

### 4-I. 문서
| 위치 | 작업 |
|---|---|
| `docs/features/2026-06-03-ezmerce-v2-backend/ezmerce-v2-backend-tech-design.md:24,39,168,187,202` | 아키텍처 "Supabase Storage" → GCS. **유령 `excel-uploads` 버킷(코드엔 없음)** 명시 |
| `docs/.../ezmerce-v2-backend-implementation-plan.md:197` | `storage_path` 스키마 참조 — 필요시 메모 |
| `TODO.md:19,27,57,62` | `product-images 버킷 + storage.objects RLS` → **GCS 버킷 + IAM**(RLS는 GCS에 없음)로 재서술 |
| `CLAUDE.md`(루트) §상품 이미지 두 소스 / §PUBLIC_BASE_URL | 공급자 중립 유지. Storage=GCS 반영(헬퍼 동작 동일) |
| `HANDOFF-*.md` | 과거 핸드오프 — 저위험, 미정독(필요시 스테일 문구만) |

---

## 5. 구현 작업 순서

### Phase A — GCS 인프라 (사용자 수행, 명령어는 제가 안내)
- [ ] A1. 버킷 2개 생성(uniform bucket-level access): `product-images`(공개) / `business-docs`(비공개)
- [ ] A2. **(D-A 확인)** product-images 공개 read 부여(`allUsers:objectViewer`) — 조직정책이 막으면 전체 서명-read 설계로 전환
- [ ] A3. 서비스계정에 두 버킷 `Storage Object Admin` + 서명 권한 확인(키 재사용/`signBlob`)
- [ ] A4. **(D-D)** product-images CORS 설정(프론트 도메인 origin, PUT/GET)

### Phase B — 백엔드 기반
- [ ] B1. `uv add google-cloud-storage` + `uv export`로 requirements 재생성
- [ ] B2. `config.py` GCS 필드 추가(`SUPABASE_*` 보존)
- [ ] B3. `app/core/gcs.py` 신설 — 클라이언트 싱글톤 + 헬퍼(`upload_bytes`/`download_bytes`/`public_url`/`signed_put_url`/`signed_get_url`)
- [ ] B4. `.env`/`.env.example` GCS 키 추가

### Phase C — 백엔드 스토리지 치환
- [ ] C1. `images.py` — `public_image_url`/`storage_path_from_public_url`/`IMAGE_BUCKET`
- [ ] C2. `uploads.py` repo(`download_object`/`upload_object`) → GCS
- [ ] C3. `uploads.py` 서비스(staging/thumbnail/attach) repo 치환 흡수 검증
- [ ] C4. `excel_export.py` `cell_image_bytes` → GCS(캐시 유지)
- [ ] C5. `auth.py` `upload_document` → GCS 비공개
- [ ] C6. **신규** `POST /uploads/sign`(도매 스코프 경로 검증)
- [ ] C7. catalog/products/admin/public 라우터 반영 검증

### Phase D — 프론트엔드
- [ ] D1. `products.ts` `uploadProductImage` — 서명URL 요청 후 GCS PUT
- [ ] D2. `products.ts` `publicImageUrl`/`productThumb` — GCS URL 빌더
- [ ] D3. bulk/Single/Detail/unmatched 반영 검증
- [ ] D4. `p/page.tsx` 스테일 주석 수정, `catalog.ts` 무변경 확인
- [ ] D5. `supabase.ts` storage 미사용 확인(auth 유지)
- [ ] D6. (선택) web `.env`에 `NEXT_PUBLIC_GCS_PUBLIC_BASE`

### Phase E — 테스트/문서/인프라/ops 정리
- [ ] E1~E3. 테스트 3종 GCS 맞춤(`test_public_card`/`test_excel_export`/`test_uploads_service`)
- [ ] E4. `Makefile deploy-api` GCS env/secret
- [ ] E5. `deploy.env`/`deploy.env.example` GCS 변수
- [ ] E6. `DEPLOY.md` GCS 문서화
- [ ] E7. ops SQL 3종 + `migrations/README.md` 버킷 런북 GCS로
- [ ] E8. `TODO.md`·tech-design·CLAUDE.md storage 섹션 갱신

### Phase F — 검증 (증거 기반)
- [ ] F1. 단일 업로드 → 카탈로그/쇼룸 표시 → **엑셀 export 사진**
- [ ] F2. 대량(ZIP) → 미매칭 매칭 → 표시 → 엑셀
- [ ] F3. 공개 QR 카드 이미지
- [ ] F4. 가입 서류 업로드(비공개)
- [ ] F5. `cd backend && .venv/bin/python -m pytest` 그린
- [ ] F6. (컷오버) Supabase 두 버킷 비우기

---

## 6. 리스크 / 갓차 (이 코드베이스 특유)

1. **역파서 silent failure** — `storage_path_from_public_url`가 마커 불일치 시 예외 없이 `None` → 엑셀 export에서 **에러 없이 사진만 사라짐**(catalog/products/admin 3곳). 교체 시 GCS 마커로 정확히, F1/F2에서 엑셀 사진 필수 확인.
2. **단일 vs 대량 이중 소스** — 단일=`representative_image_url`(완전URL)만, 대량=`product_images[]`(상대경로)만. URL 빌더 교체가 **양쪽**에 영향. 한쪽만 고치면 절반 사진 빔(과거 2회 발생).
3. **공개 버킷 org 정책(D-A)** — 막혀 있으면 상품 이미지도 서명-read 필요 → 파급 큼. **착수 전 GCP 확인.**
4. **서명 URL 경로 검증(IDOR)** — `/uploads/sign`은 service-account가 RLS를 우회하므로, 백엔드가 **도매 스코프 경로(`{wholesaler_id}/...`)를 강제 검증**해야 타 도매사 경로 발급 방지.
5. **버킷 전역 유니크(D-C)** — `product-images` 등은 십중팔구 선점됨 → 프로젝트 접두 필수. 상수→env 이동.
6. **PII(business-docs)** — GCS에서 **공개 read 절대 금지**, 서비스계정 전용. 읽기는 Phase 2 signed GET. 현재 서류 삭제 로직 없음(고아 PII 유의).
7. **경로/썸네일 구조 보존** — `thumb_path`=`thumbs/{wid}/.../{stem}.jpg` 전제 유지. 안 그러면 `cell_image_path` 폴백 깨짐.
8. **단일 클라이언트 결합** — `create_client(supabase_url, service_key)`가 DB+Auth+Storage 공용. Storage만 떼되 `SUPABASE_URL`/JWKS 의존 절대 끊지 말 것. **GCS 변수로 `SUPABASE_URL` 재활용 금지.**
9. **requirements.txt** — `uv export` 파생본, 직접 편집 금지(`uv add` 후 재생성).

---

## 7. 검증 계획 요약
- 백엔드: pytest 그린(테스트 3종 GCS 맞춤 후).
- E2E 수동: 단일/대량 업로드 → 표시 → **엑셀 export 사진**(역파서 회귀) → 공개 카드 → 서류 업로드.
- 인프라: 서명 URL로 브라우저 PUT 성공(CORS), 공개 URL 200, 비공개 버킷 익명 403.

---

## 변경이력
- 2026-06-15: 최초 작성. 레포 전수 스윕(2×워크플로우, 13 에이전트) 기반 완전 표면 인벤토리 + 확정결정(D1~D4) + 열린결정(D-A~F) 반영.
