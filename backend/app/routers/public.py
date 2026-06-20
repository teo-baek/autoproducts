from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from app.core.auth import get_current_user_optional
from app.core.config import get_settings
from app.core.supabase import get_supabase
from app.schemas.auth import CurrentUser
from app.services.images import public_image_url as _public_image_url, representative_image_url
from app.services.pricing import visible_price
from app.services.qr import qr_target_url, generate_qr_png
from app.services.customers import seller_visible_wholesaler_ids

router = APIRouter(tags=["public"])


def _pick_image(row: dict) -> str | None:
    """공개 카드 대표 이미지 — rep_url 우선, 없으면 product_images 폴백(공용 헬퍼)."""
    return representative_image_url(row.get("representative_image_url"), row.get("product_images"))


def shape_card_skus(row: dict, viewer: CurrentUser) -> list[dict]:
    """로그인 뷰어용 카드 옵션(색상×사이즈) — 재고 + 역할별 가격.

    가격은 단일 진실 visible_price() 통과(CLAUDE.md §가격 노출): 에이전시 소속 셀러 → 미노출(price=None),
    그 외 → 도매가/판매가(역할별). 도매 본인/admin 은 {wholesale_price, retail_price} 2칸.
    """
    org = row.get("wholesaler_id")
    out: list[dict] = []
    for s in row.get("product_skus") or []:
        if s.get("deleted_at"):
            continue
        price = visible_price(
            viewer.role, viewer.seller_type, {**s, "product_org": org},
            viewer_org=viewer.wholesaler_id, price_visibility=viewer.price_visibility,
        )
        out.append({"color": s["color"], "size": s["size"], "stock": s.get("stock"), **price})
    return out


@router.get("/qr/{platform_code}.png")
def qr_png(platform_code: str):
    url = qr_target_url(platform_code, get_settings().public_base_url)
    return Response(content=generate_qr_png(url), media_type="image/png")


@router.get("/p/{platform_code}")
def product_card(
    platform_code: str,
    viewer: CurrentUser | None = Depends(get_current_user_optional),
):
    sb = get_supabase()
    res = sb.table("products").select(
        "platform_code,source_p_number,item_name,fabric_composition,origin,wholesaler_id,"
        "representative_image_url,"
        "product_skus(color,size,wholesale_price,retail_price,stock,deleted_at),"
        "product_images(storage_path,is_representative,deleted_at)"
    ).eq("platform_code", platform_code).eq("status", "active").is_(
        "deleted_at", "null"            # soft-delete 된 상품은 공개 링크에서도 차단(규칙)
    ).is_("product_skus.deleted_at", "null").maybe_single().execute()  # 0행이면 None → 404
    row = res.data if res else None
    if not row:
        raise HTTPException(404, "not found")
    # 테넌트 스코프 + 정책 강제: 로그인 셀러는 '연계 테넌트 도매 − 자기가 취소한 도매' 상품에만 가격/재고 노출.
    # 취소한 도매의 상품은 QR 카드에서도 가격/재고 1도 안 보임(쇼룸·엑셀과 동일).
    scoped = seller_visible_wholesaler_ids(sb, viewer.manager_id, viewer.id) if viewer else []
    return build_card(row, viewer, scoped)


def build_card(row: dict, viewer: CurrentUser | None, scoped_ids: list[str]) -> dict:
    """공개 카드 응답 조립.

    비로그인/미승인 → 공개 최소(가격/재고 없음). 로그인+승인 + 상품이 뷰어 테넌트 스코프 내(FR-4)
    → 역할별 skus(가격/재고) 부여. 가격은 반드시 visible_price() 통과(에이전시 소속 셀러는 미노출).
    """
    # 공개(비로그인) 응답 — 가격/재고 없음. 업체품번(source_p_number)은 표시용으로 추가.
    card = {
        "platform_code": row["platform_code"],
        "source_p_number": row.get("source_p_number"),
        "item_name": row["item_name"],
        "fabric_composition": row.get("fabric_composition"),
        "origin": row.get("origin"),
        "representative_image_url": _pick_image(row),
    }
    # RISK(side-effect): 가격/재고는 '로그인 + 승인' + '테넌트 스코프 내' 뷰어에게만.
    if viewer and viewer.status == "approved" and row.get("wholesaler_id") in scoped_ids:
        card["skus"] = shape_card_skus(row, viewer)
    return card
