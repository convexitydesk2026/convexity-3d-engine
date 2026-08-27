import streamlit as st
import pandas as pd
import time
from public_core_math import render_beta_warning_and_feedback
import io

st.set_page_config(page_title="Physical Equity Journal", layout="wide")

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

render_beta_warning_and_feedback()

# Mock Broker Sync Buttons
c1, c2 = st.columns([1, 1])
if st.button("🔍 Scan for Undocumented Campaigns", use_container_width=True):
    with st.spinner("Polling broker API..."):
        time.sleep(1.5)
        st.toast("Scan complete. No undocumented campaigns detected.")
if st.button("🏁 Check for Closed Campaigns", use_container_width=True):
    with st.spinner("Verifying active positions..."):
        time.sleep(1)
        st.toast("All campaigns verified. None have hit their stop limits.")

with st.expander("📝 Global Campaign Tag Editor", expanded=False):
    st.info("Tag editor interface disabled in public viewer.")
with st.expander("📖 Strategy Tag Glossary & SOPs", expanded=False):
    st.info("SOP glossary disabled in public viewer.")
with st.expander("✈️ View Pre-Trade Staging Area (Pipeline)", expanded=False):
    st.info("Staging area empty.")

st.markdown("### 🟢 Active Campaigns")
st.warning("⚠️ Tranche Added Detected: One or more open campaigns have increased in share size. Please verify your 1R Stop Loss using the Alpha Risk Calculator.")
st.markdown("**Active Campaigns Overview & Global Editor**")

@st.cache_data
def load_dummy_campaigns():
    data = [
        {'Open Date': '2026-08-21', 'Ticker': 'BMNR', 'Status': 'Open', 'Type': 'Long', 'Regime In': 'Gear 5.0', 
         'Sector': 'Financial Services', 'Industry': 'Capital Markets', '20 SMA': 18.53, '50 SMA': 16.95, '200 SMA': 22.99, 
         'Entry $': 16.32, 'Initial Stop $': 0.00, 'Tags (Editable)': '', 'Thesis (Editable)': '', 'Days': 0},
        {'Open Date': '2026-08-21', 'Ticker': 'ECHO', 'Status': 'Open', 'Type': 'Long', 'Regime In': 'Gear 5.0', 
         'Sector': 'Communication Services', 'Industry': 'Telecom Services', '20 SMA': 88.33, '50 SMA': 95.77, '200 SMA': 105.86, 
         'Entry $': 104.14, 'Initial Stop $': 0.00, 'Tags (Editable)': '', 'Thesis (Editable)': '', 'Days': 0},
        {'Open Date': '2026-08-21', 'Ticker': 'GLD', 'Status': 'Open', 'Type': 'Long', 'Regime In': 'Gear 5.0', 
         'Sector': 'Unknown Equities', 'Industry': 'N/A', '20 SMA': 392.64, '50 SMA': 383.03, '200 SMA': 413.46, 
         'Entry $': 423.41, 'Initial Stop $': 0.00, 'Tags (Editable)': '', 'Thesis (Editable)': '', 'Days': 0}
    ]
    return pd.DataFrame(data)

df = load_dummy_campaigns()

edited_df = st.data_editor(
    df, 
    use_container_width=True, 
    hide_index=True,
    column_config={
        "Tags (Editable)": st.column_config.TextColumn("Tags (Editable)", help="Type tags here", max_chars=100),
        "Thesis (Editable)": st.column_config.TextColumn("Thesis (Editable)", help="Type your investment thesis here", max_chars=1000)
    },
    disabled=["Open Date", "Ticker", "Status", "Type", "Regime In", "Sector", "Industry", "20 SMA", "50 SMA", "200 SMA", "Entry $", "Initial Stop $", "Days"]
)

# Dummy CSV Download
csv = edited_df.to_csv(index=False).encode('utf-8')
st.download_button(
    label="💾 Download Active Campaigns & Theses (CSV)",
    data=csv,
    file_name='active_campaigns_export.csv',
    mime='text/csv',
)

st.markdown("### 🏁 Closed Campaigns (Post-Mortem & Grading)")
with st.expander("📉 View Closed Campaigns, Post-Mortem & Analytics", expanded=False):
    st.info("No campaigns have been closed recently.")
