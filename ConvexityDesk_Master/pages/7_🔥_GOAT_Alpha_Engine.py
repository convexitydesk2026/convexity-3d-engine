import streamlit as st
import streamlit.components.v1 as components
import pandas as pd
import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent))
from public_core_math import render_global_sidebar, render_page_footer, render_page_header

st.set_page_config(page_title="GOAT Alpha Engine | Convexity Desk", layout="wide")

render_global_sidebar()

st.markdown("""
    <style>
        .mobile-blocker { display: none; }
        @media (max-width: 768px) { 
            .stApp > header { display: none !important; }
            section.main > div.block-container { display: none !important; }
            .mobile-blocker { 
                display: flex !important; flex-direction: column; justify-content: center; align-items: center; 
                height: 100vh; width: 100vw; background-color: #0e1117; color: white; text-align: center; 
                padding: 40px; position: fixed; top: 0; left: 0; z-index: 999999; 
            }
        }
    </style>
    <div class="mobile-blocker">
        <h1 style="font-size: 24px; color: #ff4b4b; margin-bottom: 20px;">Desktop Only</h1>
        <p style="font-size: 16px; line-height: 1.5;">The Convexity Desk interactive tools are optimized exclusively for desktop monitors.</p>
        <p style="font-size: 16px; line-height: 1.5; color: #a1a1aa;">Please visit <b>convexitydesk.com</b> on your computer to access the platform.</p>
    </div>
""", unsafe_allow_html=True)

render_page_header("🔥 GOAT Alpha Engine", "Premium Signal Generation & Idea Tracking")

st.markdown("---")

col1, col2 = st.columns([1, 1])

with col1:
    st.markdown("### ⚡ EP Grader (Qullamaggie)")
    st.info("Wait for MRNA-style setups. Do not force trades.")
    
    with st.container(border=True):
        st.text_input("Ticker Symbol", placeholder="e.g. MRNA")
        st.checkbox("Gap > 10%?")
        st.checkbox("Relative Volume > 5x?")
        st.checkbox("Generational Catalyst? (e.g. DNA Cure)")
        
        c1, c2 = st.columns(2)
        with c1:
            st.number_input("ORB High Price", min_value=0.00, step=1.0)
        with c2:
            st.number_input("RVol Target (%)", min_value=0.0, value=300.0, step=10.0)
            
        if st.button("Grade Setup", use_container_width=True):
            st.success("Setup logged into EP Waiting Room.")
            
    st.markdown("#### EP Waiting Room")
    ep_data = pd.DataFrame([
        {"Ticker": "AKTI", "Status": "Waiting for ORB", "ORB_High": None, "RVol_Target": None, "Alert_Sent": 0},
        {"Ticker": "CSCO", "Status": "Waiting for ORB", "ORB_High": None, "RVol_Target": None, "Alert_Sent": 0},
        {"Ticker": "GOOGL", "Status": "Waiting for ORB", "ORB_High": 300.0, "RVol_Target": 10.0, "Alert_Sent": 1},
    ])
    st.dataframe(ep_data, use_container_width=True, hide_index=True)

with col2:
    st.markdown("### 🍳 The GOAT Oven")
    st.caption("Track 13F Macro Bases (e.g. IREN, RIOT, BTDR, DLR) to 200 SMA.")
    
    oven_data = pd.DataFrame([
        {"Ticker": "IREN", "Theme": "AI Power", "Target_SMA": 46.7, "Notes": "In Duquesne Family 13F for 2026 Q2", "Alert_Sent": 0},
        {"Ticker": "RIOT", "Theme": "AI Power", "Target_SMA": 18.5, "Notes": "In Duquesne Family 13F for 2026 Q2", "Alert_Sent": 1},
        {"Ticker": "BTDR", "Theme": "AI Power", "Target_SMA": 12.3, "Notes": "Duquesne...", "Alert_Sent": 0},
    ])
    st.dataframe(oven_data, use_container_width=True, hide_index=True)
    
    with st.expander("➕ Add Ticker to Oven"):
        st.text_input("New Ticker")
        st.button("Save to Oven")
        
    st.markdown("### 🦜 Squawk Box")
    st.markdown("[Alpha Radar X List by ConvexityDesk](https://x.com/i/lists/2091567520998142458)")
    
    st.info("Data Feed temporarily disconnected during infrastructure migration.")
    # components.html("""
    # <a class="twitter-timeline" data-height="600" data-theme="dark" href="https://x.com/ConvexityDesk/lists/2091567520998142458?ref_src=twsrc%5Etfw">An X List by ConvexityDesk</a> 
    # <script async src="https://platform.x.com/widgets.js" charset="utf-8"></script>
    # """, height=600, scrolling=True)

render_page_footer("The GOAT Alpha Engine centralizes high-probability idea generation. It tracks Qullamaggie Episodic Pivots, 13F institutional accumulation bases, and live Squawk Box alerts to feed the Pre-Flight Matrix.")
