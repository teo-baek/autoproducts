import os
from supabase import create_client, Client
import streamlit as st
import pandas as pd
from datetime import datetime
import json

class DBUsers:
    def get_partner_status(self, wholesaler_store_id, retailer_email):
        """소매상의 파트너십 상태를 반환합니다. (None, 'PENDING', 'APPROVED', 'REJECTED')"""
        if not self.supabase: return None
        try:
            res = self.supabase.table("partner_requests") \
                .select("status") \
                .eq("wholesaler_store_id", wholesaler_store_id) \
                .eq("retailer_email", retailer_email) \
                .maybe_single() \
                .execute()
            if res.data:
                return res.data.get("status")
            return None
        except:
            return None

    def create_partner_request(self, wholesaler_store_id, retailer_email):
        """소매상이 도매상의 카탈로그 접근 권한을 요청합니다."""
        if not self.supabase: return False, "DB 연동 안됨"
        try:
            self.supabase.table("partner_requests").upsert({
                "wholesaler_store_id": wholesaler_store_id,
                "retailer_email": retailer_email,
                "status": "PENDING"
            }, on_conflict="wholesaler_store_id,retailer_email").execute()
            return True, "성공"
        except Exception as e:
            return False, f"오류: {e}"

    def get_partner_requests_for_wholesaler(self, wholesaler_store_id):
        """도매상 기준으로 모든 파트너 요청 구뎵"""
        if not self.supabase: return []
        try:
            res = self.supabase.table("partner_requests") \
                .select("*") \
                .eq("wholesaler_store_id", wholesaler_store_id) \
                .order("created_at", desc=True) \
                .execute()
            return res.data or []
        except:
            return []

    def update_partner_request_status(self, request_id, status):
        """파트너 요청 상태를 업데이트합니다."""
        if not self.supabase: return False, "DB 연동 안됨"
        try:
            self.supabase.table("partner_requests").update({"status": status}).eq("id", request_id).execute()
            return True, "성공"
        except Exception as e:
            return False, f"오류: {e}"

