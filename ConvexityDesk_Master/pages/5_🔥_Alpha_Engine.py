import streamlit as st
import streamlit.components.v1 as components
import pandas as pd
import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent))
from public_core_math import render_global_sidebar, render_page_footer, render_page_header

st.set_page_config(page_title="Alpha Engine | Convexity Desk", layout="wide")

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

render_page_header("🔥 Alpha Engine", "Premium Signal Generation & Idea Tracking")

st.markdown("---")

# Simulated User Tier Access Control
sim_tier = st.radio("Simulate User Tier (Admin Debug):", ["Tier 1 / Beta Tester", "Tier 2 (Standard)", "Tier 3 (Free)"], horizontal=True)
if sim_tier != "Tier 1 / Beta Tester":
    st.error("🔒 **Premium Access Required:** The GOAT Alpha Engine is restricted to Tier 1 Subscribers and Beta Testers.")
    st.info("Upgrade your account to unlock proprietary Episodic Pivot graders, 13F Institutional tracking, and AVWAP Liquidity models.")
    
    # Render a CSS-blurred mock layout to tease the user
    st.markdown("""
    <div style="filter: blur(6px); opacity: 0.3; pointer-events: none; user-select: none; margin-top: 30px;">
        <div style="display: flex; gap: 20px;">
            <div style="flex: 1; border: 1px solid #ccc; border-radius: 10px; padding: 20px; height: 400px; background: #fafafa;">
                <h3 style="color: #333;">⚡ Episodic Pivots (EP) Grader</h3>
                <p style="color: #666;">Wait for MRNA-style setups. Do not force trades.</p>
                <div style="height: 40px; background: #e2e8f0; border-radius: 5px; margin-top: 20px;"></div>
                <div style="height: 40px; background: #e2e8f0; border-radius: 5px; margin-top: 10px;"></div>
                <div style="height: 150px; background: #cbd5e1; border-radius: 5px; margin-top: 20px;"></div>
            </div>
            <div style="flex: 1; border: 1px solid #ccc; border-radius: 10px; padding: 20px; height: 400px; background: #fafafa;">
                <h3 style="color: #333;">🍳 The GOAT Oven</h3>
                <p style="color: #666;">Track 13F Macro Bases to 200 SMA.</p>
                <div style="height: 120px; background: #cbd5e1; border-radius: 5px; margin-top: 20px;"></div>
                <h3 style="color: #333; margin-top: 40px;">🦜 Squawk Box</h3>
                <div style="height: 80px; background: #e2e8f0; border-radius: 5px;"></div>
            </div>
        </div>
        <div style="border: 1px solid #ccc; border-radius: 10px; padding: 20px; height: 250px; background: #fafafa; margin-top: 20px;">
             <h3 style="color: #333;">⚓ Institutional AVWAP Liquidity Traps</h3>
             <p style="color: #666;">Track high-momentum pullbacks to Anchored VWAP.</p>
             <div style="height: 100px; background: #cbd5e1; border-radius: 5px; margin-top: 20px;"></div>
        </div>
    </div>
    """, unsafe_allow_html=True)
    st.stop()


col1, col2 = st.columns([1, 1])

with col1:
    st.markdown("### ⚡ Episodic Pivots (EP) Grader")
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
    
    ep_db_path = "ep_waiting_room.json"
    import json
    from datetime import datetime
    import pytz
    
    # Get current ET date to handle the 11:59 PM auto-delete logic
    et_tz = pytz.timezone('US/Eastern')
    current_et_date = datetime.now(et_tz).strftime('%Y-%m-%d')
    
    if Path(ep_db_path).exists():
        with open(ep_db_path, "r") as f:
            ep_raw = json.load(f)
        ep_data = pd.DataFrame(ep_raw)
        
        # Auto-delete rows that are not from today (simulating the 11:59 PM ET wipe)
        if not ep_data.empty and 'Date_Added' in ep_data.columns:
            ep_data = ep_data[ep_data['Date_Added'] == current_et_date]
    else:
        ep_data = pd.DataFrame(columns=["Active", "Ticker", "Status", "ORB_High", "RVol_Target", "Alert_Sent", "Date_Added"])
        
    if ep_data.empty:
        ep_data = pd.DataFrame(columns=["Active", "Ticker", "Status", "ORB_High", "RVol_Target", "Alert_Sent", "Date_Added"])
        
    # Ensure standard types
    ep_data['Active'] = ep_data['Active'].astype(bool) if 'Active' in ep_data.columns else True

    # Make table editable (Admin can add/delete rows directly)
    edited_ep = st.data_editor(
        ep_data, 
        num_rows="dynamic",
        use_container_width=True, 
        hide_index=True,
        column_config={
            "Active": st.column_config.CheckboxColumn("Track?", default=True),
            "Ticker": st.column_config.TextColumn("Ticker", required=True),
            "Status": st.column_config.SelectboxColumn("Status", options=["Waiting for ORB", "ORB Triggered", "Failed"], required=True),
            "ORB_High": st.column_config.NumberColumn("ORB High", format="$%.2f"),
            "RVol_Target": st.column_config.NumberColumn("RVol Target", format="%.1f"),
            "Date_Added": st.column_config.TextColumn("Date Added (ET)", disabled=True)
        }
    )
    
    if not edited_ep.equals(ep_data):
        # Auto-stamp the date on new rows
        edited_ep['Date_Added'] = edited_ep['Date_Added'].fillna(current_et_date)
        with open(ep_db_path, "w") as f:
            json.dump(edited_ep.to_dict(orient="records"), f, indent=4)
        st.rerun()

with col2:
    st.markdown("### 🍳 The GOAT Oven")
    st.caption("Track 13F Macro Bases (e.g. IREN, RIOT, BTDR, DLR) to 200 SMA.")
    
    oven_db_path = "goat_oven.json"
    if Path(oven_db_path).exists():
        with open(oven_db_path, "r") as f:
            oven_raw = json.load(f)
        oven_data = pd.DataFrame(oven_raw)
    else:
        oven_data = pd.DataFrame(columns=["Active", "Ticker", "Theme", "Target_SMA", "Notes", "Alert_Sent"])
        
    if oven_data.empty:
        oven_data = pd.DataFrame(columns=["Active", "Ticker", "Theme", "Target_SMA", "Notes", "Alert_Sent"])
        
    oven_data['Active'] = oven_data['Active'].astype(bool) if 'Active' in oven_data.columns else True

    edited_oven = st.data_editor(
        oven_data,
        num_rows="dynamic",
        use_container_width=True,
        hide_index=True,
        column_config={
            "Active": st.column_config.CheckboxColumn("Track?", default=True),
            "Ticker": st.column_config.TextColumn("Ticker", required=True),
        }
    )
    
    if not edited_oven.equals(oven_data):
        with open(oven_db_path, "w") as f:
            json.dump(edited_oven.to_dict(orient="records"), f, indent=4)
        st.rerun()
        
    st.markdown("### 🦜 Squawk Box")
    st.markdown("[Alpha Radar X List by ConvexityDesk](https://x.com/i/lists/2091567520998142458)")
    
    # st.info("Data Feed temporarily disconnected during infrastructure migration.")
    components.html("""
    <a class="twitter-timeline" data-height="600" data-theme="dark" href="https://twitter.com/ConvexityDesk/lists/2091567520998142458?ref_src=twsrc%5Etfw">An X List by ConvexityDesk</a> 
    <script async src="https://platform.x.com/widgets.js" charset="utf-8"></script>
    """, height=600, scrolling=True)

st.markdown("---")
st.markdown("### ⚓ Institutional AVWAP Liquidity Traps")
st.caption("Track 'Weakness in Strength' high-momentum pullbacks to Anchored VWAP and EMA clusters.")
    
# Read from the JSON database maintained by the Webhook Server
db_path = "goat_database.json"
if Path(db_path).exists():
    import json
    with open(db_path, "r") as f:
        luk_data_raw = json.load(f)
    luk_data = pd.DataFrame(luk_data_raw)
    if luk_data.empty:
        luk_data = pd.DataFrame(columns=["Active", "Ticker", "Trap Type", "AVWAP Level", "Status", "Risk/Reward"])
        
    luk_data['Active'] = luk_data['Active'].astype(bool) if 'Active' in luk_data.columns else True

    edited_luk = st.data_editor(
        luk_data,
        num_rows="dynamic",
        use_container_width=True,
        hide_index=True,
        column_config={
            "Active": st.column_config.CheckboxColumn("Track?", default=True),
            "Ticker": st.column_config.TextColumn("Ticker", required=True),
        }
    )
    
    if not edited_luk.equals(luk_data):
        with open(db_path, "w") as f:
            json.dump(edited_luk.to_dict(orient="records"), f, indent=4)
        st.rerun()

st.markdown("<br><p style='font-size: 11px; color: #475569; line-height: 1.4;'><b>Quantitative Origins:</b> The models tracked in this engine are heavily inspired by audited market champions.<br>- <b>Episodic Pivots:</b> Popularized by Kristjan Kullamägi (Qullamaggie), featured in Jack D. Schwager's <i>Unknown Market Wizards</i>.<br>- <b>AVWAP Traps:</b> Popularized by Martin Luk, a multi-year top performer and finalist in the United States Investing Championship (USIC).</p>", unsafe_allow_html=True)

render_page_footer("The GOAT Alpha Engine centralizes high-probability idea generation. It tracks Episodic Pivots, 13F institutional accumulation bases, AVWAP liquidity traps, and live Squawk Box alerts.")
