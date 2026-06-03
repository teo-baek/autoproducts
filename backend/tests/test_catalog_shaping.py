from app.routers.catalog import shape_catalog_item
from app.schemas.auth import CurrentUser

ROW = {"platform_code":"EZM-1","item_name":"셔츠",
       "skus":[{"color":"화이트","size":"F","wholesale_price":12000,"retail_price":29000,"product_org":"org-9"}]}

def test_agency_affiliated_seller_item_has_no_price():
    u = CurrentUser(id="u", role="retail_seller", status="approved", seller_type="agency_affiliated")
    item = shape_catalog_item(ROW, u)
    assert item["skus"][0]["price"] is None

def test_independent_seller_sees_wholesale():
    u = CurrentUser(id="u", role="retail_seller", status="approved", seller_type="independent")
    item = shape_catalog_item(ROW, u)
    assert item["skus"][0]["price"] == 12000
