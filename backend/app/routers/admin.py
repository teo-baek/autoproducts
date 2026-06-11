from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from app.core.auth import get_current_user
from app.core.rbac import require_role
from app.core.supabase import get_supabase
from app.schemas.auth import CurrentUser
from app.services.accounts import approve_account, reject_account
from app.services.pricing import visible_price
from app.services.tenancy import scoped_wholesaler_ids

router = APIRouter(prefix="/admin", tags=["admin"])
_admin = require_role("admin")


def shape_account_rows(rows: list[dict], emails: dict, agencies: dict) -> list[dict]:
    """관리자 계정 목록 셰이핑 — auth 이메일 보강 + 에이전시 소속 셀러의 소속 에이전시명 부여.

    - 셀러 유형 구분은 profiles.seller_type 그대로(독립=independent / 에이전시 소속=agency_affiliated).
    - agency_affiliated 셀러는 agency_id 가 가리키는 에이전시명을 `agency_name` 으로 추가(어드민 표시용).
    - 1차에선 에이전시 미운영이라 agency_id 가 비어 agency_name=None 이지만, 운영 시작 시 자동 표시됨.
    """
    return [
        {
            **r,
            "email": emails.get(r["id"]),
            "agency_name": agencies.get(r.get("agency_id")),
        }
        for r in rows
    ]


def shape_admin_product(row: dict) -> dict:
    """도매관리자(테넌트) 합산 상품 셰이핑 — 가격 admin 양가(도매가+판매가) + 도매 출처(wholesaler_name).

    가격은 단일 진실 visible_price("admin", ...) 통과(셰이핑 우회 금지, CLAUDE.md §가격 노출).
    행마다 어느 도매 것인지 wholesaler_name 을 부여(FR-5).
    """
    org = row.get("wholesaler_id")
    skus = []
    for s in row.get("product_skus", []) or []:
        if s.get("deleted_at"):
            continue
        priced = visible_price("admin", None, {**s, "product_org": org})
        skus.append({"color": s.get("color"), "size": s.get("size"),
                     "stock": s.get("stock", 0), **priced})
    w = row.get("wholesalers")
    wholesaler_name = w.get("name") if isinstance(w, dict) else None
    return {
        "id": row["id"],
        "platform_code": row["platform_code"],
        "source_p_number": row.get("source_p_number"),
        "item_name": row["item_name"],
        "category": row.get("category"),
        "status": row.get("status", "active"),
        "is_sold_out": row.get("is_sold_out", False),
        "representative_image_url": row.get("representative_image_url"),
        "created_at": row.get("created_at"),
        "wholesaler_id": org,
        "wholesaler_name": wholesaler_name,   # 행마다 도매 출처(FR-5)
        "skus": skus,
    }


class SupabaseAdminRepo:
    def __init__(self):
        self.sb = get_supabase()

    def list_by_status(self, status: str, manager_id: str | None = None):
        q = self.sb.table("profiles").select("*").eq("status", status).is_("deleted_at", "null")
        if manager_id:
            # 1차: 자기 테넌트(도매관리자) + 미배정(신규 가입 pending) 함께. 둘째 테넌트 등장 시 정교화(범위 밖).
            q = q.or_(f"manager_id.eq.{manager_id},manager_id.is.null")
        return q.order("created_at", desc=True).execute().data or []

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

    def agency_map(self) -> dict:
        """agency_id → name (에이전시 소속 셀러의 소속 표시용). 소규모 테이블이라 살아있는 행 전량 로드."""
        try:
            rows = self.sb.table("agencies").select("id,name").is_(
                "deleted_at", "null").execute().data or []
        except Exception:  # noqa: BLE001 — 에이전시 조회 실패해도 계정 목록은 반환
            return {}
        return {r["id"]: r.get("name") for r in rows}

    def get_profile(self, uid: str):
        res = self.sb.table("profiles").select("*").eq("id", uid).is_(
            "deleted_at", "null").maybe_single().execute()
        return res.data if res else None

    def create_wholesaler(self, name: str):
        return self.sb.table("wholesalers").insert({"name": name}).execute().data[0]

    def soft_delete_wholesaler(self, wid: str):
        # 보상용(A-4): 승인 연결 실패 시 방금 만든 도매업체를 soft-delete(고아 방지, hard DELETE 금지).
        now = datetime.now(timezone.utc).isoformat()
        self.sb.table("wholesalers").update({"deleted_at": now}).eq("id", wid).execute()

    def set_status(self, uid: str, status: str, by: str, wholesaler_id: str | None = None,
                   manager_id: str | None = None):
        patch = {"status": status, "approved_by": by, "approved_at": "now()"}
        if wholesaler_id:
            patch["wholesaler_id"] = wholesaler_id
        if manager_id:
            patch["manager_id"] = manager_id   # 셀러 → 도매관리자(테넌트) 연계(FR-3/FR-7)
        return self.sb.table("profiles").update(patch).eq("id", uid).execute().data

    def link_wholesaler_to_manager(self, wholesaler_id: str, manager_id: str, by: str | None = None):
        """도매상 → 도매관리자(테넌트) 소속 연결(manager_wholesalers). 멱등 — 이미 살아있는 연결이면 skip.
        부분 unique(manager_wholesalers_wid_alive)가 race 안전망."""
        existing = self.sb.table("manager_wholesalers").select("id").eq(
            "wholesaler_id", wholesaler_id).is_("deleted_at", "null").limit(1).execute().data
        if existing:
            return existing
        row = {"wholesaler_id": wholesaler_id, "manager_id": manager_id}
        if by:
            row["created_by"] = by
        return self.sb.table("manager_wholesalers").insert(row).execute().data

    def set_price_visibility(self, uid: str, vis: str):
        return self.sb.table("profiles").update({"price_visibility": vis}).eq("id", uid).execute().data

    def list_products_for_manager(self, wholesaler_ids: list[str], *, limit: int, offset: int,
                                  search: str | None = None, status: str | None = None):
        """소속 도매(wholesaler_ids) 전체의 상품 합산 조회(FR-5). 빈 목록 → 빈 결과."""
        if not wholesaler_ids:
            return [], 0
        q = self.sb.table("products").select(
            "id,platform_code,source_p_number,item_name,category,status,is_sold_out,"
            "created_at,wholesaler_id,representative_image_url,"
            "wholesalers(name),"                                    # 도매 출처 이름 join(FR-5)
            "product_skus(color,size,wholesale_price,retail_price,stock,deleted_at)",
            count="exact",
        ).in_("wholesaler_id", wholesaler_ids).is_("deleted_at", "null").is_(
            "product_skus.deleted_at", "null")
        if status:
            q = q.eq("status", status)
        if search:
            like = f"%{search}%"
            q = q.or_(f"item_name.ilike.{like},source_p_number.ilike.{like}")
        q = q.order("created_at", desc=True).range(offset, offset + limit - 1)
        res = q.execute()
        return res.data or [], (res.count or 0)


@router.get("/accounts")
def list_accounts(status: str = "pending", user: CurrentUser = Depends(get_current_user)):
    _admin(user)
    repo = SupabaseAdminRepo()
    rows = repo.list_by_status(status, user.manager_id)   # 자기 테넌트 + 미배정 신규(FR-7)
    # email(auth 보강) + agency_name(에이전시 소속 셀러의 소속명) 부여 — seller_type 으로 유형 구분.
    return shape_account_rows(rows, repo.email_map(), repo.agency_map())


@router.post("/accounts/{uid}/approve")
def approve(uid: str, user: CurrentUser = Depends(get_current_user)):
    """승인. 도매 계정이면 도매업체 자동 생성·연결(wholesaler_id) + 테넌트(도매관리자) 소속 연결(FR-7)."""
    _admin(user)
    return approve_account(SupabaseAdminRepo(), uid, user.id, user.manager_id)


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


@router.get("/products")
def admin_products(
    user: CurrentUser = Depends(get_current_user),
    limit: int = Query(default=30, le=100),
    offset: int = Query(default=0, ge=0),
    search: str | None = None,
    status: str | None = Query(default=None, pattern="^(active|archived)$"),
):
    """도매관리자(테넌트) 합산 상품관리(FR-5) — 소속 도매 전체 상품, 행마다 도매 출처. 가격=도매가+판매가."""
    _admin(user)
    repo = SupabaseAdminRepo()
    ids = scoped_wholesaler_ids(repo.sb, user.manager_id)   # 자기 테넌트 소속 도매 전체
    rows, total = repo.list_products_for_manager(
        ids, limit=limit, offset=offset, search=search, status=status)
    return {
        "items": [shape_admin_product(r) for r in rows],
        "total": total, "limit": limit, "offset": offset,
    }
