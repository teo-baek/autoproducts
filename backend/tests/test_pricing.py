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
