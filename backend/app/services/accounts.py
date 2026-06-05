from app.services.pricing import _default_visibility

# 자가가입 허용 역할 — admin 만 관리자가 직접 온보딩(권한 상승 방지). 도매/에이전시/소매는 자가가입 후 pending→관리자 승인.
_SELF_REGISTER_ROLES = {"retail_seller", "wholesaler", "agency"}


class RegisterError(Exception):
    pass


def approve_account(repo, target_id: str, admin_id: str) -> dict:
    return repo.set_status(target_id, "approved", admin_id)

def reject_account(repo, target_id: str, admin_id: str) -> dict:
    return repo.set_status(target_id, "rejected", admin_id)


def register_account(repo, req) -> dict:
    """공개 회원가입: 검증 → Supabase Auth 계정 생성 → profiles(status=pending) 시드.

    - 자가가입은 retail_seller/wholesaler/agency (admin 만 거부 — 권한 상승 차단).
    - seller_type 은 role='retail_seller' 일 때만 채움(DB CHECK 제약 정합).
    - price_visibility 는 seller_type 기준 기본값으로 시드(관리자가 추후 override 가능).
    - 검증을 auth 계정 생성보다 먼저 수행 → 거부 시 orphan auth user 미생성.
    """
    role = req.role
    if role not in _SELF_REGISTER_ROLES:
        raise RegisterError("자가가입은 retail_seller/wholesaler/agency 만 허용됩니다")
    if role == "retail_seller" and req.seller_type not in ("independent", "agency_affiliated"):
        raise RegisterError("retail_seller 는 seller_type(independent|agency_affiliated) 가 필요합니다")
    seller_type = req.seller_type if role == "retail_seller" else None  # CHECK: 그 외 역할은 NULL

    auth_user = repo.create_auth_user(req.email, req.password)
    return repo.insert_profile({
        "id": auth_user["id"],
        "role": role,
        "status": "pending",
        "seller_type": seller_type,
        "price_visibility": _default_visibility(role, seller_type),
        "full_name": req.full_name,
        "company_name": req.company_name,
        "phone": req.phone,
        "agency_id": req.agency_id,
    })
