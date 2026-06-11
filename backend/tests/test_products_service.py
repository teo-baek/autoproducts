import pytest

from app.services.products import register_product
from app.schemas.product import ProductCreate, SkuCreate

class FakeRepo:
    def __init__(self): self.products=[]; self.skus=[]; self.seq=0; self.deleted=[]
    def next_platform_code(self):
        self.seq += 1; return f"EZM-{self.seq:06d}"
    def insert_product(self, d): d={**d,"id":"p1"}; self.products.append(d); return d
    def insert_skus(self, rows): self.skus.extend(rows); return rows
    def soft_delete_product(self, product_id): self.deleted.append(product_id)

def test_register_assigns_platform_code_and_skus():
    repo = FakeRepo()
    payload = ProductCreate(
        source_p_number="1001", item_name="린넨 셔츠",
        skus=[SkuCreate(color="화이트", size="F", wholesale_price=12000, retail_price=29000)],
    )
    out = register_product(repo, wholesaler_id="org-1", payload=payload, created_by="staff-1")
    assert out["platform_code"] == "EZM-000001"
    assert repo.skus[0]["wholesale_price"] == 12000
    assert repo.products[0]["wholesaler_id"] == "org-1"
    assert repo.products[0]["created_by"] == "staff-1"  # 누가 등록했는지


class SkuInsertFailsRepo(FakeRepo):
    def insert_skus(self, rows):
        raise Exception("skus insert failed")


def test_register_compensates_orphan_product_on_sku_failure():
    # A-2 보상: product 생성 후 SKU 삽입 실패 → 방금 만든 상품 soft-delete(빈 상품 고아 방지)
    repo = SkuInsertFailsRepo()
    payload = ProductCreate(
        source_p_number="1001", item_name="린넨 셔츠",
        skus=[SkuCreate(color="화이트", size="F", wholesale_price=12000, retail_price=29000)],
    )
    with pytest.raises(Exception, match="skus insert failed"):
        register_product(repo, wholesaler_id="org-1", payload=payload, created_by="staff-1")
    assert repo.products[0]["id"] == "p1"     # 1단계: product 생성됨
    assert repo.deleted == ["p1"]             # 2단계 실패 → 보상 삭제
