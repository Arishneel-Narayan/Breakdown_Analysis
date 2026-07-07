import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import base64
from weasyprint import HTML

# --- KALEIDO HEADLESS CHROME FIX ---
import plotly.io as pio
pio.kaleido.scope.chromium_args = tuple(
    list(pio.kaleido.scope.chromium_args) + 
    ["--no-sandbox", "--disable-dev-shm-usage", "--disable-gpu"]
)
# -----------------------------------

# --- SETUP & DATA LOADING ---
st.set_page_config(page_title="Breakdown Analysis Dashboard", layout="wide")
# ... (rest of your code remains exactly the same)
