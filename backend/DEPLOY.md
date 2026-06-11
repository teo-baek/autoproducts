# 백엔드 배포 — Google Cloud Run (`make deploy-api`)

FastAPI 백엔드(`backend/`)를 컨테이너로 Cloud Run에 자동 배포한다.
**백엔드만: `make deploy-api` / 프론트까지 한 번에: `make deploy`.** Supabase는 매니지드라 Cloud Run은 env + 시크릿만 있으면 된다.

```
make deploy-login   # 맨 처음 1회: 전용 구글계정으로 브라우저 로그인 (키 불필요)
make deploy-setup   # 1회: API 켜기 + 저장소 + 시크릿 + 권한
make deploy-api     # 그 다음부터 백엔드 배포 — 빌드 → Cloud Run  (둘 다면 make deploy)
```

인증은 전용 구글계정 로그인으로 하고, gcloud 상태를 `.gcloud-ezmerce/`(프로젝트 안)에 **격리**한다.
→ **맥OS에 로그인된 다른 구글 계정과 절대 안 섞인다.** (`make deploy-whoami` 로 확인)
빌드는 **Cloud Build**(서버사이드)라 맥 칩(arm64) 신경 안 써도 된다(자동 amd64).

> ⚠️ **서비스계정 키(JSON)는 안 쓴다.** 조직 보안정책(`iam.disableServiceAccountKeyCreation`)이
> 키 생성을 차단하는 경우가 많고, 구글도 키리스(브라우저 로그인)를 권장한다. 그래서 로그인 방식이 기본.

---

## 사전 준비 (한 번만)

### 1. 전용 GCP 프로젝트 + 결제 연결
- https://console.cloud.google.com 에서 **이 프로젝트용 구글 계정으로 로그인**.
- 상단 프로젝트 선택 → **새 프로젝트** 만들기 → 프로젝트 ID 메모(예: `ezmerce-prod`).
- **결제 계정 연결**(Billing). ⚠️ 안 하면 API 활성화가 막힌다. (Cloud Run은 사용량 적으면 거의 무료.)

### 2. `deploy.env` 채우기
```bash
cp deploy.env.example deploy.env
```
| 키 | 값 |
|---|---|
| `GCP_PROJECT` | 1번에서 만든 프로젝트 ID |
| `GCP_REGION` | `asia-northeast3` (서울, 기본값) |
| `GCP_SERVICE` | `ezmerce-api` (기본값) |
| `GCP_REPO` | `ezmerce` (기본값) |
| `SUPABASE_URL` | Supabase 프로젝트 URL |
| `PUBLIC_BASE_URL` | 공개 QR 카드 URL prefix(프론트 도메인) |
| `SUPABASE_SERVICE_KEY` | Supabase service_role 키 (setup 시 시크릿으로 올림) |

`GCP_SA_KEY`는 비워둔다(로그인 방식). 키가 허용되는 환경이면 그때만 경로 지정.

### 3. 전용 계정으로 로그인 (키리스)
```bash
make deploy-login
```
→ 브라우저가 열린다. **반드시 이 프로젝트 전용 구글계정**으로 로그인(개인계정 X).
   자격증명은 `.gcloud-ezmerce/`에만 저장돼 맥OS 기본 gcloud/구글 계정과 안 섞인다.
> 헷갈리면 로그인 화면에서 계정을 한번 더 확인. 로그인 후 `make deploy-whoami`로 확인 가능.

### 4. 1회 셋업 실행
```bash
make deploy-setup
```
→ 필요한 API 켜기 + Artifact Registry 저장소 생성 + service_role 키를 Secret Manager에 등록 +
   런타임/빌드 서비스계정 권한까지 자동.

---

## 배포
```bash
make deploy-api      # 백엔드만 (프론트까지 한 번에 = make deploy)
```
빌드(Cloud Build) → Cloud Run 배포까지 자동. 끝나면 서비스 URL을 출력한다.

확인:
```bash
make deploy-url                       # 배포된 URL
curl $(make -s deploy-url)/health     # → {"status":"ok"}
make deploy-whoami                    # 어떤 계정/프로젝트인지 (내 구글계정 아님 확인)
make deploy-logs                      # 최근 로그
```

## 로컬에서 이미지만 검증 (선택)
```bash
docker build -t ezmerce-api backend
docker run --rm -p 8080:8080 \
  -e SUPABASE_URL=https://xxxx.supabase.co -e SUPABASE_SERVICE_KEY=... \
  -e PUBLIC_BASE_URL=http://localhost:3555 ezmerce-api
# → http://localhost:8080/health
```

---

## 백엔드가 읽는 환경변수 (`app/core/config.py`)
| 키 | 비밀? | 설명 |
|---|---|---|
| `SUPABASE_URL` | 아니오 | 프로젝트 URL. JWKS(ES256) 검증 URL도 여기서 파생 |
| `SUPABASE_SERVICE_KEY` | **예 → Secret Manager** | service_role 키. RLS 우회 → 절대 이미지/깃에 굽지 말 것 |
| `PUBLIC_BASE_URL` | 아니오 | 공개 QR 카드(`/p/{code}`) URL prefix |
| `PLATFORM_CODE_PREFIX` | 아니오 | 기본 `EZM` |
| `SUPABASE_JWT_SECRET` | (레거시) | HS256 잔재. JWKS 사용 시 불필요 |

## ⚠️ 운영 전 반드시
- **CORS**: `app/main.py` 가 현재 `allow_origins=["*"]`(개발용). 프론트 오리진 화이트리스트로 좁힐 것
  (env `ALLOWED_ORIGINS` 주입식 권장).
- **이미지 가공 ↔ Cloud Run**: "요청 처리 중에만 CPU 할당" + 인스턴스 교체 →
  응답 후 백그라운드 스레드 가공은 죽을 수 있음. MVP는 요청 내 동기 처리(+timeout/memory 상향),
  대량이면 Cloud Tasks/Pub-Sub. 진행상태는 인메모리 금지 → DB `upload_job`.

## 문제 해결
- `make deploy-api` 가 "인증된 계정 없음" → `make deploy-login` 먼저.
- 권한 에러(예: `PERMISSION_DENIED`): 로그인한 계정이 프로젝트 **소유자(Owner)** 또는
  (`run.admin` + `cloudbuild.builds.editor` + `artifactregistry.admin` + `secretmanager.admin`
  + `iam.serviceAccountUser` + `serviceusage.serviceUsageAdmin`) 역할이 있어야 함.
- 빌드/배포 에러에 `@cloudbuild.gserviceaccount.com`(구형 프로젝트)이 보이면 그 SA에도
  `roles/artifactregistry.writer` `roles/run.admin` `roles/iam.serviceAccountUser` 부여.
- 토큰 만료로 재로그인 필요하면 `make deploy-login` 다시.
- `--allow-unauthenticated` 라 URL이 공개됨(앱 레벨 JWT로 보호). 폐쇄망이면 추후 IAP/인증으로.
