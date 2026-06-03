from pydantic import BaseModel, Field


class CurrentUser(BaseModel):
    id: str
    role: str
    status: str
    seller_type: str | None = None
    wholesaler_id: str | None = None  # 도매 직원 소속 도매업체
    agency_id: str | None = None  # 에이전시 직원 소속 / 에이전시 소속 셀러를 관리하는 에이전시
    price_visibility: str | None = None  # 관리자 설정형 가격 노출('wholesale'|'retail'|'none')


class RegisterRequest(BaseModel):
    """공개 회원가입 요청. 자가가입 허용 role = retail_seller | agency 만(admin/wholesaler는 관리자 온보딩)."""
    email: str
    password: str = Field(min_length=8)
    role: str                          # 'retail_seller' | 'agency'
    seller_type: str | None = None     # role='retail_seller' 일 때 'independent'|'agency_affiliated'
    full_name: str | None = None
    phone: str | None = None
    agency_id: str | None = None       # 에이전시 소속 셀러/에이전시 계정의 관리 에이전시(forward-compat)


class RegisterResponse(BaseModel):
    id: str
    role: str
    status: str
    seller_type: str | None = None
    price_visibility: str | None = None
