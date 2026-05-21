"""
소매상 주문 및 예약 관리 대시보드
"""
import streamlit as st
from services.database import DatabaseConnector
import pandas as pd

def show():
    retailer_email = st.session_state.get("email", "unknown_retailer")
    db = DatabaseConnector()
    
    st.title("📦 내 주문 및 예약 관리")
    st.markdown("도매상에게 요청한 상품들의 선예약 상태를 확인하고, 수량을 확정하거나 취소할 수 있습니다.")
    
    if not db.supabase:
        st.warning("데이터베이스가 연결되지 않았습니다.")
        return
        
    try:
        res = db.supabase.table("product_reservations").select("*").eq("retailer_email", retailer_email).order("created_at", desc=True).execute()
        my_reservations = res.data if res.data else []
    except Exception as e:
        st.error(f"예약 내역을 불러오는 중 오류 발생: {e}")
        return
        
    if not my_reservations:
        st.info("현재 요청한 예약이나 주문 내역이 없습니다. 카탈로그에서 상품을 예약해 보세요.")
        return
        
    # 상태별 필터링
    tabs = st.tabs(["대기 중 (PENDING)", "승인됨 (CONFIRMED)", "최종 확정 (COMPLETED)", "취소/거절 (기타)"])
    
    def render_reservation_list(status_filter, tab_key):
        filtered = [r for r in my_reservations if r.get("status") in status_filter]
        if not filtered:
            st.write("해당 상태의 내역이 없습니다.")
            return
            
        for r in filtered:
            rid = r.get("id")
            p_num = r.get("p_number", "")
            store_id = r.get("wholesaler_store_id", "")
            req_qty = r.get("requested_quantity", 0)
            act_qty = r.get("actual_ordered_quantity", 0)
            status = r.get("status", "")
            created_at = r.get("created_at", "")[:16].replace("T", " ")
            
            with st.container(border=True):
                st.markdown(f"### 🏷️ 상품 번호: #{p_num}")
                st.markdown(f"**도매상:** {store_id} | **신청일:** {created_at}")
                
                col1, col2, col3 = st.columns(3)
                with col1:
                    st.write(f"요청 상태: **{status}**")
                with col2:
                    st.write(f"예약 수량: **{req_qty}개**")
                with col3:
                    if status == "COMPLETED":
                        st.write(f"최종 확정: **{act_qty}개**")
                    else:
                        st.write("최종 확정: -")
                        
                st.markdown("<hr style='margin: 10px 0;'>", unsafe_allow_html=True)
                
                if status == "PENDING":
                    st.info("⏳ 도매상의 승인을 기다리고 있습니다.")
                    c1, c2 = st.columns(2)
                    with c1:
                        if st.button("❌ 예약 취소", key=f"ccl_{rid}_{tab_key}", width='stretch'):
                            succ, msg = db.cancel_reservation(rid)
                            if succ:
                                st.toast("예약이 취소되었습니다.")
                                st.rerun()
                            else:
                                st.error(msg)
                    with c2:
                        with st.popover("✏️ 수량 수정", width='stretch'):
                            new_qty = st.number_input("변경할 수량", min_value=1, step=1, value=req_qty, key=f"eq_{rid}")
                            if st.button("수량 변경 확정", key=f"ebtn_{rid}", type="primary", width='stretch'):
                                succ, msg = db.update_reservation_quantity(rid, new_qty)
                                if succ:
                                    st.toast(f"수량이 {new_qty}개로 변경되었습니다.")
                                    st.rerun()
                                else:
                                    st.error(msg)
                elif status == "CONFIRMED":
                    st.success("🎉 도매상이 예약을 승인했습니다! 방송 후 최종 주문 수량을 확정해주세요.")
                    with st.expander("📦 방송 후 최종 주문서 전송", expanded=True):
                        st.caption("실제 방송 후 고객에게 주문받은 최종 수량을 입력해주세요. (노쇼 방지)")
                        final_qty = st.number_input("최종 실 주문 수량 (개)", min_value=0, step=1, key=f"act_{rid}", value=req_qty)
                        if st.button("최종 주문 확정 전송", key=f"actbtn_{rid}", type="primary", width='stretch'):
                            succ, msg = db.confirm_order(rid, final_qty)
                            if succ:
                                st.toast("주문서가 최종 확정되었습니다!")
                                st.rerun()
                            else:
                                st.error(msg)
                elif status == "COMPLETED":
                    st.success("✅ 최종 주문서 확정이 완료되었습니다. 도매상이 상품을 준비 중입니다.")
                elif status == "REJECTED":
                    st.error("❌ 도매상에 의해 예약이 거절되었습니다. (재고 부족 등)")
                elif status == "NOSHOW":
                    st.error("🚨 기한 초과 및 노쇼로 인해 패널티가 부과되었습니다.")
                elif status == "CANCELLED":
                    st.warning("⚠️ 소매상에 의해 직접 취소된 예약입니다.")

    with tabs[0]: render_reservation_list(["PENDING"], "t0")
    with tabs[1]: render_reservation_list(["CONFIRMED"], "t1")
    with tabs[2]: render_reservation_list(["COMPLETED"], "t2")
    with tabs[3]: render_reservation_list(["CANCELLED", "NOSHOW", "REJECTED"], "t3")
