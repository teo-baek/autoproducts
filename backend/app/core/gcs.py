"""Google Cloud Storage 클라이언트 + 헬퍼 — Supabase Storage 대체.

⚠️ DB/Auth/JWT 는 계속 Supabase(`app/core/supabase.py`). 여기는 **파일 저장소**만 담당한다.
- 공개 버킷(`gcs_product_bucket`): 객체 공개 read → `public_url()` 로 표시용 URL 생성.
- 비공개 버킷(`gcs_doc_bucket`): 서비스계정 전용. 읽기는 `signed_get_url()`(가입서류 열람, Phase 2).
- 업로드: 프론트가 백엔드에서 받은 **V4 signed PUT URL** 로 GCS 에 직접 PUT(`signed_put_url()`).

**키리스 서명:** Cloud Run 런타임 SA + IAM signBlob(SA self `tokenCreator`) 로 서명한다(SA 키 파일 불필요).
`gcs_signing_sa` 가 설정되면 ADC 자격증명의 access_token 으로 IAM signBlob 을 호출해 그 SA 명의로 서명한다
(운영=런타임 SA 가 자기 자신을, 로컬=개발자 계정이 런타임 SA 를 임퍼소네이트). 빈값이면 자격증명 자체 키로 서명 시도.
"""
import threading
from datetime import timedelta
from functools import lru_cache

from google.auth import default as _google_auth_default
from google.auth.transport.requests import Request as _GoogleAuthRequest
from google.cloud import storage

from app.core.config import get_settings

_SCOPES = ["https://www.googleapis.com/auth/cloud-platform"]
_DEFAULT_SIGN_TTL = 900  # 15분

# 서명용 ADC 자격증명 캐시 — 매 서명마다 default()/refresh 하던 오버헤드 제거(대량 업로드 시 N회 → 만료시에만).
# 토큰은 ~1시간 유효하므로 만료 직전까지 재사용. FastAPI 동기 엔드포인트는 스레드풀에서 돌아 동시 호출되므로
# 초기화·갱신을 Lock 으로 보호(임계구역은 valid 체크/refresh 뿐 — 평상시 매우 짧음).
_signer = None
_signer_lock = threading.Lock()


@lru_cache
def get_gcs() -> storage.Client:
    """서비스계정(ADC) 기반 GCS 클라이언트 — DB/Auth 와 분리된 별도 전송 계층."""
    s = get_settings()
    return storage.Client(project=s.gcs_project or None)


def upload_bytes(bucket: str, path: str, data: bytes, content_type: str = "application/octet-stream") -> None:
    """bytes 를 버킷/경로에 업로드(덮어쓰기 = upsert 동등). 썸네일·staging·서류 서버측 쓰기에 사용."""
    get_gcs().bucket(bucket).blob(path).upload_from_string(data, content_type=content_type)


def download_bytes(bucket: str, path: str) -> bytes:
    """버킷/경로 객체 bytes 다운로드. 엑셀 셀 임베드·썸네일 가공 원본 읽기에 사용."""
    return get_gcs().bucket(bucket).blob(path).download_as_bytes()


def public_url(path: str) -> str:
    """공개 버킷 객체의 표시용 공개 URL. `{GCS_PUBLIC_BASE}/{path}` (Supabase public URL 대체)."""
    return f"{get_settings().gcs_public_base_url}/{path.lstrip('/')}"


def _signing_kwargs() -> dict:
    """키리스 서명 인자 — gcs_signing_sa 설정 시 IAM signBlob(access_token) 사용.

    ADC 자격증명을 모듈 캐시(`_signer`)로 재사용하고, 토큰이 만료(`not valid`)일 때만 refresh.
    `service_account_email`(서명 대상 SA)과 ADC 신원은 별개라 캐시 안전 — 운영=런타임 SA, 로컬=개발자 ADC.
    """
    sa = get_settings().gcs_signing_sa
    if not sa:
        return {}
    global _signer
    with _signer_lock:
        if _signer is None:
            _signer, _ = _google_auth_default(scopes=_SCOPES)
        if not _signer.valid:                       # 토큰 없음/만료일 때만 네트워크 refresh
            _signer.refresh(_GoogleAuthRequest())
        token = _signer.token
    return {"service_account_email": sa, "access_token": token}


def signed_put_url(bucket: str, path: str, content_type: str, ttl_seconds: int = _DEFAULT_SIGN_TTL) -> str:
    """브라우저 직접 업로드용 V4 signed PUT URL. 클라이언트는 동일 content_type 으로 PUT 해야 한다."""
    blob = get_gcs().bucket(bucket).blob(path)
    return blob.generate_signed_url(
        version="v4",
        expiration=timedelta(seconds=ttl_seconds),
        method="PUT",
        content_type=content_type,
        **_signing_kwargs(),
    )


def signed_get_url(bucket: str, path: str, ttl_seconds: int = _DEFAULT_SIGN_TTL) -> str:
    """비공개 객체(가입 서류 등) 단기 열람용 V4 signed GET URL — 공개 URL 없는 비공개 버킷 읽기."""
    blob = get_gcs().bucket(bucket).blob(path)
    return blob.generate_signed_url(
        version="v4",
        expiration=timedelta(seconds=ttl_seconds),
        method="GET",
        **_signing_kwargs(),
    )
