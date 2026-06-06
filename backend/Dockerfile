# ezmerce 백엔드(FastAPI) — Cloud Run 용 이미지.
# 빌드 컨텍스트 = backend/  (예: `docker build -t ezmerce-api backend`)
# uv 로 prod 의존성만 설치(dev/notebook 그룹 제외) → 슬림 런타임에 .venv 복사.

# ───────────────────────── builder ─────────────────────────
# runtime 과 동일한 python:3.12-slim 에서 venv 를 만들어 인터프리터 경로를 일치시킨다.
# (uv 공식 패턴: uv 바이너리만 가져오고 UV_PYTHON_DOWNLOADS=0 으로 시스템 파이썬 사용)
FROM python:3.12-slim-bookworm AS builder

# 재현성 위해 버전 핀 권장 (예: ghcr.io/astral-sh/uv:0.9.5)
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=0

WORKDIR /app

# 의존성 레이어 캐시: 락파일만 먼저 복사해 동기화 (앱 코드 변경 시 재설치 안 함)
# (BuildKit 전용 --mount 캐시는 Cloud Build(클래식 빌더)에서 미지원 + 매 빌드 새 VM 이라 무의미 → 미사용)
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-install-project --no-dev

# ───────────────────────── runtime ─────────────────────────
FROM python:3.12-slim-bookworm AS runtime

# 비루트 실행
RUN groupadd -r app && useradd -r -g app app

WORKDIR /app

# 가상환경 + 앱 코드만 (tests/notebooks/migrations 등은 .dockerignore 로 제외)
COPY --from=builder /app/.venv /app/.venv
COPY app ./app

ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

USER app
EXPOSE 8080

# Cloud Run 은 $PORT(기본 8080)를 주입. reload 없이 prod 기동, 0.0.0.0 바인딩.
# exec 로 sh 를 대체해 SIGTERM 이 uvicorn 에 직접 도달 → graceful shutdown.
CMD ["sh", "-c", "exec uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8080}"]
