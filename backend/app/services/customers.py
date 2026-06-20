"""고객관리 서비스 — 소매↔도매 '기본 전부 연결 + 취소(예외)' 모델.

모델: 같은 도매관리자(테넌트) 안에서는 모든 소매가 모든 도매와 **기본 연결**된다.
관리자가 특정 소매↔도매 매칭을 **취소**하면 그 쌍만 예외로 빠진다(wholesaler_customer_exclusions).
- 도매(wholesaler)가 보는 고객 = 테넌트 전체 소매 − (그 도매에 대해 취소된 소매).
- 도매관리자(admin) = 테넌트 전체 소매 + 도매업체. 매칭 취소/복원은 admin 만.

격리(앱레이어 책임 — service-key 가 RLS 우회): 모든 조회/쓰기는 뷰어의 **테넌트(manager_id)** 로 한정.
`repo` 는 DB 접근(routers/customers.py) — 본 모듈은 로직/격리만 담아 fake repo 로 단위 테스트.
"""
from fastapi import HTTPException

from app.schemas.auth import CurrentUser
from app.services.tenancy import scoped_wholesaler_ids

_TIERS = ("new", "regular")
_VIS = ("wholesale", "retail", "none")


def list_customers(repo, viewer: CurrentUser) -> list[dict]:
    """역할별 소매(거래처) 목록.
    - admin: 테넌트 전체 소매(+ 각 소매가 어느 도매와 '취소'됐는지 `excluded_wholesaler_ids`).
    - wholesaler: 테넌트 소매 − 자기에게 취소된 소매(기본 전부 연결).
    """
    if viewer.role == "admin":
        rows = repo.shape(repo.tenant_sellers(viewer.manager_id))
        exmap = repo.exclusions_for_sellers([r["id"] for r in rows])  # seller_id -> [wholesaler_id]
        for r in rows:
            r["excluded_wholesaler_ids"] = exmap.get(r["id"], [])
        return rows
    if viewer.role == "wholesaler":
        sellers = repo.tenant_sellers(viewer.manager_id)
        # ⚠️ RISK(side-effect): service-key가 RLS 우회 — 테넌트 소매에서 '취소된' 것만 제외(기본 전부 연결).
        excluded = set(repo.excluded_customer_ids(viewer.wholesaler_id))
        return repo.shape([s for s in sellers if s["id"] not in excluded])
    raise HTTPException(403, "고객 목록 접근 권한이 없습니다")


def list_wholesalers(repo, viewer: CurrentUser) -> list[dict]:
    """도매관리자 전용 — 테넌트 도매업체 목록(+ 연결 소매 수 = 전체 소매 − 취소)."""
    ids = scoped_wholesaler_ids(repo.sb, viewer.manager_id)
    if not ids:
        return []
    total = len(repo.tenant_sellers(viewer.manager_id))
    excl = repo.exclusion_counts(ids)  # wholesaler_id -> 취소 수
    rows = repo.wholesalers_by_ids(ids)
    for w in rows:
        w["connected_count"] = max(0, total - excl.get(w["id"], 0))
    return rows


def disconnect(repo, viewer: CurrentUser, customer_id: str, wholesaler_id: str) -> dict:
    """소매↔도매 매칭 취소(도매관리자 전용 — 라우터 가드). 취소 예외 행 추가."""
    _assert_scoped_wholesaler(repo, viewer, wholesaler_id, "취소")
    _assert_customer_in_tenant(repo, viewer, customer_id)
    return repo.add_exclusion(customer_id, wholesaler_id, viewer.id)


def reconnect(repo, viewer: CurrentUser, customer_id: str, wholesaler_id: str) -> dict:
    """취소했던 매칭 복원(도매관리자 전용 — 취소 예외 행 soft delete → 다시 연결)."""
    _assert_scoped_wholesaler(repo, viewer, wholesaler_id, "복원")
    return repo.remove_exclusion(customer_id, wholesaler_id)


def set_price_visibility(repo, viewer: CurrentUser, uid: str, vis: str) -> dict:
    """소매 가격노출 권한 설정. admin=테넌트 내 / wholesaler=연결된(취소 안 된) 소매만. (값 설정만 — visible_price() 불변)"""
    if vis not in _VIS:
        raise HTTPException(400, "price_visibility must be wholesale|retail|none")
    assert_can_manage(repo, viewer, uid)
    return repo.set_price_visibility(uid, vis)


def set_tier(repo, viewer: CurrentUser, uid: str, tier: str) -> dict:
    """소매 등급 설정 — 1차 화면 제외(잠자는 엔드포인트, 2차 자동등급용 forward-compat)."""
    if tier not in _TIERS:
        raise HTTPException(400, "tier must be new|regular")
    assert_can_manage(repo, viewer, uid)
    return repo.set_tier(uid, tier)


def assert_can_manage(repo, viewer: CurrentUser, uid: str) -> None:
    """가격노출/등급 변경 격리 게이트 — admin=테넌트 내, wholesaler=테넌트 내 + 취소 안 된 소매만."""
    if viewer.role == "admin":
        _assert_customer_in_tenant(repo, viewer, uid)
        return
    if viewer.role == "wholesaler":
        _assert_customer_in_tenant(repo, viewer, uid)
        # ⚠️ RISK(side-effect): 도매는 '취소된' 소매는 관리 불가(연결 끊긴 거래처 변조 차단).
        if uid in set(repo.excluded_customer_ids(viewer.wholesaler_id)):
            raise HTTPException(403, "거래가 취소된 거래처입니다")
        return
    raise HTTPException(403, "권한이 없습니다")


def _assert_scoped_wholesaler(repo, viewer: CurrentUser, wholesaler_id: str, action: str) -> None:
    if not wholesaler_id:
        raise HTTPException(400, "wholesaler_id required")
    # ⚠️ RISK(breaking): wholesaler_id는 자기 테넌트(scoped_wholesaler_ids) 내에서만 — 타 테넌트 도매 조작 금지.
    if wholesaler_id not in scoped_wholesaler_ids(repo.sb, viewer.manager_id):
        raise HTTPException(403, f"해당 도매업체 매칭을 {action}할 권한이 없습니다")


def _assert_customer_in_tenant(repo, viewer: CurrentUser, uid: str) -> None:
    prof = repo.get_profile(uid)
    if not prof:
        raise HTTPException(404, "대상 계정을 찾을 수 없습니다")
    if prof.get("manager_id") != viewer.manager_id:
        raise HTTPException(403, "다른 테넌트의 계정은 관리할 수 없습니다")


# ─────────────────────────────────────────────────────────────────────
# 정책 강제(소매가 보는 도매 스코프) — 쇼룸/카탈로그/엑셀이 상품을 거를 때 쓰는 단일 진실.
# ⚠️ 매칭 취소는 '관리 화면 라벨'이 아니라 여기서 실제로 상품 노출을 막는다.
# ─────────────────────────────────────────────────────────────────────
def excluded_wholesaler_ids_for_seller(sb, seller_id: str | None) -> list[str]:
    """이 소매(거래처)가 거래 '취소'한 도매 id 목록 — 소매가 상품을 보면 안 되는 도매."""
    if not seller_id:
        return []
    rows = sb.table("wholesaler_customer_exclusions").select("wholesaler_id").eq(
        "customer_id", seller_id).is_("deleted_at", "null").execute().data or []
    return [r["wholesaler_id"] for r in rows if r.get("wholesaler_id")]


def seller_visible_wholesaler_ids(sb, manager_id: str | None, seller_id: str | None) -> list[str]:
    """소매가 볼 수 있는 도매 id = 테넌트 도매 − 그 소매가 취소한 도매.
    쇼룸·카탈로그·엑셀이 상품을 스코프할 때 이걸로 거른다(정책 강제 지점). [] → 빈 결과(fail-closed)."""
    ids = scoped_wholesaler_ids(sb, manager_id)
    if not ids:
        return []
    excluded = set(excluded_wholesaler_ids_for_seller(sb, seller_id))
    return [w for w in ids if w not in excluded]
