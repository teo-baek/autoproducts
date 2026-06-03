from fastapi import APIRouter, Depends
from app.core.auth import get_current_user
from app.core.rbac import require_role
from app.core.supabase import get_supabase
from app.schemas.auth import CurrentUser

router = APIRouter(prefix="/admin", tags=["admin"])
_admin = require_role("admin")


def _set_status(uid: str, status: str, by: str):
    sb = get_supabase()
    return sb.table("profiles").update(
        {"status": status, "approved_by": by, "approved_at": "now()"}
    ).eq("id", uid).execute().data


@router.get("/accounts")
def list_accounts(status: str = "pending", user: CurrentUser = Depends(get_current_user)):
    _admin(user)
    sb = get_supabase()
    return sb.table("profiles").select("*").eq("status", status).execute().data


@router.post("/accounts/{uid}/approve")
def approve(uid: str, user: CurrentUser = Depends(get_current_user)):
    _admin(user)
    return _set_status(uid, "approved", user.id)


@router.post("/accounts/{uid}/reject")
def reject(uid: str, user: CurrentUser = Depends(get_current_user)):
    _admin(user)
    return _set_status(uid, "rejected", user.id)


@router.post("/accounts/{uid}/price-visibility")
def set_price_visibility(uid: str, payload: dict, user: CurrentUser = Depends(get_current_user)):
    """관리자가 소매업체별 가격 노출 권한을 설정 (개발 정의서: 권한 관리)."""
    _admin(user)
    vis = payload.get("price_visibility")  # 'wholesale' | 'retail' | 'none'
    if vis not in ("wholesale", "retail", "none"):
        from fastapi import HTTPException
        raise HTTPException(400, "price_visibility must be wholesale|retail|none")
    sb = get_supabase()
    return sb.table("profiles").update({"price_visibility": vis}).eq("id", uid).execute().data
