"""
AutoProducts 실시간 통계 & STR 분석 대시보드
도매상 전용 페이지로, 소매상들의 관심(클릭) 및 전환율 지표를 시각화합니다.
"""
import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
from services.database import DatabaseConnector

def show():
    # --- Aesthetics ---
    st.markdown("""
    <style>
        .kpi-card {
            background: linear-gradient(135deg, #1e293b 0%, #0f172a 100%);
            color: white;
            border-radius: 16px;
            padding: 20px;
            box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1);
        }
        .kpi-title {
            color: #94a3b8;
            font-size: 0.95rem;
            font-weight: 600;
            margin-bottom: 8px;
        }
        .kpi-value {
            font-size: 2rem;
            font-weight: 800;
        }
        .kpi-sub {
            color: #cbd5e1;
            font-size: 0.85rem;
            margin-top: 5px;
        }
    </style>
    """, unsafe_allow_html=True)

    st.title("📊 실시간 통계 & STR 분석")
    st.caption("소매상 파트너들의 상품 관심도와 예약 전환율(STR)을 실시간으로 추적합니다.")

    db = DatabaseConnector()
    if not db.supabase:
        st.error("데이터베이스 연동이 필요합니다.")
        return

    current_store_id = st.session_state.get("store_id", "test_store_01")

    # 1. 상단 필터
    col_filter, _ = st.columns([1, 2])
    with col_filter:
        time_filter = st.selectbox("📅 분석 기간", ["최근 7일", "최근 30일", "전체 기간"])
        
    if time_filter == "최근 7일":
        days = 7
    elif time_filter == "최근 30일":
        days = 30
    else:
        days = 3650 # 사실상 전체 기간

    # 데이터 로딩
    with st.spinner("데이터를 분석 중입니다..."):
        # 클릭 트렌드
        trend_data = db.get_daily_click_trend(current_store_id, days=days)
        # 인기 Top 5
        top_products = db.get_top_products_clicked(current_store_id, limit=5)
        # 유입 경로
        sources = db.get_click_sources(current_store_id)
        # 전환율
        conversion_rate = db.get_reservation_conversion_rate(current_store_id)
        
    # --- KPI 요약 카드 데이터 세팅 ---
    total_clicks = len(trend_data)
    best_item = top_products[0]["p_number"] if top_products else "없음"
    best_item_clicks = top_products[0].get("clicks", 0) if top_products else 0

    # --- AI 인사이트 브리핑 (Daily Cache) ---
    st.markdown("<br/>", unsafe_allow_html=True)
    st.subheader("💡 AI 비즈니스 인사이트")
    
    # 오늘 날짜 기준으로 캐시키 생성 (하루 1번만 API 호출되도록 최적화)
    today_str = datetime.now().strftime("%Y-%m-%d")
    cache_key = f"ai_insight_{current_store_id}_{today_str}"
    
    if cache_key not in st.session_state:
        with st.spinner("AI 매니저가 오늘의 비즈니스 리포트를 작성하고 있습니다... (하루 1회)"):
            try:
                # 평균 파트너 신뢰도 계산 (예외 발생 시 100으로 폴백)
                avg_rel = 100
                try:
                    res_p = db.supabase.table("partner_requests").select("*").eq("wholesaler_store_id", current_store_id).eq("status", "APPROVED").execute()
                    if res_p.data:
                        avg_rel = sum([r.get("seller_reliability_score", 100) for r in res_p.data]) / len(res_p.data)
                except Exception as db_e:
                    print(f"Warning: Failed to fetch reliability score, defaulting to 100. ({db_e})")
                
                stats_data = {
                    "time_filter": time_filter,
                    "total_clicks": total_clicks,
                    "conversion_rate": round(conversion_rate, 1),
                    "best_item_num": best_item,
                    "best_item_clicks": best_item_clicks,
                    "avg_reliability": round(avg_rel, 1)
                }
                
                from services.ai_agent import AIAgentService
                ai_service = AIAgentService()
                insight_text = ai_service.generate_analytics_insight(stats_data)
                st.session_state[cache_key] = insight_text
            except Exception as e:
                st.session_state[cache_key] = f"💡 통계 요약 중 오류가 발생했습니다. ({e})"
                
    st.info(st.session_state[cache_key])
    
    st.markdown("<br/>", unsafe_allow_html=True)
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        st.markdown(f"""
        <div class="kpi-card">
            <div class="kpi-title">👁️ 누적 관심(조회) 수</div>
            <div class="kpi-value">{total_clicks:,}회</div>
            <div class="kpi-sub">{time_filter} 기준</div>
        </div>
        """, unsafe_allow_html=True)
    with c2:
        st.markdown(f"""
        <div class="kpi-card">
            <div class="kpi-title">🔥 최고 인기 상품</div>
            <div class="kpi-value">#{best_item}</div>
            <div class="kpi-sub">가장 많은 큐시트 클릭</div>
        </div>
        """, unsafe_allow_html=True)
    with c3:
        conversion_str = f"{conversion_rate:.1f}%"
        st.markdown(f"""
        <div class="kpi-card">
            <div class="kpi-title">⚡ 예약 전환율 (STR)</div>
            <div class="kpi-value">{conversion_str}</div>
            <div class="kpi-sub">조회 대비 실제 예약 비중</div>
        </div>
        """, unsafe_allow_html=True)
    with c4:
        qr_count = sources.get("QR_SCAN", 0)
        link_count = sources.get("LINK_CLICK", 0)
        st.markdown(f"""
        <div class="kpi-card">
            <div class="kpi-title">📱 주요 유입 경로</div>
            <div class="kpi-value">{"QR" if qr_count >= link_count else "링크"}</div>
            <div class="kpi-sub">QR: {qr_count} / 링크: {link_count}</div>
        </div>
        """, unsafe_allow_html=True)

    st.markdown("<br/>", unsafe_allow_html=True)

    # --- 트렌드 분석 및 랭킹 ---
    col_trend, col_rank = st.columns([2, 1])
    
    with col_trend:
        st.subheader("📈 일자별 클릭 유입 트렌드")
        if trend_data:
            # 날짜별로 그룹화
            df = pd.DataFrame(trend_data)
            df['date'] = pd.to_datetime(df['created_at']).dt.date
            daily_counts = df.groupby('date').size().reset_index(name='clicks')
            # 차트 시각화
            st.area_chart(daily_counts.set_index('date'), width='stretch')
        else:
            st.info("선택한 기간 내에 트렌드 데이터가 없습니다.")

    with col_rank:
        st.subheader("🏆 인기 상품 Top 5")
        if top_products:
            top_df = pd.DataFrame(top_products)
            top_df.columns = ["품번", "클릭 수"]
            st.dataframe(top_df, width='stretch', hide_index=True)
            # st.bar_chart로도 표현
            st.bar_chart(top_df.set_index("품번"))
        else:
            st.info("인기 상품 데이터가 없습니다.")

    st.markdown("---")

    # --- 추가: 소매상별 STR 파트너 기여도 분석 ---
    st.subheader("🤝 단골 파트너별 신뢰도 및 예약 기여율")
    st.caption("파트너 소매상들이 남긴 예약 실적 및 노쇼 데이터를 기반으로 VIP를 선별하세요.")
    
    try:
        res_w = db.supabase.table("store_profiles").select("id").eq("store_id", current_store_id).execute()
        if res_w.data:
            w_id = res_w.data[0]["id"]
            # 파트너 정보 가져오기 (오류 방지를 위해 * 선택 후 파이썬에서 키 매핑)
            partners = db.supabase.table("partner_requests").select("*").eq("wholesaler_store_id", current_store_id).eq("status", "APPROVED").execute()
            if partners.data:
                parsed_data = []
                for row in partners.data:
                    parsed_data.append({
                        "소매상 이메일": row.get("retailer_email", "알 수 없음"),
                        "신뢰 점수": row.get("seller_reliability_score", 100),
                        "노쇼 횟수": row.get("no_show_count", 0),
                        "등급": row.get("grade", "Normal"),
                        "상태": row.get("status", "")
                    })
                pdf = pd.DataFrame(parsed_data)
                # 시각적인 개선을 위해
                st.dataframe(pdf, width='stretch', hide_index=True)
            else:
                st.info("아직 승인된 파트너가 없습니다.")
    except Exception as e:
        st.warning(f"파트너 데이터를 불러오는 중 오류가 발생했습니다. {e}")
