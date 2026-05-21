"""
AutoProducts 로그인 및 회원가입 페이지
비로그인 유저가 접속 시 가장 먼저 보게 되는 화면입니다.
"""
import streamlit as st
from services.auth import AuthService


def show():
    st.markdown('<div class="login-title">🏢 AutoProducts</div>', unsafe_allow_html=True)
    st.markdown('<div class="login-subtitle">동대문 도매 시장 전용 B2B SaaS 플랫폼</div>', unsafe_allow_html=True)

    tab_login, tab_signup = st.tabs(["🔑 로그인", "📝 회원가입"])

    auth = AuthService()

    # ─────────────────────────────────────────
    # 로그인 탭
    # ─────────────────────────────────────────
    with tab_login:
        st.subheader("기존 계정으로 로그인")

        login_email = st.text_input("이메일", key="login_email", placeholder="example@email.com")
        login_password = st.text_input("비밀번호", type="password", key="login_pw", placeholder="비밀번호를 입력하세요")

        if st.button("로그인", width="stretch", type="primary"):
            if login_email and login_password:
                success, msg = auth.sign_in(login_email, login_password)
                if success:
                    st.success(msg)
                    st.rerun()
                else:
                    st.error(msg)
            else:
                st.warning("이메일과 비밀번호를 모두 입력해 주세요.")

    # ─────────────────────────────────────────
    # 회원가입 탭
    # ─────────────────────────────────────────
    with tab_signup:
        st.subheader("신규 회원가입")

        signup_email = st.text_input("이메일", key="signup_email", placeholder="example@email.com")
        signup_password = st.text_input("비밀번호 (6자 이상)", type="password", key="signup_pw")
        signup_password_confirm = st.text_input("비밀번호 확인", type="password", key="signup_pw_confirm")

        role = st.radio(
            "가입 유형을 선택하세요",
            ["wholesaler", "retailer"],
            format_func=lambda x: "🏢 도매상 (매장 운영자)" if x == "wholesaler" else "🛒 소매상 (바이어/셀러)",
            horizontal=True,
        )

        # 도매상 전용 추가 정보
        store_id = ""
        store_name = ""
        drive_url = ""
        plan_type = "standard"

        if role == "wholesaler":
            st.markdown("---")
            st.markdown("##### 🏢 도매상 매장 정보")

            store_id = st.text_input(
                "매장 고유 ID (영문/숫자, 변경 불가)",
                placeholder="예: dmd_kim, fashion_07",
                help="소매상들이 카탈로그에 접속할 때 사용되는 고유 식별자입니다."
            )
            store_name = st.text_input(
                "매장 한글 이름",
                placeholder="예: 김사장네 원피스"
            )
            drive_url = st.text_input(
                "구글 드라이브 폴더 주소 (선택사항)",
                placeholder="https://drive.google.com/drive/folders/...",
                help="기존에 제품 사진을 보관하던 구글 드라이브 폴더 주소입니다. 나중에 설정에서 변경할 수 있습니다."
            )

            # 요금제 선택
            st.markdown("---")
            st.markdown("##### 💳 구독 요금제 선택")
            col1, col2 = st.columns(2)
            with col1:
                st.markdown("""
                <div class="plan-card">
                    <h4>🌟 초기 파트너</h4>
                    <p class="plan-price">월 50,000원</p>
                    <p>초기 8개 매장 한정<br/>모든 기능 무제한 + 피드백 파트너</p>
                </div>
                """, unsafe_allow_html=True)
            with col2:
                st.markdown("""
                <div class="plan-card">
                    <h4>📦 스탠다드</h4>
                    <p class="plan-price">월 100,000원</p>
                    <p>실전 검증 완료된 완성형<br/>POS 인프라 무제한 제공</p>
                </div>
                """, unsafe_allow_html=True)

            plan_type = st.selectbox(
                "요금제",
                ["partner", "standard"],
                format_func=lambda x: "🌟 초기 파트너 (월 50,000원)" if x == "partner" else "📦 스탠다드 (월 100,000원)"
            )

        # 회원가입 버튼
        if st.button("회원가입", width="stretch", type="primary"):
            # 유효성 검사
            if not signup_email or not signup_password:
                st.warning("이메일과 비밀번호를 모두 입력해 주세요.")
            elif len(signup_password) < 6:
                st.warning("비밀번호는 최소 6자 이상이어야 합니다.")
            elif signup_password != signup_password_confirm:
                st.error("비밀번호가 일치하지 않습니다.")
            elif role == "wholesaler" and not store_id:
                st.warning("도매상은 매장 고유 ID를 반드시 입력해야 합니다.")
            else:
                success, msg = auth.sign_up(
                    email=signup_email,
                    password=signup_password,
                    role=role,
                    store_id=store_id,
                    store_name=store_name,
                    drive_folder_url=drive_url,
                    plan_type=plan_type,
                )
                if success:
                    st.success(msg)
                else:
                    st.error(msg)
