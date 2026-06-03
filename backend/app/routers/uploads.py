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
    UploadError, attach_images, ingest_excel, list_unmatched, resolve_match,
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
        return self.sb.table("upload_jobs").select("*").eq("id", jid).is_("deleted_at", "null").single().execute().data

    def products_pnum_map(self, wid):
        rows = self.sb.table("products").select("id,source_p_number").eq(
            "wholesaler_id", wid).is_("deleted_at", "null").execute().data
        return {r["source_p_number"]: r["id"] for r in rows}

    def insert_images(self, rows):
        return self.sb.table("product_images").insert(rows).execute().data

    def list_unmatched_images(self, wid):
        return self.sb.table("product_images").select("*").eq(
            "wholesaler_id", wid).eq("match_status", "unmatched").is_("deleted_at", "null").execute().data

    def update_image(self, iid, patch):
        return self.sb.table("product_images").update(patch).eq("id", iid).execute().data[0]


def _guard(user: CurrentUser):
    require_approved(user)
    _wholesaler(user)
    if not user.wholesaler_id:
        raise HTTPException(400, "no wholesaler")


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
    return attach_images(SupabaseUploadRepo(), req.job_id,
                         [i.model_dump() for i in req.images], created_by=user.id)


@router.get("/{job_id}/unmatched")
def get_unmatched(job_id: str, user: CurrentUser = Depends(get_current_user)):
    """미매칭 이미지 목록(수동 매칭 후보)."""
    _guard(user)
    return list_unmatched(SupabaseUploadRepo(), job_id)


@router.post("/{job_id}/match")
def post_match(job_id: str, req: MatchRequest, user: CurrentUser = Depends(get_current_user)):
    """수동 매칭 — 품번을 상품으로 해석해 이미지에 연결."""
    _guard(user)
    try:
        return resolve_match(SupabaseUploadRepo(), job_id, req.image_id, req.source_p_number)
    except UploadError as e:
        raise HTTPException(400, str(e))
