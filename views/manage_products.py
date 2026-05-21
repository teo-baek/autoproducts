"""
등록 상품 관리 (백오피스 CRUD 최적화 버전)
"""
import streamlit as st
from services.database import DatabaseConnector

@st.cache_data(ttl=60)
def fetch_all_products(store_id):
    db_connector = DatabaseConnector()
    if not db_connector.supabase:
        return []
    res_all = db_connector.supabase.table("products").select("*").eq("store_id", store_id).order("created_at", desc=True).execute()
    return res_all.data or []

def show():
    store_id = st.session_state.get("store_id", "test_store_01")
    db_connector = DatabaseConnector()
    
    st.subheader("📦 내 매장 상품 통합 관리")
    st.markdown("라이브 방송 중 빠르게 상품 정보를 수정하거나 '품절' 처리할 수 있습니다.")
    
    if not db_connector.supabase:
        st.warning("데이터베이스가 연결되지 않았습니다.")
        return
        
    try:
        all_products = fetch_all_products(store_id)
        
        if not all_products:
            st.info("등록된 상품이 없습니다.")
            return

        # 1. 상단 필터 및 검색
        col_f1, col_f2, col_f3 = st.columns([2, 1, 1])
        with col_f1:
            filter_query = st.text_input("🔍 품번 또는 상품명 검색", key="crud_search")
        with col_f2:
            filter_soldout = st.selectbox("상태 필터", ["전체", "판매중", "품절"])
        with col_f3:
            st.write("")
            if st.button("🔄 새로고침", width='stretch'):
                fetch_all_products.clear()
                st.rerun()

        filtered_list = []
        for p in all_products:
            q = filter_query.lower()
            match_q = not q or q in str(p.get("p_number", "")).lower() or q in str(p.get("item_name", "")).lower()
            is_so = p.get("is_sold_out", False)
            match_so = True
            if filter_soldout == "판매중": match_so = not is_so
            elif filter_soldout == "품절": match_so = is_so
            
            if match_q and match_so:
                filtered_list.append(p)
                
        st.caption(f"총 {len(filtered_list)}개의 상품이 조회되었습니다.")

        # CSS for list


        # 현재 수정 중인 상품이 있는지 확인
        editing_pnum = st.session_state.get("editing_product_pnum", None)

        # 2. 리스트업 (페이지네이션 적용 또는 심플 리스트)
        # 속도를 위해 단일 row에는 텍스트와 버튼 2개만 렌더링
        for p in filtered_list:
            p_num = p.get("p_number", "")
            item_name = p.get("item_name", "")
            is_so = p.get("is_sold_out", False)
            variants = p.get("variants", [])
            image_url = p.get("image_url", "")
            description = p.get("description", "")
            
            # --- 편집 모드 영역 ---
            if editing_pnum == p_num:
                st.markdown(f"### ✏️ [{p_num}] {item_name} 수정")
                
                v_color, v_size, v_whole, v_ret = "", "", 0, 0
                if variants and isinstance(variants, list) and len(variants) > 0:
                    v = variants[0]
                    v_color = v.get("color", "")
                    v_size = v.get("size", "")
                    v_whole = v.get("wholesale", 0)
                    v_ret = v.get("retail", 0)

                with st.container():
                    c_img, c_form = st.columns([1, 3])
                    with c_img:
                        if image_url:
                            display_url = image_url
                            if not image_url.startswith("http"):
                                display_url = db_connector.get_signed_image_url(image_url)
                            if display_url:
                                st.image(display_url, width='stretch')
                            else:
                                st.info("이미지 만료/없음")
                        else: 
                            st.info("이미지 없음")
                    
                    with c_form:
                        new_name = st.text_input("상품명", value=item_name, key=f"edit_name_{p_num}")
                        cc1, cc2 = st.columns(2)
                        with cc1:
                            new_whole = st.number_input("도매가", value=int(v_whole), key=f"edit_whole_{p_num}", step=1000)
                            new_color = st.text_input("색상", value=v_color, key=f"edit_color_{p_num}")
                        with cc2:
                            new_ret = st.number_input("판매가", value=int(v_ret), key=f"edit_ret_{p_num}", step=1000)
                            new_size = st.text_input("사이즈", value=v_size, key=f"edit_size_{p_num}")
                        new_desc = st.text_area("상세설명 (AI 영업 지식용)", value=description, key=f"edit_desc_{p_num}", height=80)
                            
                        # 액션 버튼
                        ca1, ca2, ca3 = st.columns(3)
                        with ca1:
                            if st.button("💾 저장", type="primary", width='stretch', key=f"save_{p_num}"):
                                new_vars = [{
                                    "color": new_color, "size": new_size, "mix_ratio": "", 
                                    "wholesale": new_whole, "retail": new_ret, "stock": 0
                                }]
                                succ, msg = db_connector.update_product_details(store_id, p_num, new_name, new_vars, new_desc)
                                if succ:
                                    st.toast("저장 완료")
                                    st.session_state["editing_product_pnum"] = None
                                    fetch_all_products.clear()
                                    st.rerun()
                                else: st.error(msg)
                        with ca2:
                            if st.button("🗑️ 삭제", width='stretch', key=f"del_{p_num}"):
                                succ, msg = db_connector.delete_product(store_id, p_num)
                                if succ:
                                    st.toast("삭제 완료")
                                    st.session_state["editing_product_pnum"] = None
                                    fetch_all_products.clear()
                                    st.rerun()
                                else: st.error(msg)
                        with ca3:
                            if st.button("❌ 취소", width='stretch', key=f"cancel_{p_num}"):
                                st.session_state["editing_product_pnum"] = None
                                st.rerun()
                st.markdown("---")
            
            # --- 일반 리스트 뷰 영역 ---
            else:
                col_info, col_btn1, col_btn2 = st.columns([5, 1, 1])
                
                with col_info:
                    badge = "<span class='product-row-badge'>품절</span>" if is_so else ""
                    st.markdown(f"<div class='product-row'>{badge}<span class='product-row-info'>[{p_num}] {item_name}</span></div>", unsafe_allow_html=True)
                    
                with col_btn1:
                    # 품절 토글만 개별 동작 (간단하게 버튼으로 처리하여 성능 극대화)
                    if is_so:
                        if st.button("🟢 판매중 전환", key=f"toggle_{p_num}", width='stretch'):
                            db_connector.update_product_sold_out(store_id, p_num, False)
                            fetch_all_products.clear()
                            st.rerun()
                    else:
                        if st.button("🔴 품절 처리", key=f"toggle_{p_num}", width='stretch'):
                            db_connector.update_product_sold_out(store_id, p_num, True)
                            fetch_all_products.clear()
                            st.rerun()
                            
                with col_btn2:
                    if st.button("✏️ 수정", key=f"edit_btn_{p_num}", width='stretch'):
                        st.session_state["editing_product_pnum"] = p_num
                        st.rerun()

    except Exception as e:
        st.error(f"오류: {e}")
