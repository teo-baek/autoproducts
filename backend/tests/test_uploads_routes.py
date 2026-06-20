import io
import json
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
        return next((j for j in self.jobs if j["id"] == jid), None)

    def list_jobs(self, wid, limit=20):
        return [j for j in self.jobs if j.get("wholesaler_id") == wid][:limit]

    def products_pnum_map(self, wid):
        return dict(self._pmap)

    def insert_images(self, rows):
        out = []
        for r in rows:
            r = {**r, "id": f"img{len(self.images) + 1}"}; self.images.append(r); out.append(r)
        return out

    def list_unmatched_images(self, wid):
        return [i for i in self.images if i["match_status"] == "unmatched"]

    def update_image(self, iid, patch, wholesaler_id=None):
        for i in self.images:
            if i["id"] == iid and (wholesaler_id is None or i.get("wholesaler_id") == wholesaler_id):
                i.update(patch); return i
        return None


def _wholesaler():
    return CurrentUser(id="staff-1", role="wholesaler", status="approved", wholesaler_id="w1")


def _xlsx_bytes(rows):
    wb = openpyxl.Workbook(); ws = wb.active
    ws.append(["품번", "상품명", "색상", "사이즈", "도매가", "판매가"])
    for r in rows:
        ws.append(r)
    buf = io.BytesIO(); wb.save(buf); return buf.getvalue()


def test_validate_route_dry_run(monkeypatch):
    # 1단계 — 검증만(드라이런): 상품 미생성, 미리보기 카운트만
    shared = FakeUploadRepo()
    monkeypatch.setattr(up_mod, "SupabaseUploadRepo", lambda: shared)
    app.dependency_overrides[get_current_user] = _wholesaler
    try:
        data = _xlsx_bytes([("1001", "셔츠", "화이트", "F", 12000, 29000)])
        res = TestClient(app).post("/uploads/excel/validate", files={"file": ("p.xlsx", data, XLSX_CT)})
        assert res.status_code == 200
        assert res.json()["product_count"] == 1
        assert shared.products == []        # DB 미기록
    finally:
        app.dependency_overrides.clear()


def test_commit_route_creates_products_and_matches(monkeypatch):
    # 4단계 — 엑셀 + 매니페스트를 한 번에 커밋(상품 생성 + 이미지 매칭)
    shared = FakeUploadRepo()
    monkeypatch.setattr(up_mod, "SupabaseUploadRepo", lambda: shared)
    app.dependency_overrides[get_current_user] = _wholesaler
    try:
        data = _xlsx_bytes([("1001", "셔츠", "화이트", "F", 12000, 29000)])
        manifest = json.dumps([
            {"original_filename": "1001_a.jpg", "storage_path": "w1/1001_a.jpg"},
            {"original_filename": "zzz.jpg", "storage_path": "w1/zzz.jpg"},
        ])
        res = TestClient(app).post("/uploads/commit",
                                   files={"file": ("p.xlsx", data, XLSX_CT)}, data={"images": manifest})
        assert res.status_code == 200
        body = res.json()
        assert body["job_id"] == "job-1"
        assert len(body["created"]) == 1
        assert body["matched"] == ["1001_a.jpg"]
        assert body["unmatched"] == ["zzz.jpg"]
    finally:
        app.dependency_overrides.clear()


def test_commit_rejects_unsupported_format(monkeypatch):
    shared = FakeUploadRepo()
    monkeypatch.setattr(up_mod, "SupabaseUploadRepo", lambda: shared)
    app.dependency_overrides[get_current_user] = _wholesaler
    try:
        res = TestClient(app).post("/uploads/commit",
                                   files={"file": ("p.txt", b"hello", "text/plain")}, data={"images": "[]"})
        assert res.status_code == 400
    finally:
        app.dependency_overrides.clear()


def test_commit_requires_wholesaler(monkeypatch):
    app.dependency_overrides[get_current_user] = lambda: CurrentUser(
        id="u", role="retail_seller", status="approved", seller_type="independent")
    try:
        res = TestClient(app).post("/uploads/commit",
                                   files={"file": ("p.xlsx", b"x", XLSX_CT)}, data={"images": "[]"})
        assert res.status_code == 403
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


def test_list_jobs_scoped_to_owner(monkeypatch):
    shared = FakeUploadRepo()
    shared.jobs.append({"id": "job-1", "wholesaler_id": "w1", "status": "completed"})
    shared.jobs.append({"id": "job-9", "wholesaler_id": "w9", "status": "completed"})
    monkeypatch.setattr(up_mod, "SupabaseUploadRepo", lambda: shared)
    app.dependency_overrides[get_current_user] = _wholesaler
    try:
        res = TestClient(app).get("/uploads/jobs")
        assert res.status_code == 200
        jobs = res.json()["jobs"]
        assert [j["id"] for j in jobs] == ["job-1"]      # 타 업체(w9) 제외
    finally:
        app.dependency_overrides.clear()


def test_foreign_wholesaler_cannot_touch_others_job(monkeypatch):
    """도매 w1 의 job 을 w9 직원이 호출 → 404 (IDOR 차단)."""
    shared = FakeUploadRepo()
    shared.create_upload_job({"wholesaler_id": "w1"})
    monkeypatch.setattr(up_mod, "SupabaseUploadRepo", lambda: shared)
    app.dependency_overrides[get_current_user] = lambda: CurrentUser(
        id="intruder", role="wholesaler", status="approved", wholesaler_id="w9")
    try:
        c = TestClient(app)
        assert c.get("/uploads/job-1/unmatched").status_code == 404
        assert c.post("/uploads/job-1/match",
                      json={"image_id": "img1", "source_p_number": "1001"}).status_code == 404
    finally:
        app.dependency_overrides.clear()


# ── /uploads/sign — 브라우저 직접 업로드용 V4 서명 PUT URL(GCS) ───────────────────
def _fake_sign(monkeypatch):
    # 실제 GCP 호출 없이 서명 URL 만 가짜로(핸들러 로직=스코프·검증만 테스트). public_url 은 config 문자열이라 그대로 사용.
    monkeypatch.setattr(up_mod.gcs, "signed_put_url",
                        lambda bucket, path, content_type, **kw: f"https://signed.example/{path}?X=1")


def test_sign_happy_path_scopes_to_wholesaler(monkeypatch):
    _fake_sign(monkeypatch)
    app.dependency_overrides[get_current_user] = _wholesaler   # 승인된 도매 w1
    try:
        res = TestClient(app).post("/uploads/sign",
                                   json={"object_key": "bulk/1.jpg", "content_type": "image/jpeg"})
        assert res.status_code == 200
        b = res.json()
        assert b["storage_path"] == "w1/bulk/1.jpg"            # 도매 스코프 = 토큰 wid 가 prefix
        assert b["content_type"] == "image/jpeg"
        assert b["upload_url"].endswith("w1/bulk/1.jpg?X=1")
        assert b["public_url"].endswith("/w1/bulk/1.jpg")      # GCS 공개 URL 형식
    finally:
        app.dependency_overrides.clear()


def test_sign_prefix_forced_from_token_not_client(monkeypatch):
    """클라가 다른 도매 prefix(w1/...)를 보내도 토큰 wid(w9) 밑으로만 스코프 → IDOR 차단."""
    _fake_sign(monkeypatch)
    app.dependency_overrides[get_current_user] = lambda: CurrentUser(
        id="u", role="wholesaler", status="approved", wholesaler_id="w9")
    try:
        res = TestClient(app).post("/uploads/sign",
                                   json={"object_key": "w1/steal.jpg", "content_type": "image/jpeg"})
        assert res.status_code == 200
        assert res.json()["storage_path"] == "w9/w1/steal.jpg"  # 항상 호출자(w9) 밑 — 남의 칸 못 씀
    finally:
        app.dependency_overrides.clear()


def test_sign_rejects_path_traversal_and_empty(monkeypatch):
    _fake_sign(monkeypatch)
    app.dependency_overrides[get_current_user] = _wholesaler
    try:
        c = TestClient(app)
        assert c.post("/uploads/sign",
                      json={"object_key": "../other/x.jpg", "content_type": "image/jpeg"}).status_code == 400
        assert c.post("/uploads/sign",
                      json={"object_key": "   ", "content_type": "image/jpeg"}).status_code == 400
    finally:
        app.dependency_overrides.clear()


def test_sign_requires_wholesaler(monkeypatch):
    _fake_sign(monkeypatch)
    app.dependency_overrides[get_current_user] = lambda: CurrentUser(
        id="u", role="retail_seller", status="approved", seller_type="independent")
    try:
        res = TestClient(app).post("/uploads/sign",
                                   json={"object_key": "x.jpg", "content_type": "image/jpeg"})
        assert res.status_code == 403                          # 도매 전용 가드
    finally:
        app.dependency_overrides.clear()
