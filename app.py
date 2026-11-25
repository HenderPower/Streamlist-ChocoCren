from __future__ import annotations

import re
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP

import streamlit as st

import database as db

# 1-) Configuração da página e inicialização do banco 
st.set_page_config(
    page_title="ChocoCren | Gestão de Delivery",
    page_icon="🍫",
    layout="wide",
    initial_sidebar_state="expanded",
)

db.initialize_database() # chamar o db na inicialização