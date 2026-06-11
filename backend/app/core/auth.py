from functools import lru_cache

import jwt
from fastapi import Depends, Header, HTTPException
from jwt import PyJWKClient

from app.core.config import get_settings
from app.core.supabase import get_supabase
from app.schemas.auth import CurrentUser


class AuthError(Exception):
    pass


def decode_jwt(token: str, secret: str) -> dict:
    """레거시 HS256(대칭 시크릿) 검증. 신규 Supabase 프로젝트는 verify_supabase_jwt(JWKS) 사용."""
    try:
        return jwt.decode(token, secret, algorithms=["HS256"], options={"verify_aud": False})
    except Exception as e:  # noqa: BLE001
        raise AuthError(str(e))


@lru_cache
def _jwks_client() -> PyJWKClient:
    # JWKS 공개키 캐시(PyJWKClient 내부 캐시 사용)
    return PyJWKClient(get_settings().supabase_jwks_url)


def verify_supabase_jwt(token: str) -> dict:
    """Supabase 비대칭(ES256/RS256) 액세스 토큰을 JWKS 공개키로 검증."""
    try:
        signing_key = _jwks_client().get_signing_key_from_jwt(token)
        return jwt.decode(
            token, signing_key.key,
            algorithms=["ES256", "RS256"],
            options={"verify_aud": False},
        )
    except Exception as e:  # noqa: BLE001
        raise AuthError(str(e))


def _resolve_manager_id(sb, row: dict) -> str | None:
    """뷰어의 도매관리자(테넌트) id 를 역할별로 해석.

    셀러/admin: profiles.manager_id 직접. 도매상: manager_wholesalers(살아있는 1행)에서.
    멀티테넌트 스코프 키 — 모든 테넌트-스코프 조회가 이 값으로 필터한다.
    """
    if row.get("manager_id"):
        return row["manager_id"]
    if row.get("role") == "wholesaler" and row.get("wholesaler_id"):
        link = (
            sb.table("manager_wholesalers")
            .select("manager_id")
            .eq("wholesaler_id", row["wholesaler_id"])
            .is_("deleted_at", "null")
            .limit(1)
            .execute()
            .data
        )
        if link:
            return link[0].get("manager_id")
    return None


def get_current_user(authorization: str = Header(default="")) -> CurrentUser:
    if not authorization.startswith("Bearer "):
        raise HTTPException(401, "missing bearer token")
    token = authorization.split(" ", 1)[1]
    try:
        payload = verify_supabase_jwt(token)  # JWKS 공개키 검증(신규 프로젝트 기본)
    except AuthError:
        raise HTTPException(401, "invalid token")
    uid = payload["sub"]
    sb = get_supabase()
    row = sb.table("profiles").select("*").eq("id", uid).single().execute().data
    if not row:
        raise HTTPException(403, "no profile")
    row["manager_id"] = _resolve_manager_id(sb, row)
    return CurrentUser(**{k: row.get(k) for k in CurrentUser.model_fields})


def get_current_user_optional(authorization: str = Header(default="")) -> CurrentUser | None:
    """선택적 인증 — 토큰이 없거나 유효하지 않으면 None(401 미발생).

    '공개 + 로그인 시 역할별' 혼용 엔드포인트(예: QR 공개 카드)용. 가격/재고 같은
    역할 의존 필드는 호출부에서 None 여부 + status 로 게이팅한다(미로그인=공개 최소 응답).
    """
    if not authorization.startswith("Bearer "):
        return None
    token = authorization.split(" ", 1)[1]
    try:
        payload = verify_supabase_jwt(token)
    except AuthError:
        return None
    uid = payload.get("sub")
    if not uid:
        return None
    try:
        sb = get_supabase()
        row = sb.table("profiles").select("*").eq("id", uid).single().execute().data
    except Exception:  # noqa: BLE001 — 프로필 조회 실패도 익명 취급(공개 카드는 계속 동작)
        return None
    if not row:
        return None
    try:
        row["manager_id"] = _resolve_manager_id(sb, row)
    except Exception:  # noqa: BLE001 — 테넌트 해석 실패도 익명/최소 취급(공개 카드는 계속 동작)
        row["manager_id"] = None
    return CurrentUser(**{k: row.get(k) for k in CurrentUser.model_fields})
