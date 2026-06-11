import pytest
from fastapi import HTTPException

from app.routers.admin import _assert_actionable
from app.schemas.auth import CurrentUser


class _Repo:
    def __init__(self, prof=None):
        self.prof = prof

    def get_profile(self, uid):
        return self.prof


def _actor(uid="admin-1"):
    return CurrentUser(id=uid, role="admin", status="approved", manager_id="m-lalas")


def test_cannot_action_self():
    # 본인 계정 승인/거절 차단 — 자기 거절로 로그인 lockout 방지
    with pytest.raises(HTTPException) as e:
        _assert_actionable(_Repo(), "admin-1", _actor("admin-1"))
    assert e.value.status_code == 400


def test_cannot_action_other_admin():
    with pytest.raises(HTTPException) as e:
        _assert_actionable(_Repo({"role": "admin"}), "admin-2", _actor("admin-1"))
    assert e.value.status_code == 400


def test_can_action_wholesaler():
    _assert_actionable(_Repo({"role": "wholesaler"}), "w-1", _actor())  # 예외 없으면 통과


def test_can_action_seller():
    _assert_actionable(_Repo({"role": "retail_seller"}), "s-1", _actor())
