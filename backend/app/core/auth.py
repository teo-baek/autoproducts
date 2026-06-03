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
    return CurrentUser(**{k: row.get(k) for k in CurrentUser.model_fields})
