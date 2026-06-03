from fastapi import APIRouter, Depends, Query
from app.core.auth import get_current_user
from app.core.rbac import require_approved
from app.core.supabase import get_supabase
from app.schemas.auth import CurrentUser
from app.services.pricing import visible_price

router = APIRouter(prefix="/catalog", tags=["catalog"])


def shape_catalog_item(row: dict, user: CurrentUser) -> dict:
    shaped_skus = []
    for sku in row.get("skus", []):
        price = visible_price(
            user.role, user.seller_type, sku,
            viewer_org=user.wholesaler_id,
            price_visibility=user.price_visibility,  # 관리자 설정 우선
        )
        shaped_skus.append({"color": sku["color"], "size": sku["size"], **price})
    return {"platform_code": row["platform_code"], "item_name": row["item_name"], "skus": shaped_skus}


@router.get("")
def list_catalog(
    user: CurrentUser = Depends(get_current_user),
    limit: int = Query(default=30, le=100),
    cursor: str | None = None,
):
    require_approved(user)  # 미승인 → 403 (FR-5.1 / AC-6)
    sb = get_supabase()
    q = sb.table("products").select(
        "platform_code,item_name,product_skus(color,size,wholesale_price,retail_price,wholesaler_id)"
    ).eq("status", "active").is_("deleted_at", "null").order("created_at").limit(limit)
    if cursor:
        q = q.gt("created_at", cursor)
    rows = q.execute().data
    return {"items": [shape_catalog_item(_normalize(r), user) for r in rows]}


def _normalize(r: dict) -> dict:
    skus = [{**s, "product_org": s.get("wholesaler_id")} for s in r.get("product_skus", [])]
    return {"platform_code": r["platform_code"], "item_name": r["item_name"], "skus": skus}
