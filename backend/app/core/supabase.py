from functools import lru_cache

import httpx
from supabase import Client, create_client
from supabase.lib.client_options import SyncClientOptions

from app.core.config import get_settings


@lru_cache
def get_supabase() -> Client:
    s = get_settings()
    # ⚠️ HTTP/1.1 강제 + 연결 재시도. (DB/Auth 는 Supabase 유지 — 이건 그 httpx 전송계층 안정화)
    # 기본 supabase httpx 클라이언트는 http2=True 라, lru_cache 로 오래 사는 싱글톤 연결이 서버 GOAWAY 를
    # 맞으면 진행 중이던 요청이 무재시도로 깨진다(`<ConnectionTerminated error_code:1 …>` → 500).
    # 동시 업로드(/sign 병렬)에서 관측됨. http2 를 끄면 그 GOAWAY-스트림 실패 클래스가 사라지고,
    # HTTPTransport(retries) 가 죽은 keep-alive 연결 재사용 레이스를 연결 단계에서 자동 흡수한다.
    http_client = httpx.Client(
        http2=False,
        follow_redirects=True,
        timeout=httpx.Timeout(30.0),
        transport=httpx.HTTPTransport(retries=3),  # 연결 오류(ConnectError 등)만 재시도 — 멱등
    )
    # service role 키 — 서버 전용. RISK(side-effect): 절대 프론트 노출 금지
    # ⚠️ .strip(): 키/URL 은 apikey·Authorization 헤더로 들어가는데, 배포 시크릿이 끝에 줄바꿈을 달고 오면
    # (Secret Manager 를 `echo` 로 만들면 흔함) HTTP/1.1(h11)이 "Illegal header value" 로 거부한다(HTTP/2 는 봐줌).
    # 시크릿이 더럽든 깨끗하든 영구 방어 — 깨끗하면 no-op.
    return create_client(
        s.supabase_url.strip(),
        s.supabase_service_key.strip(),
        options=SyncClientOptions(httpx_client=http_client),
    )
