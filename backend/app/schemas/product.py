from pydantic import BaseModel, Field


class SkuCreate(BaseModel):
    color: str
    size: str
    wholesale_price: int = Field(ge=0)
    retail_price: int | None = Field(default=None, ge=0)
    stock: int = Field(default=0, ge=0)


class ProductCreate(BaseModel):
    source_p_number: str
    item_name: str
    category: str | None = None          # 분류(의류|잡화 등) — 마이그레이션 _07 컬럼
    fabric_composition: str | None = None
    origin: str | None = None
    lead_time_days: str | None = None
    description: str | None = None
    skus: list[SkuCreate]


class SkuReplaceRequest(BaseModel):
    """상품의 SKU 전체 교체(수정 모달) — 기존 SKU soft-delete 후 새로 삽입."""
    skus: list[SkuCreate]
