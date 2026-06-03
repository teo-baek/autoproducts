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
