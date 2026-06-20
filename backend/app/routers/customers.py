"""고객관리 라우터 — 소매(거래처) 조회 + 매칭 취소/복원 + 가격노출 설정.

모델: 테넌트 안 모든 소매↔도매 기본 연결, 관리자가 특정 쌍 취소(wholesaler_customer_exclusions).
- 도매관리자(admin) = 테넌트 전체 소매 + 도매업체, 매칭 취소/복원.
- 도매(wholesaler) = 테넌트 소매 − 취소된 소매(기본 전부 연결).
격리/스코프 로직은 services/customers.py (fake repo 단위테스트). 본 파일은 DB(repo) + 가드 + 와이어링.
"""
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException

from app.core.auth import get_current_user
from app.core.rbac import require_role
from app.core.supabase import get_supabase
from app.routers.admin import SupabaseAdminRepo, shape_account_rows
from app.schemas.auth import CurrentUser
from app.services import customers as svc

router = APIRouter(prefix="/customers", tags=["customers"])
_admin = require_role("admin")

_EXCL = "wholesaler_customer_exclusions"  # 취소된 (도매,소매) 쌍


def require_customers_access(user: CurrentUser) -> None:
    """고객관리 접근 가드 — admin 또는 승인된 wholesaler 만."""
    if user.role not in ("admin", "wholesaler"):
        raise HTTPException(403, "고객관리 접근 권한이 없습니다")
    if user.role == "wholesaler" and user.status != "approved":
        raise HTTPException(403, "승인된 도매만 접근할 수 있습니다")


class SupabaseCustomersRepo:
    """고객관리 DB 접근 — wholesaler_customer_exclusions(취소) + profiles(소매/가격노출/등급)."""

    def __init__(self):
        self.sb = get_supabase()
        self._admin_repo = SupabaseAdminRepo()   # email_map/agency_map 셰이핑 재사용

    # ── 조회 ──────────────────────────────────────────────
    def tenant_sellers(self, manager_id: str | None) -> list[dict]:
        """테넌트(도매관리자) 전체 소매 파트너 — role in (retail_seller, agency), 살아있음."""
        if not manager_id:
            return []
        return self.sb.table("profiles").select("*").eq("manager_id", manager_id).in_(
            "role", ["retail_seller", "agency"]).is_("deleted_at", "null").order(
            "created_at", desc=True).execute().data or []

    def excluded_customer_ids(self, wholesaler_id: str | None) -> list[str]:
        """이 도매에 대해 '취소된' 소매 id 목록 — 도매가 안 보는/관리 못 하는 거래처."""
        if not wholesaler_id:
            return []
        rows = self.sb.table(_EXCL).select("customer_id").eq(
            "wholesaler_id", wholesaler_id).is_("deleted_at", "null").execute().data or []
        return [r["customer_id"] for r in rows if r.get("customer_id")]

    def exclusions_for_sellers(self, ids: list[str]) -> dict:
        """소매 id → [취소된 도매 id] (admin 뷰: 어느 도매와 거래 취소됐는지)."""
        if not ids:
            return {}
        rows = self.sb.table(_EXCL).select("customer_id,wholesaler_id").in_(
            "customer_id", ids).is_("deleted_at", "null").execute().data or []
        out: dict = {}
        for r in rows:
            out.setdefault(r["customer_id"], []).append(r["wholesaler_id"])
        return out

    def exclusion_counts(self, wholesaler_ids: list[str]) -> dict:
        """도매 id → 취소 소매 수 (연결 소매 수 = 전체 − 취소)."""
        if not wholesaler_ids:
            return {}
        rows = self.sb.table(_EXCL).select("wholesaler_id").in_(
            "wholesaler_id", wholesaler_ids).is_("deleted_at", "null").execute().data or []
        counts: dict = {}
        for r in rows:
            counts[r["wholesaler_id"]] = counts.get(r["wholesaler_id"], 0) + 1
        return counts

    def wholesalers_by_ids(self, ids: list[str]) -> list[dict]:
        if not ids:
            return []
        return self.sb.table("wholesalers").select("id,name,biz_number,created_at").in_(
            "id", ids).is_("deleted_at", "null").order("created_at", desc=True).execute().data or []

    def shape(self, rows: list[dict]) -> list[dict]:
        """이메일/에이전시명 보강(admin 셰이핑 재사용). price_visibility/tier 는 행에 그대로."""
        return shape_account_rows(rows, self._admin_repo.email_map(), self._admin_repo.agency_map())

    def get_profile(self, uid: str):
        res = self.sb.table("profiles").select("*").eq("id", uid).is_(
            "deleted_at", "null").maybe_single().execute()
        return res.data if res else None

    # ── 쓰기 ──────────────────────────────────────────────
    def set_price_visibility(self, uid: str, vis: str):
        return self.sb.table("profiles").update({"price_visibility": vis}).eq("id", uid).execute().data

    def set_tier(self, uid: str, tier: str):
        # 1차 화면 제외(잠자는 엔드포인트) — 2차 자동등급용 forward-compat.
        return self.sb.table("profiles").update({"tier": tier}).eq("id", uid).execute().data

    def add_exclusion(self, customer_id: str, wholesaler_id: str, by: str | None = None):
        """매칭 취소 — 취소 예외 행 추가(멱등). 이미 살아있는 취소면 그대로."""
        existing = self.sb.table(_EXCL).select("id").eq(
            "wholesaler_id", wholesaler_id).eq("customer_id", customer_id).is_(
            "deleted_at", "null").limit(1).execute().data
        if existing:
            return existing
        row = {"wholesaler_id": wholesaler_id, "customer_id": customer_id}
        if by:
            row["created_by"] = by
        return self.sb.table(_EXCL).insert(row).execute().data

    def remove_exclusion(self, customer_id: str, wholesaler_id: str):
        """매칭 복원 — 취소 예외 행 soft delete(다시 연결). 복원 후 재취소 허용(부분 unique)."""
        now = datetime.now(timezone.utc).isoformat()
        return self.sb.table(_EXCL).update({"deleted_at": now}).eq(
            "wholesaler_id", wholesaler_id).eq("customer_id", customer_id).is_(
            "deleted_at", "null").execute().data


@router.get("")
def list_customers(user: CurrentUser = Depends(get_current_user)):
    """소매 목록 — admin=테넌트 전체(+취소 도매), wholesaler=테넌트 소매−취소(기본 전부 연결)."""
    require_customers_access(user)
    return svc.list_customers(SupabaseCustomersRepo(), user)


@router.get("/wholesalers")
def list_wholesalers(user: CurrentUser = Depends(get_current_user)):
    """도매업체 목록(도매관리자 전용) — 도매 탭 + 매칭 취소 대상. 연결 소매 수 포함."""
    _admin(user)
    return svc.list_wholesalers(SupabaseCustomersRepo(), user)


@router.post("/{uid}/disconnect")
def disconnect_customer(uid: str, payload: dict, user: CurrentUser = Depends(get_current_user)):
    """소매↔도매 매칭 취소(도매관리자 전용). payload={wholesaler_id}."""
    _admin(user)
    return svc.disconnect(SupabaseCustomersRepo(), user, uid, payload.get("wholesaler_id"))


@router.post("/{uid}/reconnect")
def reconnect_customer(uid: str, payload: dict, user: CurrentUser = Depends(get_current_user)):
    """취소했던 소매↔도매 매칭 복원(도매관리자 전용). payload={wholesaler_id}."""
    _admin(user)
    return svc.reconnect(SupabaseCustomersRepo(), user, uid, payload.get("wholesaler_id"))


@router.post("/{uid}/price-visibility")
def set_price_visibility(uid: str, payload: dict, user: CurrentUser = Depends(get_current_user)):
    """소매 가격노출 권한 설정. admin/wholesaler(연결된 소매). payload={price_visibility:wholesale|retail|none}."""
    require_customers_access(user)
    return svc.set_price_visibility(SupabaseCustomersRepo(), user, uid, payload.get("price_visibility"))


@router.post("/{uid}/tier")
def set_tier(uid: str, payload: dict, user: CurrentUser = Depends(get_current_user)):
    """[1차 화면 제외 — 잠자는 엔드포인트] 소매 등급 설정(2차 자동등급용). payload={tier:new|regular}."""
    require_customers_access(user)
    return svc.set_tier(SupabaseCustomersRepo(), user, uid, payload.get("tier"))
