"""
AutoProducts AI Agent Service
Google Gemini API를 활용하여 도매상용 AI CS 비서 및 스마트 검색 기능을 제공합니다.
"""
import streamlit as st
import google.generativeai as genai
import json

class AIAgentService:
    def __init__(self):
        self.api_key = st.secrets.get("GEMINI_API_KEY", "")
        if self.api_key:
            genai.configure(api_key=self.api_key)
            # 최신 모델 사용
            self.model = genai.GenerativeModel('gemini-2.5-flash')
        else:
            self.model = None

    def _build_system_prompt(self, retailer_info, product_context):
        """
        AI 도매 매니저의 페르소나 및 비즈니스 룰을 정의하는 시스템 프롬프트.
        """
        # 소매상 정보 파싱
        score = retailer_info.get("seller_reliability_score", 100)
        grade = retailer_info.get("grade", "Normal")
        no_show = retailer_info.get("no_show_count", 0)

        # 시스템 프롬프트
        prompt = f"""
당신은 동대문 도매 시장에서 일하는 10년 차 베테랑 B2B 도매 매니저 '오토프로덕츠 AI'입니다.
현재 접속한 소매상(파트너)의 정보와 우리 매장의 상품 목록을 기반으로 친절하고 센스 있게 응대하세요.

[접속한 소매상(파트너) 정보]
- 신뢰 점수: {score}점
- 등급: {grade}
- 과거 노쇼 횟수: {no_show}회

[우리의 비즈니스 룰 - 매우 중요]
1. 위장 소비자 방어 (낱장/샘플 구매 정책)
   - 소매상이 1장만 샘플로 사고 싶다고 하거나, 일반인처럼 낱장 구매를 문의할 경우 절대 화내거나 바로 내쫓지 마세요.
   - 대신, "현재 낱장(샘플) 구매는 도매가의 1.8배 가격으로 우선 제공 가능합니다. 추후 대량 발주 시 이번 샘플 구매에서 발생한 차액만큼 시원하게 빼드리겠습니다!" 라고 정중하게 영업하세요.
2. 단가 협의 (네고 룰)
   - 기본적으로 단가 할인은 엄격하나, 대량 주문 시 아래 룰을 따릅니다.
   - 30장 이상 주문 시: 전체 금액의 5% 할인 제안 가능.
   - 100장 이상 주문 시: 전체 금액의 10% 할인 제안 가능.
   - 위 수량에 도달하지 않으면 할인이 어렵다고 정중히 거절하세요.
3. 재고 및 상품 안내 (검색 비서 역할)
   - 소매상이 특정 색상, 스타일, 옷 종류를 찾으면 [매장 상품 리스트]를 참고하여 해당하는 '품번(p_number)'과 가격을 알려주고 추천하세요.

[매장 상품 리스트 (JSON 형식)]
{json.dumps(product_context, ensure_ascii=False, indent=2)}

[답변 가이드라인]
- 도매 시장 특유의 친근하면서도 프로페셔널한 말투를 사용하세요. ("사장님~", "네 사장님!", "맞춰드릴게요" 등)
- 거짓말을 하지 마세요. 상품 리스트에 없는 상품은 없다고 말하세요.
- 답변은 너무 길지 않게 핵심만 짚어서 전달하세요.
"""
        return prompt

    def filter_relevant_products(self, message, all_products, max_count=10):
        """
        Phase 9: 소매상 메시지에서 키워드를 추출하여 관련 상품만 최대 max_count개 필터링합니다.
        전체 카탈로그를 LLM에 주입하지 않고, 텍스트 매칭으로 1차 선별하여 토큰 비용을 절감합니다.
        """
        msg_lower = message.lower()
        # 한글/영문 공백 기준 토큰화
        keywords = [w.strip() for w in msg_lower.split() if len(w.strip()) >= 2]
        
        if not keywords:
            # 키워드가 없으면 (예: "안녕하세요") 최근 등록 상품 상위 max_count개 반환
            return all_products[:max_count]
        
        scored = []
        for p in all_products:
            score = 0
            searchable = f"{p.get('p_number', '')} {p.get('item_name', '')}".lower()
            # variants 내 color, size 정보도 검색 대상에 포함
            variants = p.get('variants', [])
            if isinstance(variants, str):
                try:
                    variants = json.loads(variants)
                except:
                    variants = []
            for v in variants:
                searchable += f" {v.get('color', '')} {v.get('size', '')}".lower()
            
            for kw in keywords:
                if kw in searchable:
                    score += 1
            
            if score > 0:
                scored.append((score, p))
        
        # 점수 내림차순 정렬 후 max_count개 반환
        scored.sort(key=lambda x: x[0], reverse=True)
        results = [item[1] for item in scored[:max_count]]
        
        # 매칭 결과가 없으면 최근 상품 상위 max_count개 폴백
        if not results:
            return all_products[:max_count]
        
        return results

    def generate_response(self, retailer_info, product_context, chat_history, message):
        """
        소매상의 메시지에 대한 AI 응답을 생성합니다.
        product_context는 이미 filter_relevant_products()로 선별된 최대 10개의 상품만 포함합니다.
        """
        if not self.model:
            return "시스템에 API 키가 설정되지 않아 AI 매니저를 호출할 수 없습니다."

        try:
            system_prompt = self._build_system_prompt(retailer_info, product_context)
            
            model = genai.GenerativeModel(
                model_name='gemini-2.5-flash',
                system_instruction=system_prompt
            )

            # 기존 대화 내역 변환 (Streamlit format -> Gemini format)
            gemini_history = []
            for chat in chat_history:
                role = "user" if chat["role"] == "user" else "model"
                gemini_history.append({"role": role, "parts": [chat["content"]]})

            # 채팅 세션 시작
            chat_session = model.start_chat(history=gemini_history)
            
            # 새 메시지 전송
            response = chat_session.send_message(message)
            return response.text

        except Exception as e:
            print(f"AI Agent Error: {e}")
            return "죄송합니다 사장님! 지금 매장에 손님이 많아 확인이 늦어지고 있습니다. 잠시 후 다시 말씀해 주세요."

    def semantic_search(self, query, all_products):
        """
        자연어 검색 쿼리를 바탕으로 가장 적합한 상품 번호(p_number) 리스트를 추론하여 반환합니다.
        """
        if not self.model or not all_products:
            return []

        # 불필요한 데이터를 줄여 토큰 낭비를 막기 위해 이름, 번호, 옵션만 추출
        simplified_products = []
        for p in all_products:
            simplified_products.append({
                "p_number": p.get("p_number"),
                "item_name": p.get("item_name"),
                "description": p.get("description", ""),
                "variants": p.get("variants")
            })

        system_instruction = """
        당신은 의류 도매 시장의 전문 상품 검색 에이전트입니다.
        주어진 [상품 카탈로그]를 바탕으로, 소매상의 [자연어 검색어]에 가장 부합하는 상품들을 찾아야 합니다.
        결과는 반드시 추천하는 상품들의 'p_number' 값들만 포함된 순수 JSON 배열 형식으로 출력하세요. (최대 10개)
        설명이나 텍스트를 절대 덧붙이지 마세요. 
        예시 출력: ["101", "105", "203"]
        """

        prompt = f"""
        [자연어 검색어]
        {query}

        [상품 카탈로그]
        {json.dumps(simplified_products, ensure_ascii=False)}
        """

        try:
            model = genai.GenerativeModel(
                model_name='gemini-2.5-flash',
                system_instruction=system_instruction
            )
            response = model.generate_content(prompt)
            # JSON 배열 추출
            text = response.text.strip()
            if text.startswith("```json"):
                text = text.replace("```json", "").replace("```", "").strip()
            elif text.startswith("```"):
                text = text.replace("```", "").strip()
                
            matched_p_numbers = json.loads(text)
            if isinstance(matched_p_numbers, list):
                return matched_p_numbers
            return []
        except Exception as e:
            print(f"AI Semantic Search Error: {e}")
            return []

    def generate_analytics_insight(self, stats_data):
        """
        도매상 통계 데이터를 바탕으로 3줄짜리 비즈니스 인사이트를 생성합니다.
        """
        if not self.model:
            return "💡 AI 인사이트 기능이 비활성화되어 있습니다. (API KEY 미설정)"

        system_instruction = """
        당신은 동대문 의류 도매 시장의 비즈니스 컨설턴트입니다.
        주어진 데이터를 분석하여 도매상(사장님)이 재고 준비나 마케팅에 참고할 수 있는 핵심 조언을 딱 3줄로 요약해서 제공하세요.
        말투는 친근하고 프로페셔널하게 작성하세요. (예: "사장님, 현재 청바지의 인기가 뜨겁습니다...")
        """

        prompt = f"""
        [최근 통계 요약 데이터]
        - 분석 기준: {stats_data.get('time_filter', '최근')}
        - 누적 상품 조회(클릭) 수: {stats_data.get('total_clicks', 0)}회
        - 조회 대비 예약 전환율(STR): {stats_data.get('conversion_rate', 0)}%
        - 조회수 1위 상품: 품번 {stats_data.get('best_item_num', '')} ({stats_data.get('best_item_clicks', 0)}회 클릭됨)
        - 파트너(소매상) 평균 신뢰도: {stats_data.get('avg_reliability', 0)}점

        위 데이터를 바탕으로 도매상이 지금 취해야 할 액션(리오더, 단가 점검 등)을 3줄로 브리핑해주세요.
        """

        try:
            model = genai.GenerativeModel(
                model_name='gemini-2.5-flash',
                system_instruction=system_instruction
            )
            response = model.generate_content(prompt)
            return response.text
        except Exception as e:
            print(f"AI Insight Error: {e}")
            return "💡 통계 분석 중 오류가 발생했습니다. 잠시 후 다시 시도해주세요."

