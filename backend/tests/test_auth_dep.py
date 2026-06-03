import jwt
import pytest
from app.core.auth import decode_jwt, verify_supabase_jwt, AuthError

SECRET = "test-secret"

def test_decode_valid_jwt():
    token = jwt.encode({"sub": "user-123"}, SECRET, algorithm="HS256")
    assert decode_jwt(token, SECRET)["sub"] == "user-123"

def test_decode_invalid_jwt_raises():
    with pytest.raises(AuthError):
        decode_jwt("garbage", SECRET)

def test_verify_supabase_jwt_garbage_raises():
    # 형식이 깨진 토큰은 JWKS 조회(네트워크) 전에 거부되어야 한다
    with pytest.raises(AuthError):
        verify_supabase_jwt("garbage")
