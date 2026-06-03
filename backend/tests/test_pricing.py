import pytest
from app.services.pricing import visible_price, PriceForbidden

SKU = {"wholesale_price": 12000, "retail_price": 29000, "product_org": "org-1"}

def test_independent_seller_sees_wholesale():
    assert visible_price("retail_seller", "independent", SKU)["price"] == 12000

def test_agency_affiliated_seller_sees_none():
    assert visible_price("retail_seller", "agency_affiliated", SKU)["price"] is None

def test_agency_sees_retail():
    assert visible_price("agency", None, SKU)["price"] == 29000

def test_wholesaler_owner_sees_both():
    out = visible_price("wholesaler", None, SKU, viewer_org="org-1")
    assert out["wholesale_price"] == 12000 and out["retail_price"] == 29000

def test_unknown_role_gets_none():
    assert visible_price("guest", None, SKU)["price"] is None


# --- 관리자 설정형 가격 노출(price_visibility) override ---

def test_admin_override_grants_wholesale_to_agency_affiliated():
    # 기본은 None 이지만 관리자가 'wholesale' 로 풀어준 경우
    out = visible_price("retail_seller", "agency_affiliated", SKU, price_visibility="wholesale")
    assert out["price"] == 12000

def test_admin_override_blocks_independent_seller():
    # 기본은 도매가지만 관리자가 'none' 으로 막은 경우(미계약 등)
    out = visible_price("retail_seller", "independent", SKU, price_visibility="none")
    assert out["price"] is None

def test_admin_override_sets_agency_to_wholesale():
    out = visible_price("agency", None, SKU, price_visibility="wholesale")
    assert out["price"] == 12000

def test_unset_visibility_falls_back_to_default():
    # price_visibility=None → seller_type 기본값 폴백 (기존 동작 보존)
    assert visible_price("retail_seller", "independent", SKU, price_visibility=None)["price"] == 12000
