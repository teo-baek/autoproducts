import logging

from app.services.pricing import _default_visibility

log = logging.getLogger("ezmerce.accounts")

# 자가가입 허용 역할 — admin 만 관리자가 직접 온보딩(권한 상승 방지). 도매/소매는 자가가입 후 pending→관리자 승인.
# [1차 비활성] 에이전시(agency) 자가가입 미허용 — 에이전시 운영 시작 시 set 에 "agency" 추가로 복구.
_SELF_REGISTER_ROLES = {"retail_seller", "wholesaler"}  # , "agency"  ← 1차 비활성


class RegisterError(Exception):
    pass


def _is_duplicate_email(e: Exception) -> bool:
    """gotrue/supabase 의 '이미 가입된 이메일' 에러 식별(메시지/코드 문자열 기반)."""
    blob = " ".join(
        str(getattr(e, attr, "") or "") for attr in ("message", "code", "error_code")
    ).lower() + " " + str(e).lower()
    return any(k in blob for k in ("already been registered", "already registered", "user already", "email_exists", "email address has already"))


def approve_account(repo, target_id: str, admin_id: str, admin_manager_id: str | None = None) -> dict:
    """승인 처리. 도매(wholesaler) 계정이 아직 도매업체에 연결돼 있지 않으면
    도매업체 행을 자동 생성해 wholesaler_id 로 연결한다(상품 API 가 wholesaler_id 필요).

    멀티테넌트(FR-7): admin_manager_id(승인 admin 의 도매관리자=테넌트)가 주어지면
    - 셀러 승인 → profiles.manager_id 를 그 테넌트로 연계(FR-3).
    - 도매 승인 → manager_wholesalers 에 소속 연결(FR-2, 멱등).
    """
    prof = repo.get_profile(target_id)
    role = prof.get("role") if prof else None
    wholesaler_id = None
    if role == "wholesaler" and not (prof.get("wholesaler_id") if prof else None):
        name = (prof.get("company_name") or prof.get("full_name") or "도매업체") if prof else "도매업체"
        wholesaler_id = repo.create_wholesaler(name)["id"]
    try:
        # 승인 = 이 도매관리자(테넌트)가 신청자를 'claim'. 셀러·도매 모두 manager_id 로 소속 확정
        # → status=approved + manager_id 라서 다른 관리자의 공유 대기 풀에서 사라진다(claim).
        result = repo.set_status(target_id, "approved", admin_id,
                                 wholesaler_id=wholesaler_id, manager_id=admin_manager_id)
        # 도매 승인: 소속 도매를 admin 의 테넌트(도매관리자)에 연결(FR-2/FR-7). 멱등.
        if role == "wholesaler" and admin_manager_id:
            wid = wholesaler_id or (prof.get("wholesaler_id") if prof else None)
            if wid:
                repo.link_wholesaler_to_manager(wid, admin_manager_id, by=admin_id)
        return result
    except Exception:
        # 보상(A-4): 도매업체는 방금 만들었는데 승인 연결(set_status / manager 소속 연결)이 실패하면
        # 고아 wholesaler 가 남는다. 방금 만든 도매업체만 soft-delete(앱레벨 best-effort, hard DELETE 금지).
        if wholesaler_id is not None:
            try:
                repo.soft_delete_wholesaler(wholesaler_id)
            except Exception:  # noqa: BLE001 — 보상 실패해도 원래 예외를 우선 전파
                log.warning("승인 실패 후 고아 도매업체 정리 실패 wholesaler_id=%s", wholesaler_id)
        raise

def reject_account(repo, target_id: str, admin_id: str, admin_manager_id: str | None = None) -> dict:
    """관리자별 거절(패스) — 전역 상태를 바꾸지 않는다(신청자는 다른 도매관리자에게 계속 pending).

    승인 admin 의 테넌트 기준으로 manager_rejections 에 기록(멱등). 거절한 관리자 목록에서만
    사라지고, 다른 관리자에겐 계속 보인다. '재승인' 개념 없음(거절은 그 관리자에겐 종결 로그).
    """
    return repo.add_manager_rejection(target_id, admin_manager_id, by=admin_id)


def register_account(repo, req) -> dict:
    """공개 회원가입: 검증 → Supabase Auth 계정 생성 → profiles(status=pending) 시드.

    - 자가가입은 retail_seller/wholesaler (admin·agency 거부 — admin 권한 상승 차단, agency 는 1차 비활성).
    - seller_type 은 role='retail_seller' 일 때만 채움(DB CHECK 제약 정합).
    - price_visibility 는 seller_type 기준 기본값으로 시드(관리자가 추후 override 가능).
    - 검증을 auth 계정 생성보다 먼저 수행 → 거부 시 orphan auth user 미생성.
    """
    role = req.role
    if role not in _SELF_REGISTER_ROLES:
        # [1차 비활성] 에이전시는 아직 회원가입 미허용 — 친화 메시지로 안내(복구 시 set 에 agency 추가하면 이 분기 미도달).
        if role == "agency":
            raise RegisterError("에이전시 회원가입은 현재 준비 중입니다. 관리자에게 문의해 주세요.")
        raise RegisterError("자가가입은 retail_seller/wholesaler 만 허용됩니다")
    if role == "retail_seller" and req.seller_type not in ("independent", "agency_affiliated"):
        raise RegisterError("retail_seller 는 seller_type(independent|agency_affiliated) 가 필요합니다")
    seller_type = req.seller_type if role == "retail_seller" else None  # CHECK: 그 외 역할은 NULL

    try:
        auth_user = repo.create_auth_user(req.email, req.password)
    except RegisterError:
        raise
    except Exception as e:  # gotrue 에러 → 친화 메시지(특히 중복 이메일)로 변환
        if _is_duplicate_email(e):
            raise RegisterError("이미 가입된 이메일입니다.") from e
        raise
    try:
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
    except Exception:
        # 보상(A-1): Auth 계정은 생성됐는데 profiles 시드가 실패하면 auth.users 고아가 남아
        # 같은 이메일 재가입이 영구 불가해진다. 방금 만든 Auth 계정을 삭제해 되돌린다.
        # auth.users 는 GoTrue 관리(우리 soft-delete 대상 아님) → admin.delete_user 로 하드 정리.
        try:
            repo.delete_auth_user(auth_user["id"])
        except Exception:  # noqa: BLE001 — 보상 실패해도 원래 예외를 우선 전파
            log.warning("프로필 시드 실패 후 고아 Auth 계정 정리 실패 user_id=%s", auth_user["id"])
        raise
