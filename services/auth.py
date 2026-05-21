"""
AutoProducts 인증 서비스 모듈
Supabase Auth를 활용한 회원가입/로그인 및 store_profiles 테이블 연동을 담당합니다.
"""
import streamlit as st
from supabase import create_client, Client


class AuthService:
    """Supabase Auth 기반 인증 및 매장 프로필 관리 서비스"""

    def __init__(self):
        self.supabase: Client = None
        self._initialize_client()

    def _initialize_client(self):
        """Supabase 클라이언트를 초기화합니다."""
        try:
            url: str = st.secrets["SUPABASE_URL"]
            key: str = st.secrets["SUPABASE_KEY"]
            self.supabase = create_client(url, key)
        except Exception:
            self.supabase = None

    # ─────────────────────────────────────────
    # 회원가입 (Sign Up)
    # ─────────────────────────────────────────
    def sign_up(self, email: str, password: str, role: str,
                store_id: str = "", store_name: str = "",
                drive_folder_url: str = "", plan_type: str = "standard"):
        """
        신규 회원가입을 처리합니다.
        1) Supabase Auth에 계정 생성
        2) store_profiles 테이블에 매장 프로필 저장
        """
        if not self.supabase:
            return False, "DB 연결 정보가 없습니다."

        try:
            # Supabase Auth 계정 생성
            auth_response = self.supabase.auth.sign_up({
                "email": email,
                "password": password,
            })

            if auth_response.user is None:
                return False, "회원가입에 실패했습니다. 이미 가입된 이메일일 수 있습니다."

            user_id = auth_response.user.id

            # store_profiles 테이블에 프로필 저장
            profile_data = {
                "id": user_id,
                "email": email,
                "role": role,  # 'wholesaler' 또는 'retailer'
                "store_id": store_id if role == "wholesaler" else "",
                "store_name": store_name if role == "wholesaler" else "",
                "drive_folder_url": drive_folder_url if role == "wholesaler" else "",
                "plan_type": plan_type if role == "wholesaler" else "free",
                "is_paid": False,
            }

            self.supabase.table("store_profiles").insert(profile_data).execute()

            return True, "회원가입이 완료되었습니다! 로그인해 주세요."

        except Exception as e:
            error_msg = str(e)
            if "already registered" in error_msg.lower() or "already been registered" in error_msg.lower():
                return False, "이미 가입된 이메일입니다. 로그인 탭을 이용해 주세요."
            return False, f"회원가입 중 오류: {error_msg}"

    # ─────────────────────────────────────────
    # 로그인 (Sign In)
    # ─────────────────────────────────────────
    def sign_in(self, email: str, password: str):
        """
        로그인을 처리하고 세션 상태에 유저 정보를 저장합니다.
        """
        if not self.supabase:
            return False, "DB 연결 정보가 없습니다."

        try:
            auth_response = self.supabase.auth.sign_in_with_password({
                "email": email,
                "password": password,
            })

            if auth_response.user is None:
                return False, "로그인에 실패했습니다. 이메일과 비밀번호를 확인해 주세요."

            user_id = auth_response.user.id

            # store_profiles에서 매장 정보 조회
            profile_response = (
                self.supabase.table("store_profiles")
                .select("*")
                .eq("id", user_id)
                .execute()
            )

            if not profile_response.data:
                return False, "매장 프로필 정보를 찾을 수 없습니다."

            profile = profile_response.data[0]

            # 세션 상태에 유저 정보 저장
            st.session_state["logged_in"] = True
            st.session_state["user_id"] = user_id
            st.session_state["email"] = email
            st.session_state["role"] = profile.get("role", "retailer")
            st.session_state["store_id"] = profile.get("store_id", "")
            st.session_state["store_name"] = profile.get("store_name", "")
            st.session_state["drive_folder_url"] = profile.get("drive_folder_url", "")
            st.session_state["plan_type"] = profile.get("plan_type", "standard")
            st.session_state["is_paid"] = profile.get("is_paid", False)

            return True, f"환영합니다, {profile.get('store_name', email)}님!"

        except Exception as e:
            error_msg = str(e)
            if "invalid" in error_msg.lower():
                return False, "이메일 또는 비밀번호가 올바르지 않습니다."
            return False, f"로그인 중 오류: {error_msg}"

    # ─────────────────────────────────────────
    # 로그아웃 (Sign Out)
    # ─────────────────────────────────────────
    def sign_out(self):
        """세션 상태를 초기화하여 로그아웃합니다."""
        keys_to_clear = [
            "logged_in", "user_id", "email", "role",
            "store_id", "store_name", "drive_folder_url",
            "plan_type", "is_paid"
        ]
        for key in keys_to_clear:
            if key in st.session_state:
                del st.session_state[key]

    # ─────────────────────────────────────────
    # 헬퍼 함수들
    # ─────────────────────────────────────────
    def is_logged_in(self) -> bool:
        return st.session_state.get("logged_in", False)

    def is_paid(self) -> bool:
        return st.session_state.get("is_paid", False)

    def get_role(self) -> str:
        return st.session_state.get("role", "")

    def get_store_id(self) -> str:
        return st.session_state.get("store_id", "")

    def get_drive_folder_url(self) -> str:
        return st.session_state.get("drive_folder_url", "")
