class PriceForbidden(Exception):
    pass


def visible_price(role: str, seller_type: str | None, sku: dict, viewer_org: str | None = None) -> dict:
    """역할×seller_type 기준 노출 가격 결정 — tech-design §3.10."""
    if role == "retail_seller" and seller_type == "independent":
        return {"price": sku["wholesale_price"]}
    if role == "retail_seller" and seller_type == "agency_affiliated":
        return {"price": None}  # 가격 미노출
    if role == "agency":
        return {"price": sku["retail_price"]}
    if role == "wholesaler" and viewer_org == sku.get("product_org"):
        return {"wholesale_price": sku["wholesale_price"], "retail_price": sku["retail_price"]}
    if role == "admin":
        return {"wholesale_price": sku["wholesale_price"], "retail_price": sku["retail_price"]}
    return {"price": None}
