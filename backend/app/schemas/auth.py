from pydantic import BaseModel


class CurrentUser(BaseModel):
    id: str
    role: str
    status: str
    seller_type: str | None = None
    organization_id: str | None = None
    price_visibility: str | None = None  # 관리자 설정형 가격 노출('wholesale'|'retail'|'none')
