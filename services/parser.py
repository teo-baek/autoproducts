import pandas as pd
import re

class ProductParser:
    def __init__(self):
        self.synonyms_pool = {
            "p_number": ['품번', '상품코드', '품목코드', '모델명'],
            "item_name": ['상품명', '품목명', '물품명', '제품명'],
            "color": ['색상', '컬러', '색상명'],
            "size": ['상세사이즈', '사이즈', '규격'],
            "mix_ratio": ['혼용률', '혼방률', '소재'],
            "wholesale": ['도매가', '도매단가', '입고가', '공급가'],
            "retail": ['소매가', '판매가', '소비자가', '매장판매가'],
            "stock": ['재고정상', '재고', '현재고', '매장량', '수량'],
            "description": ['상세설명', '비고', '상품설명', '설명']
        }

    def extract_folder_id(self, url):
        """구글 드라이브 URL에서 폴더 고유 ID를 추출하는 함수"""
        match = re.search(r"folders/([a-zA-Z0-9-_]+)", url)
        if match:
            return match.group(1)
        return url.strip()

    def clean_and_parse_price(self, price_val):
        """가격 데이터에서 쉼표나 문자를 제거하고 정수로 변환하는 함수"""
        if pd.isna(price_val):
            return 0
        try:
            price_str = re.sub(r'[^\d]', '', str(price_val))
            return int(price_str) if price_str else 0
        except:
            return 0

    def get_column_value_by_synonyms(self, row, df_columns, synonyms, default_val=""):
        """매장별로 다른 포스기 열 이름을 동의어 풀을 순회하며 감지하는 함수"""
        for synonym in synonyms:
            matched_col = [col for col in df_columns if str(col).strip() == synonym]
            if matched_col:
                val = row[matched_col[0]]
                return str(val).strip() if pd.notna(val) else default_val
        return default_val

    def parse_dataframe(self, df_raw):
        """데이터프레임을 순회하며 딕셔너리 리스트로 변환하는 메인 로직"""
        cols = df_raw.columns
        parsed_rows_data = []
        for idx, row in df_raw.iterrows():
            p_num_raw = self.get_column_value_by_synonyms(row, cols, self.synonyms_pool["p_number"])
            p_num = re.sub(r'\.0$', '', str(p_num_raw).strip())
            
            name = self.get_column_value_by_synonyms(row, cols, self.synonyms_pool["item_name"])
            col_val = self.get_column_value_by_synonyms(row, cols, self.synonyms_pool["color"])
            sz_val = self.get_column_value_by_synonyms(row, cols, self.synonyms_pool["size"], default_val="F")
            mix_val = self.get_column_value_by_synonyms(row, cols, self.synonyms_pool["mix_ratio"])
            
            wholesale_raw = self.get_column_value_by_synonyms(row, cols, self.synonyms_pool["wholesale"], default_val="0")
            retail_raw = self.get_column_value_by_synonyms(row, cols, self.synonyms_pool["retail"], default_val="0")
            
            wholesale_num = self.clean_and_parse_price(wholesale_raw)
            retail_num = self.clean_and_parse_price(retail_raw)
            
            wholesale_text = f"{wholesale_num:,}" if wholesale_num > 0 else "0"
            retail_text = f"{retail_num:,}" if retail_num > 0 else "0"
            
            stk_val = self.get_column_value_by_synonyms(row, cols, self.synonyms_pool["stock"], default_val="0")
            stk_val = re.sub(r'\.0$', '', stk_val)
            
            desc_val = self.get_column_value_by_synonyms(row, cols, self.synonyms_pool["description"], default_val="")
            
            # P_CODE 연산 후 최종 값 주입 방식 유지
            p_code_num1 = int(wholesale_num / 1000)
            p_code_num2 = int(retail_num / 1000)
            p_code_text = f"{p_code_num1}_{p_code_num2}"
            
            parsed_rows_data.append({
                "p_number": p_num, "item_name": name, "color": col_val, "size": sz_val,
                "mix_ratio": mix_val, "wholesale": wholesale_text, "retail": retail_text,
                "stock": stk_val, "p_code": p_code_text, "description": desc_val
            })
        return parsed_rows_data
