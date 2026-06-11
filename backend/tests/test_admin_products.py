from app.routers.admin import shape_admin_product


def _row():
    return {
        "id": "p1", "platform_code": "EZM-1", "source_p_number": "P1", "item_name": "셔츠",
        "category": None, "status": "active", "is_sold_out": False,
        "representative_image_url": None, "created_at": "2026-06-01",
        "wholesaler_id": "w1", "wholesalers": {"name": "라라스도매A"},
        "product_skus": [
            {"color": "블랙", "size": "S", "wholesale_price": 6000, "retail_price": 12000, "stock": 3, "deleted_at": None},
            {"color": "블랙", "size": "M", "wholesale_price": 6000, "retail_price": 12000, "stock": 0, "deleted_at": "2026-01-01"},
        ],
    }


def test_shape_admin_product_has_wholesaler_source():
    out = shape_admin_product(_row())
    assert out["wholesaler_name"] == "라라스도매A"   # 행마다 도매 출처(FR-5)
    assert out["wholesaler_id"] == "w1"


def test_shape_admin_product_admin_sees_both_prices():
    out = shape_admin_product(_row())
    assert out["skus"][0]["wholesale_price"] == 6000   # admin → 도매가+판매가 둘 다
    assert out["skus"][0]["retail_price"] == 12000
    assert out["skus"][0]["stock"] == 3


def test_shape_admin_product_skips_deleted_skus():
    assert len(shape_admin_product(_row())["skus"]) == 1  # soft-delete 제외


def test_shape_admin_product_missing_join_name_is_none():
    row = _row()
    row["wholesalers"] = None
    assert shape_admin_product(row)["wholesaler_name"] is None  # join 없으면 None(크래시 없이)
