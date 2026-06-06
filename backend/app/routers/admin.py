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

    def email_map(self) -> dict:
        """auth.users 의 id→email 매핑(service key 의 admin API). profiles 엔 이메일이 없으므로 보강용."""
        out: dict = {}
        try:
            page = 1
            while page <= 20:  # 안전 상한(최대 ~2000계정)
                res = self.sb.auth.admin.list_users(page=page, per_page=100)
                users = res if isinstance(res, list) else (getattr(res, "users", None) or [])
                if not users:
                    break
                for u in users:
                    uid = getattr(u, "id", None)
                    if uid:
                        out[uid] = getattr(u, "email", None)
                if len(users) < 100:
                    break
                page += 1
        except Exception:  # noqa: BLE001 — 이메일 보강 실패해도 목록은 반환
            pass
        return out

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
    repo = SupabaseAdminRepo()
    rows = repo.list_by_status(status)
    emails = repo.email_map()
    return [{**r, "email": emails.get(r["id"])} for r in rows]


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
