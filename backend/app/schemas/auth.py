from pydantic import BaseModel


class CurrentUser(BaseModel):
    id: str
    role: str
    status: str
    seller_type: str | None = None
    wholesaler_id: str | None = None  # 도매 직원 소속 도매업체
    agency_id: str | None = None  # 에이전시 직원 소속 / 에이전시 소속 셀러를 관리하는 에이전시
    price_visibility: str | None = None  # 관리자 설정형 가격 노출('wholesale'|'retail'|'none')
