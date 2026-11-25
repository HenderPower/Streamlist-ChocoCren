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

# 2-) aplicando tema claro e escuro via CSS
st.markdown( 
    """  
    <style>
    :root {
        color-scheme: light;
        --cc-coral: #ff604e;
        --cc-dark: #171717;
        --cc-gray: #ffffff;
        --cc-background: #BFDDF3;
        --cc-surface: #ffffff;
        --cc-muted: #555555;
    }
    html, body, .stApp, [data-testid="stAppViewContainer"], section[data-testid="stMain"] {
        background-color: var(--cc-background) !important;
        color: var(--cc-dark) !important;
    }
    .stApp h1, .stApp h2, .stApp h3, .stApp h4, .stApp h5, .stApp h6,
    .stApp [data-testid="stMarkdownContainer"] p,
    .stApp [data-testid="stMarkdownContainer"] li,
    .stApp [data-testid="stMarkdownContainer"] strong,
    .stApp [data-testid="stMarkdownContainer"] em,
    .stApp [data-testid="stWidgetLabel"],
    .stApp [data-testid="stWidgetLabel"] p,
    .stApp [data-testid="stWidgetLabel"] label,
    .stApp [data-testid="stRadio"] label,
    .stApp [data-testid="stCheckbox"] label,
    .stApp [data-testid="stCaptionContainer"],
    .stApp [data-testid="stCaptionContainer"] p,
    .stApp [data-testid="stMetricLabel"],
    .stApp [data-testid="stMetricLabel"] *,
    .stApp [data-testid="stMetricValue"],
    .stApp [data-testid="stMetricValue"] * {
        color: var(--cc-dark) !important;
        -webkit-text-fill-color: var(--cc-dark) !important;
        opacity: 1 !important;
    }
    [data-testid="stSidebar"] {
        background: var(--cc-gray) !important;
        border-right: 1px solid #8d8d8d;
    }
    [data-testid="stSidebar"] * {
        color: #111111 !important;
    }
    [data-testid="stSidebar"] [data-testid="stRadio"] label {
        font-weight: 600;
    }
    [data-testid="stHeader"] {
        background: rgba(238, 238, 238, 0.96) !important;
    }
    .block-container {
        padding-top: 1.1rem;
        padding-bottom: 2rem;
        max-width: 1500px;
    }
    .cc-topbar {
        background: #aaaaaa;
        border-radius: 9px 9px 0 0;
        padding: 12px 18px;
        display: flex;
        align-items: center;
        justify-content: space-between;
        margin-bottom: 1.1rem;
        color: #151515 !important;
    }
    .cc-brand, .cc-admin {
        color: #151515 !important;
    }
    .cc-brand {
        font-size: 1.08rem;
        font-weight: 800;
        letter-spacing: .02em;
    }
    .cc-admin {
        font-size: .82rem;
        font-weight: 600;
    }
    .cc-subtitle {
        color: #555555 !important;
        margin-top: -.65rem;
        margin-bottom: 1.1rem;
        font-size: .86rem;
    }
    div[data-testid="stMetric"] {
        background: #ffffff !important;
        border-radius: 13px;
        padding: 14px 16px;
        border: 1px solid #e1e1e1;
        min-height: 104px;
    }
    div[data-testid="stMetricLabel"] *,
    div[data-testid="stMetricValue"] * {
        color: #171717 !important;
        opacity: 1 !important;
    }
    .stApp input, .stApp textarea,
    .stApp [data-baseweb="input"] input,
    .stApp [data-baseweb="textarea"] textarea {
        color: #171717 !important;
        background-color: #ffffff !important;
        caret-color: #171717 !important;
        -webkit-text-fill-color: #171717 !important;
    }
    .stApp [data-baseweb="input"] > div,
    .stApp [data-baseweb="textarea"] {
        background-color: #ffffff !important;
        border-color: #b8b8b8 !important;
    }
    .stApp [data-baseweb="select"] > div {
        background-color: #ffffff !important;
        border-color: #b8b8b8 !important;
    }
    .stApp [data-baseweb="select"] *,
    .stApp [role="listbox"],
    .stApp [role="option"] {
        color: #171717 !important;
        -webkit-text-fill-color: #171717 !important;
    }
    .stApp [role="listbox"], .stApp [role="option"] {
        background-color: #ffffff !important;
    }
    .stApp input::placeholder, .stApp textarea::placeholder {
        color: #777777 !important;
        -webkit-text-fill-color: #777777 !important;
        opacity: 1 !important;
    }
    div.stButton > button, div.stFormSubmitButton > button {
        border-radius: 8px;
        font-weight: 650;
        min-height: 2.35rem;
        color: #171717 !important;
        background-color: #ffffff !important;
        border-color: #b8b8b8 !important;
    }
    div.stButton > button[kind="primary"],
    div.stFormSubmitButton > button[kind="primary"] {
        background: var(--cc-coral) !important;
        border-color: var(--cc-coral) !important;
        color: #ffffff !important;
    }
    div[data-testid="stForm"] {
        background: #ffffff !important;
        color: #171717 !important;
        border: 1px solid #e2e2e2;
        border-radius: 12px;
        padding: 16px;
    }
    div[data-testid="stExpander"] {
        background: #ffffff !important;
        color: #171717 !important;
        border: 1px solid #e2e2e2;
        border-radius: 10px;
    }
    div[data-testid="stExpander"] summary,
    div[data-testid="stExpander"] summary * {
        color: #171717 !important;
    }
    .stApp [data-testid="stTabs"] button,
    .stApp [data-testid="stTabs"] button * {
        color: #333333 !important;
        -webkit-text-fill-color: #333333 !important;
    }
    .stApp [data-testid="stTabs"] button[aria-selected="true"] {
        color: var(--cc-coral) !important;
        -webkit-text-fill-color: var(--cc-coral) !important;
    }
    .stApp [data-testid="stDataFrame"] {
        color: #171717 !important;
    }
    .stApp [data-testid="stAlert"] {
        background-color: #edf2f7 !important;
        border: 1px solid #cbd5e1 !important;
        border-radius: 10px;
    }
    .stApp [data-testid="stAlert"][kind="success"] {
        background-color: #e8f5ec !important;
        border-color: #b8dec3 !important;
    }
    .stApp [data-testid="stAlert"][kind="warning"] {
        background-color: #fff5db !important;
        border-color: #f0d58a !important;
    }
    .stApp [data-testid="stAlert"][kind="error"] {
        background-color: #fdeceb !important;
        border-color: #efb8b5 !important;
    }
    .stApp [data-testid="stAlert"][kind="info"] {
        background-color: #eaf1fb !important;
        border-color: #c6d7f0 !important;
    }
    .stApp [data-testid="stAlert"] [data-testid="stMarkdownContainer"] p {
        color: #263238 !important;
        -webkit-text-fill-color: #263238 !important;
        opacity: 1 !important;
    }
    .stApp [data-testid="stVegaLiteChart"] {
        background: #ffffff !important;
        border-radius: 10px;
    }
    .cc-status {
        display: inline-block;
        background: #efefef;
        border: 1px solid #bbbbbb;
        color: #222222 !important;
        border-radius: 99px;
        padding: 2px 9px;
        font-size: .75rem;
    }
    .cc-note {
        color: #555555 !important;
        font-size: .85rem;
    }
    </style>
    """,
    unsafe_allow_html=True,
)