from fastapi import APIRouter, HTTPException
from app.core.supabase import get_supabase
from app.schemas.auth import RegisterRequest, RegisterResponse
from app.services.accounts import register_account, RegisterError

router = APIRouter(prefix="/auth", tags=["auth"])


class SupabaseAuthRepo:
    def __init__(self):
        self.sb = get_supabase()

    def create_auth_user(self, email: str, password: str) -> dict:
        # service key → admin API. 폐쇄형이라 관리자 승인이 게이트 → email_confirm=True (메일 인증 생략)
        # RISK(verify-live): gotrue 응답 형태(res.user.id) 라이브 스모크로 확인 필요
        res = self.sb.auth.admin.create_user(
            {"email": email, "password": password, "email_confirm": True}
        )
        return {"id": res.user.id}

    def insert_profile(self, d: dict) -> dict:
        return self.sb.table("profiles").insert(d).execute().data[0]


@router.post("/register", response_model=RegisterResponse)
def register(req: RegisterRequest):
    """공개 회원가입 (FR-1.3). 가입 후 status=pending → 관리자 승인 대기."""
    try:
        return register_account(SupabaseAuthRepo(), req)
    except RegisterError as e:
        raise HTTPException(400, str(e))
