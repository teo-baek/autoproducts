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
    fabric_composition: str | None = None
    origin: str | None = None
    lead_time_days: str | None = None
    description: str | None = None
    skus: list[SkuCreate]
