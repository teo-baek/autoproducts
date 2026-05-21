"""
파트너 소매상 관리 대시보드
도매상이 카탈로그 접근 권한을 신청한 소매상들을 승인/거절/취소 관리합니다.
"""
import streamlit as st
from services.database import DatabaseConnector


def show():
    store_id = st.session_state.get("store_id", "test_store_01")
    db = DatabaseConnector()

    st.title("🤝 파트너 소매상 관리")
    st.markdown("내 카탈로그 열람 승인을 신청한 소매상들을 관리합니다. 승인된 소매상만 가격, 품번 등 전체 상품 정보를 볼 수 있습니다.")

    if not db.supabase:
        st.warning("데이터베이스가 연결되지 않았습니다.")
        return

    if st.button("🔄 새로고침", key="partner_refresh"):
        st.rerun()

    all_requests = db.get_partner_requests_for_wholesaler(store_id)
    pending = [r for r in all_requests if r.get("status") == "PENDING"]
    approved = [r for r in all_requests if r.get("status") == "APPROVED"]
    rejected = [r for r in all_requests if r.get("status") == "REJECTED"]

    tab1, tab2, tab3 = st.tabs([
        f"⏳ 승인 대기 ({len(pending)})",
        f"✅ 파트너 소매상 ({len(approved)})",
        f"❌ 거절 내역 ({len(rejected)})"
    ])

    def render_request_row(r, actions):
        rid = r.get("id")
        email = r.get("retailer_email", "")
        created_at = r.get("created_at", "")[:16].replace("T", " ")
        no_show_count = r.get("no_show_count", 0)
        score = r.get("seller_reliability_score", 100)
        grade = r.get("grade", "Normal")

        col_info, col_score, col_btns = st.columns([3, 2, 2])
        with col_info:
            st.markdown(f"**📧 {email}**")
            st.caption(f"신청일시: {created_at}")
        with col_score:
            st.markdown(f"**🎖️ 등급: {grade}**")
            if no_show_count >= 3 or score <= 70:
                st.error(f"⚠️ 위험: 노쇼 {no_show_count}회 / 신뢰도 {score}점")
            elif no_show_count > 0:
                st.warning(f"주의: 노쇼 {no_show_count}회 / 신뢰도 {score}점")
            else:
                st.success(f"✔️ 양호: 노쇼 {no_show_count}회 / 신뢰도 {score}점")
        with col_btns:
            for label, status, btn_type in actions:
                if st.button(label, key=f"{status}_{rid}", type=btn_type, width='stretch'):
                    db.update_partner_request_status(rid, status)
                    st.toast(f"{email} — {label} 처리 완료")
                    st.rerun()
        st.markdown("---")

    with tab1:
        if not pending:
            st.info("현재 승인 대기 중인 신청이 없습니다.")
        for r in pending:
            render_request_row(r, [
                ("✅ 승인", "APPROVED", "primary"),
                ("❌ 거절", "REJECTED", "secondary"),
            ])

    with tab2:
        if not approved:
            st.info("승인된 파트너 소매상이 없습니다.")
        st.caption("파트너 소매상은 내 카탈로그의 가격, 품번, 사이즈를 모두 확인할 수 있으며, 방송용 재고 예약도 가능합니다.")
        for r in approved:
            render_request_row(r, [
                ("🚫 접근 취소", "REJECTED", "secondary"),
            ])

    with tab3:
        if not rejected:
            st.info("거절 내역이 없습니다.")
        for r in rejected:
            render_request_row(r, [
                ("✅ 재승인", "APPROVED", "primary"),
            ])
