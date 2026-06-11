import pytest

from app.services.accounts import approve_account, reject_account
from app.routers.admin import shape_account_rows


class FakeProfiles:
    def __init__(self, profile=None):
        self.updated = {}
        self.profile = profile
        self.created_wholesalers = []
        self.deleted_wholesalers = []        # 보상(A-4)으로 soft-delete 된 도매업체 id
        self.links = []                      # link_wholesaler_to_manager 기록(테넌트 소속 연결)

    def get_profile(self, uid):
        return self.profile

    def create_wholesaler(self, name):
        w = {"id": f"w-{len(self.created_wholesalers) + 1}", "name": name}
        self.created_wholesalers.append(w)
        return w

    def set_status(self, uid, status, by, wholesaler_id=None, manager_id=None):
        self.updated = {"id": uid, "status": status, "approved_by": by,
                        "wholesaler_id": wholesaler_id, "manager_id": manager_id}
        return self.updated

    def soft_delete_wholesaler(self, wid):
        self.deleted_wholesalers.append(wid)

    def link_wholesaler_to_manager(self, wholesaler_id, manager_id, by=None):
        self.links.append({"wholesaler_id": wholesaler_id, "manager_id": manager_id, "by": by})
        return self.links[-1]


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


# ── A-4 보상: 승인 도중 set_status 실패 시 방금 만든 도매업체 정리 ──────────────
class SetStatusFailsRepo(FakeProfiles):
    def set_status(self, uid, status, by, wholesaler_id=None, manager_id=None):
        raise Exception("set_status failed")


def test_approve_compensates_orphan_wholesaler_on_status_failure():
    # 도매업체 생성 후 승인 연결(set_status) 실패 → 방금 만든 도매업체 soft-delete(고아 방지)
    repo = SetStatusFailsRepo(profile={"role": "wholesaler", "wholesaler_id": None, "company_name": "라라스도매"})
    with pytest.raises(Exception, match="set_status failed"):
        approve_account(repo, target_id="w-user", admin_id="admin-1")
    assert len(repo.created_wholesalers) == 1                                  # 1단계: 도매업체 생성됨
    assert repo.deleted_wholesalers == [repo.created_wholesalers[0]["id"]]     # 2단계 실패 → 보상 삭제


def test_approve_retail_failure_no_wholesaler_compensation():
    # 소매 승인은 도매업체를 안 만드므로 set_status 실패해도 보상 대상 없음(불필요한 삭제 안 함)
    repo = SetStatusFailsRepo(profile={"role": "retail_seller"})
    with pytest.raises(Exception, match="set_status failed"):
        approve_account(repo, target_id="seller-1", admin_id="admin-1")
    assert repo.created_wholesalers == []
    assert repo.deleted_wholesalers == []


# ── 관리자 계정 목록 셰이핑 — 이메일 보강 + 에이전시 소속명 ─────────────────
def test_shape_account_rows_attaches_email_and_agency_name():
    rows = [
        {"id": "s1", "role": "retail_seller", "seller_type": "agency_affiliated", "agency_id": "a1"},
        {"id": "s2", "role": "retail_seller", "seller_type": "independent", "agency_id": None},
        {"id": "w1", "role": "wholesaler", "seller_type": None, "agency_id": None},
    ]
    emails = {"s1": "s1@x.com", "w1": "w1@x.com"}
    agencies = {"a1": "라라스에이전시"}
    out = shape_account_rows(rows, emails, agencies)
    assert out[0]["email"] == "s1@x.com"
    assert out[0]["agency_name"] == "라라스에이전시"  # 에이전시 소속 → 소속명 부여
    assert out[1]["email"] is None                     # auth 이메일 없으면 None(목록은 유지)
    assert out[1]["agency_name"] is None               # 일반(라이브셀러) → 소속 없음
    assert out[2]["agency_name"] is None               # 도매 계정 → 해당 없음


def test_shape_account_rows_unknown_agency_id_is_none():
    rows = [{"id": "s1", "role": "retail_seller", "seller_type": "agency_affiliated", "agency_id": "ghost"}]
    out = shape_account_rows(rows, {}, {"a1": "라라스에이전시"})
    assert out[0]["agency_name"] is None  # 매핑에 없는 agency_id → None(크래시 없이)


# ── 테넌트(도매관리자) 스코프 승인 — FR-2/FR-3/FR-7 ──────────────────────────
def test_approve_seller_links_manager_id():
    repo = FakeProfiles(profile={"role": "retail_seller"})
    out = approve_account(repo, target_id="seller-1", admin_id="admin-1", admin_manager_id="m-lalas")
    assert out["manager_id"] == "m-lalas"   # 셀러 → 테넌트 연계(FR-3)
    assert repo.links == []                  # 셀러는 도매 연결표 미사용


def test_approve_wholesaler_links_to_manager():
    repo = FakeProfiles(profile={"role": "wholesaler", "wholesaler_id": None, "company_name": "라라스도매"})
    approve_account(repo, target_id="w-user", admin_id="admin-1", admin_manager_id="m-lalas")
    assert len(repo.links) == 1                                          # 도매 → 연결표 소속(FR-2)
    assert repo.links[0]["manager_id"] == "m-lalas"
    assert repo.links[0]["wholesaler_id"] == repo.created_wholesalers[0]["id"]


def test_approve_wholesaler_with_existing_id_links_existing():
    repo = FakeProfiles(profile={"role": "wholesaler", "wholesaler_id": "w-existing"})
    approve_account(repo, target_id="w-user", admin_id="admin-1", admin_manager_id="m-lalas")
    assert repo.created_wholesalers == []
    assert repo.links == [{"wholesaler_id": "w-existing", "manager_id": "m-lalas", "by": "admin-1"}]


def test_approve_without_manager_id_skips_linking():
    # admin_manager_id 미전달(마이그레이션 전/레거시) → 연결 안 함(기존 동작 보존)
    repo = FakeProfiles(profile={"role": "wholesaler", "wholesaler_id": None, "company_name": "x"})
    approve_account(repo, target_id="w-user", admin_id="admin-1")
    assert repo.links == []


class LinkFailsRepo(FakeProfiles):
    def link_wholesaler_to_manager(self, wholesaler_id, manager_id, by=None):
        raise Exception("link failed")


def test_approve_compensates_wholesaler_on_link_failure():
    # 도매업체 생성 후 테넌트 소속 연결 실패 → 방금 만든 도매업체 soft-delete 보상(고아 방지, A-4 연장)
    repo = LinkFailsRepo(profile={"role": "wholesaler", "wholesaler_id": None, "company_name": "라라스도매"})
    with pytest.raises(Exception, match="link failed"):
        approve_account(repo, target_id="w-user", admin_id="admin-1", admin_manager_id="m-lalas")
    assert len(repo.created_wholesalers) == 1
    assert repo.deleted_wholesalers == [repo.created_wholesalers[0]["id"]]
