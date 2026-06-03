from app.schemas.entities import (
    Agency,
    Product,
    ProductImage,
    ProductSku,
    Profile,
    UploadJob,
    Wholesaler,
)
from app.schemas.enums import PriceVisibility, ProductStatus, UserRole


def test_profile_parses_enums_and_ignores_extra():
    # supabase row 에 모르는 컬럼이 섞여와도 무시되어야 한다
    p = Profile(
        id="u1", role="retail_seller", status="approved",
        seller_type="independent", price_visibility="wholesale",
        unknown_db_col="x",
    )
    assert p.role is UserRole.retail_seller
    assert p.price_visibility is PriceVisibility.wholesale
    assert p.wholesaler_id is None


def test_product_defaults():
    pr = Product(id="p1", wholesaler_id="w1", platform_code="EZM-000001",
                 source_p_number="1001", item_name="린넨 셔츠")
    assert pr.status is ProductStatus.active
    assert pr.is_sold_out is False
    assert pr.deleted_at is None


def test_sku_optional_retail_and_stock_default():
    s = ProductSku(id="s1", product_id="p1", color="화이트", size="F", wholesale_price=12000)
    assert s.retail_price is None and s.stock == 0


def test_all_entities_instantiable():
    assert Wholesaler(id="w", name="도매A").name == "도매A"
    assert Agency(id="a", name="에이전시A").name == "에이전시A"
    assert ProductImage(id="i", wholesaler_id="w", storage_path="1001.jpg").match_status.value == "unmatched"
    assert UploadJob(id="j", wholesaler_id="w").status.value == "uploaded"
