import jwt
import pytest
from app.core.auth import decode_jwt, AuthError

SECRET = "test-secret"

def test_decode_valid_jwt():
    token = jwt.encode({"sub": "user-123"}, SECRET, algorithm="HS256")
    assert decode_jwt(token, SECRET)["sub"] == "user-123"

def test_decode_invalid_jwt_raises():
    with pytest.raises(AuthError):
        decode_jwt("garbage", SECRET)
