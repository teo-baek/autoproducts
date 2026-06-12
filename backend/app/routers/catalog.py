from fastapi import APIRouter, Depends, Query, Response
from app.core.auth import get_current_user
from app.core.config import get_settings
from app.core.rbac import require_approved, require_role
from app.core.supabase import get_supabase
from app.schemas.auth import CurrentUser
from app.services.pricing import visible_price, visible_price_columns
from app.services.excel_export import build_render_xlsx, cell_image_bytes, cell_image_path, price_code
from app.services.images import representative_image_url, storage_path_from_public_url
from app.services.tenancy import scoped_wholesaler_ids

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
        # stock(재고=가용)·이미지는 가격이 아니므로 visible_price 셰이핑과 무관(가공 우회 아님).
        # 셀러 쇼룸현황이 변형(색상×사이즈)별 카드로 가용 재고를 보여주는 데 쓴다.
        shaped_skus.append(
            {"color": sku["color"], "size": sku["size"], "stock": sku.get("stock"), **price}
        )
    return {
        "platform_code": row["platform_code"],
        "item_name": row["item_name"],
        "source_p_number": row.get("source_p_number"),  # 쇼룸/엑셀 "품번"
        "fabric_composition": row.get("fabric_composition"),  # 쇼룸 카드 혼용률 표시
        "representative_image_url": row.get("representative_image_url"),
        "created_at": row.get("created_at"),  # 커서 페이지네이션(클라이언트 다음 cursor)용
        "skus": shaped_skus,
    }


def _query_catalog_rows(sb, limit: int, cursor: str | None = None,
                        wholesaler_ids: list[str] | None = None) -> list[dict]:
    # wholesaler_id 는 products(상위) 컬럼 — product_skus 엔 없음(잠복 버그였음)
    # source_p_number(품번)·representative_image_url·created_at·skus.stock 은 셀러 쇼룸현황
    # (품번/이미지/사이즈별 재고/커서) 표시용으로 추가 노출. 품번은 export 의 "품번"과 동일 의미.
    q = sb.table("products").select(
        "platform_code,item_name,source_p_number,fabric_composition,wholesaler_id,representative_image_url,created_at,"
        "product_skus(color,size,wholesale_price,retail_price,stock),"
        "product_images(storage_path,is_representative,deleted_at)"   # 대량 업로드 사진 폴백용
    ).eq("status", "active").is_("deleted_at", "null").is_(
        "product_skus.deleted_at", "null"   # 개별 soft-delete 된 SKU 는 배열에서 제외(규칙: 모든 조회 deleted_at)
    ).order("created_at").limit(limit)
    if wholesaler_ids is not None:
        q = q.in_("wholesaler_id", wholesaler_ids)   # 테넌트 스코프(FR-4). [] → 빈 결과(fail-closed)
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
    # 보안(도매사↔도매사 격리): 카탈로그는 '셀러 쇼룸' 전용이다. wholesaler 가 호출하면 같은 테넌트의
    # 타 도매사 상품·이미지(representative_image_url)가 노출된다 → 셀러 역할만 허용. admin 은 /admin/products 사용.
    require_role("retail_seller", "agency")(user)
    sb = get_supabase()
    ids = scoped_wholesaler_ids(sb, user.manager_id)   # 뷰어 연계 도매관리자의 소속 도매만(FR-4)
    rows = _query_catalog_rows(sb, limit, cursor, wholesaler_ids=ids)
    return {"items": [shape_catalog_item(_normalize(r), user) for r in rows]}


def _query_catalog_export_rows(sb, limit: int, wholesaler_ids: list[str] | None = None) -> list[dict]:
    """스타일 엑셀용 — VIEW 쿼리에 사진(대표/이미지)·품번·혼용률을 더 얹은 조회."""
    q = sb.table("products").select(
        "platform_code,item_name,source_p_number,fabric_composition,wholesaler_id,"
        "representative_image_url,"
        "product_skus(color,size,wholesale_price,retail_price,stock,deleted_at),"
        "product_images(storage_path,thumbnail_path,is_representative,deleted_at)"   # 썸네일 우선용
    ).eq("status", "active").is_("deleted_at", "null").is_(
        "product_skus.deleted_at", "null"
    ).is_("product_images.deleted_at", "null").order("created_at").limit(limit)
    if wholesaler_ids is not None:
        q = q.in_("wholesaler_id", wholesaler_ids)   # 테넌트 스코프(FR-4)
    return q.execute().data


def _styled_export_rows(rows: list[dict], user: CurrentUser) -> list[dict]:
    """조회 행 → build_render_xlsx 입력. 가격은 역할별 visible_price_columns(셰이핑 우회 금지)."""
    out = []
    for r in rows:
        org = r.get("wholesaler_id")
        skus = []
        for s in r.get("product_skus") or []:
            cols = visible_price_columns(
                user.role, user.seller_type, {**s, "product_org": org},
                viewer_org=user.wholesaler_id, price_visibility=user.price_visibility,
            )
            # P CODE = 가격코드(라이브셀러 작업용). raw 도매·판매로 계산하되, 가격이 역할상 '완전 미노출'
            # (도매·판매 둘 다 None = none 셀러)이면 코드도 빈칸으로 유출 방지. 그 외(도매가만 보는
            # 라이브셀러 포함)는 코드 노출 — 셀러 본인 작업데이터(사용자 확정 2026-06-07).
            price_hidden = cols.get("wholesale_price") is None and cols.get("retail_price") is None
            p_code = "" if price_hidden else price_code(s.get("wholesale_price"), s.get("retail_price"))
            skus.append({"color": s.get("color"), "size": s.get("size"),
                         "stock": s.get("stock"), "p_code": p_code, **cols})
        imgs = [im for im in (r.get("product_images") or []) if not im.get("deleted_at")]
        imgs.sort(key=lambda im: not im.get("is_representative"))  # 대표 먼저
        out.append({
            "source_p_number": r.get("source_p_number"),
            "item_name": r.get("item_name"),
            "fabric_composition": r.get("fabric_composition"),
            "platform_code": r.get("platform_code"),
            # 썸네일 우선. product_images 없으면(단일 업로드) 대표 URL→경로 폴백(엑셀 사진 누락 방지).
            "_storage_path": (cell_image_path(imgs[0]) if imgs
                              else storage_path_from_public_url(r.get("representative_image_url"))),
            "skus": skus,
        })
    return out


@router.get("/export.xlsx")
def export_catalog(user: CurrentUser = Depends(get_current_user)):
    """폐쇄형 카탈로그 엑셀 출력(사진·QR 박은 A~J 스타일, FR-3). 가격은 역할별로 서버에서 셰이핑(FR-5.2)."""
    require_approved(user)
    require_role("retail_seller", "agency")(user)  # 보안: 셀러 전용(도매사↔도매사 이미지 격리, list_catalog 과 동일)
    sb = get_supabase()
    ids = scoped_wholesaler_ids(sb, user.manager_id)   # 테넌트 스코프(FR-4)
    styled = _styled_export_rows(_query_catalog_export_rows(sb, _EXPORT_MAX, wholesaler_ids=ids), user)
    for x in styled:                       # 한 장씩 다운로드→축소(대량 OOM 방지)
        sp = x.pop("_storage_path")
        x["image_bytes"] = cell_image_bytes(sb, sp) if sp else None
    data = build_render_xlsx(styled, base_url=get_settings().public_base_url)  # K=QR 링크 텍스트, L=QR 이미지
    return Response(
        content=data,
        media_type=XLSX_MEDIA,
        headers={"Content-Disposition": 'attachment; filename="ezmerce-catalog.xlsx"'},
    )


def _normalize(r: dict) -> dict:
    # product_org = 상품 소유 도매업체(products.wholesaler_id) — pricing 의 wholesaler 자기조직 판별용
    org = r.get("wholesaler_id")
    skus = [{**s, "product_org": org} for s in r.get("product_skus", [])]
    return {
        "platform_code": r["platform_code"],
        "item_name": r["item_name"],
        "source_p_number": r.get("source_p_number"),
        "fabric_composition": r.get("fabric_composition"),  # 쇼룸 카드 혼용률
        # 단일 업로드(rep_url) 없으면 product_images 로 폴백 → 대량 상품도 쇼룸에 사진 노출
        "representative_image_url": representative_image_url(
            r.get("representative_image_url"), r.get("product_images")
        ),
        "created_at": r.get("created_at"),
        "skus": skus,
    }
