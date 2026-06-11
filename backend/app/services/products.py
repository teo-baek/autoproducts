import logging

from app.schemas.product import ProductCreate

log = logging.getLogger("ezmerce.products")


def register_product(repo, wholesaler_id: str, payload: ProductCreate, created_by: str | None = None) -> dict:
    code = repo.next_platform_code()
    row = {
        "wholesaler_id": wholesaler_id,
        "created_by": created_by,  # 누가 등록했는지
        "platform_code": code,
        "source_p_number": payload.source_p_number,
        "item_name": payload.item_name,
        "fabric_composition": payload.fabric_composition,
        "origin": payload.origin,
        "lead_time_days": payload.lead_time_days,
        "description": payload.description,
    }
    if payload.category is not None:        # 마이그레이션 _07 미적용 환경 보호 — 값 있을 때만 포함
        row["category"] = payload.category
    product = repo.insert_product(row)
    try:
        repo.insert_skus([{**s.model_dump(), "product_id": product["id"]} for s in payload.skus])
    except Exception:
        # 보상(A-2): product 는 생성됐는데 SKU 삽입이 실패하면 SKU 없는 빈 상품(고아)이 남는다.
        # 방금 만든 상품을 soft-delete 해 정리(앱레벨 best-effort 원자성, hard DELETE 금지).
        try:
            repo.soft_delete_product(product["id"])
        except Exception:  # noqa: BLE001 — 보상 실패해도 원래 예외를 우선 전파
            log.warning("SKU 삽입 실패 후 고아 상품 정리 실패 product_id=%s", product.get("id"))
        raise
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
