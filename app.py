"""
AutoProducts — 앱 엔트리포인트 (동적 권한 라우터)
로그인 여부, 결제 상태, 사용자 역할(도매상/소매상)에 따라
사이드바 메뉴에 노출되는 페이지를 동적으로 제어합니다.
"""
import streamlit as st

# ─────────────────────────────────────────
# ★ 개발자 모드 (Bypass) 설정
# ─────────────────────────────────────────
DEV_MODE = False  # True 시 로그인/승인 우회 및 Mock 세션 가동

st.set_page_config(
    page_title="AutoProducts (DEV)" if DEV_MODE else "AutoProducts",
    page_icon="🏢",
    layout="wide",
)

from services.theme import apply_common_theme
apply_common_theme()

# ─────────────────────────────────────────
# 페이지 모듈 임포트
# ─────────────────────────────────────────
from views import login as login_page
from views import billing as billing_page
from views import cue_sheet as cue_sheet_page

# 새로 분할된 백오피스 모듈들
from views import product_registration
from views import manage_products
from views import manage_orders
from views import manage_partners
from views import analytics
from views import retailer_orders
from views import ai_chat

from services.auth import AuthService

# ─────────────────────────────────────────
# 개발자 모드 세션 초기화 (프리패스)
# ─────────────────────────────────────────
if DEV_MODE and "logged_in" not in st.session_state:
    st.session_state["logged_in"] = True
    st.session_state["is_paid"] = True
    st.session_state["role"] = "wholesaler"  # 기본 테스트 역할: 도매상
    st.session_state["store_name"] = "동대문김사장 (Mock)"
    st.session_state["email"] = "mock_wholesaler@example.com"
    st.session_state["store_id"] = "mock-store-id-123"
    st.session_state["drive_folder_url"] = "https://drive.google.com/drive/folders/mock-folder-id"
    st.session_state["has_ai_agent"] = True  # AI 에이전트 결제 기본 적용

# ─────────────────────────────────────────
# 전역 세션 상태 초기화 (탭 전환 시 데이터 유실 방지)
# ─────────────────────────────────────────
if "my_cue_sheet" not in st.session_state:
    st.session_state["my_cue_sheet"] = []

logged_in = st.session_state.get("logged_in", False)
is_paid = st.session_state.get("is_paid", False)
user_role = st.session_state.get("role", "")

# ─────────────────────────────────────────
# 동적 라우팅 (Role-based Navigation)
# ─────────────────────────────────────────

if not logged_in:
    # ▸ 비로그인 상태: 오직 로그인/회원가입 화면만 렌더링
    login_page.show()

elif user_role == "wholesaler" and not is_paid:
    # ▸ 도매상 가입 완료 but 미결제: 입금 안내 화면만 렌더링
    billing_page.show()

else:
    # ▸ 인증 + 결제 완료 유저: 역할에 따른 탭 구성
    auth = AuthService()

    # 사이드바에 유저 정보 표시
    with st.sidebar:
        st.markdown("---")
        store_name = st.session_state.get("store_name", "")
        email = st.session_state.get("email", "")
        role_label = "🏢 도매상" if user_role == "wholesaler" else "🛒 소매상"

        st.markdown(f"**{role_label}**")
        st.markdown(f"**{store_name or email}**")
        st.caption(f"{email}")

        if DEV_MODE:
            st.markdown("---")
            st.markdown("🛠️ **DEV MODE CONTROLLER**")
            # 가상 역할 스위칭 라디오 버튼
            dev_role = st.radio(
                "테스트 역할 스위치",
                ["🏢 도매상", "🛒 소매상"],
                index=0 if user_role == "wholesaler" else 1,
                key="dev_role_switcher_radio"
            )
            mapped_role = "wholesaler" if "도매상" in dev_role else "retailer"
            if mapped_role != user_role:
                st.session_state["role"] = mapped_role
                if mapped_role == "wholesaler":
                    st.session_state["store_name"] = "동대문김사장 (Mock)"
                    st.session_state["email"] = "mock_wholesaler@example.com"
                    st.session_state["is_paid"] = True
                else:
                    st.session_state["store_name"] = "소매상나라 (Mock)"
                    st.session_state["email"] = "mock_retailer@example.com"
                    st.session_state["is_paid"] = False
                st.rerun()

        st.markdown("---")
        if st.button("🚪 로그아웃", width="stretch"):
            auth.sign_out()
            st.rerun()
        st.markdown("---")

    if user_role == "wholesaler":
        # ★ 도매상: 사이드바 라우터 메뉴 최적화 (B안: 헤딩 + 버튼 리스트)
        if "current_page" not in st.session_state:
            st.session_state["current_page"] = "상품 등록 센터"

        def change_page(page):
            st.session_state["current_page"] = page

        st.sidebar.markdown("### ■ 상품 파트")
        if st.sidebar.button("📤 상품 등록 센터", width="stretch", type="primary" if st.session_state["current_page"] == "상품 등록 센터" else "secondary"):
            change_page("상품 등록 센터")
            st.rerun()
        if st.sidebar.button("📦 등록 상품 관리", width="stretch", type="primary" if st.session_state["current_page"] == "등록 상품 관리" else "secondary"):
            change_page("등록 상품 관리")
            st.rerun()

        st.sidebar.markdown("### ■ 매장 운영 파트")
        if st.sidebar.button("📝 예약 및 주문 관리", width="stretch", type="primary" if st.session_state["current_page"] == "예약 및 주문 관리" else "secondary"):
            change_page("예약 및 주문 관리")
            st.rerun()
        if st.sidebar.button("🤝 파트너 소매상 관리", width="stretch", type="primary" if st.session_state["current_page"] == "파트너 소매상 관리" else "secondary"):
            change_page("파트너 소매상 관리")
            st.rerun()

        st.sidebar.markdown("### ■ 분석 및 카탈로그")
        if st.sidebar.button("📊 실시간 통계 & STR", width="stretch", type="primary" if st.session_state["current_page"] == "실시간 통계" else "secondary"):
            change_page("실시간 통계")
            st.rerun()
        if st.sidebar.button("📱 내 카탈로그 미리보기", width="stretch", type="primary" if st.session_state["current_page"] == "카탈로그 미리보기" else "secondary"):
            change_page("카탈로그 미리보기")
            st.rerun()

        # 현재 페이지 렌더링
        page = st.session_state["current_page"]
        if page == "상품 등록 센터": product_registration.show()
        elif page == "등록 상품 관리": manage_products.show()
        elif page == "예약 및 주문 관리": manage_orders.show()
        elif page == "파트너 소매상 관리": manage_partners.show()
        elif page == "실시간 통계": analytics.show()
        elif page == "카탈로그 미리보기": cue_sheet_page.show()

    elif user_role == "retailer":
        # ★ 소매상: 사이드바 라우터
        if "retailer_page" not in st.session_state:
            st.session_state["retailer_page"] = "전체 상품 카탈로그"

        def change_r_page(page):
            st.session_state["retailer_page"] = page

        st.sidebar.markdown("### ■ 소매상 메뉴")
        if st.sidebar.button("🛍️ 전체 상품 카탈로그", width="stretch", type="primary" if st.session_state["retailer_page"] == "전체 상품 카탈로그" else "secondary"):
            change_r_page("전체 상품 카탈로그")
            st.rerun()
        if st.sidebar.button("📦 내 주문/예약 관리", width="stretch", type="primary" if st.session_state["retailer_page"] == "내 주문/예약 관리" else "secondary"):
            change_r_page("내 주문/예약 관리")
            st.rerun()
        if st.sidebar.button("💬 AI 도매 매니저 상담", width="stretch", type="primary" if st.session_state["retailer_page"] == "AI 상담" else "secondary"):
            change_r_page("AI 상담")
            st.rerun()

        page = st.session_state["retailer_page"]
        if page == "전체 상품 카탈로그": cue_sheet_page.show()
        elif page == "내 주문/예약 관리": retailer_orders.show()
        elif page == "AI 상담": ai_chat.show()
    else:
        # 역할 미지정 예외 처리
        st.error("계정 역할이 지정되지 않았습니다. 관리자에게 문의해 주세요.")