from app.services.products import register_product
from app.schemas.product import ProductCreate, SkuCreate

class FakeRepo:
    def __init__(self): self.products=[]; self.skus=[]; self.seq=0
    def next_platform_code(self):
        self.seq += 1; return f"EZM-{self.seq:06d}"
    def insert_product(self, d): d={**d,"id":"p1"}; self.products.append(d); return d
    def insert_skus(self, rows): self.skus.extend(rows); return rows

def test_register_assigns_platform_code_and_skus():
    repo = FakeRepo()
    payload = ProductCreate(
        source_p_number="1001", item_name="린넨 셔츠",
        skus=[SkuCreate(color="화이트", size="F", wholesale_price=12000, retail_price=29000)],
    )
    out = register_product(repo, wholesaler_id="org-1", payload=payload)
    assert out["platform_code"] == "EZM-000001"
    assert repo.skus[0]["wholesale_price"] == 12000
    assert repo.products[0]["wholesaler_id"] == "org-1"
