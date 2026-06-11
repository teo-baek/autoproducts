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


def visible_price_columns(
    role: str,
    seller_type: str | None,
    sku: dict,
    viewer_org: str | None = None,
    price_visibility: str | None = None,
) -> dict:
    """스타일 엑셀(도매가/판매가 2칸 고정 레이아웃)용 — 역할별로 채울 칸 정규화.

    가격 결정은 visible_price() 단일 진실을 재사용(셰이핑 우회 금지, CLAUDE.md §가격 노출).
    결과를 항상 {wholesale_price, retail_price} 2칸으로 펼치되, 미노출 칸은 None.
    - 관리뷰(admin·도매 본인) → 둘 다 채움
    - 단일가 노출(셀러/에이전시) → 노출 모드에 맞는 칸 하나만, 나머지 None
    - 미노출 → 둘 다 None
    """
    p = visible_price(role, seller_type, sku, viewer_org=viewer_org, price_visibility=price_visibility)
    if "wholesale_price" in p:                       # 관리뷰: 도매가+판매가 둘 다
        return {"wholesale_price": p.get("wholesale_price"), "retail_price": p.get("retail_price")}
    price = p.get("price")
    if price is None:                                # 미노출
        return {"wholesale_price": None, "retail_price": None}
    vis = price_visibility or _default_visibility(role, seller_type)
    if vis == "wholesale":
        return {"wholesale_price": price, "retail_price": None}
    return {"wholesale_price": None, "retail_price": price}  # retail
