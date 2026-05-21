import os
from supabase import create_client, Client
import streamlit as st
import pandas as pd
from datetime import datetime
import json

from .db_core import DBCore
from .db_products import DBProducts
from .db_orders import DBOrders
from .db_users import DBUsers
from .db_analytics import DBAnalytics

class DatabaseConnector(DBCore, DBProducts, DBOrders, DBUsers, DBAnalytics):
    pass
