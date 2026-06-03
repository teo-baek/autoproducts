"""테이블별 엔티티 모델 (migrations/*.sql 와 1:1). ORM 아님 — Supabase dict ↔ 모델 변환용.

Supabase(supabase-py)가 돌려주는 dict 를 `Product(**row)` 로 검증·역직렬화하고,
응답 스키마로도 재사용한다. 알 수 없는 컬럼은 무시(extra='ignore').
DTO(요청/응답 전용 형태)는 app/schemas/ 에 따로 둔다.
"""
from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.entities.enums import (
    AccountStatus,
    ImageMatch,
    PriceVisibility,
    ProductStatus,
    SellerType,
    UploadStatus,
    UserRole,
)


class _Entity(BaseModel):
    model_config = ConfigDict(extra="ignore")


class Wholesaler(_Entity):
    id: str
    name: str
    biz_number: str | None = None
    created_at: datetime | None = None
    deleted_at: datetime | None = None


class Agency(_Entity):
    id: str
    name: str
    biz_number: str | None = None
    created_at: datetime | None = None
    deleted_at: datetime | None = None


class Profile(_Entity):
    id: str
    role: UserRole
    status: AccountStatus = AccountStatus.pending
    full_name: str | None = None
    phone: str | None = None
    wholesaler_id: str | None = None      # 도매 직원 소속 도매업체
    agency_id: str | None = None          # 에이전시 직원 소속 / 에이전시 소속 셀러를 관리하는 에이전시
    seller_type: SellerType | None = None
    price_visibility: PriceVisibility | None = None
    approved_at: datetime | None = None
    approved_by: str | None = None
    created_at: datetime | None = None
    deleted_at: datetime | None = None


class Product(_Entity):
    id: str
    wholesaler_id: str
    platform_code: str
    source_p_number: str
    item_name: str
    fabric_composition: str | None = None
    origin: str | None = None
    lead_time_days: str | None = None
    description: str | None = None
    representative_image_url: str | None = None
    status: ProductStatus = ProductStatus.active
    is_sold_out: bool = False
    created_at: datetime | None = None
    updated_at: datetime | None = None
    deleted_at: datetime | None = None


class ProductSku(_Entity):
    id: str
    product_id: str
    color: str
    size: str
    wholesale_price: int
    retail_price: int | None = None
    stock: int = 0
    created_at: datetime | None = None
    deleted_at: datetime | None = None


class ProductImage(_Entity):
    id: str
    product_id: str | None = None         # NULL = 미매칭
    wholesaler_id: str
    storage_path: str
    original_filename: str | None = None
    match_status: ImageMatch = ImageMatch.unmatched
    is_representative: bool = False
    sort_order: int = 0
    created_at: datetime | None = None
    deleted_at: datetime | None = None


class UploadJob(_Entity):
    id: str
    wholesaler_id: str
    created_by: str | None = None
    file_path: str | None = None
    status: UploadStatus = UploadStatus.uploaded
    total_rows: int = 0
    matched_rows: int = 0
    error_rows: int = 0
    error_detail: dict | list | None = None
    created_at: datetime | None = None
    completed_at: datetime | None = None
    deleted_at: datetime | None = None
