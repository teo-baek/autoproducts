from fastapi.testclient import TestClient
from app.main import app
from app.core.auth import get_current_user
from app.schemas.auth import CurrentUser
import app.routers.products as prod_mod


def _patch_repo(monkeypatch, store):
    class FakeRepo:
        def __init__(self, owner_wid=None):
            self.owner_wid = owner_wid

        def next_platform_code(self):
            return "EZM-000001"

        def insert_product(self, d):
            d = {**d, "id": "p1"}; store[d["id"]] = d; return d

        def insert_skus(self, rows):
            return rows

        def update_product(self, pid, patch):
            p = store.get(pid)
            if not p or (self.owner_wid is not None and p["wholesaler_id"] != self.owner_wid):
                raise prod_mod.ProductForbidden("상품을 찾을 수 없거나 권한이 없습니다")
            p.update(patch); return p

    monkeypatch.setattr(prod_mod, "SupabaseProductRepo", FakeRepo)


def _wholesaler(wid):
    return lambda: CurrentUser(id=f"u-{wid}", role="wholesaler", status="approved", wholesaler_id=wid)


def test_patch_blocked_for_foreign_wholesaler(monkeypatch):
    store = {"p1": {"id": "p1", "wholesaler_id": "w1", "item_name": "x"}}
    _patch_repo(monkeypatch, store)
    app.dependency_overrides[get_current_user] = _wholesaler("w9")
    try:
        r = TestClient(app).patch("/products/p1", json={"item_name": "해킹"})
        assert r.status_code == 404            # 타 업체 상품 → 404
        assert store["p1"]["item_name"] == "x"  # 변경 안 됨
    finally:
        app.dependency_overrides.clear()


def test_patch_owner_ok_and_strips_immutable_fields(monkeypatch):
    store = {"p1": {"id": "p1", "wholesaler_id": "w1", "platform_code": "EZM-000001", "item_name": "x"}}
    _patch_repo(monkeypatch, store)
    app.dependency_overrides[get_current_user] = _wholesaler("w1")
    try:
        r = TestClient(app).patch("/products/p1", json={
            "item_name": "수정", "wholesaler_id": "w9", "platform_code": "HACK"})
        assert r.status_code == 200
        assert store["p1"]["item_name"] == "수정"
        assert store["p1"]["wholesaler_id"] == "w1"          # 소유 이전 차단(불변)
        assert store["p1"]["platform_code"] == "EZM-000001"  # 식별자 불변
    finally:
        app.dependency_overrides.clear()


def test_delete_blocked_for_foreign_wholesaler(monkeypatch):
    store = {"p1": {"id": "p1", "wholesaler_id": "w1"}}
    _patch_repo(monkeypatch, store)
    app.dependency_overrides[get_current_user] = _wholesaler("w9")
    try:
        r = TestClient(app).delete("/products/p1")
        assert r.status_code == 404
        assert "deleted_at" not in store["p1"]               # soft delete 안 됨
    finally:
        app.dependency_overrides.clear()
