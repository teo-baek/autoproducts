"""고객관리 서비스 테스트 — '기본 전부 연결 + 취소(예외)' 모델 + 격리(테넌트·취소).

핵심: 도매는 테넌트 소매를 기본 전부 보되, '취소된' 소매만 빠진다. 취소는 (도매,소매) 쌍 단위.
"""
import types

import pytest
from fastapi import HTTPException

from app.schemas.auth import CurrentUser
from app.services import customers as svc


# scoped_wholesaler_ids(sb, manager_id) 용 fake sb — 테넌트 도매 목록을 그대로 돌려줌.
class _SB:
    def __init__(self, wholesaler_ids):
        self._d = [{"wholesaler_id": w} for w in wholesaler_ids]

    def table(self, name):
        return self

    def select(self, *a, **k):
        return self

    def eq(self, *a, **k):
        return self

    def is_(self, *a, **k):
        return self

    def execute(self):
        return types.SimpleNamespace(data=self._d)


class FakeRepo:
    """취소(예외) 모델을 메모리로 흉내. exclusions = 취소된 (도매,소매) 쌍."""

    def __init__(self, *, profiles=None, exclusions=None, tenant_wholesalers=None, wholesalers=None):
        self._profiles = {p["id"]: p for p in (profiles or [])}
        self._exclusions = list(exclusions or [])      # [(wholesaler_id, customer_id), ...]
        self.sb = _SB(tenant_wholesalers or [])
        self._wholesalers = wholesalers or []
        self.calls = []

    def tenant_sellers(self, manager_id):
        return [p for p in self._profiles.values()
                if p.get("manager_id") == manager_id and p.get("role") in ("retail_seller", "agency")]

    def excluded_customer_ids(self, wid):
        return [c for (w, c) in self._exclusions if w == wid]

    def exclusions_for_sellers(self, ids):
        m = {}
        for (w, c) in self._exclusions:
            if c in ids:
                m.setdefault(c, []).append(w)
        return m

    def exclusion_counts(self, wids):
        counts = {}
        for (w, c) in self._exclusions:
            if w in wids:
                counts[w] = counts.get(w, 0) + 1
        return counts

    def wholesalers_by_ids(self, ids):
        return [dict(w) for w in self._wholesalers if w["id"] in ids]

    def shape(self, rows):
        return [dict(r) for r in rows]

    def get_profile(self, uid):
        return self._profiles.get(uid)

    def add_exclusion(self, c, w, by):
        self.calls.append(("exclude", c, w))
        if (w, c) not in self._exclusions:
            self._exclusions.append((w, c))
        return [{"customer_id": c, "wholesaler_id": w}]

    def remove_exclusion(self, c, w):
        self.calls.append(("restore", c, w))
        self._exclusions = [(ww, cc) for (ww, cc) in self._exclusions if not (ww == w and cc == c)]
        return [{"customer_id": c, "wholesaler_id": w}]

    def set_price_visibility(self, uid, vis):
        self.calls.append(("set_vis", uid, vis))
        return [{"id": uid, "price_visibility": vis}]

    def set_tier(self, uid, tier):
        self.calls.append(("set_tier", uid, tier))
        return [{"id": uid, "tier": tier}]


def _admin(mid="m-lalas"):
    return CurrentUser(id="admin-1", role="admin", status="approved", manager_id=mid)


def _wholesaler(wid="w-A", mid="m-lalas"):
    return CurrentUser(id="who-1", role="wholesaler", status="approved",
                       wholesaler_id=wid, manager_id=mid)


def _seller(sid, mid="m-lalas"):
    return {"id": sid, "role": "retail_seller", "status": "approved", "manager_id": mid,
            "full_name": f"담당-{sid}", "price_visibility": None}


# ── 조회: 기본 전부 연결 + 취소 격리 ─────────────────────────────────
def test_wholesaler_sees_all_tenant_sellers_by_default():
    repo = FakeRepo(profiles=[_seller("s1"), _seller("s2"), _seller("s3")])
    rows = svc.list_customers(repo, _wholesaler("w-A"))
    assert {r["id"] for r in rows} == {"s1", "s2", "s3"}   # 취소 없음 → 전부 연결


def test_wholesaler_excluded_seller_hidden_others_unaffected():
    repo = FakeRepo(
        profiles=[_seller("s1"), _seller("s2")],
        exclusions=[("w-A", "s1")],   # 도매 A 가 s1 매칭 취소
    )
    a = svc.list_customers(repo, _wholesaler("w-A"))
    assert {r["id"] for r in a} == {"s2"}                  # A 는 s1 안 보임
    b = svc.list_customers(repo, _wholesaler("w-B"))
    assert {r["id"] for r in b} == {"s1", "s2"}            # B 는 둘 다 보임(취소는 쌍 단위)


def test_wholesaler_excludes_only_own_tenant():
    repo = FakeRepo(profiles=[_seller("s1"), _seller("x1", mid="m-other")])
    rows = svc.list_customers(repo, _wholesaler("w-A", mid="m-lalas"))
    assert {r["id"] for r in rows} == {"s1"}               # 타 테넌트(x1) 안 보임


def test_admin_sees_all_with_excluded_ids():
    repo = FakeRepo(
        profiles=[_seller("s1"), _seller("s2")],
        exclusions=[("w-A", "s1")],
    )
    rows = svc.list_customers(repo, _admin())
    by_id = {r["id"]: r for r in rows}
    assert set(by_id) == {"s1", "s2"}
    assert by_id["s1"]["excluded_wholesaler_ids"] == ["w-A"]
    assert by_id["s2"]["excluded_wholesaler_ids"] == []


# ── 취소/복원 (admin) ────────────────────────────────────────────────
def test_disconnect_then_wholesaler_loses_seller():
    repo = FakeRepo(profiles=[_seller("s1")], tenant_wholesalers=["w-A"])
    assert {r["id"] for r in svc.list_customers(repo, _wholesaler("w-A"))} == {"s1"}
    svc.disconnect(repo, _admin(), "s1", "w-A")
    assert svc.list_customers(repo, _wholesaler("w-A")) == []   # 취소 후 안 보임


def test_reconnect_restores():
    repo = FakeRepo(profiles=[_seller("s1")], exclusions=[("w-A", "s1")],
                    tenant_wholesalers=["w-A"])
    svc.reconnect(repo, _admin(), "s1", "w-A")
    assert {r["id"] for r in svc.list_customers(repo, _wholesaler("w-A"))} == {"s1"}


def test_disconnect_out_of_tenant_wholesaler_403():
    repo = FakeRepo(profiles=[_seller("s1")], tenant_wholesalers=["w-A"])
    with pytest.raises(HTTPException) as e:
        svc.disconnect(repo, _admin(), "s1", "w-OTHER")
    assert e.value.status_code == 403


def test_disconnect_missing_customer_404():
    repo = FakeRepo(profiles=[], tenant_wholesalers=["w-A"])
    with pytest.raises(HTTPException) as e:
        svc.disconnect(repo, _admin(), "ghost", "w-A")
    assert e.value.status_code == 404


# ── 쓰기 격리(가격노출) ──────────────────────────────────────────────
def test_wholesaler_can_set_vis_on_connected():
    repo = FakeRepo(profiles=[_seller("s1")])   # 취소 없음 → 연결됨
    svc.set_price_visibility(repo, _wholesaler("w-A"), "s1", "wholesale")
    assert ("set_vis", "s1", "wholesale") in repo.calls


def test_wholesaler_cannot_set_vis_on_excluded():
    repo = FakeRepo(profiles=[_seller("s1")], exclusions=[("w-A", "s1")])
    with pytest.raises(HTTPException) as e:
        svc.set_price_visibility(repo, _wholesaler("w-A"), "s1", "wholesale")
    assert e.value.status_code == 403
    assert repo.calls == []                      # 변조 차단


def test_wholesaler_cannot_set_vis_other_tenant():
    repo = FakeRepo(profiles=[_seller("x1", mid="m-other")])
    with pytest.raises(HTTPException) as e:
        svc.set_price_visibility(repo, _wholesaler("w-A", mid="m-lalas"), "x1", "retail")
    assert e.value.status_code in (403, 404)


def test_admin_set_vis_tenant_ok_other_tenant_403():
    repo = FakeRepo(profiles=[_seller("s1"), _seller("x1", mid="m-other")])
    svc.set_price_visibility(repo, _admin(), "s1", "none")
    assert ("set_vis", "s1", "none") in repo.calls
    with pytest.raises(HTTPException) as e:
        svc.set_price_visibility(repo, _admin(), "x1", "none")
    assert e.value.status_code == 403


def test_bad_vis_400():
    repo = FakeRepo(profiles=[_seller("s1")])
    with pytest.raises(HTTPException) as e:
        svc.set_price_visibility(repo, _admin(), "s1", "BOGUS")
    assert e.value.status_code == 400


# ── 도매업체 목록 연결 소매 수 ───────────────────────────────────────
# ── 정책 강제: 소매가 보는 도매 스코프(쇼룸/카탈로그/엑셀/QR 공용) ──────
class _SBMulti:
    """테이블별 다른 데이터를 돌려주는 fake sb (scoped + exclusions 두 쿼리용)."""

    def __init__(self, by_table):
        self._t = by_table
        self._cur = None

    def table(self, name):
        self._cur = name
        return self

    def select(self, *a, **k):
        return self

    def eq(self, *a, **k):
        return self

    def is_(self, *a, **k):
        return self

    def execute(self):
        return types.SimpleNamespace(data=self._t.get(self._cur, []))


def test_seller_visible_excludes_cancelled_wholesalers():
    sb = _SBMulti({
        "manager_wholesalers": [{"wholesaler_id": "w-A"}, {"wholesaler_id": "w-B"}, {"wholesaler_id": "w-C"}],
        "wholesaler_customer_exclusions": [{"wholesaler_id": "w-B"}],   # 이 소매가 B 취소
    })
    assert svc.seller_visible_wholesaler_ids(sb, "m-lalas", "s1") == ["w-A", "w-C"]  # B 제외


def test_seller_visible_all_when_no_exclusions():
    sb = _SBMulti({
        "manager_wholesalers": [{"wholesaler_id": "w-A"}, {"wholesaler_id": "w-B"}],
        "wholesaler_customer_exclusions": [],
    })
    assert svc.seller_visible_wholesaler_ids(sb, "m-lalas", "s1") == ["w-A", "w-B"]   # 전부 연결


def test_seller_visible_empty_tenant_fail_closed():
    sb = _SBMulti({"manager_wholesalers": [], "wholesaler_customer_exclusions": []})
    assert svc.seller_visible_wholesaler_ids(sb, "m-lalas", "s1") == []
    assert svc.seller_visible_wholesaler_ids(sb, None, "s1") == []


def test_list_wholesalers_connected_count():
    repo = FakeRepo(
        profiles=[_seller("s1"), _seller("s2"), _seller("s3")],   # 테넌트 소매 3
        exclusions=[("w-A", "s1")],                                # A 가 1건 취소
        tenant_wholesalers=["w-A"],
        wholesalers=[{"id": "w-A", "name": "도매A"}, {"id": "w-B", "name": "도매B"}],
    )
    out = svc.list_wholesalers(repo, _admin())
    assert [w["id"] for w in out] == ["w-A"]      # 테넌트 소속만
    assert out[0]["connected_count"] == 2          # 3 − 1 취소
