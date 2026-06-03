import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.services.accounts import register_account, RegisterError
from app.schemas.auth import RegisterRequest


class FakeAuthRepo:
    def __init__(self):
        self.profiles = []
        self.auth = []

    def create_auth_user(self, email, password):
        self.auth.append({"email": email, "password": password})
        return {"id": "uid-1"}

    def insert_profile(self, d):
        d = {**d}
        self.profiles.append(d)
        return d


def _req(**kw):
    base = dict(email="a@b.com", password="pw12345678", role="retail_seller", seller_type="independent")
    base.update(kw)
    return RegisterRequest(**base)


def test_register_independent_seller_seeds_wholesale_visibility():
    repo = FakeAuthRepo()
    out = register_account(repo, _req(full_name="홍길동"))
    assert out["id"] == "uid-1"
    assert out["status"] == "pending"               # 가입 직후 승인 대기
    assert out["seller_type"] == "independent"
    assert out["price_visibility"] == "wholesale"   # independent → 도매가 (시드)
    assert repo.auth[0]["email"] == "a@b.com"


def test_register_agency_affiliated_seller_visibility_none():
    out = register_account(FakeAuthRepo(), _req(seller_type="agency_affiliated"))
    assert out["price_visibility"] == "none"        # 에이전시 소속 셀러 → 미노출


def test_register_agency_role_has_null_seller_type():
    out = register_account(FakeAuthRepo(), _req(role="agency", seller_type=None))
    assert out["seller_type"] is None               # CHECK 제약(seller_type_only_for_retail) 정합
    assert out["price_visibility"] == "retail"


def test_register_rejects_privileged_roles_before_auth_create():
    repo = FakeAuthRepo()
    for role in ("admin", "wholesaler"):
        with pytest.raises(RegisterError):
            register_account(repo, _req(role=role, seller_type=None))
    assert repo.auth == []                           # 검증이 먼저 → orphan auth user 미생성


def test_register_retail_seller_requires_seller_type():
    with pytest.raises(RegisterError):
        register_account(FakeAuthRepo(), _req(seller_type=None))


def test_register_route_public_returns_pending(monkeypatch):
    import app.routers.auth as auth_mod
    monkeypatch.setattr(auth_mod, "SupabaseAuthRepo", FakeAuthRepo)
    res = TestClient(app).post("/auth/register", json={
        "email": "a@b.com", "password": "pw12345678",
        "role": "retail_seller", "seller_type": "independent",
    })
    assert res.status_code == 200
    body = res.json()
    assert body["status"] == "pending"
    assert body["price_visibility"] == "wholesale"


def test_register_route_rejects_admin(monkeypatch):
    import app.routers.auth as auth_mod
    monkeypatch.setattr(auth_mod, "SupabaseAuthRepo", FakeAuthRepo)
    res = TestClient(app).post("/auth/register", json={
        "email": "a@b.com", "password": "pw12345678", "role": "admin",
    })
    assert res.status_code == 400
