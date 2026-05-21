import os
from supabase import create_client, Client
import streamlit as st
import pandas as pd
from datetime import datetime
import json

class DBProducts:
    def sync_products_to_db(self, parsed_rows_data, file_list_map, store_id="test_store_01", supabase_url_map=None):
        """파싱된 엑셀 데이터를 Supabase 'products' 테이블에 일괄 저장(백업)합니다.
           같은 품번(p_number)을 가진 행들의 옵션(색상, 사이즈 등)을 JSONB 배열(variants)로 묶어 압축합니다.
        """
        if not self.supabase:
            return False, "DB 접속 정보(secrets.toml)가 설정되지 않아 클라우드 저장을 건너뛰었습니다."

        try:
            # 1. 품번(p_number) 기준으로 데이터 그룹화
            grouped_data = {}
            for row in parsed_rows_data:
                p_num_clean = re.sub(r'\.0$', '', str(row["p_number"]).strip())
                
                # 품번 누락 데이터는 제외
                if not p_num_clean or p_num_clean.lower() == "nan":
                    continue
                    
                color_val = str(row["color"]).strip()
                if color_val.lower() == "nan": color_val = ""
                
                size_val = str(row["size"]).strip()
                if size_val.lower() == "nan": size_val = ""
                
                # 옵션 단일 객체 생성
                variant_obj = {
                    "color": color_val,
                    "size": size_val,
                    "mix_ratio": str(row["mix_ratio"]),
                    "wholesale": self.clean_number(row["wholesale"]),
                    "retail": self.clean_number(row["retail"]),
                    "stock": self.clean_number(row["stock"])
                }
                
                if p_num_clean not in grouped_data:
                    # supabase_url_map(드라이브→Supabase 이전된 URL)이 있으면 우선 사용, 없으면 Drive 썸네일 URL 폴백
                    if supabase_url_map and p_num_clean in supabase_url_map:
                        image_url = supabase_url_map[p_num_clean]
                    else:
                        file_id = file_list_map.get(p_num_clean, "") if file_list_map else ""
                        image_url = f"https://drive.google.com/thumbnail?id={file_id}&sz=w500" if file_id else ""
                    
                    grouped_data[p_num_clean] = {
                        "store_id": store_id,
                        "p_number": p_num_clean,
                        "item_name": str(row["item_name"]),
                        "image_url": image_url,
                        "description": str(row.get("description", "")),
                        "variants": [variant_obj] # JSON 배열의 시작
                    }
                else:
                    # 이미 존재하는 품번이면 variants 배열에 옵션만 추가
                    grouped_data[p_num_clean]["variants"].append(variant_obj)
                    # 기존 설명이 비어있고 현재 행에 설명이 있다면 병합
                    if not grouped_data[p_num_clean].get("description") and row.get("description"):
                        grouped_data[p_num_clean]["description"] = str(row["description"])

            # 2. Supabase에 넣을 최종 데이터 리스트 생성
            insert_data = list(grouped_data.values())

            # 3. Supabase에 데이터 일괄 삽입 및 업데이트 (Upsert)
            # JSONB 구조이므로 이제 (store_id, p_number) 단 두 개만으로 완벽한 고유 키가 됩니다.
            data, count = self.supabase.table("products").upsert(
                insert_data, 
                on_conflict="store_id,p_number"
            ).execute()
            return True, f"총 {len(insert_data)}개의 제품(품번 기준)이 클라우드 DB에 JSON 형태로 완벽히 동기화되었습니다!"
            
        except Exception as e:
            return False, f"DB 저장 중 오류 발생: {e}"

    def upload_product_image(self, file_bytes, store_id, p_number):
        """Supabase Storage에 이미지를 업로드하고 Public URL을 반환합니다."""
        if not self.supabase:
            return None
        
        try:
            # 안전한 파일명 생성 (확장자는 기본적으로 jpg로 통일)
            safe_p_number = str(p_number).strip().replace("/", "_").replace("\\", "_")
            # 스토어ID 단위로 폴더 분리
            path = f"{store_id}/{safe_p_number}.jpg"
            
            # 이미 존재하는 파일 덮어쓰기 (upsert)
            res = self.supabase.storage.from_("product-images").upload(
                path=path,
                file=file_bytes,
                file_options={"content-type": "image/jpeg", "upsert": "true"}
            )
            
            # 보안을 위해 Private Storage Path 반환 (나중에 Signed URL로 변환)
            return path
        except Exception as e:
            print(f"Storage upload error: {e}")
            return None

    def get_signed_image_url(self, path, expires_in=3600):
        """Private 스토리지의 파일에 접근하기 위한 임시 서명된 URL을 생성합니다. 기본 1시간(3600초)"""
        if not self.supabase or not path: return ""
        try:
            # path가 이미 http 주소라면 레거시 데이터이므로 그대로 반환
            if path.startswith("http"):
                return path
            # 서명된 URL 발급
            res = self.supabase.storage.from_("product-images").create_signed_url(path, expires_in)
            if isinstance(res, dict) and "signedURL" in res:
                return res["signedURL"]
            return res
        except Exception as e:
            print(f"Signed URL error: {e}")
            return ""

    def insert_single_product(self, store_id, p_number, item_name, image_url, wholesale, retail, color, size):
        """개별 상품을 DB에 즉시 등록(또는 업데이트)합니다."""
        if not self.supabase:
            return False, "DB 연결 정보가 없습니다."
        
        p_num_clean = str(p_number).strip()
        if not p_num_clean:
            return False, "품번은 필수입니다."
            
        variant_obj = {
            "color": str(color).strip(),
            "size": str(size).strip(),
            "mix_ratio": "",
            "wholesale": self.clean_number(wholesale),
            "retail": self.clean_number(retail),
            "stock": 0
        }
        
        insert_data = {
            "store_id": store_id,
            "p_number": p_num_clean,
            "item_name": item_name,
            "image_url": image_url,
            "description": "",
            "variants": [variant_obj]
        }
        
        try:
            self.supabase.table("products").upsert(insert_data, on_conflict="store_id,p_number").execute()
            return True, "성공적으로 등록되었습니다."
        except Exception as e:
            return False, f"DB 등록 중 오류: {e}"

    def update_product_image(self, store_id, p_number, image_url):
        """DB에 특정 상품의 image_url만 업데이트합니다."""
        if not self.supabase: return False
        try:
            self.supabase.table("products").update({"image_url": image_url}).eq("store_id", store_id).eq("p_number", p_number).execute()
            return True
        except:
            return False

    def update_product_sold_out(self, store_id, p_number, is_sold_out):
        """상품의 품절 상태를 업데이트합니다."""
        if not self.supabase: return False, "DB 연동 안됨"
        try:
            self.supabase.table("products").update({"is_sold_out": is_sold_out}).eq("store_id", store_id).eq("p_number", p_number).execute()
            return True, "성공"
        except Exception as e:
            return False, f"오류: {e}"

    def update_product_details(self, store_id, p_number, item_name, variants, description=""):
        """상품 정보를 수정합니다."""
        if not self.supabase: return False, "DB 연동 안됨"
        try:
            self.supabase.table("products").update({
                "item_name": item_name, 
                "variants": variants,
                "description": description
            }).eq("store_id", store_id).eq("p_number", p_number).execute()
            return True, "성공"
        except Exception as e:
            return False, f"오류: {e}"

    def delete_product(self, store_id, p_number):
        """상품과 관련 이미지를 삭제합니다."""
        if not self.supabase: return False, "DB 연동 안됨"
        try:
            safe_p_number = str(p_number).strip().replace("/", "_").replace("\\", "_")
            path = f"{store_id}/{safe_p_number}.jpg"
            try:
                self.supabase.storage.from_("product-images").remove([path])
            except:
                pass
            self.supabase.table("products").delete().eq("store_id", store_id).eq("p_number", p_number).execute()
            return True, "성공"
        except Exception as e:
            return False, f"오류: {e}"

    def get_products(self, store_id):
        """특정 도매상의 상품 목록을 가져옵니다."""
        if not self.supabase: return []
        try:
            res = self.supabase.table("products").select("*").eq("store_id", store_id).execute()
            return res.data if res.data else []
        except Exception as e:
            print(f"Error fetching products: {e}")
            return []

