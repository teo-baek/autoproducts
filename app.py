"""
AutoProducts — 앱 엔트리포인트 (Auth-Free Magic Toggle Version)
로그인 없이 사이드바의 토글 스위치로 즉시 권한을 변경하며 UI를 개발/테스트합니다.
"""
import streamlit as st
from services.theme import apply_common_theme

st.set_page_config(
    page_title="AutoProducts (DEV)",
    page_icon="🏢",
    layout="wide",
    initial_sidebar_state="expanded"
)

apply_common_theme()

# 화면 모듈 임포트 (로그인, 결제 제외)
from views import cue_sheet as cue_sheet_page
from views import product_registration
from views import manage_products
from views import manage_orders
from views import manage_partners
from views import retailer_orders
from views import ai_chat
# 새로 만들 빈 모듈 (미리 라우팅)
# from views import pos_terminal

# ─────────────────────────────────────────
# Auth-Free 세션 초기화 (기본값: 도매상)
# ─────────────────────────────────────────
if "role" not in st.session_state:
    st.session_state["role"] = "wholesaler"
    st.session_state["store_name"] = "동대문김사장 (Mock)"
    st.session_state["store_id"] = "mock-store-id-123"

# ─────────────────────────────────────────
# 마법의 토글 스위치 (Magic Toggle)
# ─────────────────────────────────────────
with st.sidebar:
    st.markdown("### 🛠️ 개발/테스트 스위치")
    # 라디오 버튼으로 권한 즉각 스위칭
    selected_mode = st.radio(
        "권한 모드 선택:",
        ["🏢 도매상 모드", "🛒 소매상 모드"],
        index=0 if st.session_state["role"] == "wholesaler" else 1,
        key="dev_role_toggle"
    )
    
    # 토글 변경 감지 및 세션 업데이트
    new_role = "wholesaler" if "도매상" in selected_mode else "retailer"
    if new_role != st.session_state["role"]:
        st.session_state["role"] = new_role
        if new_role == "wholesaler":
            st.session_state["store_name"] = "동대문김사장 (Mock)"
            st.session_state["store_id"] = "mock-store-id-123"
        else:
            st.session_state["store_name"] = "소매상나라 (Mock)"
            st.session_state["store_id"] = "mock-retailer-id-456"
        st.rerun()

    st.markdown("---")
    st.markdown(f"**현재 모드:** {st.session_state['store_name']}")
    st.markdown("---")

# ─────────────────────────────────────────
# 라우팅 로직 (Routing)
# ─────────────────────────────────────────
user_role = st.session_state["role"]

if user_role == "wholesaler":
    if "wholesaler_page" not in st.session_state:
        st.session_state["wholesaler_page"] = "상품 등록 센터"

    def change_page(page):
        st.session_state["wholesaler_page"] = page

    st.sidebar.markdown("### ■ 상품 파트")
    if st.sidebar.button("📤 상품 등록 센터", width="stretch", type="primary" if st.session_state["wholesaler_page"] == "상품 등록 센터" else "secondary"):
        change_page("상품 등록 센터"); st.rerun()
    if st.sidebar.button("📦 등록 상품 관리", width="stretch", type="primary" if st.session_state["wholesaler_page"] == "등록 상품 관리" else "secondary"):
        change_page("등록 상품 관리"); st.rerun()
    
    st.sidebar.markdown("### ■ 매장 결제 파트")
    if st.sidebar.button("💳 7:3 POS 터미널", width="stretch", type="primary" if st.session_state["wholesaler_page"] == "POS 터미널" else "secondary"):
        change_page("POS 터미널"); st.rerun()

    st.sidebar.markdown("### ■ 영업 지원")
    if st.sidebar.button("📝 예약 및 주문 관리", width="stretch", type="primary" if st.session_state["wholesaler_page"] == "주문 관리" else "secondary"):
        change_page("주문 관리"); st.rerun()
    if st.sidebar.button("🤝 파트너/샘플 관리", width="stretch", type="primary" if st.session_state["wholesaler_page"] == "파트너 관리" else "secondary"):
        change_page("파트너 관리"); st.rerun()

    # 페이지 렌더링
    page = st.session_state["wholesaler_page"]
    if page == "상품 등록 센터": product_registration.show()
    elif page == "등록 상품 관리": manage_products.show()
    elif page == "POS 터미널": st.title("💳 7:3 POS 터미널 (개발 중...)") # 차후 pos_terminal.py 모듈 연동
    elif page == "주문 관리": manage_orders.show()
    elif page == "파트너 관리": manage_partners.show()

elif user_role == "retailer":
    if "retailer_page" not in st.session_state:
        st.session_state["retailer_page"] = "글로벌 카탈로그"

    def change_r_page(page):
        st.session_state["retailer_page"] = page

    st.sidebar.markdown("### ■ 소매상 파트")
    if st.sidebar.button("🛍️ 글로벌 카탈로그", width="stretch", type="primary" if st.session_state["retailer_page"] == "글로벌 카탈로그" else "secondary"):
        change_r_page("글로벌 카탈로그"); st.rerun()
    if st.sidebar.button("📺 라이브 방송 대시보드", width="stretch", type="primary" if st.session_state["retailer_page"] == "라이브 대시보드" else "secondary"):
        change_r_page("라이브 대시보드"); st.rerun()

    page = st.session_state["retailer_page"]
    if page == "글로벌 카탈로그": cue_sheet_page.show()
    elif page == "라이브 대시보드": st.title("📺 라이브 대시보드 (개발 중...)")