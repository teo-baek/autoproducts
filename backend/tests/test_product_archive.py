from app.services.products import archive_product

class FakeRepo:
    def __init__(self): self.patch=None
    def update_product(self, pid, patch): self.patch={"id":pid, **patch}; return self.patch

def test_archive_sets_status_archived():
    repo = FakeRepo()
    out = archive_product(repo, "p1")
    assert out["status"] == "archived"
