from pydantic import BaseModel


class CurrentUser(BaseModel):
    id: str
    role: str
    status: str
    seller_type: str | None = None
    organization_id: str | None = None
