import streamlit as st

def apply_common_theme():
    """
    모든 페이지에 공통으로 적용될 프리미엄 통합 테마 CSS를 주입합니다.
    글로벌 사용자들도 편안하게 느낄 수 있는 눈이 편안한 색상 팔레트(Steel Blue, Muted Coral 등)를 사용합니다.
    """
    st.markdown("""
    <style>
        /* 글로벌 텍스트 색상 및 폰트 부드럽게 조정 */
        html, body, [class*="css"] {
            color: #334155; /* Slate 700: 순수 검정보다 눈에 편함 */
        }
        
        /* 알림/캡션 텍스트 */
        .streamlit-expanderHeader, .st-emotion-cache-1wivap2 {
            color: #718096; /* Slate 500 */
        }

        /* -------------------------------------
           통합 컴포넌트 스타일 (카드, 뱃지 등)
        -------------------------------------- */
        /* 프리미엄 카드 배경 */
        .premium-card {
            background-color: #FAFBFC; /* Off-White */
            border: 1px solid #E2E8F0;
            border-radius: 12px;
            padding: 20px;
            box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.05);
            margin-bottom: 1rem;
        }

        /* 상태 뱃지 (품절, 위험 등) */
        .badge-danger {
            background-color: #D4726A; /* Muted Coral */
            color: white;
            padding: 4px 10px;
            border-radius: 12px;
            font-size: 0.8rem;
            font-weight: 600;
        }
        
        .badge-success {
            background-color: #6BAF8D; /* Mint Sage */
            color: white;
            padding: 4px 10px;
            border-radius: 12px;
            font-size: 0.8rem;
            font-weight: 600;
        }
        
        .badge-warning {
            background-color: #F6AD55; /* Muted Orange */
            color: white;
            padding: 4px 10px;
            border-radius: 12px;
            font-size: 0.8rem;
            font-weight: 600;
        }

        /* -------------------------------------
           과거 파편화된 CSS 클래스 통합 매핑
        -------------------------------------- */
        /* manage_products.py 의 리스트 행 */
        .product-row {
            background: #FAFBFC;
            border: 1px solid #E2E8F0;
            padding: 12px 16px;
            border-radius: 12px;
            margin-bottom: 12px;
            display: flex;
            align-items: center;
            justify-content: space-between;
            box-shadow: 0 1px 3px rgba(0,0,0,0.02);
            transition: all 0.2s ease-in-out;
        }
        .product-row:hover {
            box-shadow: 0 4px 6px rgba(0,0,0,0.04);
            transform: translateY(-1px);
        }
        .product-row-info { 
            font-weight: 600; 
            color: #334155; 
        }
        /* 이전 .product-row-badge 를 badge-danger 로 대체 유도, 하위 호환 유지 */
        .product-row-badge { 
            background: #D4726A; 
            color: white; 
            padding: 4px 10px; 
            border-radius: 12px; 
            font-size: 0.8rem; 
            margin-right: 12px;
            font-weight: 600;
        }

        /* billing.py 스타일 */
        .billing-container {
            max-width: 600px;
            margin: 0 auto;
            text-align: center;
            padding: 40px 20px;
        }
        .billing-icon { font-size: 4rem; margin-bottom: 15px; }
        .billing-title {
            font-size: 1.8rem;
            font-weight: 800;
            color: #334155;
            margin-bottom: 10px;
        }
        .billing-desc {
            color: #718096;
            font-size: 1rem;
            margin-bottom: 30px;
            line-height: 1.6;
        }
        .account-box {
            background: linear-gradient(135deg, #FAFBFC, #F1F5F9);
            border: 2px solid #CBD5E1;
            border-radius: 16px;
            padding: 25px;
            margin: 20px 0;
            box-shadow: 0 4px 6px rgba(0,0,0,0.02);
        }
        .account-box h4 { color: #4F7CAC; margin: 0 0 12px 0; font-size: 1.1rem; font-weight: 700; }
        .account-info { font-size: 1.2rem; font-weight: 700; color: #334155; }
        .status-waiting {
            background: #FFF5F5;
            border: 1px solid #FED7D7;
            border-radius: 12px;
            padding: 15px;
            margin-top: 20px;
            color: #C53030;
            font-weight: 600;
        }
        
        /* 로그인 페이지 스타일 */
        .login-title {
            font-size: 2.5rem;
            font-weight: 900;
            color: #4F7CAC;
            text-align: center;
            margin-bottom: 0.5rem;
            letter-spacing: -0.05em;
        }
        .login-subtitle {
            font-size: 1.1rem;
            color: #718096;
            text-align: center;
            margin-bottom: 2rem;
            font-weight: 500;
        }
        
        /* -------------------------------------
           반응형 레이아웃 오버라이드 (Mobile)
        -------------------------------------- */
        @media (max-width: 768px) {
            /* 큐시트 모바일에서 컬럼 스택 */
            .st-emotion-cache-1wivap2 {
                flex-direction: column !important;
            }
        }
    </style>
    """, unsafe_allow_html=True)
