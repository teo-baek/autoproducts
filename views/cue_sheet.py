"""
AutoProducts 모바일 큐시트 카탈로그 페이지
DB에 저장된 상품 데이터를 모바일 친화적인 카드 UI로 렌더링합니다.
소매상 로그인 시 도매가를 자동으로 숨깁니다.
"""
import streamlit as st
from services.database import DatabaseConnector
import json


def show():
    # --- 커스텀 CSS 주입 (Aesthetics 최적화) ---
    st.markdown("""
    <style>
        .product-card {
            background: white;
            border-radius: 20px;
            padding: 20px;
            margin-bottom: 25px;
            box-shadow: 0 10px 15px -3px rgba(0, 0, 0, 0.05), 0 4px 6px -2px rgba(0, 0, 0, 0.025);
            border: 1px solid #f1f5f9;
            transition: transform 0.2s ease, box-shadow 0.2s ease;
        }
        .product-card:hover {
            transform: translateY(-4px);
            box-shadow: 0 20px 25px -5px rgba(0, 0, 0, 0.1), 0 10px 10px -5px rgba(0, 0, 0, 0.04);
        }
        .p-number {
            color: #3b82f6;
            font-weight: 700;
            font-size: 1.2rem;
            margin-bottom: 2px;
        }
        .item-name {
            color: #1e293b;
            font-weight: 800;
            font-size: 1.5rem;
            margin-bottom: 12px;
        }
        .tag {
            display: inline-block;
            background-color: #f1f5f9;
            color: #475569;
            padding: 4px 10px;
            border-radius: 15px;
            font-size: 0.85rem;
            font-weight: 600;
            margin-right: 6px;
            margin-bottom: 6px;
            border: 1px solid #e2e8f0;
        }
        .price-box {
            margin-top: 15px;
            padding-top: 15px;
            border-top: 1px dashed #cbd5e1;
            display: flex;
            justify-content: space-between;
        }
        .retail-price {
            color: #64748b;
            font-size: 0.95rem;
        }
        .wholesale-price {
            color: #ef4444;
            font-weight: 800;
            font-size: 1.1rem;
        }
        .sold-out-card {
            opacity: 0.6;
            border: 2px solid #ef4444;
            filter: grayscale(20%);
        }
        .sold-out-badge {
            background: linear-gradient(135deg, #ef4444 0%, #b91c1c 100%);
            color: white;
            padding: 5px 15px;
            border-radius: 20px;
            font-weight: 800;
            font-size: 0.85rem;
            display: inline-block;
            margin-bottom: 12px;
            box-shadow: 0 4px 6px -1px rgba(239, 68, 68, 0.4);
        }
    </style>
    """, unsafe_allow_html=True)

    st.title("📱 라이브 큐시트 카탈로그")
    st.caption("스마트폰 화면에 최적화된 모바일 전용 상품 목록입니다.")

    # 로그인 유저의 역할 감지 → 소매상이면 자동으로 도매가 숨김
    user_role = st.session_state.get("role", "")
    is_retailer = user_role == "retailer"

    # URL 파라미터 읽어오기
    url_store_id = st.query_params.get("store_id", "")
    initial_search = st.query_params.get("search", "")

    partner_status_map = {}
    current_store_id = ""

    if is_retailer:
        # 소매상: URL 파라미터가 없으면 전체 상품 갤러리 노출
        current_store_id = url_store_id  # 빈 문자열이면 전체 조회
        
        # 소매상의 파트너십 상태 맵(전체 도매상 대상)을 미리 로드
        db_temp = DatabaseConnector()
        retailer_email = st.session_state.get("email", "")
        if db_temp.supabase and retailer_email:
            try:
                res_partners = db_temp.supabase.table("partner_requests") \
                    .select("wholesaler_store_id, status") \
                    .eq("retailer_email", retailer_email) \
                    .execute()
                if res_partners.data:
                    for r in res_partners.data:
                        partner_status_map[r["wholesaler_store_id"]] = r["status"]
            except:
                pass
    else:
        # 도매상 본인: 세션의 store_id = 자신의 카탈로그
        current_store_id = st.session_state.get("store_id", "test_store_01")

    # 1. 검색창 및 도매가 토글
    col_search, col_toggle = st.columns([3, 1])
    with col_search:
        store_display_name = current_store_id if current_store_id else "전체 도매상"
        search_query = st.text_input(
            f"🔍 [{store_display_name}] 상품 검색",
            value=initial_search,
            placeholder="예: 5015 또는 티셔츠"
        )
    
    hide_wholesale = True if is_retailer else False
    # 2. DB 데이터 불러오기
    @st.cache_data(ttl=60)
    def fetch_products(store_id_filter):
        db = DatabaseConnector()
        if not db.supabase:
            return []
        query = db.supabase.table("products").select("*")
        if store_id_filter:
            query = query.eq("store_id", store_id_filter)
        response = query.order("created_at", desc=True).execute()
        return response.data

    products = fetch_products(current_store_id)

    if not products:
        st.warning("등록된 상품이 없거나 DB 연결에 실패했습니다.")
        st.stop()

    # 3. 검색 필터링 적용 (하이브리드 스마트 검색)
    if search_query:
        q = search_query.strip().lower()
        
        # 자연어 검색 판단 조건 (Classifier)
        # 띄어쓰기가 포함된 긴 문장이거나, 특정 종결 어미가 있는 경우 AI 검색 트리거
        nlp_triggers = ["찾아", "추천", "어때", "보여", "알려", "원해", "좋은"]
        is_semantic = False
        
        if len(q) >= 8 and " " in q:
            is_semantic = True
        elif any(trigger in q for trigger in nlp_triggers):
            is_semantic = True
            
        if is_semantic:
            with st.spinner("✨ AI가 상품의 맥락을 분석하여 추천을 검색 중입니다..."):
                from services.ai_agent import AIAgentService
                ai_service = AIAgentService()
                matched_p_numbers = ai_service.semantic_search(q, products)
                
                if matched_p_numbers:
                    filtered_products = [p for p in products if p.get("p_number") in matched_p_numbers]
                else:
                    st.info("AI 검색 결과가 없습니다. 조건에 맞는 상품이 없을 수 있습니다.")
                    filtered_products = []
        else:
            # 기존 로컬 검색 (즉시 필터링)
            filtered_products = [
                p for p in products
                if q in str(p.get("p_number", "")).lower() or q in str(p.get("item_name", "")).lower()
            ]
    else:
        filtered_products = products

    st.markdown(f"<p style='color: #64748b; font-size: 0.9rem;'>총 {len(filtered_products)}개의 상품이 검색되었습니다.</p>", unsafe_allow_html=True)

    # --- 페이지네이션 (Load More) 도입 ---
    if "page_size" not in st.session_state:
        st.session_state["page_size"] = 12
    

    # --- Phase 7 & 9: 소매상 맞춤형 큐시트 (Cart) + 라이브 방송 모드 ---
    live_broadcast_mode = False
    if is_retailer:
        if "my_cue_sheet" not in st.session_state:
            st.session_state["my_cue_sheet"] = []
            
        col_cart1, col_live, col_cart2 = st.columns([2, 2, 1])
        with col_cart1:
            show_only_cart = st.toggle(f"🛒 내 방송용 큐시트만 보기 ({len(st.session_state['my_cue_sheet'])}개)")
        with col_live:
            live_broadcast_mode = st.toggle("🔴 라이브 방송 모드 (이미지 12시간 유지)")
        with col_cart2:
            if st.button("내 큐시트 비우기"):
                st.session_state["my_cue_sheet"] = []
                st.rerun()
                
        if show_only_cart:
            filtered_products = [p for p in filtered_products if p.get("p_number") in st.session_state["my_cue_sheet"]]
            if not filtered_products:
                st.info("아직 큐시트에 담긴 상품이 없습니다. 전체 목록에서 상품을 담아주세요.")

    # --- Phase 4 & 5: 예약 데이터 불러오기 ---
    db = DatabaseConnector()
    retailer_email = st.session_state.get("email", "unknown_retailer")

    # 상단 글로벌 승인 배너 삭제 (이제 상품별 개별 승인 로직으로 대체됨)
    # 소매상의 경우 전체 카탈로그를 불러오므로 해당 소매상의 모든 예약을 가져옵니다.
    if is_retailer:
        try:
            res_reservations = db.supabase.table("product_reservations") \
                .select("*") \
                .eq("retailer_email", retailer_email) \
                .execute()
            my_reservations = res_reservations.data if res_reservations.data else []
            res_map = {r.get("p_number"): r for r in my_reservations}
        except:
            res_map = {}
    else:
        res_map = {}

    # 페이지네이션: 표시할 상품만 슬라이싱
    visible_products = filtered_products[:st.session_state["page_size"]]

    # 4. 카드 UI 렌더링
    grid_cols = st.columns(3)
    for i, p in enumerate(visible_products):
        with grid_cols[i % 3]:
            p_num = p.get("p_number", "")
            product_store_id = p.get("store_id", "")
            item_name = p.get("item_name", "이름 없음")
            image_url = p.get("image_url", "")
            variants = p.get("variants", [])

            if isinstance(variants, str):
                try:
                    variants = json.loads(variants)
                except Exception:
                    variants = []

            colors = list(set([v.get("color") for v in variants if v.get("color")]))
            sizes = list(set([v.get("size") for v in variants if v.get("size")]))

            retail_price = variants[0].get("retail", "0") if variants else "0"
            wholesale_price = variants[0].get("wholesale", "0") if variants else "0"

            # 파트너십 상태 확인 (개별 상품별)
            if is_retailer:
                partner_status = partner_status_map.get(product_store_id)
                is_full_access = (partner_status == "APPROVED")
            else:
                partner_status = "APPROVED"
                is_full_access = True

            with st.container(border=True):
                # st.markdown(f'<div class="{"product-card sold-out-card" if p.get("is_sold_out", False) else "product-card"}">', unsafe_allow_html=True)

                # --- 도매상 출처 뱃지 표시 ---
                st.markdown(f'<span style="background:#e2e8f0; color:#475569; padding:3px 8px; border-radius:10px; font-size:0.75rem; font-weight:bold; margin-bottom:10px; display:inline-block;">🏢 {product_store_id}</span>', unsafe_allow_html=True)

                if p.get("is_sold_out", False):
                    st.markdown('<div class="sold-out-badge">🔴 품절 (SOLD OUT)</div>', unsafe_allow_html=True)

                # ─── 갤러리 모드: 이미지 및 텍스트 정보는 모든 사용자에게 공개 ───
                if image_url:
                    if not image_url.startswith("http"):
                        # Public URL 사용으로 로딩 속도 10배 최적화 (서버 통신 제거)
                        image_url = db.supabase.storage.from_("product-images").get_public_url(image_url)
            
                    if image_url:
                        html_img = f'''
                        <div style="width: 100%; height: 350px; background-color: #f8fafc; border-radius: 8px; margin-bottom: 15px; display: flex; align-items: center; justify-content: center; overflow: hidden;">
                            <img src="{image_url}" style="width: 100%; height: 100%; object-fit: contain;">
                        </div>
                        '''
                        st.markdown(html_img, unsafe_allow_html=True)
                    else:
                        st.markdown('<div style="width: 100%; height: 350px; background-color: #f8fafc; border-radius: 8px; margin-bottom: 15px; display: flex; align-items: center; justify-content: center; color: #94a3b8; font-weight: bold;">📷 이미지를 불러올 수 없습니다</div>', unsafe_allow_html=True)
                else:
                    st.markdown('<div style="width: 100%; height: 350px; background-color: #f8fafc; border-radius: 8px; margin-bottom: 15px; display: flex; align-items: center; justify-content: center; color: #94a3b8; font-weight: bold;">📷 이미지 없음</div>', unsafe_allow_html=True)

                st.markdown(f'<div class="p-number">#{p_num}</div>', unsafe_allow_html=True)
                st.markdown(f'<div class="item-name">{item_name}</div>', unsafe_allow_html=True)

                color_html = "".join([f'<span class="tag">🎨 {c}</span>' for c in colors])
                size_html = "".join([f'<span class="tag">📏 {s}</span>' for s in sizes])
                st.markdown(f'<div>{color_html}{size_html}</div>', unsafe_allow_html=True)

                # ─── 미승인 소매상: 단가 정보 블라인드 및 파트너 신청 버튼 ───
                if not is_full_access:
                    st.markdown("<hr style='margin: 15px 0; border: none; border-top: 1px dashed #e2e8f0;'>", unsafe_allow_html=True)
                    if partner_status == "PENDING":
                        st.warning("⏳ **해당 도매상에게 단가 열람 승인 대기 중입니다.**")
                    else:
                        st.info("🔒 단가 및 상세 정보를 보려면 도매상의 승인이 필요합니다.")
                        if st.button("📋 단가 보기 (파트너 승인 신청)", type="primary", width='stretch', key=f"req_partner_{p_num}_{product_store_id}"):
                            succ, msg = db.create_partner_request(product_store_id, retailer_email)
                            if succ:
                                st.toast(f"[{product_store_id}] 도매상에게 파트너 승인 요청이 전송되었습니다!")
                                st.rerun()
                            else:
                                st.error(msg)
                    continue  # 아래의 단가 표시 및 예약 폼 렌더링 건너뜀

                price_html = f'''
                <div class="price-box">
                    <div class="retail-price">판매가: {retail_price:,}원</div>
                '''
                if not hide_wholesale:
                    price_html += f'<div class="wholesale-price">도매가: {wholesale_price:,}원</div>'
                price_html += '</div>'

                st.markdown(price_html, unsafe_allow_html=True)
        
                # --- Phase 7: 방송용 큐시트 담기 및 로그 추적 ---
                if is_retailer and is_full_access:
                    if p_num in st.session_state.get("my_cue_sheet", []):
                        if st.button("❌ 큐시트에서 빼기", key=f"remove_cart_{p_num}", width='stretch'):
                            st.session_state["my_cue_sheet"].remove(p_num)
                            st.rerun()
                    else:
                        if st.button("➕ 내 방송용 큐시트에 담기", key=f"add_cart_{p_num}", width='stretch'):
                            st.session_state["my_cue_sheet"].append(p_num)
                            # 담는 시점에 관심(클릭) 로그를 남깁니다.
                            click_source = "QR_SCAN" if url_store_id else "LINK_CLICK"
                            db.log_product_click(product_store_id, p_num, retailer_email, source=click_source)
                            st.toast(f"'{item_name}' 상품이 내 큐시트에 추가되었습니다!")
                            st.rerun()

                # --- Phase 4: 예약 및 주문 폼 (팝업 방식) ---
                if is_retailer:
                    st.markdown("<hr style='margin: 15px 0; border: none; border-top: 1px dashed #e2e8f0;'>", unsafe_allow_html=True)
                    
                    with st.popover("📦 예약하기 (모달 팝업)", width='stretch'):
                        st.markdown("#### 재고 선예약 요청")
                        req_qty = st.number_input("필요 수량 (개)", min_value=1, step=10, key=f"req_{p_num}")
                        if st.button("도매상에게 예약 요청 전송", key=f"req_btn_{p_num}", type="primary", width='stretch'):
                            click_source = "QR_SCAN" if url_store_id else "LINK_CLICK"
                            db.log_product_click(product_store_id, p_num, retailer_email, source=click_source)
                    
                            succ, msg = db.create_reservation(product_store_id, retailer_email, p_num, req_qty)
                            if succ:
                                st.toast("예약 요청이 전송되었습니다! [내 주문/예약 관리] 탭에서 확인하세요.")
                                st.rerun()
                            else:
                                st.error(msg)


    # 페이지네이션: 더 보기 버튼
    if len(visible_products) < len(filtered_products):
        st.markdown("<br>", unsafe_allow_html=True)
        if st.button("👇 더 보기 (Load More)", type="secondary", width='stretch'):
            st.session_state["page_size"] += 12
            st.rerun()

    # AI 챗봇 기능은 별도 뷰(views/ai_chat.py)로 분리되었습니다.
