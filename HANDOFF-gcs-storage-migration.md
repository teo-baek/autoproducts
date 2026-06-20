# HANDOFF — Supabase Storage → GCS 이전 + 업로드 속도 최적화

> 🚨🚨🚨 **STOP — 배포 전에 반드시 읽으세요 (사장님 본인에게 남기는 메모)** 🚨🚨🚨
>
> ## ⚠️ 첫 배포 테스트에서 버그 2개 잡아 고쳤다(둘 다 `core/supabase.py`) → **백엔드 재배포하고 다시 테스트!!** ⚠️
>
> **2026-06-18 업데이트 — 둘 다 `backend/app/core/supabase.py` 한 파일에서 수정·검증 완료(pytest 205, 라이브 HTTP/1.1 쿼리 200):**
> - **버그①** `서버 오류: <ConnectionTerminated error_code:1 …>` — Supabase httpx 가 **HTTP/2** 라 lru_cache 싱글톤 연결이 오래 살다 서버 GOAWAY 맞으면 진행 중 요청이 무재시도로 깨짐(동시 5개 `/sign`이 노출↑). **수정=http2=False + HTTPTransport(retries=3) 주입.**
> - **버그②** `서버 오류: Illegal header value b'eyJhbGci…'`(=service key) — 배포 시크릿 `SUPABASE_SERVICE_KEY` **끝에 줄바꿈**이 붙어 HTTP/1.1(h11)이 헤더 거부(HTTP/2 는 봐줬음 → ①수정으로 드러남). **수정=키/URL `.strip()`**(시크릿 더럽든말든 영구 방어). 재현·확정함.
> - **➡️ 지금 할 일: `make deploy-api` 재배포(두 수정 반영) 후 사진 여러 장 업로드 재테스트!!** (프론트 변경 없으니 deploy-web 불필요)
> - (선택) 시크릿 위생: `printf %s "<키>" | gcloud secrets versions add ezmerce-supabase-service-key --data-file=-` 로 줄바꿈 없이 재등록하면 깔끔 — 단 `.strip()` 덕에 안 해도 됨.
>
> **첫 배포 시 스모크 테스트(여전히 유효):**
> 1. **`make deploy-api`** (이번 수정 반영) — 프론트도 바뀌었으면 **`make deploy-web` 같이**(둘은 짝)
> 2. `make deploy-api`가 **URL 찍고 정상 종료** 확인 (안 뜨면 컨테이너 부팅 실패)
> 3. 배포 화면에서 **사진 여러 장 대량등록** ← 이번 버그가 동시 업로드에서 났으니 꼭 여러 장으로
> 4. 이상하면 롤백: `gcloud run services update-traffic ezmerce-api --to-revisions=<이전리비전>=100 --region=asia-northeast3`
>
> ---

> 브랜치: `v2-dev` / 최종 갱신: 2026-06-16
> 새 세션은 이 파일 경로만 주고 시작: `HANDOFF-gcs-storage-migration.md`
> 상세 설계/인벤토리: `docs/features/2026-06-15-supabase-storage-to-gcs/supabase-storage-to-gcs-implementation-plan.md`

---

## 🎯 Goal
**Storage(파일 저장소)만** Supabase → Google Cloud Storage 로 이전. **DB·Auth(GoTrue)·JWT 는 Supabase 그대로.**
- **본 이전은 완료·검증됨**(아래 Current Progress).
- **업로드 속도 최적화 1+2 = 완료·검증됨 (2026-06-15)**. 사용자 결정대로 **1+2만**(3 배치-서명 엔드포인트는 제외). 상세는 아래 "✅ 업로드 속도 최적화 (완료)".

---

## ✅ Current Progress (GCS 이전 — 완료)
Phase A~F 전부 적용 + 검증 통과 (`pytest 203 passed`, 프론트 `tsc --noEmit` 0 에러, app/에 Supabase 스토리지 호출 0건).

- **인프라(실제 생성됨)**: GCP 프로젝트 `ezmerce`, 리전 `asia-northeast3`.
  - 버킷 `ezmerce-product-images`(공개 read + CORS: GET/PUT, origin=`ezmerce.web.app`·`localhost:3555`)
  - 버킷 `ezmerce-business-docs`(비공개·public-access-prevention enforced, PII)
  - 런타임 SA `115315993388-compute@developer.gserviceaccount.com` = 두 버킷 `objectAdmin` + self `serviceAccountTokenCreator`(키리스 V4 서명) + `iamcredentials` API 활성화
  - 로컬 서명 권한: `dailyperforman@gmail.com`, `jslee@goldenplanet.co.kr`(=로컬 ADC) 둘 다 tokenCreator 부여됨
- **백엔드**:
  - `app/core/gcs.py`(신설) — GCS 클라이언트 + `upload_bytes`/`download_bytes`/`public_url`/`signed_put_url`/`signed_get_url`
  - `app/core/config.py` — `GCS_PROJECT`/`GCS_PRODUCT_BUCKET`/`GCS_DOC_BUCKET`/`GCS_PUBLIC_BASE`/`GCS_SIGNING_SA` + `gcs_public_base_url` 프로퍼티
  - `POST /uploads/sign`(`app/routers/uploads.py`) — 도매 스코프(`{wholesaler_id}/`) 서버 강제 V4 signed PUT URL. 요청 `{object_key(상대경로), content_type}` → 응답 `{upload_url, storage_path, public_url, content_type}`
  - 치환: `images.py`(public_image_url/storage_path_from_public_url), `excel_export.py`(cell_image_bytes, `sb` 인자 제거), `uploads.py`(repo download/upload_object), `auth.py`(upload_document → 비공개 버킷)
- **프론트(`apps/web`)**: `lib/products.ts` `uploadProductImage`(서명URL 요청 → GCS PUT), `publicImageUrl`(=`NEXT_PUBLIC_GCS_PUBLIC_BASE`). 호출부(bulk/Single/Detail/unmatched)는 시그니처·반환형 유지로 무수정.
- **검증된 것(라이브)**: 공개버킷 read 200·비공개 403, 키리스 서명→PUT→공개 GET 라운드트립 OK(dailyperforman + jslee ADC 둘 다), `/uploads/sign` 단위테스트 4개(스코프 강제·IDOR·`..`차단·권한).
- **DB 무변경**(프리런치라 백필·객체이전 없음). Supabase 버킷의 옛 객체는 **그대로 보존**(참조 안 됨, 컷오버 시 `gsutil rm -r`로 비우면 됨 — 아직 안 함).

---

## ✅ What Worked
- **키리스 서명**: SA 키 파일 없이(조직정책상 키 생성 막힐 수 있음) 런타임 SA + IAM `signBlob`(self tokenCreator)로 V4 서명. 운영(Cloud Run)은 런타임 SA로 자동, 로컬은 ADC(jslee, tokenCreator 부여됨)로 동작.
- **공개버킷 모델 유지**: GCP 조직정책이 공개버킷 허용 확인됨 → 상품이미지는 공개 read 그대로(전부 서명-read 전환 불필요). URL=`https://storage.googleapis.com/ezmerce-product-images/{path}`.
- **경로 규칙 보존**: `{wid}/...`, `staging/`, `thumbs/...` 그대로 → storage_path·manifest·thumb 로직 무변경.

## ⚠️ What Didn't Work / 함정 (반복 금지)
- **로컬 ADC 신원 불일치**: 처음 `dailyperforman`(gcloud 로그인 계정)에만 서명권한 줬는데, 로컬 ADC(`google.auth.default()`)는 `jslee@goldenplanet.co.kr` 였음 → signBlob 403. **해결됨**: jslee 에도 tokenCreator 부여(IAM 전파 ~60초). 로컬 `make dev` 업로드는 이제 ADC 전환 없이 jslee 로 동작.
- **`gcloud auth application-default login` 은 브라우저 인터랙티브** → 에이전트가 헤드리스로 못 함. ADC 전환이 필요하면 사용자가 직접.
- **Turbopack `.next` stale 캐시 panic**: dev 재시작 시 `Next.js package not found` FATAL + `/login` 반복 GET. 원인=오래된 `.next` 캐시(코드 무관). **해결**: `cd apps/web && rm -rf .next` 후 dev 재시작. (이 프로젝트 Next 16.2.6 커스텀 — `apps/web/AGENTS.md` 참고. 또 나면 `rm -rf .next node_modules/.cache`.)
- **`storage_path_from_public_url` 역파서**: 마커 불일치 시 조용히 None → 엑셀 export 사진 누락. 프론트 `NEXT_PUBLIC_GCS_PUBLIC_BASE` 와 백엔드 `GCS_PUBLIC_BASE` 가 **반드시 동일**해야 함.

---

## ✅ 업로드 속도 최적화 (완료 — 2026-06-15)

**왜**: 업로드가 전보다 느려짐. 전=브라우저→Supabase 직접 1회 PUT. 후=① `/uploads/sign`(서명, signBlob 네트워크 호출 ~100~300ms) + ② GCS PUT, **2홉**. 특히 대량(bulk)이 **순차 루프**라 N장이면 직렬로 쌓였음.

### ✅ Task 1 — 서명 자격증명 캐시 (백엔드)
- **파일**: `backend/app/core/gcs.py` → `_signing_kwargs()`
- **적용**: 모듈 레벨 ADC 자격증명 캐시(`_signer`) + `threading.Lock`(`_signer_lock`). 토큰이 `not valid`일 때만 `refresh()` — 매 서명마다 `default()`+`refresh()` 하던 오버헤드 제거. **FastAPI 동기 엔드포인트는 스레드풀에서 동시 실행**되므로 초기화·갱신을 Lock 으로 보호(핸드오프 원안의 lock-free 보다 안전하게 강화).
- **왜 `.valid` 만으로 안전한가**: google-auth `REFRESH_THRESHOLD = 3분45초` — `.valid` 는 **실제 만료 225초 전에 이미 False**가 되어 미리 refresh. 만료 경계 레이스 없음(적대 리뷰 high 지적은 이 내장 버퍼를 몰라 생긴 오탐, 라이브러리 소스로 반증).
- **검증**: `pytest` **205 passed**. 신설 `tests/test_gcs_signing.py` 2건 — 캐시 적중(default 1회만)·만료 시 refresh·SA 미설정 시 무동작 검증.

### ✅ Task 2 — 대량 업로드 병렬화 (프론트)
- **파일**: `apps/web/src/app/(dash)/products/bulk/page.tsx` → `addImages()` 의 개별 이미지 업로드 루프
- **적용**: 순차 `for await` → **동시성 제한 워커풀**(`UPLOAD_CONCURRENCY = 5`). 공유 `cursor` 를 N개 `uploadWorker()` 가 `const i = cursor++`(await 이전이라 JS 단일스레드에서 원자적)로 소비, `Promise.all` 로 대기. 인덱스(`idx=start+i`)·키(`bulk/${stamp}-${i}`)·상태(uploading→done/error)·에러(`setImgFailed`/`setImgErrMsg`)·`busy` 가드 전부 기존 순차루프와 동일 보존.
- **ZIP staging 루프는 의도적으로 순차 유지** — 대용량 동시 staging 은 운영 512Mi 메모리 위협(범위 외).
- **검증**: `tsc --noEmit` 0 에러. 적대 리뷰(프론트 워커풀 lens) = **ship**(레이스/회귀 없음). ⚠️ **사용자 잔여**: dev 재시작 후 실제 대량 업로드 체감/진행률·실패표시 수동 확인(`.next` 콜드 컴파일 첫 1회 느림은 정상, 워밍업 후 측정).

### 적대 리뷰 판정 요약 (3관점 병렬)
high 4건 주장 중 **실결함 0** — 1) 만료 레이스=`.valid` 225초 버퍼로 오탐, 2) 크로스-SA=ADC신원⊥서명SA(설정 불변)로 오탐, 3) 에러메시지 덮어쓰기=기존 순차루프와 동일 계약(비회귀), 4) 락경합=저부하·herd방지로 비결함. 유일 채택=캐시 단위테스트 부재 → 추가 완료.

### (제외) Task 3
배치 서명 엔드포인트(`/sign` 1회에 N개 URL)는 **안 함**(사용자 결정). 1+2로 충분.

---

## 참고 포인터
- 프로젝트 메모리: `storage-gcs-migration`(결정·갓차 요약)
- 규칙: 루트 `CLAUDE.md`(상단에 Storage=GCS 명시됨), `apps/web/AGENTS.md`(Next 커스텀 경고)
- 로컬 실행: `make web`(:3555) / `make api`(:8444) / `make dev`(둘 다)
- 배포: `make deploy-api`(GCS env 자동 주입, 운영 서명 자동) / `make deploy-web`
