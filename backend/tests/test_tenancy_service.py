import types

from app.services.tenancy import scoped_wholesaler_ids


class _Q:
    def __init__(self, data):
        self._d = data

    def select(self, *a, **k):
        return self

    def eq(self, *a, **k):
        return self

    def is_(self, *a, **k):
        return self

    def execute(self):
        return types.SimpleNamespace(data=self._d)


class _SB:
    def __init__(self, data):
        self._d = data
        self.tables = []

    def table(self, name):
        self.tables.append(name)
        return _Q(self._d)


def test_none_manager_returns_empty_without_query():
    sb = _SB([{"wholesaler_id": "w-1"}])
    assert scoped_wholesaler_ids(sb, None) == []
    assert scoped_wholesaler_ids(sb, "") == []
    assert sb.tables == []  # manager_id 없으면 쿼리도 안 함(fail-closed)


def test_returns_wholesaler_ids_for_manager():
    sb = _SB([{"wholesaler_id": "w-1"}, {"wholesaler_id": "w-2"}])
    assert scoped_wholesaler_ids(sb, "m-lalas") == ["w-1", "w-2"]
    assert sb.tables == ["manager_wholesalers"]


def test_empty_links_returns_empty():
    assert scoped_wholesaler_ids(_SB([]), "m-lalas") == []


def test_skips_rows_without_wholesaler_id():
    sb = _SB([{"wholesaler_id": "w-1"}, {"wholesaler_id": None}])
    assert scoped_wholesaler_ids(sb, "m-lalas") == ["w-1"]
