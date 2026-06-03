import jwt
from fastapi import Depends, Header
from app.core.config import get_settings
from app.core.supabase import get_supabase
from app.schemas.auth import CurrentUser


class AuthError(Exception):
    pass


def decode_jwt(token: str, secret: str) -> dict:
    try:
        return jwt.decode(token, secret, algorithms=["HS256"], options={"verify_aud": False})
    except Exception as e:  # noqa: BLE001
        raise AuthError(str(e))


def get_current_user(authorization: str = Header(default="")) -> CurrentUser:
    from fastapi import HTTPException
    if not authorization.startswith("Bearer "):
        raise HTTPException(401, "missing bearer token")
    token = authorization.split(" ", 1)[1]
    try:
        payload = decode_jwt(token, get_settings().supabase_jwt_secret)
    except AuthError:
        raise HTTPException(401, "invalid token")
    uid = payload["sub"]
    sb = get_supabase()
    row = sb.table("profiles").select("*").eq("id", uid).single().execute().data
    if not row:
        raise HTTPException(403, "no profile")
    return CurrentUser(**{k: row.get(k) for k in CurrentUser.model_fields})
