import os

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile

from app.core.auth import get_current_user
from app.core.supabase import get_supabase
from app.schemas.auth import CurrentUser, RegisterRequest, RegisterResponse
from app.services.accounts import RegisterError, register_account

router = APIRouter(prefix="/auth", tags=["auth"])

# 서류 업로드 정책 — 사업자등록증/신분증(민감 PII). 비공개 버킷, 백엔드 경유(service key)만.
_DOC_BUCKET = "business-docs"
_ALLOWED_DOC_TYPES = {"image/jpeg", "image/png", "application/pdf"}
_MAX_DOC_BYTES = 5 * 1024 * 1024  # 5MB (디자인 스펙)
_DOC_FIELDS = {"business_cert": "business_cert_path", "id_doc": "id_doc_path"}


class SupabaseAuthRepo:
    def __init__(self):
        self.sb = get_supabase()

    def create_auth_user(self, email: str, password: str) -> dict:
        # service key → admin API. 폐쇄형이라 관리자 승인이 게이트 → email_confirm=True (메일 인증 생략)
        res = self.sb.auth.admin.create_user(
            {"email": email, "password": password, "email_confirm": True}
        )
        return {"id": res.user.id}

    def insert_profile(self, d: dict) -> dict:
        return self.sb.table("profiles").insert(d).execute().data[0]

    def upload_document(self, user_id: str, kind: str, filename: str, content: bytes, content_type: str) -> str:
        # 비공개 버킷에 service key 로 저장. 경로는 본인 uid 폴더로 스코프.
        ext = os.path.splitext(filename or "")[1].lower()
        path = f"{user_id}/{kind}{ext}"
        self.sb.storage.from_(_DOC_BUCKET).upload(
            path,
            content,
            {"content-type": content_type or "application/octet-stream", "upsert": "true"},
        )
        return path

    def set_document_paths(self, user_id: str, paths: dict) -> dict:
        return (
            self.sb.table("profiles")
            .update(paths)
            .eq("id", user_id)
            .is_("deleted_at", "null")
            .execute()
            .data[0]
        )


@router.get("/me", response_model=CurrentUser)
def me(user: CurrentUser = Depends(get_current_user)):
    """현재 로그인 사용자(역할/상태/소속/회사명). 프론트 역할 게이트·헤더 표시용."""
    return user


@router.post("/register", response_model=RegisterResponse)
def register(req: RegisterRequest):
    """공개 회원가입 (FR-1.3). 가입 후 status=pending → 관리자 승인 대기.

    비밀번호는 Supabase Auth(GoTrue)가 bcrypt 해싱·저장(auth.users). 본 서버는 보관하지 않음.
    도매/에이전시 사업자 서류는 가입 직후 로그인하여 `POST /auth/register/documents`(인증) 로 별도 업로드.
    """
    try:
        return register_account(SupabaseAuthRepo(), req)
    except RegisterError as e:
        raise HTTPException(400, str(e))


@router.post("/register/documents")
async def upload_documents(
    business_cert: UploadFile | None = File(default=None),
    id_doc: UploadFile | None = File(default=None),
    user: CurrentUser = Depends(get_current_user),
):
    """사업자등록증/신분증 업로드 (인증 필요 — 본인 계정에만).

    보안: 익명 직접 Storage 쓰기 금지 → 가입 직후 로그인한 본인이 호출, 백엔드가 service key 로
    **비공개 버킷**에 저장(경로는 본인 uid 폴더). ⚠️ 신분증은 민감 PII(주민번호) — 마스킹 권고.
    """
    repo = SupabaseAuthRepo()
    paths: dict = {}
    for kind, col in _DOC_FIELDS.items():
        up = business_cert if kind == "business_cert" else id_doc
        if up is None:
            continue
        if up.content_type not in _ALLOWED_DOC_TYPES:
            raise HTTPException(400, f"{kind}: JPG/PNG/PDF 만 허용됩니다")
        content = await up.read()
        if len(content) > _MAX_DOC_BYTES:
            raise HTTPException(400, f"{kind}: 5MB 를 초과했습니다")
        paths[col] = repo.upload_document(user.id, kind, up.filename or kind, content, up.content_type)
    if not paths:
        raise HTTPException(400, "업로드할 파일이 없습니다 (business_cert / id_doc)")
    repo.set_document_paths(user.id, paths)
    return {"ok": True, "paths": paths}
