import os
from tempfile import NamedTemporaryFile

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile

from app.core.auth import get_current_user
from app.core.rbac import require_approved, require_role
from app.core.supabase import get_supabase
from app.schemas.auth import CurrentUser
from app.schemas.upload import AttachImagesRequest, MatchRequest
from app.services.platform_code import next_platform_code
from app.services.uploads import (
    UploadError, UploadForbidden, attach_images, ingest_excel, list_unmatched, resolve_match,
)

router = APIRouter(prefix="/uploads", tags=["uploads"])
_wholesaler = require_role("wholesaler")


class SupabaseUploadRepo:
    def __init__(self):
        self.sb = get_supabase()

    def next_platform_code(self):
        return next_platform_code(self.sb)

    def insert_product(self, d):
        return self.sb.table("products").insert(d).execute().data[0]

    def insert_skus(self, rows):
        return self.sb.table("product_skus").insert(rows).execute().data

    def create_upload_job(self, d):
        return self.sb.table("upload_jobs").insert(d).execute().data[0]

    def update_upload_job(self, jid, patch):
        return self.sb.table("upload_jobs").update(patch).eq("id", jid).execute().data[0]

    def get_upload_job(self, jid):
        # maybe_single: 0행이면 예외 대신 data=None (없는 job → 서비스가 404 처리)
        res = self.sb.table("upload_jobs").select("*").eq("id", jid).is_("deleted_at", "null").maybe_single().execute()
        return res.data if res else None

    def list_jobs(self, wid, limit=20):
        return self.sb.table("upload_jobs").select(
            "id,status,total_rows,matched_rows,error_rows,error_detail,file_path,created_at,completed_at"
        ).eq("wholesaler_id", wid).is_("deleted_at", "null").order(
            "created_at", desc=True).limit(limit).execute().data or []

    def products_pnum_map(self, wid):
        rows = self.sb.table("products").select("id,source_p_number").eq(
            "wholesaler_id", wid).is_("deleted_at", "null").execute().data
        return {r["source_p_number"]: r["id"] for r in rows}

    def insert_images(self, rows):
        return self.sb.table("product_images").insert(rows).execute().data

    def list_unmatched_images(self, wid):
        return self.sb.table("product_images").select("*").eq(
            "wholesaler_id", wid).eq("match_status", "unmatched").is_("deleted_at", "null").execute().data

    def update_image(self, iid, patch, wholesaler_id=None):
        q = self.sb.table("product_images").update(patch).eq("id", iid)
        if wholesaler_id is not None:           # 도매업체 스코프 — 타 업체 이미지 조작 차단
            q = q.eq("wholesaler_id", wholesaler_id)
        data = q.execute().data
        return data[0] if data else None


def _guard(user: CurrentUser):
    require_approved(user)
    _wholesaler(user)
    if not user.wholesaler_id:
        raise HTTPException(400, "no wholesaler")


def _run(fn):
    """UploadForbidden → 404, UploadError → 400 매핑."""
    try:
        return fn()
    except UploadForbidden as e:
        raise HTTPException(404, str(e))
    except UploadError as e:
        raise HTTPException(400, str(e))


@router.post("/excel")
async def upload_excel(file: UploadFile = File(...), user: CurrentUser = Depends(get_current_user)):
    """표준 엑셀 업로드(multipart) → 품번별 상품 일괄생성 (FR-2.2)."""
    _guard(user)
    data = await file.read()
    with NamedTemporaryFile(suffix=".xlsx", delete=False) as tmp:
        tmp.write(data)
        path = tmp.name
    try:
        out = ingest_excel(SupabaseUploadRepo(), user.wholesaler_id, path,
                           created_by=user.id, source_label=file.filename)
    finally:
        os.unlink(path)
    return {"job_id": out["job"]["id"], "created": out["products"], "errors": out["errors"]}


@router.post("/images")
def upload_images(req: AttachImagesRequest, user: CurrentUser = Depends(get_current_user)):
    """프론트가 Storage 에 올린 이미지 매니페스트 → 품번 자동매칭 (FR-2.3)."""
    _guard(user)
    return _run(lambda: attach_images(
        SupabaseUploadRepo(), req.job_id, [i.model_dump() for i in req.images],
        created_by=user.id, caller_wid=user.wholesaler_id))


@router.get("/jobs")
def list_jobs(user: CurrentUser = Depends(get_current_user), limit: int = 20):
    """도매 본인 최근 업로드 잡 목록(미매칭 관리 화면 기본 잡 선택용)."""
    _guard(user)
    return {"jobs": SupabaseUploadRepo().list_jobs(user.wholesaler_id, limit)}


@router.get("/{job_id}/unmatched")
def get_unmatched(job_id: str, user: CurrentUser = Depends(get_current_user)):
    """미매칭 이미지 목록(수동 매칭 후보)."""
    _guard(user)
    return _run(lambda: list_unmatched(SupabaseUploadRepo(), job_id, caller_wid=user.wholesaler_id))


@router.post("/{job_id}/match")
def post_match(job_id: str, req: MatchRequest, user: CurrentUser = Depends(get_current_user)):
    """수동 매칭 — 품번을 상품으로 해석해 이미지에 연결."""
    _guard(user)
    return _run(lambda: resolve_match(
        SupabaseUploadRepo(), job_id, req.image_id, req.source_p_number, caller_wid=user.wholesaler_id))
