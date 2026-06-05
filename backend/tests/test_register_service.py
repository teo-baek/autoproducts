import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.services.accounts import register_account, RegisterError
from app.schemas.auth import RegisterRequest


import os


class FakeAuthRepo:
    def __init__(self):
        self.profiles = []
        self.auth = []
        self.uploaded = []

    def create_auth_user(self, email, password):
        self.auth.append({"email": email, "password": password})
        return {"id": "uid-1"}

    def insert_profile(self, d):
        d = {**d}
        self.profiles.append(d)
        return d

    def upload_document(self, user_id, kind, filename, content, content_type):
        self.uploaded.append((user_id, kind, len(content), content_type))
        return f"{user_id}/{kind}{os.path.splitext(filename)[1]}"

    def set_document_paths(self, user_id, paths):
        return {"id": user_id, **paths}


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


def test_register_rejects_admin_before_auth_create():
    repo = FakeAuthRepo()
    with pytest.raises(RegisterError):                # admin 만 자가가입 거부(권한 상승 차단)
        register_account(repo, _req(role="admin", seller_type=None))
    assert repo.auth == []                            # 검증이 먼저 → orphan auth user 미생성


def test_register_wholesaler_self_register_allowed():
    out = register_account(FakeAuthRepo(), _req(role="wholesaler", seller_type=None, company_name="(주)도매프로"))
    assert out["role"] == "wholesaler"
    assert out["status"] == "pending"                 # 도매도 가입 후 관리자 승인 대기
    assert out["seller_type"] is None                 # CHECK 제약 정합
    assert out["price_visibility"] == "none"          # 도매 기본 시드(관리뷰는 role 기준 별도)
    assert out["company_name"] == "(주)도매프로"        # 회사명 저장


def test_register_stores_company_name():
    out = register_account(FakeAuthRepo(), _req(company_name="라라스상회"))
    assert out["company_name"] == "라라스상회"


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


def test_upload_documents_authenticated(monkeypatch):
    import app.routers.auth as auth_mod
    from app.core.auth import get_current_user
    from app.schemas.auth import CurrentUser

    monkeypatch.setattr(auth_mod, "SupabaseAuthRepo", FakeAuthRepo)
    app.dependency_overrides[get_current_user] = lambda: CurrentUser(
        id="uid-1", role="wholesaler", status="pending"
    )
    try:
        c = TestClient(app)
        # 파일 없음 → 400
        assert c.post("/auth/register/documents").status_code == 400
        # 정상 PDF → 200 + 경로 기록
        ok = c.post(
            "/auth/register/documents",
            files={"business_cert": ("cert.pdf", b"%PDF-1.4 hi", "application/pdf")},
        )
        assert ok.status_code == 200
        assert ok.json()["paths"]["business_cert_path"].endswith(".pdf")
        # 허용 안 되는 타입 → 400
        bad = c.post(
            "/auth/register/documents",
            files={"business_cert": ("x.txt", b"hello", "text/plain")},
        )
        assert bad.status_code == 400
    finally:
        app.dependency_overrides.pop(get_current_user, None)
