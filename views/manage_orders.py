"""
도매상 예약 및 주문 관리 대시보드
"""
import streamlit as st
from services.database import DatabaseConnector
import pandas as pd

def show():
    store_id = st.session_state.get("store_id", "test_store_01")
    db = DatabaseConnector()
    
    st.title("📝 실시간 예약 및 주문 관리")
    st.markdown("소매상들의 라이브 방송 재고 선예약 요청 및 최종 확정 주문서를 관리하고 승인/반려합니다.")
    
    if not db.supabase:
        st.warning("데이터베이스가 연결되지 않았습니다.")
        return
        
    reservations = db.get_reservations_for_wholesaler(store_id)
    
    if not reservations:
        st.info("현재 대기 중인 예약이나 주문 내역이 없습니다.")
        return
        
    # 상태별 필터링
    tabs = st.tabs(["전체 내역", "대기 중 (PENDING)", "예약 승인됨 (CONFIRMED)", "최종 확정 (COMPLETED)", "취소/노쇼 (CANCELLED/NOSHOW)"])
    
    def render_reservation_list(status_filter=None, prefix="all"):
        filtered = [r for r in reservations if status_filter is None or r.get("status") in status_filter]
        if not filtered:
            st.write("해당 상태의 내역이 없습니다.")
            return
            
        for r in filtered:
            rid = r.get("id")
            p_num = r.get("p_number", "")
            retailer = r.get("retailer_email", "")
            req_qty = r.get("requested_quantity", 0)
            act_qty = r.get("actual_ordered_quantity", 0)
            status = r.get("status", "")
            created_at = r.get("created_at", "")[:16].replace("T", " ")
            
            with st.container():
                st.markdown(f"**[{p_num}]** | 👤 {retailer} | 📅 {created_at}")
                col1, col2, col3, col4 = st.columns([2, 2, 2, 3])
                
                with col1:
                    st.write(f"요청 상태: **{status}**")
                with col2:
                    st.write(f"예약 수량: **{req_qty}개**")
                with col3:
                    if status == "COMPLETED":
                        st.write(f"최종 주문: **{act_qty}개**")
                    else:
                        st.write("최종 주문: -")
                        
                with col4:
                    if status == "PENDING":
                        c_a, c_r = st.columns(2)
                        with c_a:
                            if st.button("✅ 승인", key=f"app_{rid}_{prefix}", width='stretch'):
                                db.update_reservation_status(rid, "CONFIRMED")
                                st.toast("예약 승인됨")
                                st.rerun()
                        with c_r:
                            if st.button("❌ 거절", key=f"rej_{rid}_{prefix}", width='stretch'):
                                db.update_reservation_status(rid, "REJECTED")
                                st.toast("예약 거절됨")
                                st.rerun()
                    elif status == "CONFIRMED":
                        c_n, = st.columns(1)
                        with c_n:
                            if st.button("🚨 노쇼 처리 (패널티)", key=f"ns_{rid}_{prefix}", type="primary", width='stretch'):
                                db.mark_as_noshow(rid, store_id, retailer)
                                st.toast("노쇼 처리 및 패널티 부여 완료")
                                st.rerun()
                st.markdown("---")

    with tabs[0]: render_reservation_list(None, "t0")
    with tabs[1]: render_reservation_list(["PENDING"], "t1")
    with tabs[2]: render_reservation_list(["CONFIRMED"], "t2")
    with tabs[3]: render_reservation_list(["COMPLETED"], "t3")
    with tabs[4]: render_reservation_list(["CANCELLED", "NOSHOW", "REJECTED"], "t4")

    st.subheader("💡 소매상 신뢰도 및 소진율 (STR) 요약")
    st.markdown("최종 확정(COMPLETED) 건을 바탕으로 평균 소진율을 계산합니다.")
    completed_res = [r for r in reservations if r.get("status") == "COMPLETED" and r.get("requested_quantity", 0) > 0]
    
    if completed_res:
        summary_data = []
        for r in completed_res:
            ret = r.get("retailer_email")
            str_val = (r.get("actual_ordered_quantity", 0) / r.get("requested_quantity", 1)) * 100
            summary_data.append({"소매상": ret, "소진율(%)": round(str_val, 2)})
            
        df = pd.DataFrame(summary_data)
        st.dataframe(df.groupby("소매상").mean().reset_index(), width='stretch')
    else:
        st.write("아직 주문 완료된 통계가 없습니다.")
