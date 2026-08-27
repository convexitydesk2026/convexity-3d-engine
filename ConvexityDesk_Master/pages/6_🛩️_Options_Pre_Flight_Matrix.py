import streamlit as st
import pandas as pd
import yfinance as yf
from public_core_math import render_beta_warning_and_feedback
import numpy as np
import datetime

st.set_page_config(page_title="Pre-Flight Matrix | Convexity Desk", layout="wide")

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

st.title("Options Governor & Pre-Flight Matrix")
st.markdown("This module polls live market data to mechanically enforce risk parameters across all options strategies.")

@st.cache_data(ttl=900)  # Refresh every 15 minutes
def fetch_live_market_data():
    end_date = datetime.date.today()
    start_date = end_date - datetime.timedelta(days=400) # Need enough data for 200 SMA and 1-yr IVR
    
    spy = yf.Ticker("SPY").history(start=start_date, end=end_date + datetime.timedelta(days=1))
    vix = yf.Ticker("^VIX").history(start=start_date, end=end_date + datetime.timedelta(days=1))
    
    # Process SPY
    spy['sma_50'] = spy['Close'].rolling(window=50).mean()
    spy['sma_200'] = spy['Close'].rolling(window=200).mean()
    
    # Simple ADX Approximation (14-day rolling volatility trend)
    # A true ADX requires High/Low/Close. We will use a 14-day historical volatility vs 50-day to gauge 'trendiness'
    spy['tr'] = np.maximum(spy['High'] - spy['Low'], 
                np.maximum(abs(spy['High'] - spy['Close'].shift(1)), abs(spy['Low'] - spy['Close'].shift(1))))
    spy['atr'] = spy['tr'].rolling(14).mean()
    spy['adx_proxy'] = (spy['atr'] / spy['Close']) * 1000 # Normalizing for scale (usually 0-50)
    
    # Process VIX to get IVR
    vix_1yr = vix.tail(252)
    vix_high = vix_1yr['Close'].max()
    vix_low = vix_1yr['Close'].min()
    vix_current = vix_1yr['Close'].iloc[-1]
    
    ivr_live = ((vix_current - vix_low) / (vix_high - vix_low)) * 100 if vix_high != vix_low else 0.0
    
    spy_spot_matrix = float(spy['Close'].iloc[-1])
    spy_50_matrix = float(spy['sma_50'].iloc[-1])
    spy_200_matrix = float(spy['sma_200'].iloc[-1])
    spy_adx_matrix = float(spy['adx_proxy'].iloc[-1])
    
    return spy_spot_matrix, spy_50_matrix, spy_200_matrix, spy_adx_matrix, float(ivr_live), float(vix_current)

try:
    with st.spinner("Polling live SPY and VIX data from Yahoo Finance..."):
        spy_spot, spy_50, spy_200, spy_adx, ivr_live, vix_current = fetch_live_market_data()
        
    st.markdown(f"**Live Diagnostics:** SPY: `${spy_spot:.2f}` | 50-SMA: `${spy_50:.2f}` | 200-SMA: `${spy_200:.2f}` | VIX: `{vix_current:.2f}` | IV Rank: `{ivr_live:.1f}%`")
    
    # Core Logic
    cal_ripe = ivr_live < 30.0 and spy_spot > spy_50
    ic_ripe = (30.0 <= ivr_live <= 70.0) and (spy_adx > 0 and spy_adx < 20.0)
    bp_ripe = (ivr_live >= 30.0) and (spy_spot > spy_50 or spy_spot < spy_200)
    bc_ripe = (30.0 <= ivr_live <= 80.0) and (spy_spot < spy_50)
    
    cal_status = "🟢 RIPE" if cal_ripe else "🔴 BANNED"
    ic_status = "🟢 RIPE" if ic_ripe else "🔴 BANNED"
    bp_status = "🟢 RIPE" if bp_ripe else "🔴 BANNED"
    bc_status = "🟢 RIPE" if bc_ripe else "🔴 BANNED"
    th_status = "🟢 ACCUMULATE" if ivr_live < 30.0 else "🔵 HOLD"

    cal_reason = "IVR < 30% and SPY > 50 SMA." if cal_ripe else f"IV Rank is {ivr_live:.0f}% or SPY < 50 SMA."
    
    if ic_ripe:
        ic_reason = f"IV Rank ({ivr_live:.0f}%) and ADX ({spy_adx:.1f}) are optimal (Rangebound)."
    else:
        if ivr_live > 70.0 or ivr_live < 30.0:
            ic_reason = f"IV Rank ({ivr_live:.0f}%) is out of 30-70% range."
        else:
            ic_reason = f"ADX is {spy_adx:.1f} (Must be < 20. Market is trending)."

    if bp_ripe:
        bp_reason = f"IV Rank >= 30% and SPY is structurally safe (> 50 or < 200 SMA)."
    else:
        if ivr_live < 30.0:
            bp_reason = "IV Rank is < 30% (Premiums too cheap)."
        else:
            bp_reason = "SPY trend is unsafe for short puts."

    if bc_ripe:
        bc_reason = f"IV Rank 30-80% and SPY < 50 SMA."
    else:
        if spy_spot >= spy_50:
            bc_reason = "SPY > 50 SMA (Banned during Bull Regimes)."
        else:
            bc_reason = f"IV Rank out of bounds."

    th_reason = "VIX Crush (IVR < 30%). Insurance is cheap." if ivr_live < 30.0 else f"IV Rank > 30%. Do not overpay."

    matrix_data = [
        {"Strategy": "Theta Machine (Calendars)", "Description": "Positive-Theta/Vega spread. Profits from time decay and rising IV.", "Status": cal_status, "Reason": cal_reason},
        {"Strategy": "VRP: Iron Condors", "Description": "Market-neutral strategy. Profits when asset remains rangebound.", "Status": ic_status, "Reason": ic_reason},
        {"Strategy": "VRP: Bull Put Spreads", "Description": "Directional strategy. Profits if asset stays above short put strike.", "Status": bp_status, "Reason": bp_reason},
        {"Strategy": "VRP: Bear Call Spreads", "Description": "Directional strategy. Profits if asset stays below short call strike.", "Status": bc_status, "Reason": bc_reason},
        {"Strategy": "Deep OTM Tail Hedges", "Description": "Catastrophic insurance. Protects portfolio against black swan crashes.", "Status": th_status, "Reason": th_reason}
    ]
    
    st.markdown("### Pre-Flight Clearance Matrix")
    
    st.dataframe(
        pd.DataFrame(matrix_data).style.apply(
            lambda x: ['background-color: #dcfce7; color: #166534; font-weight: bold' if '🟢' in str(v) else 
                       'background-color: #fee2e2; color: #991b1b; font-weight: bold' if '🔴' in str(v) else 
                       'background-color: #dbeafe; color: #1e40af; font-weight: bold' if '🔵' in str(v) else '' for v in x],
            subset=['Status']
        ),
        hide_index=True,
        use_container_width=True
    )
    
except Exception as e:
    st.error(f"Failed to fetch live market data from Yahoo Finance: {e}")
