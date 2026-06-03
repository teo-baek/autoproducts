from fastapi import APIRouter, HTTPException
from fastapi.responses import Response
from app.core.config import get_settings
from app.core.supabase import get_supabase
from app.services.qr import qr_target_url, generate_qr_png

router = APIRouter(tags=["public"])


@router.get("/qr/{platform_code}.png")
def qr_png(platform_code: str):
    url = qr_target_url(platform_code, get_settings().public_base_url)
    return Response(content=generate_qr_png(url), media_type="image/png")


@router.get("/p/{platform_code}")
def product_card(platform_code: str):
    sb = get_supabase()
    row = sb.table("products").select(
        "platform_code,item_name,fabric_composition,origin,representative_image_url"
    ).eq("platform_code", platform_code).eq("status", "active").single().execute().data
    if not row:
        raise HTTPException(404, "not found")
    return row  # RISK(side-effect): 공개 링크 — 가격 필드 절대 포함 금지
