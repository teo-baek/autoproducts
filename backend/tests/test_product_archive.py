from app.services.products import archive_product, soft_delete_product

class FakeRepo:
    def __init__(self): self.patch=None
    def update_product(self, pid, patch): self.patch={"id":pid, **patch}; return self.patch

def test_archive_sets_status_archived():
    repo = FakeRepo()
    out = archive_product(repo, "p1")
    assert out["status"] == "archived"

def test_soft_delete_sets_deleted_at_not_status():
    repo = FakeRepo()
    out = soft_delete_product(repo, "p1", "2026-06-03T12:00:00+00:00")
    assert out["deleted_at"] == "2026-06-03T12:00:00+00:00"
    assert "status" not in out  # 삭제(deleted_at)는 보관(status=archived)과 별개
