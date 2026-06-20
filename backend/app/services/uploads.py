"""업로드 오케스트레이션 — 표준 엑셀 → 상품 일괄생성, 이미지 파일명 자동매칭.

이미지는 '프론트 직접 업로드' 모델: 프론트가 백엔드 발급 V4 signed PUT URL(POST /uploads/sign)로
GCS 에 직접 업로드한 뒤 {original_filename, storage_path} 매니페스트를 백엔드로 보내면, 백엔드가 품번 매칭 + 기록만 한다.
엑셀은 데이터 파일이라 multipart 로 받아 서버에서 파싱한다.

보안: 백엔드는 service key 로 접속(RLS 우회)하므로, 도매업체 격리는 **앱 레이어에서** 강제한다.
job/이미지에 대한 모든 접근은 호출자(caller_wid)의 소속 도매업체 소유인지 검증한다(IDOR 방지).

repo 프로토콜(라우터의 SupabaseUploadRepo / 테스트의 FakeUploadRepo 가 구현):
  next_platform_code() / insert_product(d) / insert_skus(rows)
  create_upload_job(d) / update_upload_job(id, patch) / get_upload_job(id) -> dict|None
  products_pnum_map(wholesaler_id) -> {source_p_number: product_id}
  insert_images(rows) / list_unmatched_images(wholesaler_id)
  update_image(id, patch, wholesaler_id=None) -> dict|None
"""
import hashlib
import io
import logging
import posixpath
import zipfile
from concurrent.futures import ThreadPoolExecutor

log = logging.getLogger("ezmerce.uploads")


def _safe_object_name(name: str) -> str:
    """Supabase Storage 객체 키는 ASCII 제한 — 한글/공백/일부 특수문자는 InvalidKey(400) 거부.

    그래서 저장 키는 원본명의 해시(ASCII) + 확장자로 만든다(결정적이라 재업로드 시 같은 키 → upsert).
    진짜 파일명(한글 등)은 호출부가 original_filename 으로 따로 보관(품번 매칭·표시는 그걸로).
    """
    base = posixpath.basename(str(name).replace("\\", "/"))
    ext = base.rsplit(".", 1)[-1].lower() if "." in base else "jpg"
    ext = "".join(c for c in ext if c.isalnum()) or "jpg"
    digest = hashlib.md5(name.encode("utf-8")).hexdigest()[:16]
    return f"{digest}.{ext}"

from app.services.excel_parse import parse_template_rows
from app.services.image_match import match_filename_to_product
from app.services.image_process import process_image_bytes, thumb_path

# 커밋 중 이미지 재가공 동시 수 — Cloud Run(512Mi/1Gi)에서 PIL 디코드 피크 메모리 한도.
# 개별 업로드(썸네일 미생성) 대량을 8 동시로 디코드하면 512Mi OOM(503+재시작) → 보수적으로 낮춤.
# ZIP staging 의 _ZIP_WORKERS(4) 와 동일 기조. 배치(_IMG_BATCH)마다 executor 를 새로 만들어 메모리 회수.
_IMG_WORKERS = 4
_IMG_BATCH = 16

# ZIP 흡수 설정
_ZIP_IMG_EXTS = (".jpg", ".jpeg", ".png", ".webp", ".gif")
_ZIP_CONTENT_TYPE = {".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".png": "image/png",
                     ".webp": "image/webp", ".gif": "image/gif"}
_ZIP_MAX_IMAGES = 1000   # 초과 시 분할 업로드 안내
# ⚠️ 운영 Cloud Run 인스턴스가 512Mi 메모리(Makefile deploy) — 아래 값은 그 한도에 맞춘 보수적 기본값.
# 메모리를 올리면(예: 2Gi) 이 상수들도 키울 수 있다.
_ZIP_MAX_BYTES = 100 * 1024 * 1024   # ZIP 1개 최대 100MB(더 큰 사진 묶음은 나눠서)
_ZIP_WORKERS = 4                      # 동시 가공 수(PIL 디코드 메모리 상한 고려 — _IMG_WORKERS 보다 보수적)
_ZIP_BATCH = 16                       # 한 번에 메모리에 올리는 이미지 수(배치 처리로 피크 메모리 제한)


class UploadError(Exception):
    """잘못된 요청(검증 실패 등) → 400."""


class UploadForbidden(UploadError):
    """존재하지 않거나 호출자 소유가 아닌 리소스 → 404(존재 노출 방지)."""


def _friendly_db_error(e: Exception) -> str:
    """DB raw 예외 → 사용자 친화 한국어 사유(내부 제약명/JSON 미노출)."""
    s = str(e)
    if "23505" in s or "duplicate key" in s or "unique constraint" in s:
        return "이미 등록된 품번입니다 (중복 — 건너뜀)"
    if "23503" in s or "foreign key" in s:
        return "참조 데이터가 올바르지 않습니다"
    return "상품 등록 중 오류가 발생했습니다"


def _owned_job(repo, job_id: str, caller_wid: str | None) -> dict:
    job = repo.get_upload_job(job_id)
    if not job or caller_wid is None or job.get("wholesaler_id") != caller_wid:
        # 미존재/타 도매업체 모두 동일하게 404 — job_id 추측 공격에 정보 미노출
        raise UploadForbidden("업로드 작업을 찾을 수 없거나 권한이 없습니다")
    return job


def _group_rows(rows: list[dict]) -> list[dict]:
    """연속된 (품번, 상품명) 블록을 한 상품으로 그룹핑.

    ⚠️ 품번은 유일키가 아니다(한 파일 안에서도 같은 품번이 다른 상품일 수 있음 — 현장 확인).
    따라서 '품번으로 전역 그룹핑' 하지 않는다. POS 내보내기는 한 상품의 색상/사이즈 변형을
    연속된 행으로 나열하므로, 연속된 (품번,상품명)이면 한 상품의 SKU 들로 본다.
    같은 품번이 떨어져서 다시 나오면(또는 상품명이 바뀌면) 별개의 상품으로 분리된다.
    """
    groups: list[dict] = []
    prev_sig = None
    for r in rows:
        sig = (r["source_p_number"], r["item_name"])
        if prev_sig is None or sig != prev_sig:
            groups.append({"source_p_number": r["source_p_number"], "item_name": r["item_name"],
                           "fabric_composition": r.get("fabric_composition"), "skus": []})
            prev_sig = sig
        g = groups[-1]
        if not g.get("fabric_composition") and r.get("fabric_composition"):  # 혼용률은 상품 단위
            g["fabric_composition"] = r["fabric_composition"]
        g["skus"].append({
            "color": r["color"], "size": r["size"],
            "wholesale_price": r["wholesale_price"], "retail_price": r["retail_price"],
            "stock": r.get("stock", 0),
        })
    return groups


def preview_excel(parse_path: str) -> dict:
    """드라이런 — 파싱 + 그룹핑만 하고 DB 에 아무것도 쓰지 않는다(마법사 1단계 검증용).

    반환: 생성될 상품/ SKU 수 + 행 단위 오류 + 폐기 행 수. 실제 저장은 commit(ingest_excel)에서.
    """
    res = parse_template_rows(parse_path)
    groups = _group_rows(res.rows)
    return {"product_count": len(groups),
            "sku_count": sum(len(g["skus"]) for g in groups),
            "errors": res.errors, "dropped": res.dropped}


def ingest_excel(repo, wholesaler_id: str, parse_path: str,
                 created_by: str | None = None, source_label: str | None = None) -> dict:
    """표준 엑셀 파싱 → 연속 (품번,상품명) 블록별로 상품 1개 + SKU N개 생성, upload_job 기록.

    상품 단위 insert 는 개별 try — 충돌 시 해당 상품만 error 로 떨구고 계속.
    """
    res = parse_template_rows(parse_path)
    groups = _group_rows(res.rows)

    created, insert_errors = [], []
    for g in groups:
        product = None
        try:
            code = repo.next_platform_code()
            product = repo.insert_product({
                "wholesaler_id": wholesaler_id,
                "created_by": created_by,
                "platform_code": code,
                # 품번 없는 행(엑셀에 품번이 없는 상품)은 이지머스 자체 품번(platform_code)으로 등록 (QA 3차 1p)
                "source_p_number": g["source_p_number"] or code,
                "item_name": g["item_name"],
                "fabric_composition": g.get("fabric_composition"),
            })
            repo.insert_skus([{**s, "product_id": product["id"]} for s in g["skus"]])
            created.append(product)
        except Exception as e:   # 충돌 등 — 상품 단위로 격리, 친화 사유로 기록
            # 보상(A-3): product 는 생겼는데 SKU 삽입이 실패하면 SKU 없는 고아 상품이 남는다.
            # 그 경우 방금 만든 상품을 soft-delete 해 정리(insert_product 자체 실패면 product=None → 정리 불필요).
            if product is not None and hasattr(repo, "soft_delete_product"):
                try:
                    repo.soft_delete_product(product["id"])
                except Exception:  # noqa: BLE001 — 보상 실패해도 등록 흐름은 계속
                    log.warning("대량등록 SKU 실패 후 고아 상품 정리 실패 product_id=%s", product.get("id"))
            insert_errors.append({"source_p_number": g["source_p_number"], "reason": _friendly_db_error(e)})

    errors = res.errors + insert_errors
    job = repo.create_upload_job({
        "wholesaler_id": wholesaler_id,
        "created_by": created_by,
        "file_path": source_label,
        "status": "needs_matching" if created else "failed",   # 상품 생성됨 → 이미지 매칭 대기
        "total_rows": len(res.rows) + len(res.errors),
        "matched_rows": 0,
        "error_rows": len(errors),
        "error_detail": errors or None,
    })
    return {"job": job, "products": created, "errors": errors, "dropped": res.dropped}


def _thumbnail_from_bytes(repo, storage_path: str, raw: bytes) -> tuple[str | None, str]:
    """원본 바이트 → 가공 → thumbs/ 업로드. (thumbnail_path|None, status) 반환. 예외 미전파."""
    result = process_image_bytes(raw)
    if result.status != "ok" or result.data is None:
        return None, "error"
    dst = thumb_path(storage_path)
    try:
        repo.upload_object(dst, result.data)
    except Exception:
        return None, "error"
    return dst, "ok"


def _process_one_image(repo, row: dict) -> str:
    """(매니페스트 경로) 원본 다운로드 → 가공 → row['thumbnail_path'] 기록. 이미지 단위 격리.

    반환 상태: 'ok'(썸네일 생성) / 'none'(원본을 못 가져옴) / 'error'(다운로드는 됐으나 가공/업로드 실패).
    """
    src = row["storage_path"]
    try:
        raw = repo.download_object(src)
    except Exception:
        return "none"
    if not raw:
        return "none"
    dst, status = _thumbnail_from_bytes(repo, src, raw)
    if dst:
        row["thumbnail_path"] = dst
    return status


def attach_images(repo, job_id: str, images: list[dict],
                  created_by: str | None = None, caller_wid: str | None = None,
                  process: bool = True) -> dict:
    """프론트가 Storage 에 올린 이미지 매니페스트를 품번 자동매칭 + 서버측 썸네일 가공 후 기록.

    가공은 repo 가 storage 접근 메서드(download_object/upload_object)를 가질 때만 수행한다
    (단위 테스트의 FakeUploadRepo 처럼 없으면 자동 건너뜀 — 매칭/기록은 그대로).
    매칭 여부와 무관하게 전 이미지를 가공(미매칭 이미지도 썸네일 → 수동매칭 UI 프리뷰 깔끔).
    """
    job = _owned_job(repo, job_id, caller_wid)
    wholesaler_id = job["wholesaler_id"]
    pmap = repo.products_pnum_map(wholesaler_id)

    rows, matched, unmatched = [], [], []
    for img in images:
        fname = img["original_filename"]
        pid = match_filename_to_product(fname, pmap)
        rows.append({
            "wholesaler_id": wholesaler_id,
            "storage_path": img["storage_path"],
            "thumbnail_path": img.get("thumbnail_path"),   # staging 단계에서 이미 가공됐으면 그대로 사용
            "original_filename": fname,
            "product_id": pid,
            "match_status": "matched" if pid else "unmatched",
            "created_by": created_by,
        })
        (matched if pid else unmatched).append(fname)

    # 서버측 썸네일 가공 — 아직 썸네일이 없는 행만(원본 다운로드→리사이즈→thumbs 업로드). 이미지 단위 격리.
    processed = {"ok": 0, "none": 0, "error": 0}
    to_process = [r for r in rows if r.get("thumbnail_path") is None]
    can_process = (process and to_process
                   and hasattr(repo, "download_object") and hasattr(repo, "upload_object"))
    if can_process:
        # 배치 단위 가공 — 배치마다 executor 종료로 디코드 메모리 회수 + 동시 수 제한(_IMG_WORKERS).
        # 개별 업로드 대량(예: 250장)이 512Mi/1Gi 안에서 OOM 없이 끝나게 한다(staging 과 같은 배치 패턴).
        for i in range(0, len(to_process), _IMG_BATCH):
            batch = to_process[i:i + _IMG_BATCH]
            with ThreadPoolExecutor(max_workers=_IMG_WORKERS) as ex:
                for status in ex.map(lambda r: _process_one_image(repo, r), batch):
                    processed[status] += 1

    inserted = repo.insert_images(rows) if rows else []
    prev_matched = job.get("matched_rows") or 0
    repo.update_upload_job(job_id, {
        "matched_rows": prev_matched + len(matched),       # 분할 업로드 누적
        "status": "completed" if not unmatched else "needs_matching",
    })
    return {"job_id": job_id, "matched": matched, "unmatched": unmatched,
            "processed": processed, "images": inserted}


def list_unmatched(repo, job_id: str, caller_wid: str | None = None) -> list[dict]:
    """job 의 도매업체 범위에서 아직 미매칭인 이미지 목록(수동 매칭 후보)."""
    job = _owned_job(repo, job_id, caller_wid)
    return repo.list_unmatched_images(job["wholesaler_id"])


def resolve_match(repo, job_id: str, image_id: str, source_p_number: str,
                  caller_wid: str | None = None) -> dict:
    """수동 매칭 — 품번을 상품으로 해석해 이미지에 연결. 이미지도 같은 도매업체로 스코프."""
    job = _owned_job(repo, job_id, caller_wid)
    wholesaler_id = job["wholesaler_id"]
    pid = repo.products_pnum_map(wholesaler_id).get(source_p_number)
    if not pid:
        raise UploadError(f"품번 {source_p_number} 에 해당하는 상품이 없습니다")
    updated = repo.update_image(image_id, {"product_id": pid, "match_status": "matched"},
                                wholesaler_id=wholesaler_id)
    if not updated:
        raise UploadForbidden("이미지를 찾을 수 없거나 권한이 없습니다")
    return updated


# ── ZIP 일괄 이미지 업로드 ───────────────────────────────────────────────────
def _zip_member_name(info: "zipfile.ZipInfo") -> str:
    """ZIP 멤버 파일명 — Windows 제작 zip 의 한글 파일명(cp437로 저장됨)을 복구."""
    name = info.filename
    if info.flag_bits & 0x800:        # UTF-8 플래그가 켜져 있으면 그대로
        return name
    try:                              # cp437 로 디코드된 바이트를 cp949(한글)로 재해석
        return name.encode("cp437").decode("cp949")
    except (UnicodeEncodeError, UnicodeDecodeError):
        return name


def _zip_image_members(zf: "zipfile.ZipFile", max_images: int = _ZIP_MAX_IMAGES) -> list[tuple]:
    """ZIP 안의 이미지 멤버만 [(ZipInfo, 파일명, content_type)] 로. 숨김/맥OS 잔재/비이미지 제외.

    바이트는 아직 읽지 않는다(배치 처리에서 필요할 때만 read → 피크 메모리 제한).
    개수가 max_images 초과면 UploadError(분할 업로드 안내).
    """
    out: list[tuple] = []
    for info in zf.infolist():
        if info.is_dir():
            continue
        name = _zip_member_name(info)
        if "__MACOSX" in name:                 # 맥OS 압축 잔재
            continue
        base = posixpath.basename(name.replace("\\", "/"))
        if not base or base.startswith("._") or base == ".DS_Store":
            continue
        ext = ("." + base.rsplit(".", 1)[-1].lower()) if "." in base else ""
        if ext not in _ZIP_IMG_EXTS:
            continue
        out.append((info, base, _ZIP_CONTENT_TYPE.get(ext, "application/octet-stream")))
        if len(out) > max_images:
            raise UploadError(
                f"ZIP 안의 이미지가 너무 많습니다(최대 {max_images}장). 나눠서 올려주세요.")
    return out


def stage_zip_to_manifest(repo, wholesaler_id: str, zip_bytes: bytes) -> dict:
    """ZIP 1개 → 안의 이미지를 Storage(staging) 에 업로드 + 썸네일 가공 후 **매니페스트만** 반환.

    이 단계에선 DB(상품/이미지/잡)에 아무것도 쓰지 않는다(품번 매칭도 안 함). 매칭/기록은
    4단계 commit 의 attach_images 에서 일괄 수행한다(상품이 그때 생기므로).
    메모리 보호(Cloud Run 512Mi): zip 은 한 번만 메모리에 두고 _ZIP_BATCH 단위로 읽어
    _ZIP_WORKERS 로 가공. 반환: {manifest:[{original_filename, storage_path, thumbnail_path}], processed}.
    """
    if len(zip_bytes) > _ZIP_MAX_BYTES:
        raise UploadError(
            f"ZIP 용량이 너무 큽니다(최대 {_ZIP_MAX_BYTES // (1024 * 1024)}MB). 사진을 나눠서 올려주세요.")
    try:
        zf = zipfile.ZipFile(io.BytesIO(zip_bytes))
    except zipfile.BadZipFile:
        raise UploadError("올바른 ZIP 파일이 아닙니다.")

    def _handle(payload: tuple[str, bytes, str]) -> dict:
        base, raw, ctype = payload
        # 저장 키는 ASCII 안전값(해시) — 한글 파일명을 키로 쓰면 Supabase InvalidKey.
        storage_path = f"{wholesaler_id}/staging/{_safe_object_name(base)}"
        try:
            repo.upload_object(storage_path, raw, content_type=ctype)
        except Exception:
            log.exception("staging 원본 업로드 실패 path=%s", storage_path)  # 실제 Storage 오류 노출
            return {"status": "none", "item": None}
        dst, status = _thumbnail_from_bytes(repo, storage_path, raw)
        return {"status": status,
                "item": {"original_filename": base, "storage_path": storage_path,
                         "thumbnail_path": dst}}

    results: list[dict] = []
    with zf:
        members = _zip_image_members(zf)
        if not members:
            raise UploadError("ZIP 안에 이미지 파일(JPG/PNG 등)이 없습니다.")
        for i in range(0, len(members), _ZIP_BATCH):       # 배치 단위로만 메모리에 적재
            batch = members[i:i + _ZIP_BATCH]
            payloads = [(base, zf.read(info), ctype) for (info, base, ctype) in batch]
            with ThreadPoolExecutor(max_workers=_ZIP_WORKERS) as ex:
                results.extend(ex.map(_handle, payloads))

    manifest = [r["item"] for r in results if r["item"] is not None]
    processed = {"ok": 0, "none": 0, "error": 0}
    for r in results:
        processed[r["status"]] += 1

    if results and not manifest:   # 전 이미지 업로드 실패 = 저장소 미준비(버킷 없음 등)
        raise UploadError("이미지 저장소가 아직 준비되지 않았습니다. 잠시 후 다시 시도하거나 관리자에게 문의해주세요.")

    return {"manifest": manifest, "processed": processed}
