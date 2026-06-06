from app.services.accounts import approve_account, reject_account


class FakeProfiles:
    def __init__(self, profile=None):
        self.updated = {}
        self.profile = profile
        self.created_wholesalers = []

    def get_profile(self, uid):
        return self.profile

    def create_wholesaler(self, name):
        w = {"id": f"w-{len(self.created_wholesalers) + 1}", "name": name}
        self.created_wholesalers.append(w)
        return w

    def set_status(self, uid, status, by, wholesaler_id=None):
        self.updated = {"id": uid, "status": status, "approved_by": by, "wholesaler_id": wholesaler_id}
        return self.updated


def test_approve_sets_status_approved():
    repo = FakeProfiles(profile={"role": "retail_seller"})
    out = approve_account(repo, target_id="seller-1", admin_id="admin-1")
    assert out["status"] == "approved"
    assert out["approved_by"] == "admin-1"
    assert out["wholesaler_id"] is None              # 소매는 도매업체 미생성
    assert repo.created_wholesalers == []


def test_approve_wholesaler_auto_provisions_wholesaler():
    repo = FakeProfiles(profile={"role": "wholesaler", "wholesaler_id": None, "company_name": "라라스도매"})
    out = approve_account(repo, target_id="w-user", admin_id="admin-1")
    assert out["status"] == "approved"
    assert len(repo.created_wholesalers) == 1
    assert repo.created_wholesalers[0]["name"] == "라라스도매"   # 회사명으로 생성
    assert out["wholesaler_id"] == repo.created_wholesalers[0]["id"]


def test_approve_wholesaler_with_existing_id_does_not_recreate():
    repo = FakeProfiles(profile={"role": "wholesaler", "wholesaler_id": "w-existing"})
    out = approve_account(repo, target_id="w-user", admin_id="admin-1")
    assert repo.created_wholesalers == []             # 이미 연결됨 → 재생성 안 함
    assert out["wholesaler_id"] is None               # 추가 연결 없음(기존 유지)


def test_reject_sets_status_rejected():
    repo = FakeProfiles(profile={"role": "wholesaler"})
    out = reject_account(repo, target_id="seller-1", admin_id="admin-1")
    assert out["status"] == "rejected"
