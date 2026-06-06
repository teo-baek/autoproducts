import openpyxl
import pytest
from app.services.uploads import (
    ingest_excel, attach_images, resolve_match, list_unmatched, UploadError, UploadForbidden,
)


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
        return next((j for j in self.jobs if j["id"] == jid), None)   # 없는 job → None

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


def _make_xlsx(path, rows):
    wb = openpyxl.Workbook(); ws = wb.active
    ws.append(["품번", "상품명", "색상", "사이즈", "도매가", "판매가"])
    for r in rows:
        ws.append(r)
    wb.save(path)


def test_ingest_excel_groups_rows_into_products_and_skus(tmp_path):
    p = tmp_path / "in.xlsx"
    _make_xlsx(p, [
        ("1001", "린넨셔츠", "화이트", "F", 12000, 29000),
        ("1001", "린넨셔츠", "블랙", "F", 12000, 29000),   # 같은 품번 → 같은 상품, sku 추가
        ("1002", "데님", "인디고", "M", 20000, 45000),
    ])
    repo = FakeUploadRepo()
    out = ingest_excel(repo, "w1", str(p), created_by="staff-1")
    assert len(out["products"]) == 2            # 품번 2종 → 상품 2개
    assert len(repo.skus) == 3                  # sku 3행
    assert out["job"]["status"] == "needs_matching"
    assert out["job"]["total_rows"] == 3
    assert repo.products[0]["created_by"] == "staff-1"


def test_ingest_excel_records_parse_errors(tmp_path):
    p = tmp_path / "in.xlsx"
    _make_xlsx(p, [
        ("1001", "정상", "화이트", "F", 12000, 29000),
        ("1002", "", "블랙", "F", 12000, 29000),            # 상품명 누락 → error
        ("1003", "가격이상", "레드", "F", "NOTNUM", 29000),  # 도매가 정수변환 실패 → error
    ])
    repo = FakeUploadRepo()
    out = ingest_excel(repo, "w1", str(p))
    assert len(out["products"]) == 1
    assert out["job"]["error_rows"] == 2
    assert len(out["errors"]) == 2


def test_ingest_excel_no_valid_rows_marks_failed(tmp_path):
    p = tmp_path / "in.xlsx"
    # 품번·상품명 둘 다 없으면 식별 불가 → 유효행 0 → failed
    _make_xlsx(p, [("", "", "화이트", "F", 12000, 29000)])
    out = ingest_excel(FakeUploadRepo(), "w1", str(p))
    assert out["products"] == []
    assert out["job"]["status"] == "failed"


def test_attach_images_matches_by_filename_and_updates_job():
    repo = FakeUploadRepo()
    repo.create_upload_job({"wholesaler_id": "w1"})
    repo.insert_product({"wholesaler_id": "w1", "source_p_number": "1001",
                         "platform_code": "EZM-1", "item_name": "셔츠"})
    out = attach_images(repo, "job-1", [
        {"original_filename": "1001_front.jpg", "storage_path": "w1/1001_front.jpg"},
        {"original_filename": "9999.jpg", "storage_path": "w1/9999.jpg"},
    ], created_by="staff-1", caller_wid="w1")
    assert out["matched"] == ["1001_front.jpg"]
    assert out["unmatched"] == ["9999.jpg"]
    assert any(i["match_status"] == "matched" and i["product_id"] == "p1" for i in repo.images)
    job = repo.get_upload_job("job-1")
    assert job["matched_rows"] == 1
    assert job["status"] == "needs_matching"     # 미매칭 잔존 → 계속 매칭 대기


def test_attach_images_all_matched_completes_job():
    repo = FakeUploadRepo()
    repo.create_upload_job({"wholesaler_id": "w1"})
    repo.insert_product({"wholesaler_id": "w1", "source_p_number": "1001",
                         "platform_code": "EZM-1", "item_name": "셔츠"})
    attach_images(repo, "job-1", [{"original_filename": "1001.jpg", "storage_path": "w1/1001.jpg"}],
                  caller_wid="w1")
    assert repo.get_upload_job("job-1")["status"] == "completed"


def test_resolve_match_links_image_to_product():
    repo = FakeUploadRepo()
    repo.create_upload_job({"wholesaler_id": "w1"})
    repo.insert_product({"wholesaler_id": "w1", "source_p_number": "1001",
                         "platform_code": "EZM-1", "item_name": "셔츠"})
    repo.insert_images([{"wholesaler_id": "w1", "storage_path": "w1/x.jpg",
                         "original_filename": "x.jpg", "product_id": None, "match_status": "unmatched"}])
    out = resolve_match(repo, "job-1", image_id="img1", source_p_number="1001", caller_wid="w1")
    assert out["product_id"] == "p1" and out["match_status"] == "matched"


def test_resolve_match_unknown_pnum_raises():
    repo = FakeUploadRepo()
    repo.create_upload_job({"wholesaler_id": "w1"})
    with pytest.raises(UploadError):
        resolve_match(repo, "job-1", image_id="img1", source_p_number="NOPE", caller_wid="w1")


def test_uploads_reject_foreign_caller_idor():
    """도매 w1 의 job 을 w2 가 건드리면 모두 404(UploadForbidden) — IDOR 차단."""
    repo = FakeUploadRepo()
    repo.create_upload_job({"wholesaler_id": "w1"})
    repo.insert_product({"wholesaler_id": "w1", "source_p_number": "1001",
                         "platform_code": "EZM-1", "item_name": "셔츠"})
    with pytest.raises(UploadForbidden):
        attach_images(repo, "job-1", [{"original_filename": "1001.jpg", "storage_path": "x"}], caller_wid="w2")
    with pytest.raises(UploadForbidden):
        list_unmatched(repo, "job-1", caller_wid="w2")
    with pytest.raises(UploadForbidden):
        resolve_match(repo, "job-1", image_id="img1", source_p_number="1001", caller_wid="w2")


def test_resolve_match_foreign_image_forbidden():
    """job 은 내 소유여도, 대상 이미지가 타 업체 소유면 갱신 거부."""
    repo = FakeUploadRepo()
    repo.create_upload_job({"wholesaler_id": "w1"})
    repo.insert_product({"wholesaler_id": "w1", "source_p_number": "1001",
                         "platform_code": "EZM-1", "item_name": "셔츠"})
    repo.insert_images([{"wholesaler_id": "w2", "storage_path": "w2/x.jpg",   # 타 업체 이미지
                         "original_filename": "x.jpg", "product_id": None, "match_status": "unmatched"}])
    with pytest.raises(UploadForbidden):
        resolve_match(repo, "job-1", image_id="img1", source_p_number="1001", caller_wid="w1")


def test_ingest_excel_duplicate_pnum_becomes_error_not_crash():
    """재업로드(품번 UNIQUE 충돌)는 해당 품번만 error 로 떨구고 나머지는 계속."""
    class DupRepo(FakeUploadRepo):
        def insert_product(self, d):
            if d["source_p_number"] == "DUP":
                raise Exception("duplicate key value violates unique constraint")
            return super().insert_product(d)
    import openpyxl as _x
    import tempfile, os
    fd, p = tempfile.mkstemp(suffix=".xlsx"); os.close(fd)
    wb = _x.Workbook(); ws = wb.active
    ws.append(["품번", "상품명", "색상", "사이즈", "도매가", "판매가"])
    ws.append(("DUP", "중복", "화이트", "F", 1000, 2000))
    ws.append(("OK1", "정상", "블랙", "F", 1000, 2000))
    wb.save(p)
    out = ingest_excel(DupRepo(), "w1", p)
    os.unlink(p)
    assert len(out["products"]) == 1                      # OK1 만 생성
    assert any(e.get("source_p_number") == "DUP" for e in out["errors"])
    assert out["job"]["status"] == "needs_matching"       # 일부라도 생성됨


def test_list_unmatched_returns_only_unmatched():
    repo = FakeUploadRepo()
    repo.create_upload_job({"wholesaler_id": "w1"})
    repo.insert_images([
        {"wholesaler_id": "w1", "storage_path": "a", "original_filename": "a.jpg",
         "product_id": None, "match_status": "unmatched"},
        {"wholesaler_id": "w1", "storage_path": "b", "original_filename": "b.jpg",
         "product_id": "p1", "match_status": "matched"},
    ])
    out = list_unmatched(repo, "job-1", caller_wid="w1")
    assert len(out) == 1 and out[0]["original_filename"] == "a.jpg"
