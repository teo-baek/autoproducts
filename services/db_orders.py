import os
from supabase import create_client, Client
import streamlit as st
import pandas as pd
from datetime import datetime
import json

class DBOrders:
    def create_reservation(self, store_id, retailer_email, p_number, quantity):
        if not self.supabase: return False, "DB 연동 안됨"
        try:
            data = {
                "store_id": store_id,
                "retailer_email": retailer_email,
                "p_number": p_number,
                "requested_quantity": quantity,
                "status": "PENDING"
            }
            self.supabase.table("product_reservations").insert(data).execute()
            return True, "성공"
        except Exception as e:
            return False, f"오류: {e}"

    def get_reservations_for_wholesaler(self, store_id):
        if not self.supabase: return []
        try:
            res = self.supabase.table("product_reservations").select("*").eq("store_id", store_id).order("created_at", desc=True).execute()
            return res.data or []
        except:
            return []

    def get_reservations_for_retailer(self, store_id, retailer_email):
        if not self.supabase: return []
        try:
            res = self.supabase.table("product_reservations").select("*").eq("store_id", store_id).eq("retailer_email", retailer_email).order("created_at", desc=True).execute()
            return res.data or []
        except:
            return []

    def update_reservation_status(self, reservation_id, status):
        if not self.supabase: return False, "DB 연동 안됨"
        try:
            self.supabase.table("product_reservations").update({"status": status}).eq("id", reservation_id).execute()
            return True, "성공"
        except Exception as e:
            return False, f"오류: {e}"

    def cancel_reservation(self, reservation_id):
        """소매상이 PENDING 상태의 예약을 취소합니다."""
        if not self.supabase: return False, "DB 연동 안됨"
        try:
            self.supabase.table("product_reservations").delete().eq("id", reservation_id).eq("status", "PENDING").execute()
            return True, "예약이 취소되었습니다."
        except Exception as e:
            return False, f"오류: {e}"

    def update_reservation_quantity(self, reservation_id, new_quantity):
        """소매상이 PENDING 상태의 예약 수량을 수정합니다."""
        if not self.supabase: return False, "DB 연동 안됨"
        try:
            self.supabase.table("product_reservations").update(
                {"requested_quantity": new_quantity}
            ).eq("id", reservation_id).eq("status", "PENDING").execute()
            return True, "수량이 수정되었습니다."
        except Exception as e:
            return False, f"오류: {e}"

    def confirm_order(self, reservation_id, actual_quantity):
        if not self.supabase: return False, "DB 연동 안됨"
        try:
            self.supabase.table("product_reservations").update({
                "actual_ordered_quantity": actual_quantity,
                "status": "COMPLETED"
            }).eq("id", reservation_id).execute()
            return True, "성공"
        except Exception as e:
            return False, f"오류: {e}"

    def mark_as_noshow(self, reservation_id, store_id, retailer_email):
        """예약을 노쇼(No-show) 처리하고 상대 소매상의 신뢰도 점수를 차감합니다."""
        if not self.supabase: return False, "DB 연동 안됨"
        try:
            # 1. 예약 상태 업데이트
            self.supabase.table("product_reservations").update({"status": "NOSHOW"}).eq("id", reservation_id).execute()
            
            # 2. 파트너 계약 데이터 조회 후 점수 차감
            res = self.supabase.table("partner_requests") \
                .select("*") \
                .eq("wholesaler_store_id", store_id) \
                .eq("retailer_email", retailer_email) \
                .execute()
                
            if res.data:
                current_noshow = res.data[0].get("no_show_count", 0)
                current_score = res.data[0].get("seller_reliability_score", 100)
                
                self.supabase.table("partner_requests").update({
                    "no_show_count": current_noshow + 1,
                    "seller_reliability_score": max(0, current_score - 10)
                }).eq("id", res.data[0]["id"]).execute()
                
            return True, "성공"
        except Exception as e:
            return False, f"오류: {e}"

