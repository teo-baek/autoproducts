import streamlit as st
import json
from services.database import DatabaseConnector
from services.ai_agent import AIAgentService

def show():
    st.title("💬 AI 도매 매니저 상담")
    
    db = DatabaseConnector()
    retailer_email = st.session_state.get("email", "")
    
    if not retailer_email:
        st.warning("로그인이 필요합니다.")
        return
        
    st.markdown("### 상담할 도매상 선택")
    
    # Get approved wholesalers for this retailer
    try:
        res = db.supabase.table("partner_requests").select("wholesaler_store_id, status").eq("retailer_email", retailer_email).execute()
        approved_stores = [r["wholesaler_store_id"] for r in res.data if r.get("status") == "APPROVED"]
    except Exception as e:
        st.error(f"도매상 목록을 불러오는 중 오류가 발생했습니다. {e}")
        return
        
    # 개발 모드(DEV_MODE) 테스트 편의성을 위해 세션에 현재 보고 있던 store_id가 있다면 포함
    current_catalog_store = st.session_state.get("current_store_id_for_retailer", "")
    if current_catalog_store and current_catalog_store not in approved_stores:
        approved_stores.append(current_catalog_store)
        
    if not approved_stores:
        st.info("현재 승인된 도매상이 없습니다. '전체 상품 카탈로그' 메뉴에서 먼저 파트너 요청을 진행해주세요.")
        return
        
    # 기본 선택값을 방금 카탈로그에서 보던 매장으로 설정
    default_idx = 0
    if current_catalog_store in approved_stores:
        default_idx = approved_stores.index(current_catalog_store)
        
    selected_store = st.selectbox("도매상 ID", approved_stores, index=default_idx)
    
    if not selected_store:
        return
        
    # Check premium status
    try:
        res_w = db.supabase.table("store_profiles").select("has_ai_agent, store_name").eq("store_id", selected_store).execute()
        if not res_w.data:
            st.error(f"{selected_store} 도매상 프로필을 찾을 수 없습니다.")
            return
        has_ai_agent = res_w.data[0].get("has_ai_agent", False)
        store_name = res_w.data[0].get("store_name", selected_store)
    except Exception as e:
        has_ai_agent = False
        store_name = selected_store
        
    st.markdown("---")
    
    if not has_ai_agent:
        st.warning(f"🔒 **{store_name}** 매장은 현재 AI 매니저 상담(프리미엄 요금제)을 지원하지 않습니다.")
        st.info("해당 도매상이 프리미엄 요금제로 업그레이드하면 24시간 재고/단가 상담이 가능해집니다!")
        return
        
    st.caption(f"**{store_name}** 매장의 재고, 단가 문의, 상품 검색 등 무엇이든 물어보세요! (위장 소비자 식별 및 단가 흥정 가능)")
    
    ai_service = AIAgentService()
    
    # Fetch products for context
    products = db.get_products(selected_store)
    
    # Streamlit session state for chat
    chat_key = f"ai_chat_history_{selected_store}"
    if chat_key not in st.session_state:
        st.session_state[chat_key] = [
            {"role": "assistant", "content": f"안녕하세요 사장님! **{store_name}** 전담 AI 매니저입니다. 무엇을 도와드릴까요? (예: 흰색 바지 찾아주세요, 100장 단가 네고 가능한가요?)"}
        ]

    # Render previous messages
    for msg in st.session_state[chat_key]:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])
            
    # Input
    if user_input := st.chat_input("메시지를 입력하세요 (예: 흰색 바지 추천해줘)..."):
        st.session_state[chat_key].append({"role": "user", "content": user_input})
        with st.chat_message("user"):
            st.markdown(user_input)
            
        with st.chat_message("assistant"):
            with st.spinner("AI 매니저가 확인 중입니다..."):
                retailer_info = {
                    "seller_reliability_score": 100,
                    "grade": "Normal",
                    "no_show_count": 0
                }
                try:
                    res_p = db.supabase.table("partner_requests").select("*").eq("wholesaler_store_id", selected_store).eq("retailer_email", retailer_email).execute()
                    if res_p.data:
                        retailer_info = res_p.data[0]
                except:
                    pass

                relevant_products = ai_service.filter_relevant_products(user_input, products, max_count=10)
                product_context = [
                    {
                        "p_number": p.get("p_number"), 
                        "item_name": p.get("item_name"),
                        "description": p.get("description", ""),
                        "variants": p.get("variants")
                    } for p in relevant_products
                ]
                
                response_text = ai_service.generate_response(
                    retailer_info=retailer_info,
                    product_context=product_context,
                    chat_history=st.session_state[chat_key][:-1],
                    message=user_input
                )
                
                st.markdown(response_text)
                st.session_state[chat_key].append({"role": "assistant", "content": response_text})
