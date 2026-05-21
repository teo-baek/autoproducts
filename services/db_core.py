import os
from supabase import create_client, Client
import streamlit as st
import pandas as pd
from datetime import datetime
import json

import re

@st.cache_resource
def get_supabase_client() -> Client:
    url = st.secrets["SUPABASE_URL"]
    key = st.secrets["SUPABASE_KEY"]
    return create_client(url, key)

class DBCore:
    def __init__(self):
        self.supabase: Client = get_supabase_client()

    def clean_number(self, val_str):
        """콤마가 포함된 문자열을 정수로 변환"""
        try:
            return int(re.sub(r'[^\d]', '', str(val_str)))
        except:
            return 0

