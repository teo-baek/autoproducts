class PriceForbidden(Exception):
    pass


def _default_visibility(role: str, seller_type: str | None) -> str:
    """price_visibility 미설정 시 seller_type 기준 기본값 (가입/승인 시드와 동일 규칙)."""
    if role == "retail_seller" and seller_type == "independent":
        return "wholesale"
    if role == "retail_seller" and seller_type == "agency_affiliated":
        return "none"
    if role == "agency":
        return "retail"
    return "none"


def visible_price(
    role: str,
    seller_type: str | None,
    sku: dict,
    viewer_org: str | None = None,
    price_visibility: str | None = None,
) -> dict:
    """역할 + 관리자 설정(price_visibility) 기준 노출 가격 결정 — tech-design §3.10.

    - wholesaler(자기 조직) / admin: 관리뷰 → 도매가 + 판매가 모두
    - 그 외(소매셀러 / 에이전시): 관리자가 설정한 price_visibility 우선,
      미설정(None)이면 seller_type 기준 기본값으로 폴백.
    """
    if role == "wholesaler" and viewer_org == sku.get("product_org"):
        return {"wholesale_price": sku["wholesale_price"], "retail_price": sku["retail_price"]}
    if role == "admin":
        return {"wholesale_price": sku["wholesale_price"], "retail_price": sku["retail_price"]}

    vis = price_visibility or _default_visibility(role, seller_type)
    if vis == "wholesale":
        return {"price": sku["wholesale_price"]}
    if vis == "retail":
        return {"price": sku["retail_price"]}
    return {"price": None}  # 'none' / 미설정+기본 none → 가격 미노출
