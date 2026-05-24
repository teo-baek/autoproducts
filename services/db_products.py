import os
import re
from supabase import create_client, Client
import streamlit as st

class DBProducts:
    def clean_number(self, val):
        """숫자 형식의 데이터를 정수로 클렌징"""
        if pd.isna(val) or val == "" or str(val).lower() == "nan": return 0
        try: return int(float(str(val).replace(",", "")))
        except: return 0

    def sync_products_to_db(self, parsed_rows_data, file_list_map, store_id="test_store_01", supabase_url_map=None):
        """파싱된 엑셀 데이터를 Supabase에 일괄 저장합니다. (V2 정규화 스키마 적용)"""
        if not self.supabase:
            return False, "DB 접속 정보가 없습니다."

        try:
            # 1. 부모(products) 데이터 준비
            products_data_map = {}
            skus_data_list = [] # 나중에 product_id를 주입해야 함
            
            for row in parsed_rows_data:
                p_num_clean = re.sub(r'\.0$', '', str(row.get("p_number", ""))).strip()
                if not p_num_clean or p_num_clean.lower() == "nan": continue
                    
                if p_num_clean not in products_data_map:
                    if supabase_url_map and p_num_clean in supabase_url_map:
                        image_url = supabase_url_map[p_num_clean]
                    else:
                        file_id = file_list_map.get(p_num_clean, "") if file_list_map else ""
                        image_url = f"https://drive.google.com/thumbnail?id={file_id}&sz=w500" if file_id else ""
                    
                    products_data_map[p_num_clean] = {
                        "store_id": store_id,
                        "p_number": p_num_clean,
                        "item_name": str(row.get("item_name", "")),
                        "fabric_composition": str(row.get("fabric_composition", "")),
                        "origin": str(row.get("origin", "")),
                        "lead_time_days": str(row.get("lead_time_days", "")),
                        "description": str(row.get("description", "")),
                        "image_url": image_url
                    }
                else:
                    if not products_data_map[p_num_clean].get("description") and row.get("description"):
                        products_data_map[p_num_clean]["description"] = str(row["description"])

                # 자식(SKU) 임시 데이터 보관 (product_id는 아직 모름)
                c = str(row.get("color", "")).strip()
                s = str(row.get("size", "")).strip()
                if c.lower() == "nan": c = ""
                if s.lower() == "nan": s = ""
                
                skus_data_list.append({
                    "p_number": p_num_clean, # 나중에 매핑용
                    "color": c,
                    "size": s,
                    "wholesale_price": self.clean_number(row.get("wholesale")),
                    "retail_price": self.clean_number(row.get("retail")),
                    "stock": self.clean_number(row.get("stock"))
                })

            # 2. 부모 테이블(products) Bulk Upsert
            parent_insert_data = list(products_data_map.values())
            res_parent = self.supabase.table("products").upsert(
                parent_insert_data, 
                on_conflict="store_id,p_number"
            ).execute()
            
            # 3. 매핑을 위한 p_number -> id(UUID) 딕셔너리 생성
            inserted_parents = res_parent.data
            pnum_to_id = {p["p_number"]: p["id"] for p in inserted_parents}
            
            # 4. 자식 테이블(product_skus) 데이터 조립
            final_skus = []
            for sku in skus_data_list:
                parent_id = pnum_to_id.get(sku["p_number"])
                if parent_id:
                    final_skus.append({
                        "product_id": parent_id,
                        "color": sku["color"],
                        "size": sku["size"],
                        "wholesale_price": sku["wholesale_price"],
                        "retail_price": sku["retail_price"],
                        "stock": sku["stock"]
                    })
            
            # 5. 자식 테이블(product_skus) Bulk Upsert
            if final_skus:
                self.supabase.table("product_skus").upsert(
                    final_skus,
                    on_conflict="product_id,color,size"
                ).execute()

            return True, f"총 {len(parent_insert_data)}개의 제품 및 SKU가 완벽히 동기화되었습니다!"
            
        except Exception as e:
            return False, f"DB 저장 중 오류 발생: {e}"

    def get_products(self, store_id):
        """특정 도매상의 상품 목록과 하위 SKU를 모두 가져옵니다 (조인)."""
        if not self.supabase: return []
        try:
            res = self.supabase.table("products").select("*, product_skus(*)").eq("store_id", store_id).order("created_at", desc=True).execute()
            return res.data if res.data else []
        except Exception as e:
            print(f"Error fetching products: {e}")
            return []

    def update_product_sold_out(self, store_id, p_number, is_sold_out):
        """상품 전체 품절 토글"""
        if not self.supabase: return False, "DB 연동 안됨"
        try:
            self.supabase.table("products").update({"is_sold_out": is_sold_out}).eq("store_id", store_id).eq("p_number", p_number).execute()
            return True, "성공"
        except Exception as e:
            return False, f"오류: {e}"

    def delete_product(self, store_id, p_number):
        """상품과 관련 이미지를 삭제합니다. (CASCADE로 SKU 자동 삭제됨)"""
        if not self.supabase: return False, "DB 연동 안됨"
        try:
            safe_p_number = str(p_number).strip().replace("/", "_").replace("\\", "_")
            path = f"{store_id}/{safe_p_number}.jpg"
            try:
                self.supabase.storage.from_("product-images").remove([path])
            except: pass
            
            self.supabase.table("products").delete().eq("store_id", store_id).eq("p_number", p_number).execute()
            return True, "성공"
        except Exception as e:
            return False, f"오류: {e}"

    def update_product_details(self, store_id, p_number, item_name, description=""):
        """간단 상품 텍스트 정보 업데이트"""
        if not self.supabase: return False, "DB 연동 안됨"
        try:
            self.supabase.table("products").update({
                "item_name": item_name, 
                "description": description
            }).eq("store_id", store_id).eq("p_number", p_number).execute()
            return True, "성공"
        except Exception as e:
            return False, f"오류: {e}"

    def get_signed_image_url(self, path, expires_in=3600):
        if not self.supabase or not path: return ""
        try:
            if path.startswith("http"): return path
            res = self.supabase.storage.from_("product-images").create_signed_url(path, expires_in)
            if isinstance(res, dict) and "signedURL" in res: return res["signedURL"]
            return res
        except Exception as e:
            return ""

    def upload_product_image(self, file_bytes, store_id, p_number):
        if not self.supabase: return None
        try:
            safe_p_number = str(p_number).strip().replace("/", "_").replace("\\", "_")
            path = f"{store_id}/{safe_p_number}.jpg"
            self.supabase.storage.from_("product-images").upload(
                path=path, file=file_bytes, file_options={"content-type": "image/jpeg", "upsert": "true"}
            )
            return path
        except: return None
