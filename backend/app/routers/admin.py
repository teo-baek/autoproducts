from fastapi import APIRouter, Depends, HTTPException
from app.core.auth import get_current_user
from app.core.rbac import require_role
from app.core.supabase import get_supabase
from app.schemas.auth import CurrentUser
from app.services.accounts import approve_account, reject_account

router = APIRouter(prefix="/admin", tags=["admin"])
_admin = require_role("admin")


class SupabaseAdminRepo:
    def __init__(self):
        self.sb = get_supabase()

    def list_by_status(self, status: str):
        return self.sb.table("profiles").select("*").eq("status", status).is_(
            "deleted_at", "null").order("created_at", desc=True).execute().data or []

    def get_profile(self, uid: str):
        res = self.sb.table("profiles").select("*").eq("id", uid).is_(
            "deleted_at", "null").maybe_single().execute()
        return res.data if res else None

    def create_wholesaler(self, name: str):
        return self.sb.table("wholesalers").insert({"name": name}).execute().data[0]

    def set_status(self, uid: str, status: str, by: str, wholesaler_id: str | None = None):
        patch = {"status": status, "approved_by": by, "approved_at": "now()"}
        if wholesaler_id:
            patch["wholesaler_id"] = wholesaler_id
        return self.sb.table("profiles").update(patch).eq("id", uid).execute().data

    def set_price_visibility(self, uid: str, vis: str):
        return self.sb.table("profiles").update({"price_visibility": vis}).eq("id", uid).execute().data


@router.get("/accounts")
def list_accounts(status: str = "pending", user: CurrentUser = Depends(get_current_user)):
    _admin(user)
    return SupabaseAdminRepo().list_by_status(status)


@router.post("/accounts/{uid}/approve")
def approve(uid: str, user: CurrentUser = Depends(get_current_user)):
    """승인. 도매 계정이면 도매업체 자동 생성·연결(wholesaler_id)."""
    _admin(user)
    return approve_account(SupabaseAdminRepo(), uid, user.id)


@router.post("/accounts/{uid}/reject")
def reject(uid: str, user: CurrentUser = Depends(get_current_user)):
    _admin(user)
    return reject_account(SupabaseAdminRepo(), uid, user.id)


@router.post("/accounts/{uid}/price-visibility")
def set_price_visibility(uid: str, payload: dict, user: CurrentUser = Depends(get_current_user)):
    """관리자가 소매업체별 가격 노출 권한을 설정 (개발 정의서: 권한 관리)."""
    _admin(user)
    vis = payload.get("price_visibility")  # 'wholesale' | 'retail' | 'none'
    if vis not in ("wholesale", "retail", "none"):
        raise HTTPException(400, "price_visibility must be wholesale|retail|none")
    return SupabaseAdminRepo().set_price_visibility(uid, vis)
