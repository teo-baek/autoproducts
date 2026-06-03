from fastapi import APIRouter, Depends, HTTPException
from app.core.auth import get_current_user
from app.core.rbac import require_role, require_approved
from app.core.supabase import get_supabase
from app.schemas.auth import CurrentUser
from app.schemas.product import ProductCreate
from datetime import datetime, timezone
from app.services.products import register_product, soft_delete_product
from app.services.platform_code import next_platform_code

router = APIRouter(prefix="/products", tags=["products"])


class SupabaseProductRepo:
    def __init__(self): self.sb = get_supabase()
    def next_platform_code(self): return next_platform_code(self.sb)
    def insert_product(self, d): return self.sb.table("products").insert(d).execute().data[0]
    def insert_skus(self, rows): return self.sb.table("product_skus").insert(rows).execute().data
    def update_product(self, pid, patch):
        return self.sb.table("products").update(patch).eq("id", pid).execute().data[0]


@router.post("")
def create_product(payload: ProductCreate, user: CurrentUser = Depends(get_current_user)):
    require_approved(user); require_role("wholesaler")(user)
    if not user.wholesaler_id:
        raise HTTPException(400, "no wholesaler")
    return register_product(SupabaseProductRepo(), user.wholesaler_id, payload, created_by=user.id)


@router.patch("/{pid}")
def patch_product(pid: str, patch: dict, user: CurrentUser = Depends(get_current_user)):
    require_approved(user); require_role("wholesaler")(user)
    patch = {**patch, "updated_by": user.id}  # 누가 수정했는지 기록
    return SupabaseProductRepo().update_product(pid, patch)  # RISK(side-effect): 소유 wholesaler 검증 필요


@router.delete("/{pid}")
def delete_product(pid: str, user: CurrentUser = Depends(get_current_user)):
    require_approved(user); require_role("wholesaler")(user)
    # hard DELETE 금지 — soft delete(deleted_at). 자식(skus/images)은 DB 트리거가 cascade
    return soft_delete_product(SupabaseProductRepo(), pid, datetime.now(timezone.utc).isoformat(), updated_by=user.id)
