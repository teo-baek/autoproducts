from app.routers.catalog import shape_catalog_item
from app.schemas.auth import CurrentUser

ROW = {"platform_code":"EZM-1","item_name":"셔츠","source_p_number":"P-001",
       "fabric_composition":"면100","representative_image_url":"https://img/ezm-1.jpg",
       "created_at":"2026-06-01T00:00:00Z",
       "skus":[{"color":"화이트","size":"F","stock":7,"wholesale_price":12000,"retail_price":29000,"product_org":"org-9"}]}

def test_agency_affiliated_seller_item_has_no_price():
    u = CurrentUser(id="u", role="retail_seller", status="approved", seller_type="agency_affiliated")
    item = shape_catalog_item(ROW, u)
    assert item["skus"][0]["price"] is None

def test_independent_seller_sees_wholesale():
    u = CurrentUser(id="u", role="retail_seller", status="approved", seller_type="independent")
    item = shape_catalog_item(ROW, u)
    assert item["skus"][0]["price"] == 12000

def test_shape_exposes_stock_and_image_for_showroom():
    # 셀러 쇼룸현황: 변형별 가용재고(stock)·대표이미지·커서(created_at) 가 응답에 실려야 한다.
    u = CurrentUser(id="u", role="retail_seller", status="approved", seller_type="independent")
    item = shape_catalog_item(ROW, u)
    assert item["skus"][0]["stock"] == 7
    assert item["representative_image_url"] == "https://img/ezm-1.jpg"
    assert item["created_at"] == "2026-06-01T00:00:00Z"
    assert item["source_p_number"] == "P-001"
    assert item["fabric_composition"] == "면100"  # 쇼룸 카드 혼용률 노출

def test_stock_exposed_even_when_price_hidden():
    # 가격 미노출(agency_affiliated)이어도 가용재고는 보여야 함(가격≠재고).
    u = CurrentUser(id="u", role="retail_seller", status="approved", seller_type="agency_affiliated")
    item = shape_catalog_item(ROW, u)
    assert item["skus"][0]["price"] is None
    assert item["skus"][0]["stock"] == 7
