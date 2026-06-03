from app.services.accounts import approve_account

class FakeProfiles:
    def __init__(self): self.updated = {}
    def set_status(self, uid, status, by):
        self.updated = {"id": uid, "status": status, "approved_by": by}
        return self.updated

def test_approve_sets_status_approved():
    repo = FakeProfiles()
    out = approve_account(repo, target_id="seller-1", admin_id="admin-1")
    assert out["status"] == "approved"
    assert out["approved_by"] == "admin-1"
