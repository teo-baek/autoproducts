import os
from supabase import create_client, Client
import streamlit as st
import pandas as pd
from datetime import datetime
import json

class DBAnalytics:
    def log_product_click(self, wholesaler_store_id, p_number, retailer_email, source='LINK_CLICK'):
        """소매상의 상품 조회/클릭 로그를 남깁니다."""
        if not self.supabase: return False
        try:
            # 1. 도매상의 UUID 조회 (store_id -> id)
            res_w = self.supabase.table("store_profiles").select("id").eq("store_id", wholesaler_store_id).execute()
            if not res_w.data: return False
            wholesaler_uuid = res_w.data[0]["id"]

            # 2. 소매상의 UUID 조회 (retailer_email -> id)
            res_r = self.supabase.table("store_profiles").select("id").eq("email", retailer_email).execute()
            if not res_r.data: return False
            retailer_uuid = res_r.data[0]["id"]

            # 3. 로그 삽입
            self.supabase.table("product_clicks").insert({
                "store_id": wholesaler_uuid,
                "p_number": p_number,
                "retailer_id": retailer_uuid,
                "source": source
            }).execute()
            return True
        except Exception as e:
            print(f"log_product_click error: {e}")
            return False

    def get_daily_click_trend(self, wholesaler_store_id, days=7):
        """최근 N일간의 도매상 총 클릭 수 트렌드를 반환합니다."""
        if not self.supabase: return []
        try:
            res_w = self.supabase.table("store_profiles").select("id").eq("store_id", wholesaler_store_id).execute()
            if not res_w.data: return []
            wholesaler_uuid = res_w.data[0]["id"]
            
            import datetime
            cutoff = datetime.datetime.utcnow() - datetime.timedelta(days=days)
            cutoff_iso = cutoff.isoformat()
            
            res = self.supabase.table("product_clicks") \
                .select("created_at") \
                .eq("store_id", wholesaler_uuid) \
                .gte("created_at", cutoff_iso) \
                .execute()
                
            return res.data or []
        except:
            return []

    def get_top_products_clicked(self, wholesaler_store_id, limit=5):
        """클릭수 기준 상위 N개 상품과 클릭수를 반환합니다."""
        if not self.supabase: return []
        try:
            res_w = self.supabase.table("store_profiles").select("id").eq("store_id", wholesaler_store_id).execute()
            if not res_w.data: return []
            wholesaler_uuid = res_w.data[0]["id"]
            
            res = self.supabase.table("product_clicks").select("p_number").eq("store_id", wholesaler_uuid).execute()
            if not res.data: return []
            
            from collections import Counter
            counts = Counter(row["p_number"] for row in res.data)
            top_items = counts.most_common(limit)
            return [{"p_number": k, "clicks": v} for k, v in top_items]
        except:
            return []

    def get_click_sources(self, wholesaler_store_id):
        """QR_SCAN vs LINK_CLICK 비율 계산"""
        if not self.supabase: return {}
        try:
            res_w = self.supabase.table("store_profiles").select("id").eq("store_id", wholesaler_store_id).execute()
            if not res_w.data: return {}
            wholesaler_uuid = res_w.data[0]["id"]
            
            res = self.supabase.table("product_clicks").select("source").eq("store_id", wholesaler_uuid).execute()
            if not res.data: return {}
            
            sources = [row["source"] for row in res.data]
            return {"QR_SCAN": sources.count("QR_SCAN"), "LINK_CLICK": sources.count("LINK_CLICK")}
        except:
            return {}

    def get_reservation_conversion_rate(self, wholesaler_store_id):
        """조회 대비 실제 예약 전환율을 계산하여 반환합니다."""
        if not self.supabase: return 0.0
        try:
            res_w = self.supabase.table("store_profiles").select("id").eq("store_id", wholesaler_store_id).execute()
            if not res_w.data: return 0.0
            wholesaler_uuid = res_w.data[0]["id"]
            
            res_clicks = self.supabase.table("product_clicks").select("id", count="exact").eq("store_id", wholesaler_uuid).execute()
            total_clicks = res_clicks.count if hasattr(res_clicks, 'count') and res_clicks.count is not None else len(res_clicks.data or [])
            if total_clicks == 0: return 0.0
            
            res_resv = self.supabase.table("product_reservations").select("id", count="exact").eq("store_id", wholesaler_store_id).execute()
            total_resv = res_resv.count if hasattr(res_resv, 'count') and res_resv.count is not None else len(res_resv.data or [])
            
            return (total_resv / total_clicks) * 100
        except:
            return 0.0

