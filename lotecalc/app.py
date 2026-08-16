"""
===============================================================================
PROJECT: LoteCalc DR (B2B PropTech SaaS)
FILE: app.py
VERSION: 1.8 (Expander Branding & Layout Fix)
DATE: August 03, 2026
AUTHOR: P1 (Lead PropTech Developer)
===============================================================================
"""

import os
import sqlite3
import streamlit as st
import streamlit.components.v1 as components
from translations import TEXT
from spatial_engine import get_sector_from_gps
from data_validator import validate_lot_inputs
from real_estate_math import FeasibilityEngine
from pdf_generator import generate_tear_sheet

st.set_page_config(page_title="LoteCalc DR", page_icon="🏢", layout="centered", initial_sidebar_state="collapsed")

st.markdown("""
    <style>
        header {visibility: hidden;}
        footer {visibility: hidden;}
        .stButton>button {
            width: 100%; height: 60px; border-radius: 10px;
            background-color: #007aff; color: white; font-size: 18px; font-weight: bold;
        }
        div[data-testid="metric-container"] {
            background-color: #f2f2f7; border-radius: 10px; padding: 15px;
        }
    </style>
""", unsafe_allow_html=True)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, 'zoning_dr.db')

if 'lang' not in st.session_state:
    st.session_state['lang'] = 'EN'

def toggle_lang():
    st.session_state['lang'] = 'ES' if st.session_state['lang'] == 'EN' else 'EN'

t = TEXT[st.session_state['lang']]

# --- UI HEADER ---
col1, col2 = st.columns([4, 1])
with col1:
    st.title(t["app_title"])
    st.caption(t["subtitle"])
with col2:
    st.button("EN / ES", on_click=toggle_lang)

st.divider()

# --- STEP 1: GEOLOCATION ---
st.subheader(t["step_1"])

try:
    MAPS_API_KEY = st.secrets["MAPS_API_KEY"]
except KeyError:
    st.error("API Key missing from Streamlit Secrets.")
    MAPS_API_KEY = ""

google_map_component = components.declare_component("google_map", path=os.path.join(BASE_DIR, "map_component"))
gps_data = google_map_component(api_key=MAPS_API_KEY, key="gmap")

sector_id = None
lat, lon = None, None
if gps_data:
    lat, lon = gps_data.get('lat'), gps_data.get('lon')
    sector_id = get_sector_from_gps(lat, lon)
    
    if sector_id:
        st.success(f"✅ GPS Locked: Sector {sector_id} (Lat: {lat:.4f}, Lon: {lon:.4f})")
    else:
        st.error("❌ Selected location is outside Polígono Central coverage.")

# --- STEP 2: LOT DIMENSIONS ---
st.subheader(t["step_2"])
col_w, col_d = st.columns(2)
with col_w:
    width_input = st.text_input(t["lot_width"], placeholder="e.g. 30")
with col_d:
    depth_input = st.text_input(t["lot_depth"], placeholder="e.g. 40")

# --- STEP 3: FINANCIAL ASSUMPTIONS ---
st.subheader(t["step_3"])
asking_price_input = st.text_input(t["asking_price"], placeholder="e.g. 1,500,000")

col_p, col_f = st.columns(2)
with col_p:
    permuta_input = st.selectbox(t["permuta"], ["0", "10", "20", "30", "40", "50"])
with col_f:
    finish_input = st.selectbox(t["finish_quality"], ["Economical", "Medium", "High", "Ultra"], index=1)

col_pt, col_pk = st.columns(2)
with col_pt:
    project_type_input = st.selectbox(t["project_type"], ["Studio/1BR Heavy", "2BR Standard", "3BR Family Heavy"], index=1)
with col_pk:
    parking_size_input = st.selectbox("Parking Space Size", ["Legal Minimum (2.30 x 5.00)", "Mid Size (2.50 x 5.20)", "Large (2.70 x 5.50)"], index=1)

st.divider()

# --- OPTIONAL: BROKER BRANDING ---
broker_name = ""
broker_phone = ""
broker_logo_bytes = None
logo_ext = ""

with st.expander("👤 Report Branding (Optional)"):
    st.info("This information will appear at the top of your generated PDF.")
    broker_name = st.text_input("Your Name / Agency", placeholder="e.g. Juan Perez Realty")
    broker_phone = st.text_input("Contact Number", placeholder="e.g. +1 809-555-0199")
    uploaded_logo = st.file_uploader("Upload Logo (PNG/JPG)", type=["png", "jpg", "jpeg"])
    
    if uploaded_logo:
        broker_logo_bytes = uploaded_logo.read()
        logo_ext = uploaded_logo.name.split('.')[-1]

# --- CALCULATE BUTTON ---
st.divider()
if st.button(t["btn_calculate"]):
    if not sector_id:
        st.error("Please lock a valid GPS location on the map first.")
    else:
        val = validate_lot_inputs(width_input, depth_input, asking_price_input, permuta_input)
        if not val["is_valid"]:
            for err in val["errors"]:
                st.error(err)
        else:
            w, d, price, permuta = val["clean_data"]
            
            conn = sqlite3.connect(DB_PATH)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM zoning_parameters WHERE Sector_ID = ?", (sector_id,))
            zoning_data = dict(cursor.fetchone())
            conn.close()
            
            engine = FeasibilityEngine(w, d, zoning_data, project_type_input, finish_input, price, permuta, parking_size_input)
            res = engine.run_feasibility()
            
            if "FATAL ERROR" in res["Status"]:
                st.error(res["Status"])
            else:
                st.subheader(t["results_title"])
                
                m1, m2 = st.columns(2)
                m1.metric(t["units"], res["Buildable_Units"])
                m2.metric(t["parking"], res["Total_Parking"])
                
                m3, m4 = st.columns(2)
                m3.metric(t["gsa"], f"{res['GSA_m2']:,.0f}")
                m4.metric(t["timeline"], res["Timeline_Months"])
                
                st.divider()
                
                if res["Status"] == "Viable":
                    r1, r2 = st.columns(2)
                    r1.metric(t["revenue"], f"${res['Gross_Revenue']:,.0f}")
                    r2.metric(t["cost"], f"${res['Total_Cost']:,.0f}")
                    
                    r3, r4 = st.columns(2)
                    r3.metric(t["roc"], f"{res['ROC']}%")
                    r4.metric(t["irr"], f"{res['IRR']}%" if isinstance(res['IRR'], (int, float)) else res['IRR'])
                else:
                    st.metric(t["max_land"], f"${res['Max_Land_Value']:,.0f}")
                
                if res.get("Warnings"):
                    st.warning(t["warnings"])
                    for warning_text in res["Warnings"]:
                        st.write(f"- {warning_text}")
                
                st.divider()
                
                inputs_dict = {
                    "sector": sector_id,
                    "width": w,
                    "depth": d,
                    "price": price if price else 0,
                    "permuta": permuta,
                    "lat": lat,
                    "lon": lon,
                    "api_key": MAPS_API_KEY,
                    "broker_name": broker_name,
                    "broker_phone": broker_phone,
                    "broker_logo": broker_logo_bytes,
                    "logo_ext": logo_ext
                }
                
                pdf_bytes = generate_tear_sheet(res, inputs_dict)
                
                st.download_button(
                    label=t["download_pdf"],
                    data=pdf_bytes,
                    file_name="LoteCalc_TearSheet.pdf",
                    mime="application/pdf",
                    type="primary"
                )