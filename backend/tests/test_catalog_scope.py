import types

from app.routers.catalog import _query_catalog_rows, _query_catalog_export_rows


class _RecQ:
    """쿼리 빌더 fake — .in_ 호출 여부/인자를 기록."""
    def __init__(self, data, calls):
        self._data = data
        self.calls = calls

    def select(self, *a, **k):
        return self

    def eq(self, *a, **k):
        return self

    def is_(self, *a, **k):
        return self

    def order(self, *a, **k):
        return self

    def limit(self, *a, **k):
        return self

    def gt(self, *a, **k):
        self.calls.append(("gt",) + a)
        return self

    def in_(self, col, vals):
        self.calls.append(("in_", col, list(vals)))
        return self

    def execute(self):
        return types.SimpleNamespace(data=self._data)


class _RecSB:
    def __init__(self, data=None):
        self._data = data or []
        self.calls = []

    def table(self, name):
        return _RecQ(self._data, self.calls)


def test_catalog_rows_applies_in_filter_when_ids_given():
    sb = _RecSB()
    _query_catalog_rows(sb, 30, wholesaler_ids=["w1", "w2"])
    assert ("in_", "wholesaler_id", ["w1", "w2"]) in sb.calls


def test_catalog_rows_no_filter_when_ids_none():
    sb = _RecSB()
    _query_catalog_rows(sb, 30, wholesaler_ids=None)
    assert not any(c[0] == "in_" for c in sb.calls)


def test_catalog_rows_empty_ids_filters_to_empty_scope():
    sb = _RecSB()
    _query_catalog_rows(sb, 30, wholesaler_ids=[])
    assert ("in_", "wholesaler_id", []) in sb.calls  # fail-closed: 빈 스코프 → 빈 결과


def test_export_rows_applies_in_filter_when_ids_given():
    sb = _RecSB()
    _query_catalog_export_rows(sb, 1000, wholesaler_ids=["w1"])
    assert ("in_", "wholesaler_id", ["w1"]) in sb.calls


def test_export_rows_no_filter_when_ids_none():
    sb = _RecSB()
    _query_catalog_export_rows(sb, 1000, wholesaler_ids=None)
    assert not any(c[0] == "in_" for c in sb.calls)
