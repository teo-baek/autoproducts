"""
AutoProducts 구독 활성화 대기 페이지
회원가입은 완료했지만 아직 결제(입금)가 확인되지 않은 도매상에게 보여지는 안내 화면입니다.
"""
import streamlit as st
from services.auth import AuthService


def show():
    auth = AuthService()



    plan_type = st.session_state.get("plan_type", "standard")
    store_name = st.session_state.get("store_name", "")
    price_text = "50,000원" if plan_type == "partner" else "100,000원"

    st.markdown(f"""
    <div class="billing-container">
        <div class="billing-icon">⏳</div>
        <div class="billing-title">구독 활성화 대기 중</div>
        <div class="billing-desc">
            <strong>{store_name}</strong>님, 회원가입이 완료되었습니다!<br/>
            아래 계좌로 월 구독료를 입금해 주시면,<br/>
            관리자 확인 즉시 모든 기능이 <strong>자동으로 활성화</strong>됩니다.
        </div>
    </div>
    """, unsafe_allow_html=True)

    st.markdown(f"""
    <div class="account-box">
        <h4>💳 구독료 입금 안내</h4>
        <p class="account-info">
            카카오뱅크 3333-00-0000000<br/>
            예금주: (주)오토프로덕츠<br/><br/>
            월 구독료: <strong>{price_text}</strong><br/>
            입금자명: <strong>{store_name}</strong>
        </p>
    </div>
    """, unsafe_allow_html=True)

    st.markdown("""
    <div class="status-waiting">
        🔴 현재 상태: 입금 확인 대기 중 — 서비스 이용이 제한됩니다.
    </div>
    """, unsafe_allow_html=True)

    st.markdown("---")

    # 입금 확인 재시도 버튼
    if st.button("🔄 입금 확인 상태 새로고침", width="stretch"):
        # DB에서 is_paid 값을 다시 조회
        if auth.supabase:
            user_id = st.session_state.get("user_id", "")
            if user_id:
                response = (
                    auth.supabase.table("store_profiles")
                    .select("is_paid")
                    .eq("id", user_id)
                    .execute()
                )
                if response.data and response.data[0].get("is_paid", False):
                    st.session_state["is_paid"] = True
                    st.success("🎉 입금이 확인되었습니다! 잠시 후 서비스가 활성화됩니다.")
                    st.rerun()
                else:
                    st.info("아직 입금이 확인되지 않았습니다. 입금 후 다시 시도해 주세요.")

    st.markdown("")

    # 로그아웃 버튼
    if st.button("로그아웃", width="stretch"):
        auth.sign_out()
        st.rerun()
