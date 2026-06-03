import io
import openpyxl
from fastapi.testclient import TestClient
from app.main import app
from app.core.auth import get_current_user
from app.schemas.auth import CurrentUser
import app.routers.uploads as up_mod

XLSX_CT = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


class FakeUploadRepo:
    def __init__(self):
        self.products = []; self.skus = []; self.jobs = []; self.images = []
        self.seq = 0; self._pmap = {}

    def next_platform_code(self):
        self.seq += 1; return f"EZM-{self.seq:06d}"

    def insert_product(self, d):
        d = {**d, "id": f"p{len(self.products) + 1}"}
        self.products.append(d); self._pmap[d["source_p_number"]] = d["id"]; return d

    def insert_skus(self, rows):
        self.skus.extend(rows); return rows

    def create_upload_job(self, d):
        d = {**d, "id": "job-1"}; self.jobs.append(d); return d

    def update_upload_job(self, jid, patch):
        for j in self.jobs:
            if j["id"] == jid: j.update(patch); return j
        return {"id": jid, **patch}

    def get_upload_job(self, jid):
        return next((j for j in self.jobs if j["id"] == jid), {"id": jid, "wholesaler_id": "w1"})

    def products_pnum_map(self, wid):
        return dict(self._pmap)

    def insert_images(self, rows):
        out = []
        for r in rows:
            r = {**r, "id": f"img{len(self.images) + 1}"}; self.images.append(r); out.append(r)
        return out

    def list_unmatched_images(self, wid):
        return [i for i in self.images if i["match_status"] == "unmatched"]

    def update_image(self, iid, patch):
        for i in self.images:
            if i["id"] == iid: i.update(patch); return i
        return {"id": iid, **patch}


def _wholesaler():
    return CurrentUser(id="staff-1", role="wholesaler", status="approved", wholesaler_id="w1")


def _xlsx_bytes(rows):
    wb = openpyxl.Workbook(); ws = wb.active
    ws.append(["품번", "상품명", "색상", "사이즈", "도매가", "판매가"])
    for r in rows:
        ws.append(r)
    buf = io.BytesIO(); wb.save(buf); return buf.getvalue()


def test_upload_excel_route_creates_products(monkeypatch):
    shared = FakeUploadRepo()
    monkeypatch.setattr(up_mod, "SupabaseUploadRepo", lambda: shared)
    app.dependency_overrides[get_current_user] = _wholesaler
    try:
        data = _xlsx_bytes([("1001", "셔츠", "화이트", "F", 12000, 29000)])
        res = TestClient(app).post("/uploads/excel", files={"file": ("p.xlsx", data, XLSX_CT)})
        assert res.status_code == 200
        body = res.json()
        assert body["job_id"] == "job-1"
        assert len(body["created"]) == 1
    finally:
        app.dependency_overrides.clear()


def test_upload_excel_requires_wholesaler(monkeypatch):
    app.dependency_overrides[get_current_user] = lambda: CurrentUser(
        id="u", role="retail_seller", status="approved", seller_type="independent")
    try:
        res = TestClient(app).post("/uploads/excel", files={"file": ("p.xlsx", b"x", XLSX_CT)})
        assert res.status_code == 403
    finally:
        app.dependency_overrides.clear()


def test_attach_images_route_splits_matched(monkeypatch):
    shared = FakeUploadRepo()
    shared.create_upload_job({"wholesaler_id": "w1"})
    shared.insert_product({"wholesaler_id": "w1", "source_p_number": "1001",
                           "platform_code": "EZM-1", "item_name": "셔츠"})
    monkeypatch.setattr(up_mod, "SupabaseUploadRepo", lambda: shared)
    app.dependency_overrides[get_current_user] = _wholesaler
    try:
        res = TestClient(app).post("/uploads/images", json={"job_id": "job-1", "images": [
            {"original_filename": "1001_a.jpg", "storage_path": "w1/1001_a.jpg"},
            {"original_filename": "zzz.jpg", "storage_path": "w1/zzz.jpg"},
        ]})
        assert res.status_code == 200
        body = res.json()
        assert body["matched"] == ["1001_a.jpg"]
        assert body["unmatched"] == ["zzz.jpg"]
    finally:
        app.dependency_overrides.clear()


def test_unmatched_and_manual_match_routes(monkeypatch):
    shared = FakeUploadRepo()
    shared.create_upload_job({"wholesaler_id": "w1"})
    shared.insert_product({"wholesaler_id": "w1", "source_p_number": "1001",
                           "platform_code": "EZM-1", "item_name": "셔츠"})
    shared.insert_images([{"wholesaler_id": "w1", "storage_path": "w1/x.jpg",
                           "original_filename": "x.jpg", "product_id": None, "match_status": "unmatched"}])
    monkeypatch.setattr(up_mod, "SupabaseUploadRepo", lambda: shared)
    app.dependency_overrides[get_current_user] = _wholesaler
    try:
        c = TestClient(app)
        un = c.get("/uploads/job-1/unmatched")
        assert un.status_code == 200 and len(un.json()) == 1
        m = c.post("/uploads/job-1/match", json={"image_id": "img1", "source_p_number": "1001"})
        assert m.status_code == 200 and m.json()["match_status"] == "matched"
        bad = c.post("/uploads/job-1/match", json={"image_id": "img1", "source_p_number": "NOPE"})
        assert bad.status_code == 400
    finally:
        app.dependency_overrides.clear()
