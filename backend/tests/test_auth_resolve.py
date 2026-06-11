import types

from app.core.auth import _resolve_manager_id


class _Q:
    def __init__(self, data):
        self._d = data

    def select(self, *a, **k):
        return self

    def eq(self, *a, **k):
        return self

    def is_(self, *a, **k):
        return self

    def limit(self, *a, **k):
        return self

    def execute(self):
        return types.SimpleNamespace(data=self._d)


class _SB:
    def __init__(self, data):
        self._d = data
        self.queried = False

    def table(self, name):
        self.queried = True
        return _Q(self._d)


def test_seller_uses_profile_manager_id_without_query():
    sb = _SB([])
    row = {"role": "retail_seller", "manager_id": "m-1", "wholesaler_id": None}
    assert _resolve_manager_id(sb, row) == "m-1"
    assert sb.queried is False  # profiles.manager_id 직접 → 연결표 조회 안 함


def test_admin_uses_profile_manager_id():
    assert _resolve_manager_id(_SB([]), {"role": "admin", "manager_id": "m-1"}) == "m-1"


def test_wholesaler_resolves_from_link_table():
    sb = _SB([{"manager_id": "m-9"}])
    row = {"role": "wholesaler", "manager_id": None, "wholesaler_id": "w-1"}
    assert _resolve_manager_id(sb, row) == "m-9"
    assert sb.queried is True


def test_wholesaler_unlinked_returns_none():
    row = {"role": "wholesaler", "manager_id": None, "wholesaler_id": "w-1"}
    assert _resolve_manager_id(_SB([]), row) is None


def test_no_info_returns_none():
    row = {"role": "retail_seller", "manager_id": None, "wholesaler_id": None}
    assert _resolve_manager_id(_SB([]), row) is None
