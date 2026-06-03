from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException

from app.core.auth import get_current_user
from app.core.rbac import require_role, require_approved
from app.core.supabase import get_supabase
from app.schemas.auth import CurrentUser
from app.schemas.product import ProductCreate
from app.services.products import register_product, soft_delete_product
from app.services.platform_code import next_platform_code

router = APIRouter(prefix="/products", tags=["products"])

# PATCH 로 바꿀 수 없는 컬럼(소유/식별/감사) — mass-assignment 차단
_IMMUTABLE = {"id", "platform_code", "wholesaler_id", "created_by", "created_at", "deleted_at"}


class ProductForbidden(Exception):
    """대상 상품이 없거나 호출자 소유가 아님 → 404."""


class SupabaseProductRepo:
    def __init__(self, owner_wid: str | None = None):
        self.sb = get_supabase()
        self.owner_wid = owner_wid          # 설정 시 update 를 이 도매업체로 스코프(IDOR 차단)

    def next_platform_code(self):
        return next_platform_code(self.sb)

    def insert_product(self, d):
        return self.sb.table("products").insert(d).execute().data[0]

    def insert_skus(self, rows):
        return self.sb.table("product_skus").insert(rows).execute().data

    def update_product(self, pid, patch):
        q = self.sb.table("products").update(patch).eq("id", pid)
        if self.owner_wid is not None:
            q = q.eq("wholesaler_id", self.owner_wid)
        data = q.execute().data
        if not data:
            raise ProductForbidden("상품을 찾을 수 없거나 권한이 없습니다")
        return data[0]


@router.post("")
def create_product(payload: ProductCreate, user: CurrentUser = Depends(get_current_user)):
    require_approved(user); require_role("wholesaler")(user)
    if not user.wholesaler_id:
        raise HTTPException(400, "no wholesaler")
    return register_product(SupabaseProductRepo(), user.wholesaler_id, payload, created_by=user.id)


@router.patch("/{pid}")
def patch_product(pid: str, patch: dict, user: CurrentUser = Depends(get_current_user)):
    require_approved(user); require_role("wholesaler")(user)
    patch = {k: v for k, v in patch.items() if k not in _IMMUTABLE}   # 불변 컬럼 제거
    patch["updated_by"] = user.id                                     # 누가 수정했는지
    try:
        return SupabaseProductRepo(owner_wid=user.wholesaler_id).update_product(pid, patch)
    except ProductForbidden as e:
        raise HTTPException(404, str(e))


@router.delete("/{pid}")
def delete_product(pid: str, user: CurrentUser = Depends(get_current_user)):
    require_approved(user); require_role("wholesaler")(user)
    # hard DELETE 금지 — soft delete(deleted_at). 자식(skus/images)은 DB 트리거가 cascade
    try:
        return soft_delete_product(SupabaseProductRepo(owner_wid=user.wholesaler_id), pid,
                                   datetime.now(timezone.utc).isoformat(), updated_by=user.id)
    except ProductForbidden as e:
        raise HTTPException(404, str(e))
