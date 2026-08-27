import streamlit as st
import pandas as pd
import time
from public_core_math import render_page_footer
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




with st.expander("📝 Global Campaign Tag Editor", expanded=True):
    st.markdown("Use this interface to manage your global quant tags.")
    st.multiselect("Active System Tags", 
        ["13F", "VCP (Volatility Contraction Pattern)", "ALCC", "Q-EP", "M-FLOW", "ATR-Ext", 
         "Mean Reversion", "RSP>SPY Divergence", "PEAD", "Macro Regime Shift", "Sector Rotation"],
        default=["VCP (Volatility Contraction Pattern)", "ATR-Ext", "Macro Regime Shift", "Sector Rotation", "Mean Reversion", "Q-EP"]
    )
with st.expander("📖 Strategy Tag Glossary & SOPs (Standard Operating Procedures)", expanded=False):
    st.markdown("Document your exact trigger conditions for each strategy tag.")
    sop_df = pd.DataFrame([
        {"Tag": "VCP (Volatility Contraction Pattern)", "Description": "Price tightens from left to right with volume drying up.", "Action": "Buy on breakout"},
        {"Tag": "Mean Reversion", "Description": "Asset trades significantly below historical moving averages (e.g. 3 ATRs below 20SMA).", "Action": "Buy on first green day"}
    ])
    st.data_editor(sop_df, num_rows="dynamic", use_container_width=True, hide_index=True)
    
with st.expander("✈️ View Pre-Trade Staging Area (Pipeline)", expanded=False):
    st.markdown("Staged ideas waiting for execution.")
    pipeline_df = pd.DataFrame([
        {"Date Added": "2026-08-27", "Ticker": "AMD", "Setup": "VCP Breakout", "Target Entry": 155.00, "Notes": "Wait for confirmation volume"}
    ])
    st.data_editor(pipeline_df, num_rows="dynamic", use_container_width=True, hide_index=True)

st.markdown("### 🟢 Active Campaigns")
st.warning("⚠️ Tranche Added Detected: One or more open campaigns have increased in share size. Please verify your 1R Stop Loss using the Alpha Risk Calculator.")
st.markdown("**Active Campaigns Overview & Global Editor**")

@st.cache_data
def load_dummy_campaigns():
    data = [
        {'Open Date': '2026-08-21', 'Ticker': 'BMNR', 'Status': 'Open', 'Type': 'Long', 'Regime In': 'Gear 5.0', 
         'Sector': 'Financial Services', 'Industry': 'Capital Markets', '20 SMA': 18.53, '50 SMA': 16.95, '200 SMA': 22.99, 
         'Entry $': 16.32, 'Initial Stop $': 14.50, 'Tags (Editable)': 'VCP, Sector Rotation', 'Thesis (Editable)': 'Capitalizing on rotation into financials; tight volatility contraction pattern breakout.', 'Days': 6},
        {'Open Date': '2026-08-21', 'Ticker': 'ECHO', 'Status': 'Open', 'Type': 'Long', 'Regime In': 'Gear 5.0', 
         'Sector': 'Communication Services', 'Industry': 'Telecom Services', '20 SMA': 88.33, '50 SMA': 95.77, '200 SMA': 105.86, 
         'Entry $': 104.14, 'Initial Stop $': 100.00, 'Tags (Editable)': 'Mean Reversion, ATR-Ext', 'Thesis (Editable)': 'Severe downside ATR extension triggering a mechanical mean reversion bounce play.', 'Days': 6},
        {'Open Date': '2026-08-21', 'Ticker': 'GLD', 'Status': 'Open', 'Type': 'Long', 'Regime In': 'Gear 5.0', 
         'Sector': 'Commodities', 'Industry': 'Precious Metals', '20 SMA': 392.64, '50 SMA': 383.03, '200 SMA': 413.46, 
         'Entry $': 423.41, 'Initial Stop $': 410.00, 'Tags (Editable)': 'Macro Regime Shift, Q-EP', 'Thesis (Editable)': 'Macro hedge deployed defensively due to early signals of Alpha Engine deceleration.', 'Days': 6}
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
    st.markdown("Log and review closed trades to analyze performance.")
    closed_df = pd.DataFrame([
        {"Close Date": "2026-08-10", "Ticker": "MSFT", "P/L ($)": 1500, "Return (%)": 5.2, "Post-Mortem": "Followed rules perfectly. Target hit."},
        {"Close Date": "2026-08-15", "Ticker": "NFLX", "P/L ($)": -800, "Return (%)": -3.5, "Post-Mortem": "Stopped out. Should have sized smaller."}
    ])
    st.data_editor(closed_df, num_rows="dynamic", use_container_width=True, hide_index=True)

render_page_footer("The Physical Equity Journal enforces strict adherence to system logic. It acts as a professional swing-trader's accountability matrix, ensuring that every position has a documented mathematical edge, valid technical setup, and logical stop loss.")
