from app.schemas.product import ProductCreate


def register_product(repo, wholesaler_id: str, payload: ProductCreate, created_by: str | None = None) -> dict:
    code = repo.next_platform_code()
    product = repo.insert_product({
        "wholesaler_id": wholesaler_id,
        "created_by": created_by,  # 누가 등록했는지
        "platform_code": code,
        "source_p_number": payload.source_p_number,
        "item_name": payload.item_name,
        "fabric_composition": payload.fabric_composition,
        "origin": payload.origin,
        "lead_time_days": payload.lead_time_days,
        "description": payload.description,
    })
    repo.insert_skus([{**s.model_dump(), "product_id": product["id"]} for s in payload.skus])
    return product


def update_product(repo, product_id: str, patch: dict) -> dict:
    return repo.update_product(product_id, patch)


def archive_product(repo, product_id: str) -> dict:
    return repo.update_product(product_id, {"status": "archived"})


def soft_delete_product(repo, product_id: str, deleted_at: str, updated_by: str | None = None) -> dict:
    # hard DELETE 금지 — deleted_at 만 찍는다. 자식(skus/images)은 DB soft-cascade 트리거가 처리.
    patch = {"deleted_at": deleted_at}
    if updated_by:
        patch["updated_by"] = updated_by
    return repo.update_product(product_id, patch)
