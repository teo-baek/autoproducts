"""업로드 오케스트레이션 — 표준 엑셀 → 상품 일괄생성, 이미지 파일명 자동매칭.

이미지는 '프론트 직접 Storage' 모델: 프론트가 product-images 버킷에 직접 업로드한 뒤
{original_filename, storage_path} 매니페스트를 백엔드로 보내면, 백엔드가 품번 매칭 + 기록만 한다.
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
from concurrent.futures import ThreadPoolExecutor

from app.services.excel_parse import parse_template_rows
from app.services.image_match import match_filename_to_product
from app.services.image_process import process_image_bytes, thumb_path

_IMG_WORKERS = 8


class UploadError(Exception):
    """잘못된 요청(검증 실패 등) → 400."""


class UploadForbidden(UploadError):
    """존재하지 않거나 호출자 소유가 아닌 리소스 → 404(존재 노출 방지)."""


def _owned_job(repo, job_id: str, caller_wid: str | None) -> dict:
    job = repo.get_upload_job(job_id)
    if not job or caller_wid is None or job.get("wholesaler_id") != caller_wid:
        # 미존재/타 도매업체 모두 동일하게 404 — job_id 추측 공격에 정보 미노출
        raise UploadForbidden("업로드 작업을 찾을 수 없거나 권한이 없습니다")
    return job


def ingest_excel(repo, wholesaler_id: str, parse_path: str,
                 created_by: str | None = None, source_label: str | None = None) -> dict:
    """표준 엑셀 파싱 → 품번별로 상품 1개 + SKU N개 생성, upload_job 기록.

    품번별 insert 는 개별 try — UNIQUE 충돌(재업로드 등) 시 해당 품번만 error 로 떨구고 계속.
    """
    res = parse_template_rows(parse_path)

    grouped: dict[str, dict] = {}
    order: list[str] = []
    for r in res.rows:
        key = r["source_p_number"]
        if key not in grouped:
            # 혼용률은 상품 단위 — 그룹 첫 행 중 값이 있는 것을 채택.
            grouped[key] = {"item_name": r["item_name"],
                            "fabric_composition": r.get("fabric_composition"), "skus": []}
            order.append(key)
        elif not grouped[key].get("fabric_composition") and r.get("fabric_composition"):
            grouped[key]["fabric_composition"] = r["fabric_composition"]
        grouped[key]["skus"].append({
            "color": r["color"], "size": r["size"],
            "wholesale_price": r["wholesale_price"], "retail_price": r["retail_price"],
            "stock": r.get("stock", 0),
        })

    created, insert_errors = [], []
    for key in order:
        g = grouped[key]
        try:
            product = repo.insert_product({
                "wholesaler_id": wholesaler_id,
                "created_by": created_by,
                "platform_code": repo.next_platform_code(),
                "source_p_number": key,
                "item_name": g["item_name"],
                "fabric_composition": g.get("fabric_composition"),
            })
            repo.insert_skus([{**s, "product_id": product["id"]} for s in g["skus"]])
            created.append(product)
        except Exception as e:   # UNIQUE 충돌 등 — 품번 단위로 격리
            insert_errors.append({"source_p_number": key, "reason": str(e)[:200]})

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
    return {"job": job, "products": created, "errors": errors}


def _process_one_image(repo, row: dict) -> str:
    """원본 다운로드 → 가공 → thumbs/ 업로드 → row['thumbnail_path'] 기록. 이미지 단위 격리.

    반환 상태: 'ok'(썸네일 생성) / 'none'(원본을 못 가져옴) / 'error'(다운로드는 됐으나 가공/업로드 실패).
    실패해도 예외를 전파하지 않는다(배치 전체 보호) — thumbnail_path 는 None 으로 남고 원본 폴백.
    """
    src = row["storage_path"]
    try:
        raw = repo.download_object(src)
    except Exception:
        return "none"
    if not raw:
        return "none"
    result = process_image_bytes(raw)
    if result.status != "ok" or result.data is None:
        return "error"
    dst = thumb_path(src)
    try:
        repo.upload_object(dst, result.data)
    except Exception:
        return "error"
    row["thumbnail_path"] = dst
    return "ok"


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
            "thumbnail_path": None,
            "original_filename": fname,
            "product_id": pid,
            "match_status": "matched" if pid else "unmatched",
            "created_by": created_by,
        })
        (matched if pid else unmatched).append(fname)

    # 서버측 썸네일 가공(원본 다운로드→리사이즈→thumbs 업로드) — 이미지 단위 병렬 + 격리.
    processed = {"ok": 0, "none": 0, "error": 0}
    can_process = (process and rows
                   and hasattr(repo, "download_object") and hasattr(repo, "upload_object"))
    if can_process:
        with ThreadPoolExecutor(max_workers=_IMG_WORKERS) as ex:
            for status in ex.map(lambda r: _process_one_image(repo, r), rows):
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
