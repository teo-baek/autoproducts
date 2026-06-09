from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, Response

from app.core.auth import get_current_user
from app.core.config import get_settings
from app.core.rbac import require_role, require_approved
from app.core.supabase import get_supabase
from app.schemas.auth import CurrentUser
from app.schemas.product import ProductCreate, SkuReplaceRequest
from app.services.excel_export import build_render_xlsx, cell_image_bytes, cell_image_path
from app.services.pricing import visible_price
from app.services.products import register_product, soft_delete_product
from app.services.platform_code import next_platform_code

router = APIRouter(prefix="/products", tags=["products"])

# PATCH 로 바꿀 수 없는 컬럼(소유/식별/감사) — mass-assignment 차단
_IMMUTABLE = {"id", "platform_code", "wholesaler_id", "created_by", "created_at", "deleted_at"}

# 조회 시 임베드할 컬럼(살아있는 자식만 — deleted_at 필터는 쿼리에서)
_SELECT = (
    "*,"
    "product_skus(id,color,size,wholesale_price,retail_price,stock,deleted_at),"
    "product_images(id,storage_path,thumbnail_path,original_filename,is_representative,match_status,sort_order,deleted_at)"
)


class ProductForbidden(Exception):
    """대상 상품이 없거나 호출자 소유가 아님 → 404."""


def shape_owner_product(row: dict, wholesaler_id: str) -> dict:
    """도매 본인 관리뷰로 셰이핑 — 가격은 visible_price() 통과(도매가+판매가 모두 노출).

    가격을 찍는 모든 출력 경로는 visible_price() 를 거친다(CLAUDE.md §가격 노출).
    본인 상품이므로 결과는 항상 {wholesale_price, retail_price}.
    """
    skus = []
    for s in row.get("product_skus", []) or []:
        if s.get("deleted_at"):
            continue
        priced = visible_price(
            "wholesaler", None, {**s, "product_org": wholesaler_id},
            viewer_org=wholesaler_id,
        )
        skus.append({"id": s["id"], "color": s["color"], "size": s["size"],
                     "stock": s.get("stock", 0), **priced})
    images = sorted(
        ({"id": im["id"], "storage_path": im["storage_path"],
          "thumbnail_path": im.get("thumbnail_path"),   # 엑셀 export 썸네일 우선용
          "original_filename": im.get("original_filename"),
          "is_representative": im.get("is_representative", False),
          "match_status": im.get("match_status")}
         for im in (row.get("product_images") or []) if not im.get("deleted_at")),
        key=lambda im: (not im["is_representative"]),
    )
    return {
        "id": row["id"],
        "platform_code": row["platform_code"],
        "source_p_number": row["source_p_number"],
        "item_name": row["item_name"],
        "category": row.get("category"),
        "fabric_composition": row.get("fabric_composition"),
        "origin": row.get("origin"),
        "lead_time_days": row.get("lead_time_days"),
        "description": row.get("description"),
        "representative_image_url": row.get("representative_image_url"),
        "status": row.get("status", "active"),
        "is_sold_out": row.get("is_sold_out", False),
        "created_at": row.get("created_at"),
        "skus": skus,
        "images": images,
    }


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

    def soft_delete_product(self, product_id):
        # 보상용(A-2): 등록 도중 SKU 삽입 실패 시 방금 만든 상품을 soft-delete(hard DELETE 금지).
        now = datetime.now(timezone.utc).isoformat()
        self.sb.table("products").update({"deleted_at": now}).eq("id", product_id).execute()

    def update_product(self, pid, patch):
        q = self.sb.table("products").update(patch).eq("id", pid)
        if self.owner_wid is not None:
            q = q.eq("wholesaler_id", self.owner_wid)
        data = q.execute().data
        if not data:
            raise ProductForbidden("상품을 찾을 수 없거나 권한이 없습니다")
        return data[0]

    def list_products(self, *, limit, offset, category=None, search=None, status=None):
        # 도매 본인(owner_wid) 상품만. 살아있는 행 + 살아있는 자식(SKU/이미지).
        q = self.sb.table("products").select(_SELECT, count="exact").eq(
            "wholesaler_id", self.owner_wid).is_("deleted_at", "null")
        if status:
            q = q.eq("status", status)
        if category:                         # 컬럼은 _07 마이그레이션. 탭 선택 시에만 적용.
            q = q.eq("category", category)
        if search:
            like = f"%{search}%"
            q = q.or_(f"item_name.ilike.{like},source_p_number.ilike.{like}")
        q = q.is_("product_skus.deleted_at", "null").is_("product_images.deleted_at", "null")
        q = q.order("created_at", desc=True).range(offset, offset + limit - 1)
        res = q.execute()
        return res.data or [], (res.count or 0)

    def get_product(self, pid):
        res = self.sb.table("products").select(_SELECT).eq("id", pid).eq(
            "wholesaler_id", self.owner_wid).is_("deleted_at", "null").maybe_single().execute()
        return res.data if res else None

    def replace_skus(self, pid, skus, updated_by=None):
        # 기존 SKU soft-delete(hard DELETE 금지) 후 새 세트 삽입. 소유 검증은 호출부에서 get_product 로.
        now = datetime.now(timezone.utc).isoformat()
        self.sb.table("product_skus").update({"deleted_at": now, "updated_by": updated_by}).eq(
            "product_id", pid).is_("deleted_at", "null").execute()
        rows = [{**s, "product_id": pid, "created_by": updated_by} for s in skus]
        if rows:
            self.sb.table("product_skus").insert(rows).execute()


@router.post("")
def create_product(payload: ProductCreate, user: CurrentUser = Depends(get_current_user)):
    require_approved(user); require_role("wholesaler")(user)
    if not user.wholesaler_id:
        raise HTTPException(400, "no wholesaler")
    return register_product(SupabaseProductRepo(), user.wholesaler_id, payload, created_by=user.id)


@router.get("")
def list_products(
    user: CurrentUser = Depends(get_current_user),
    limit: int = Query(default=20, le=100),
    offset: int = Query(default=0, ge=0),
    category: str | None = None,
    search: str | None = None,
    status: str | None = Query(default=None, pattern="^(active|archived)$"),
):
    """도매 본인 상품 관리뷰 목록 (필터 + 페이지네이션). 가격=도매가+판매가."""
    require_approved(user); require_role("wholesaler")(user)
    if not user.wholesaler_id:
        raise HTTPException(400, "no wholesaler")
    rows, total = SupabaseProductRepo(owner_wid=user.wholesaler_id).list_products(
        limit=limit, offset=offset, category=category, search=search, status=status)
    return {
        "items": [shape_owner_product(r, user.wholesaler_id) for r in rows],
        "total": total, "limit": limit, "offset": offset,
    }


# ⚠️ /{pid} 보다 먼저 선언해야 함 — 안 그러면 'export.xlsx' 가 pid 로 잡힘
@router.get("/export.xlsx")
def export_products(
    user: CurrentUser = Depends(get_current_user),
    category: str | None = None,
    search: str | None = None,
    status: str | None = Query(default=None, pattern="^(active|archived)$"),
):
    """도매 본인 상품 목록 엑셀 다운로드(사진·QR 박은 A~L 스타일, 관리뷰=도매가+판매가).

    가격은 shape_owner_product 가 이미 visible_price() 로 셰이핑(도매 본인 → 둘 다).
    QR 은 K열(QR 링크=URL 텍스트) + L열(QR 이미지=PNG 임베드) 두 열로 출력.
    """
    require_approved(user); require_role("wholesaler")(user)
    if not user.wholesaler_id:
        raise HTTPException(400, "no wholesaler")
    rows, _ = SupabaseProductRepo(owner_wid=user.wholesaler_id).list_products(
        limit=1000, offset=0, category=category, search=search, status=status)
    items = [shape_owner_product(r, user.wholesaler_id) for r in rows]
    # 이미지가 하나라도 있을 때만 Storage 클라이언트 사용(없으면 다운로드 시도 자체를 안 함)
    sb = get_supabase() if any(it.get("images") for it in items) else None
    render_rows = []
    for it in items:
        imgs = it.get("images") or []
        storage_path = cell_image_path(imgs[0]) if imgs else None  # 대표(정렬상 첫째) · 썸네일 우선
        render_rows.append({
            "source_p_number": it["source_p_number"],
            "item_name": it["item_name"],
            "fabric_composition": it.get("fabric_composition"),
            "platform_code": it["platform_code"],
            "image_bytes": cell_image_bytes(sb, storage_path) if storage_path else None,
            "skus": [{"color": s.get("color"), "size": s.get("size"), "stock": s.get("stock"),
                      "wholesale_price": s.get("wholesale_price"),
                      "retail_price": s.get("retail_price")} for s in it["skus"]],
        })
    data = build_render_xlsx(render_rows, base_url=get_settings().public_base_url)  # K=QR 링크 텍스트, L=QR 이미지
    return Response(
        content=data,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": 'attachment; filename="ezmerce-products.xlsx"'},
    )


@router.get("/{pid}")
def get_product(pid: str, user: CurrentUser = Depends(get_current_user)):
    """단건 상세(수정 폼 프리필). 타 업체/미존재 → 404."""
    require_approved(user); require_role("wholesaler")(user)
    if not user.wholesaler_id:
        raise HTTPException(400, "no wholesaler")
    row = SupabaseProductRepo(owner_wid=user.wholesaler_id).get_product(pid)
    if not row:
        raise HTTPException(404, "상품을 찾을 수 없거나 권한이 없습니다")
    return shape_owner_product(row, user.wholesaler_id)


@router.patch("/{pid}")
def patch_product(pid: str, patch: dict, user: CurrentUser = Depends(get_current_user)):
    require_approved(user); require_role("wholesaler")(user)
    patch = {k: v for k, v in patch.items() if k not in _IMMUTABLE}   # 불변 컬럼 제거
    patch["updated_by"] = user.id                                     # 누가 수정했는지
    try:
        return SupabaseProductRepo(owner_wid=user.wholesaler_id).update_product(pid, patch)
    except ProductForbidden as e:
        raise HTTPException(404, str(e))


@router.put("/{pid}/skus")
def replace_skus(pid: str, req: SkuReplaceRequest, user: CurrentUser = Depends(get_current_user)):
    """상품 SKU 전체 교체(수정 모달). 타 업체/미존재 → 404."""
    require_approved(user); require_role("wholesaler")(user)
    if not user.wholesaler_id:
        raise HTTPException(400, "no wholesaler")
    repo = SupabaseProductRepo(owner_wid=user.wholesaler_id)
    if not repo.get_product(pid):
        raise HTTPException(404, "상품을 찾을 수 없거나 권한이 없습니다")
    repo.replace_skus(pid, [s.model_dump() for s in req.skus], updated_by=user.id)
    return shape_owner_product(repo.get_product(pid), user.wholesaler_id)


@router.delete("/{pid}")
def delete_product(pid: str, user: CurrentUser = Depends(get_current_user)):
    require_approved(user); require_role("wholesaler")(user)
    # hard DELETE 금지 — soft delete(deleted_at). 자식(skus/images)은 DB 트리거가 cascade
    try:
        return soft_delete_product(SupabaseProductRepo(owner_wid=user.wholesaler_id), pid,
                                   datetime.now(timezone.utc).isoformat(), updated_by=user.id)
    except ProductForbidden as e:
        raise HTTPException(404, str(e))
