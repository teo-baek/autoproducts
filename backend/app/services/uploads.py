"""업로드 오케스트레이션 — 표준 엑셀 → 상품 일괄생성, 이미지 파일명 자동매칭.

이미지는 '프론트 직접 Storage' 모델: 프론트가 product-images 버킷에 직접 업로드한 뒤
{original_filename, storage_path} 매니페스트를 백엔드로 보내면, 백엔드가 품번 매칭 + 기록만 한다.
엑셀은 데이터 파일이라 multipart 로 받아 서버에서 파싱한다.

repo 프로토콜(라우터의 SupabaseUploadRepo / 테스트의 FakeUploadRepo 가 구현):
  next_platform_code() / insert_product(d) / insert_skus(rows)
  create_upload_job(d) / update_upload_job(id, patch) / get_upload_job(id)
  products_pnum_map(wholesaler_id) -> {source_p_number: product_id}
  insert_images(rows) / list_unmatched_images(wholesaler_id) / update_image(id, patch)
"""
from app.services.excel_parse import parse_template_rows
from app.services.image_match import match_filename_to_product


class UploadError(Exception):
    pass


def ingest_excel(repo, wholesaler_id: str, parse_path: str,
                 created_by: str | None = None, source_label: str | None = None) -> dict:
    """표준 엑셀 파싱 → 품번별로 상품 1개 + SKU N개 생성, upload_job 기록."""
    res = parse_template_rows(parse_path)

    grouped: dict[str, dict] = {}
    order: list[str] = []
    for r in res.rows:
        key = r["source_p_number"]
        if key not in grouped:
            grouped[key] = {"item_name": r["item_name"], "skus": []}
            order.append(key)
        grouped[key]["skus"].append({
            "color": r["color"], "size": r["size"],
            "wholesale_price": r["wholesale_price"], "retail_price": r["retail_price"],
        })

    created = []
    for key in order:
        g = grouped[key]
        product = repo.insert_product({
            "wholesaler_id": wholesaler_id,
            "created_by": created_by,
            "platform_code": repo.next_platform_code(),
            "source_p_number": key,
            "item_name": g["item_name"],
        })
        repo.insert_skus([{**s, "product_id": product["id"]} for s in g["skus"]])
        created.append(product)

    job = repo.create_upload_job({
        "wholesaler_id": wholesaler_id,
        "created_by": created_by,
        "file_path": source_label,
        "status": "needs_matching" if created else "failed",   # 상품 생성됨 → 이미지 매칭 대기
        "total_rows": len(res.rows) + len(res.errors),
        "matched_rows": 0,
        "error_rows": len(res.errors),
        "error_detail": res.errors or None,
    })
    return {"job": job, "products": created, "errors": res.errors}


def attach_images(repo, job_id: str, images: list[dict], created_by: str | None = None) -> dict:
    """프론트가 Storage 에 올린 이미지 매니페스트를 품번 자동매칭 후 product_images 기록."""
    job = repo.get_upload_job(job_id)
    wholesaler_id = job["wholesaler_id"]
    pmap = repo.products_pnum_map(wholesaler_id)

    rows, matched, unmatched = [], [], []
    for img in images:
        fname = img["original_filename"]
        pid = match_filename_to_product(fname, pmap)
        rows.append({
            "wholesaler_id": wholesaler_id,
            "storage_path": img["storage_path"],
            "original_filename": fname,
            "product_id": pid,
            "match_status": "matched" if pid else "unmatched",
            "created_by": created_by,
        })
        (matched if pid else unmatched).append(fname)

    inserted = repo.insert_images(rows) if rows else []
    repo.update_upload_job(job_id, {
        "matched_rows": len(matched),
        "status": "completed" if not unmatched else "needs_matching",
    })
    return {"job_id": job_id, "matched": matched, "unmatched": unmatched, "images": inserted}


def list_unmatched(repo, job_id: str) -> list[dict]:
    """job 의 도매업체 범위에서 아직 미매칭인 이미지 목록(수동 매칭 후보)."""
    job = repo.get_upload_job(job_id)
    return repo.list_unmatched_images(job["wholesaler_id"])


def resolve_match(repo, job_id: str, image_id: str, source_p_number: str) -> dict:
    """수동 매칭 — 품번을 상품으로 해석해 이미지에 연결."""
    job = repo.get_upload_job(job_id)
    pmap = repo.products_pnum_map(job["wholesaler_id"])
    pid = pmap.get(source_p_number)
    if not pid:
        raise UploadError(f"품번 {source_p_number} 에 해당하는 상품이 없습니다")
    return repo.update_image(image_id, {"product_id": pid, "match_status": "matched"})
