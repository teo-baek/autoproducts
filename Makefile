# ezmerce — 개발 단축 명령  (사용법: `make` 또는 `make help`)
# 백엔드 = FastAPI(:8444) / 프론트 = Next(:3555)

WEB_DIR  := apps/web
API_DIR  := backend
WEB_PORT := 3555
API_PORT := 8444

.DEFAULT_GOAL := help
.PHONY: help dev web api front backend install build stop ports migrate

help: ## 명령 목록 보기
	@echo "ezmerce make 명령:"
	@grep -E '^[a-zA-Z_-]+:.*## .*$$' $(MAKEFILE_LIST) | sort \
	  | awk 'BEGIN{FS=":.*## "}{printf "  \033[36m%-14s\033[0m %s\n", $$1, $$2}'

dev: ## 프론트(:3555) + 백엔드(:8444) 동시 실행 — Ctrl+C 로 둘 다 종료
	@echo "▶ backend :$(API_PORT)  +  web :$(WEB_PORT)   (Ctrl+C 로 둘 다 종료)"
	@trap 'kill 0' EXIT INT TERM; \
	  ( cd $(API_DIR) && .venv/bin/python -m app.main ) & \
	  ( cd $(WEB_DIR) && npm run dev ) & \
	  wait

api: ## 백엔드만 실행 (FastAPI :8444)
	cd $(API_DIR) && .venv/bin/python -m app.main

backend: api ## (별칭) 백엔드 실행

web: ## 프론트만 실행 (Next :3555)
	cd $(WEB_DIR) && npm run dev

front: web ## (별칭) 프론트 실행

install: ## 백엔드+프론트 의존성 설치 (uv + npm)
	cd $(API_DIR) && uv sync --all-groups
	cd $(WEB_DIR) && npm install

build: ## 프론트 프로덕션 빌드 (next build)
	cd $(WEB_DIR) && npm run build

stop: ## :3555 / :8444 에 떠있는 dev 서버 종료
	-@lsof -ti:$(WEB_PORT) | xargs kill 2>/dev/null
	-@lsof -ti:$(API_PORT) | xargs kill 2>/dev/null
	@echo "stopped :$(WEB_PORT), :$(API_PORT)"

ports: ## 포트 사용 현황 확인
	@lsof -nP -iTCP:$(WEB_PORT) -iTCP:$(API_PORT) -sTCP:LISTEN 2>/dev/null || echo "둘 다 사용 안 함"

migrate: ## DB 마이그레이션 안내 (DDL 은 Supabase SQL Editor 에서 직접)
	@echo "DDL 은 Supabase SQL Editor 에서 실행하세요 (순서: $(API_DIR)/migrations/README.md)"
	@echo "최신: $(API_DIR)/migrations/2026-06-06_v2_core_09_pnum_not_unique.sql"

# ── Cloud Run 자동 배포 (make deploy) ───────────────────────────────
# 설정은 git 에 안 올라가는 deploy.env 에서 읽는다 (deploy.env.example 복사해서 채우기).
# 전용 서비스계정 키로만 인증하고 gcloud 상태를 .gcloud-ezmerce/ 에 격리한다
# → 맥OS 에 로그인된 다른 구글 계정과 절대 안 섞인다.  (가이드: backend/DEPLOY.md)
-include deploy.env

# deploy.env 값에 인라인 주석(# ...)이 섞여도 안전하게 — 주석 제거 후 남는 앞뒤 공백 제거
GCP_PROJECT     := $(strip $(GCP_PROJECT))
GCP_REGION      := $(strip $(GCP_REGION))
GCP_SERVICE     := $(strip $(GCP_SERVICE))
GCP_REPO        := $(strip $(GCP_REPO))
SUPABASE_URL    := $(strip $(SUPABASE_URL))
PUBLIC_BASE_URL := $(strip $(PUBLIC_BASE_URL))

GCLOUD  := CLOUDSDK_CONFIG=$(CURDIR)/.gcloud-ezmerce gcloud
GIT_SHA := $(shell git rev-parse --short HEAD 2>/dev/null || echo manual)
IMAGE    = $(GCP_REGION)-docker.pkg.dev/$(GCP_PROJECT)/$(GCP_REPO)/$(GCP_SERVICE):$(GIT_SHA)

.PHONY: deploy deploy-login deploy-auth deploy-setup deploy-url deploy-logs deploy-whoami

deploy-login: ## 1회: 전용 구글계정으로 브라우저 로그인 (격리 gcloud, 키 불필요)
	@test -n "$(GCP_PROJECT)" || { echo "✗ deploy.env 의 GCP_PROJECT 먼저 설정 (cp deploy.env.example deploy.env)"; exit 1; }
	@echo "▶ 브라우저가 열립니다 — '이 프로젝트 전용 구글계정'으로 로그인하세요 (개인계정 아님!)"
	@$(GCLOUD) auth login
	@$(GCLOUD) config set project "$(GCP_PROJECT)" >/dev/null 2>&1 || true
	@echo "✓ 로그인: $$($(GCLOUD) auth list --filter=status:ACTIVE --format='value(account)' 2>/dev/null)  /  project=$(GCP_PROJECT)"

deploy-auth: ## (내부) 격리된 전용 계정 인증 확인 — 내 기본 구글계정과 안 섞임
	@test -f deploy.env || { echo "✗ deploy.env 없음 — 'cp deploy.env.example deploy.env' 후 값 채우기 (가이드: backend/DEPLOY.md)"; exit 1; }
	@test -n "$(GCP_PROJECT)" || { echo "✗ deploy.env 의 GCP_PROJECT 미설정"; exit 1; }
	@if [ -n "$(GCP_SA_KEY)" ] && [ -f "$(GCP_SA_KEY)" ]; then \
	   $(GCLOUD) auth activate-service-account --key-file="$(GCP_SA_KEY)" --project="$(GCP_PROJECT)" >/dev/null 2>&1; \
	 fi
	@ACC=$$($(GCLOUD) auth list --filter=status:ACTIVE --format='value(account)' 2>/dev/null); \
	  if [ -z "$$ACC" ]; then echo "✗ 인증된 계정 없음 — 먼저 'make deploy-login' (브라우저 로그인) 하세요"; exit 1; fi; \
	  echo "✓ 인증: $$ACC  /  project=$(GCP_PROJECT)"

deploy-whoami: deploy-auth ## 지금 어떤 계정/프로젝트로 배포되는지 확인 (내 구글계정 아님 확인용)
	@$(GCLOUD) config list --format='value(core.account,core.project)'

deploy-setup: deploy-auth ## 1회 셋업: API 켜기 + Artifact Registry + 시크릿 + 권한
	@echo "▶ API 활성화 (run/build/artifactregistry/secretmanager)..."
	@$(GCLOUD) services enable run.googleapis.com cloudbuild.googleapis.com artifactregistry.googleapis.com secretmanager.googleapis.com --project=$(GCP_PROJECT)
	@echo "▶ Artifact Registry($(GCP_REPO)) 확인/생성..."
	@$(GCLOUD) artifacts repositories describe $(GCP_REPO) --location=$(GCP_REGION) --project=$(GCP_PROJECT) >/dev/null 2>&1 \
	  || $(GCLOUD) artifacts repositories create $(GCP_REPO) --repository-format=docker --location=$(GCP_REGION) --project=$(GCP_PROJECT)
	@echo "▶ 시크릿(ezmerce-supabase-service-key) 등록/갱신..."
	@case "$(SUPABASE_SERVICE_KEY)" in ""|PASTE_SERVICE_ROLE_KEY*) echo "✗ deploy.env 의 SUPABASE_SERVICE_KEY 미입력 — Supabase 대시보드 → Project Settings → API → service_role 키"; exit 1 ;; esac
	@if $(GCLOUD) secrets describe ezmerce-supabase-service-key --project=$(GCP_PROJECT) >/dev/null 2>&1; then \
	   printf '%s' "$(SUPABASE_SERVICE_KEY)" | $(GCLOUD) secrets versions add ezmerce-supabase-service-key --data-file=- --project=$(GCP_PROJECT) >/dev/null; \
	 else \
	   printf '%s' "$(SUPABASE_SERVICE_KEY)" | $(GCLOUD) secrets create ezmerce-supabase-service-key --data-file=- --project=$(GCP_PROJECT) >/dev/null; \
	 fi
	@echo "▶ Cloud Build/런타임 서비스계정 권한 부여..."
	@PN=$$($(GCLOUD) projects describe $(GCP_PROJECT) --format='value(projectNumber)'); \
	  CSA="$${PN}-compute@developer.gserviceaccount.com"; \
	  for ROLE in roles/cloudbuild.builds.builder roles/artifactregistry.writer roles/logging.logWriter roles/secretmanager.secretAccessor; do \
	    $(GCLOUD) projects add-iam-policy-binding $(GCP_PROJECT) --member="serviceAccount:$${CSA}" --role="$${ROLE}" >/dev/null; \
	  done
	@echo "✓ 셋업 완료 — 이제 'make deploy'"

deploy: deploy-auth ## ★ 빌드(Cloud Build) → Cloud Run 자동 배포
	@echo "▶ 빌드+푸시: $(IMAGE)"
	@$(GCLOUD) builds submit $(API_DIR) --config $(API_DIR)/cloudbuild.yaml --substitutions=_IMAGE=$(IMAGE) --project=$(GCP_PROJECT)
	@echo "▶ Cloud Run 배포: $(GCP_SERVICE) ($(GCP_REGION))"
	@$(GCLOUD) run deploy $(GCP_SERVICE) \
	  --image "$(IMAGE)" --region=$(GCP_REGION) --project=$(GCP_PROJECT) \
	  --platform=managed --allow-unauthenticated --port=8080 \
	  --cpu=1 --memory=512Mi --concurrency=40 --timeout=300 \
	  --min-instances=0 --max-instances=4 \
	  --set-env-vars=SUPABASE_URL=$(SUPABASE_URL),PUBLIC_BASE_URL=$(PUBLIC_BASE_URL),PLATFORM_CODE_PREFIX=EZM \
	  --set-secrets=SUPABASE_SERVICE_KEY=ezmerce-supabase-service-key:latest
	@echo "✓ 배포 완료 — URL: $$($(GCLOUD) run services describe $(GCP_SERVICE) --region=$(GCP_REGION) --project=$(GCP_PROJECT) --format='value(status.url)' 2>/dev/null)"

deploy-url: deploy-auth ## 배포된 서비스 URL 출력
	@$(GCLOUD) run services describe $(GCP_SERVICE) --region=$(GCP_REGION) --project=$(GCP_PROJECT) --format='value(status.url)'

deploy-logs: deploy-auth ## 최근 로그 50줄
	@$(GCLOUD) run services logs read $(GCP_SERVICE) --region=$(GCP_REGION) --project=$(GCP_PROJECT) --limit=50
