import json
import logging
import os
from datetime import datetime, timezone
from tempfile import NamedTemporaryFile

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile

from app.core.auth import get_current_user
from app.core.rbac import require_approved, require_role
from app.core.supabase import get_supabase
from app.schemas.auth import CurrentUser
from app.schemas.upload import MatchRequest
from app.services.excel_parse import ExcelFormatError
from app.services.platform_code import next_platform_code
from app.services.uploads import (
    _ZIP_MAX_BYTES, UploadError, UploadForbidden, attach_images, ingest_excel,
    list_unmatched, preview_excel, resolve_match, stage_zip_to_manifest,
)

_EXCEL_EXTS = (".xlsx", ".xls", ".csv")

router = APIRouter(prefix="/uploads", tags=["uploads"])
log = logging.getLogger("ezmerce.uploads")
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

    def soft_delete_product(self, product_id):
        # 보상용(A-3): 대량등록 중 SKU 삽입 실패 시 방금 만든 상품을 soft-delete(고아 방지, hard DELETE 금지).
        now = datetime.now(timezone.utc).isoformat()
        self.sb.table("products").update({"deleted_at": now}).eq("id", product_id).execute()

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
        try:
            return self.sb.table("product_images").insert(rows).execute().data
        except Exception as e:
            # _08(thumbnail_path) 미적용 환경 호환 — 컬럼 없이 재시도(썸네일 경로만 보류, 원본은 정상)
            if "thumbnail_path" in str(e):
                stripped = [{k: v for k, v in r.items() if k != "thumbnail_path"} for r in rows]
                return self.sb.table("product_images").insert(stripped).execute().data
            raise

    # ── Storage(이미지 가공용) ── service key 라 RLS 우회; 경로는 도매 스코프로 프론트가 생성 ──
    def download_object(self, path, bucket="product-images"):
        return self.sb.storage.from_(bucket).download(path)   # bytes

    def upload_object(self, path, data, bucket="product-images", content_type="image/jpeg"):
        # 재가공/재업로드 멱등 위해 upsert. supabase-py file_options 값은 문자열.
        self.sb.storage.from_(bucket).upload(
            path, data, {"content-type": content_type, "upsert": "true"})
        return path

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


async def _save_excel_temp(file: UploadFile) -> str:
    """업로드 엑셀을 임시파일로 저장하고 경로 반환(파서가 확장자로 형식 분기). 미지원이면 400."""
    fn = (file.filename or "").lower()
    ext = next((e for e in _EXCEL_EXTS if fn.endswith(e)), None)
    if ext is None:
        raise HTTPException(400, "엑셀(.xlsx/.xls) 또는 CSV(.csv) 파일만 지원합니다.")
    data = await file.read()
    with NamedTemporaryFile(suffix=ext, delete=False) as tmp:
        tmp.write(data)
        return tmp.name


@router.post("/excel/validate")
async def validate_excel(file: UploadFile = File(...), user: CurrentUser = Depends(get_current_user)):
    """1단계 — 엑셀 검증만(드라이런). DB 에 쓰지 않고 미리보기(상품/SKU 수)·오류·폐기수만 반환."""
    _guard(user)
    path = await _save_excel_temp(file)
    try:
        return preview_excel(path)
    except ExcelFormatError as e:
        raise HTTPException(400, str(e))
    except Exception:
        log.exception("엑셀 검증 실패 wid=%s", user.wholesaler_id)
        raise HTTPException(400, "엑셀을 읽는 중 오류가 발생했습니다. 파일 형식·내용을 확인해주세요.")
    finally:
        os.unlink(path)


@router.post("/zip/stage")
async def stage_zip(file: UploadFile = File(...), user: CurrentUser = Depends(get_current_user)):
    """2단계 — ZIP 의 이미지를 Storage(staging)에 올리고 매니페스트만 반환(아직 등록 X)."""
    _guard(user)
    if not (file.filename or "").lower().endswith(".zip"):
        raise HTTPException(400, "ZIP(.zip) 파일만 지원합니다.")
    if file.size and file.size > _ZIP_MAX_BYTES:   # 큰 파일은 메모리에 읽기 전에 차단(운영 512Mi 보호)
        raise HTTPException(
            400, f"ZIP 용량이 너무 큽니다(최대 {_ZIP_MAX_BYTES // (1024 * 1024)}MB). 사진을 나눠서 올려주세요.")
    data = await file.read()
    try:
        return stage_zip_to_manifest(SupabaseUploadRepo(), user.wholesaler_id, data)
    except UploadError as e:
        raise HTTPException(400, str(e))
    except Exception:
        log.exception("ZIP staging 실패 wid=%s", user.wholesaler_id)
        raise HTTPException(400, "ZIP 처리 중 오류가 발생했습니다. 파일을 확인해주세요.")


@router.post("/commit")
async def commit_upload(file: UploadFile = File(...), images: str = Form("[]"),
                        user: CurrentUser = Depends(get_current_user)):
    """4단계 — 검증한 엑셀 + staging 매니페스트(images=JSON)를 받아 상품 생성 + 이미지 매칭을 한 번에."""
    _guard(user)
    try:
        manifest = json.loads(images) if images else []
        assert isinstance(manifest, list)
    except (ValueError, TypeError, AssertionError):
        raise HTTPException(400, "이미지 매니페스트 형식이 올바르지 않습니다.")

    path = await _save_excel_temp(file)
    repo = SupabaseUploadRepo()
    try:
        out = ingest_excel(repo, user.wholesaler_id, path, created_by=user.id, source_label=file.filename)
    except ExcelFormatError as e:
        raise HTTPException(400, str(e))
    except Exception:
        log.exception("커밋(엑셀) 실패 wid=%s", user.wholesaler_id)
        raise HTTPException(400, "상품 등록 중 오류가 발생했습니다. 파일 형식·내용을 확인해주세요.")
    finally:
        os.unlink(path)

    job_id = out["job"]["id"]
    matched, unmatched = [], []
    if manifest and out["products"]:        # 상품이 생겨야 이미지 매칭 가능
        try:
            res = attach_images(repo, job_id, manifest, created_by=user.id, caller_wid=user.wholesaler_id)
            matched, unmatched = res.get("matched", []), res.get("unmatched", [])
        except Exception:                   # 상품은 이미 생성됨 — 이미지 매칭만 실패(미매칭 관리에서 보강)
            log.exception("커밋(이미지 매칭) 실패 job=%s", job_id)
    return {"job_id": job_id, "created": out["products"], "errors": out["errors"],
            "dropped": out.get("dropped", 0), "matched": matched, "unmatched": unmatched}


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
