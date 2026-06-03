from fastapi import APIRouter, Depends, Query, Response
from app.core.auth import get_current_user
from app.core.config import get_settings
from app.core.rbac import require_approved
from app.core.supabase import get_supabase
from app.schemas.auth import CurrentUser
from app.services.pricing import visible_price
from app.services.excel_export import catalog_xlsx_bytes

router = APIRouter(prefix="/catalog", tags=["catalog"])

XLSX_MEDIA = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
_EXPORT_MAX = 1000  # RISK(scale): 엑셀 출력은 페이지네이션 없이 상한까지만. 초과분은 누락(Phase2 스트리밍 고려)


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


def _query_catalog_rows(sb, limit: int, cursor: str | None = None) -> list[dict]:
    # wholesaler_id 는 products(상위) 컬럼 — product_skus 엔 없음(잠복 버그였음)
    q = sb.table("products").select(
        "platform_code,item_name,wholesaler_id,product_skus(color,size,wholesale_price,retail_price)"
    ).eq("status", "active").is_("deleted_at", "null").is_(
        "product_skus.deleted_at", "null"   # 개별 soft-delete 된 SKU 는 배열에서 제외(규칙: 모든 조회 deleted_at)
    ).order("created_at").limit(limit)
    if cursor:
        q = q.gt("created_at", cursor)
    return q.execute().data


@router.get("")
def list_catalog(
    user: CurrentUser = Depends(get_current_user),
    limit: int = Query(default=30, le=100),
    cursor: str | None = None,
):
    require_approved(user)  # 미승인 → 403 (FR-5.1 / AC-6)
    rows = _query_catalog_rows(get_supabase(), limit, cursor)
    return {"items": [shape_catalog_item(_normalize(r), user) for r in rows]}


def _export_row(item: dict) -> dict:
    """카탈로그 항목 → 엑셀 1행. 대표가격 = 첫 SKU 노출가(price 우선, 관리뷰는 wholesale_price)."""
    price = None
    if item["skus"]:
        s0 = item["skus"][0]
        price = s0.get("price", s0.get("wholesale_price"))
    return {"platform_code": item["platform_code"], "item_name": item["item_name"], "price": price}


@router.get("/export.xlsx")
def export_catalog(user: CurrentUser = Depends(get_current_user)):
    """폐쇄형 카탈로그 엑셀 출력 + QR (FR-3). 가격은 역할별로 서버에서 셰이핑."""
    require_approved(user)
    rows = _query_catalog_rows(get_supabase(), _EXPORT_MAX)
    items = [shape_catalog_item(_normalize(r), user) for r in rows]
    data = catalog_xlsx_bytes([_export_row(it) for it in items], base_url=get_settings().public_base_url)
    return Response(
        content=data,
        media_type=XLSX_MEDIA,
        headers={"Content-Disposition": 'attachment; filename="ezmerce-catalog.xlsx"'},
    )


def _normalize(r: dict) -> dict:
    # product_org = 상품 소유 도매업체(products.wholesaler_id) — pricing 의 wholesaler 자기조직 판별용
    org = r.get("wholesaler_id")
    skus = [{**s, "product_org": org} for s in r.get("product_skus", [])]
    return {"platform_code": r["platform_code"], "item_name": r["item_name"], "skus": skus}
