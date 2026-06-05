# ezmerce — 개발 단축 명령  (사용법: `make` 또는 `make help`)
# 백엔드 = FastAPI(:8444) / 프론트 = Next(:3555)

WEB_DIR  := apps/web
API_DIR  := backend
WEB_PORT := 3555
API_PORT := 8444

.DEFAULT_GOAL := help
.PHONY: help dev web api front backend install web-install api-install test build stop ports migrate

help: ## 명령 목록 보기
	@echo "ezmerce make 명령:"
	@grep -E '^[a-zA-Z_-]+:.*## .*$$' $(MAKEFILE_LIST) | sort \
	  | awk 'BEGIN{FS=":.*## "}{printf "  \033[36m%-13s\033[0m %s\n", $$1, $$2}'

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

install: api-install web-install ## 백엔드+프론트 의존성 전체 설치

api-install: ## 백엔드 의존성 (uv sync)
	cd $(API_DIR) && uv sync --all-groups

web-install: ## 프론트 의존성 (npm install)
	cd $(WEB_DIR) && npm install

test: ## 백엔드 테스트 (pytest)
	cd $(API_DIR) && .venv/bin/python -m pytest -q

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
	@echo "최신: $(API_DIR)/migrations/2026-06-05_v2_core_06_register_fields.sql"
