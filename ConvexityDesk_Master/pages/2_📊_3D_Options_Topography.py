"""
=============================================================================
Script Name: app.py
Purpose: Public PLG Lead Magnet for Convexity Desk.
         Full Institutional 3D Options Topography Engine & VRP Masterclass.
=============================================================================
"""
import streamlit as st
import numpy as np
import pandas as pd
import plotly.graph_objects as go
import yfinance as yf
import math
import io

# ==========================================
# 1. PAGE CONFIG & UI SETUP
# ==========================================
st.set_page_config(page_title="3D Options Topography | Convexity Desk", layout="wide", initial_sidebar_state="expanded")

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
        <p style="font-size: 16px; line-height: 1.5;">The Convexity Desk interactive tools (including the 3D Options Topography Engine) are optimized exclusively for desktop monitors.</p>
        <p style="font-size: 16px; line-height: 1.5; color: #a1a1aa;">Please visit <b>convexitydesk.com</b> on your computer to access the platform.</p>
    </div>
""", unsafe_allow_html=True)

st.markdown("""
    <style>
    .premium-banner { background: linear-gradient(90deg, #1e293b 0%, #0f172a 100%); color: white; padding: 20px; border-radius: 8px; text-align: center; margin-bottom: 20px; border: 1px solid #334155;}
    .info-box { background-color: #f8fafc; border: 1px solid #cbd5e1; padding: 20px; border-radius: 8px; margin-bottom: 20px; }
    </style>
""", unsafe_allow_html=True)

st.warning("⚠️ Website under development. Do not rely on the results. Come back in one week. If you still see this header it means we are NOT yet ready for public use.")

# ==========================================
# 2. CORE QUANTITATIVE MATH (BLACK-SCHOLES)
# ==========================================
def normCDF(x):
    t = 1 / (1 + 0.2316419 * abs(x))
    d = 0.3989423 * np.exp(-x * x / 2)
    prob = d * t * (0.3193815 + t * (-0.3565638 + t * (1.781478 + t * (-1.821256 + t * 1.330274))))
    return 1 - prob if x > 0 else prob

def normPDF(x):
    return np.exp(-0.5 * x * x) / np.sqrt(2 * np.pi)

def get_put_greeks(S, K, T, r, v):
    if K <= 0 or S <= 0: return 0.0, 0.0, 0.0, 0.0, 0.0
    T = max(T, 0.0001)
    d1 = (math.log(S / K) + (r + 0.5 * v ** 2) * T) / (v * math.sqrt(T))
    d2 = d1 - v * math.sqrt(T)
    price = K * math.exp(-r * T) * normCDF(-d2) - S * normCDF(-d1)
    delta = normCDF(d1) - 1
    gamma = normPDF(d1) / (S * v * math.sqrt(T))
    vega = (S * normPDF(d1) * math.sqrt(T)) / 100
    theta = (- (S * v * normPDF(d1)) / (2 * math.sqrt(T)) + r * K * math.exp(-r * T) * normCDF(-d2)) / 365
    return price, delta, gamma, vega, theta

def get_call_greeks(S, K, T, r, v):
    if K <= 0 or S <= 0: return 0.0, 0.0, 0.0, 0.0, 0.0
    T = max(T, 0.0001)
    d1 = (math.log(S / K) + (r + 0.5 * v ** 2) * T) / (v * math.sqrt(T))
    d2 = d1 - v * math.sqrt(T)
    price = S * normCDF(d1) - K * math.exp(-r * T) * normCDF(d2)
    delta = normCDF(d1)
    gamma = normPDF(d1) / (S * v * math.sqrt(T))
    vega = (S * normPDF(d1) * math.sqrt(T)) / 100
    theta = (- (S * v * normPDF(d1)) / (2 * math.sqrt(T)) - r * K * math.exp(-r * T) * normCDF(d2)) / 365
    return price, delta, gamma, vega, theta

@st.cache_data(ttl=3600)
def get_live_market_data(ticker="SPY"):
    try:
        spot = float(yf.Ticker(ticker).history(period="1d")['Close'].iloc[-1])
        vix = float(yf.Ticker("^VIX").history(period="1d")['Close'].iloc[-1])
        return spot, vix
    except:
        return 550.0, 15.0

def load_portfolio_data(file_or_path):
    try:
        df = pd.read_csv(file_or_path)
        df['CloseDate'] = pd.to_datetime(df['CloseDate'])
        df['EntryDate'] = pd.to_datetime(df['EntryDate'])
        df['DaysHeld'] = (df['CloseDate'] - df['EntryDate']).dt.days
        df['ROC'] = (df['RealizedPnL'] / df['CapitalAtRisk']) * 100
        return df
    except Exception as e:
        st.error(f"Error loading data: {e}")
        return None

# ==========================================
# 3. SESSION STATE 
# ==========================================
if 'portfolio_df' not in st.session_state: st.session_state.portfolio_df = None

if 'trade_params' not in st.session_state:
    init_spot, init_vix = get_live_market_data("SPY")
    st.session_state.trade_params = {
        'strategy': 'VRP: Bull Put Spread',
        'ticker': 'SPY', 'dte': 45.0, 
        'k_s': float(round(init_spot * 0.95)),
        'k_l': float(round(init_spot * 0.95)) - 25.0, # 25-point default spread
        'k_cs': float(round(init_spot * 1.05)),
        'k_cl': float(round(init_spot * 1.05)) + 25.0,
        'qty': 10.0, 'spot': init_spot, 'vix': init_vix
    }

# ==========================================
# 4. SIDEBAR
# ==========================================
with st.sidebar:
    st.markdown("### ⚙️ Trade Parameters")
    
    strats = ["VRP: Bull Put Spread", "VRP: Bear Call Spread", "VRP: Iron Condor", "Deep OTM Tail Hedge (Long Put)"]
    current_strat = st.session_state.trade_params.get('strategy', "VRP: Bull Put Spread")
    strat_sel = st.selectbox("Select Options Strategy", strats, index=strats.index(current_strat))

    with st.form("trade_form"):
        tckr_input = st.text_input("Ticker Symbol (SPY, NDX, etc.)", value=st.session_state.trade_params['ticker'])
        dte_input = st.number_input("Days to Expiration (DTE)", value=float(st.session_state.trade_params['dte']))
        
        if strat_sel == "VRP: Bull Put Spread":
            ks_input = st.number_input("Short Put Strike", value=float(st.session_state.trade_params['k_s']))
            kl_input = st.number_input("Long Put Strike", value=float(st.session_state.trade_params['k_l']))
            kcs_input, kcl_input = 0.0, 0.0
        elif strat_sel == "VRP: Bear Call Spread":
            ks_input = st.number_input("Short Call Strike", value=float(st.session_state.trade_params.get('k_cs', st.session_state.trade_params['k_s'])))
            kl_input = st.number_input("Long Call Strike", value=float(st.session_state.trade_params.get('k_cl', st.session_state.trade_params['k_l'])))
            kcs_input, kcl_input = 0.0, 0.0
        elif strat_sel == "VRP: Iron Condor":
            st.markdown("**Put Wing**")
            ks_input = st.number_input("Short Put Strike", value=float(st.session_state.trade_params['k_s']))
            kl_input = st.number_input("Long Put Strike", value=float(st.session_state.trade_params['k_l']))
            st.markdown("**Call Wing**")
            kcs_input = st.number_input("Short Call Strike", value=float(st.session_state.trade_params.get('k_cs', 580)))
            kcl_input = st.number_input("Long Call Strike", value=float(st.session_state.trade_params.get('k_cl', 605)))
        elif strat_sel == "Deep OTM Tail Hedge (Long Put)":
            ks_input = 0.0
            kl_input = st.number_input("Long Put Strike", value=float(st.session_state.trade_params['k_l']))
            kcs_input, kcl_input = 0.0, 0.0

        qty_input = st.number_input("Contracts", value=float(st.session_state.trade_params['qty']))
        
        submit = st.form_submit_button("Update Topography", type="primary")
        
        if submit:
            new_spot, new_vix = get_live_market_data(tckr_input)
            
            # Map values properly based on strategy
            p_ks = ks_input if strat_sel in ["VRP: Bull Put Spread", "VRP: Iron Condor"] else st.session_state.trade_params['k_s']
            p_kl = kl_input if strat_sel in ["VRP: Bull Put Spread", "VRP: Iron Condor", "Deep OTM Tail Hedge (Long Put)"] else st.session_state.trade_params['k_l']
            p_kcs = ks_input if strat_sel == "VRP: Bear Call Spread" else kcs_input if strat_sel == "VRP: Iron Condor" else st.session_state.trade_params.get('k_cs', 0.0)
            p_kcl = kl_input if strat_sel == "VRP: Bear Call Spread" else kcl_input if strat_sel == "VRP: Iron Condor" else st.session_state.trade_params.get('k_cl', 0.0)

            st.session_state.trade_params = {
                'strategy': strat_sel, 'ticker': tckr_input.upper(), 'dte': dte_input, 
                'k_s': p_ks, 'k_l': p_kl, 'k_cs': p_kcs, 'k_cl': p_kcl,
                'qty': qty_input, 'spot': new_spot, 'vix': new_vix
            }
            st.rerun()

    st.markdown("---")
    with st.expander("📊 Portfolio Analysis", expanded=True):
        uploaded_file = st.file_uploader("Upload Flex Query (CSV)", type="csv")
        if uploaded_file is not None:
            st.session_state.portfolio_df = load_portfolio_data(uploaded_file)
            st.rerun()
            
        st.markdown("<div style='text-align: center; margin-bottom: 10px; font-size: 14px;'>Or explore our live demo data:</div>", unsafe_allow_html=True)
        if st.button("Load Golden Path Demo", type="primary", use_container_width=True):
            st.session_state.portfolio_df = load_portfolio_data("demo_portfolio.csv")
            st.rerun()

# ==========================================
# 5. MAIN UI & INTERACTIVE SLIDERS
# ==========================================

tab1 = st.container()
tab2 = st.container()

with tab1:
    st.markdown("""
    <div class='premium-banner'>
        <h2 style='margin:0; color:white;'>Institutional Options Topography Engine & Ledger</h2>
        <p style='margin:5px 0 0 0; color:#94a3b8;'>Visualizing the Gamma Cliff and Theta Glide Path across multiple Volatility Risk Premium strategies.</p>
    </div>
    """, unsafe_allow_html=True)
    
    st.markdown("### 🟢 Active Options Performance Ledger")
    
    @st.cache_data
    def load_dummy_options_ledger(spot_p):
        data = [
            {'Strategy': 'VRP: Bull Put Spread', 'Ticker': 'SPY', 'DTE': 35.0, 'Contracts': 10.0, 'Short Put': round(spot_p*0.95), 'Long Put': round(spot_p*0.95)-25, 'Short Call': 0.0, 'Long Call': 0.0, 'Status': '🟢 RIPE', 'Open PnL': 150.00},
            {'Strategy': 'VRP: Iron Condor', 'Ticker': 'SPY', 'DTE': 35.0, 'Contracts': 5.0, 'Short Put': round(spot_p*0.93), 'Long Put': round(spot_p*0.93)-25, 'Short Call': round(spot_p*1.07), 'Long Call': round(spot_p*1.07)+25, 'Status': '🟢 RIPE', 'Open PnL': -45.00},
            {'Strategy': 'Deep OTM Tail Hedge (Long Put)', 'Ticker': 'SPY', 'DTE': 120.0, 'Contracts': 20.0, 'Short Put': 0.0, 'Long Put': round(spot_p*0.80), 'Short Call': 0.0, 'Long Call': 0.0, 'Status': '🔵 HOLD', 'Open PnL': -125.50},
        ]
        return pd.DataFrame(data)
        
    df_opts = load_dummy_options_ledger(st.session_state.trade_params['spot'])
    
    st.markdown("To interact with the engine, you can **click on any row** in the active ledger, **manually edit** the table cells, upload a custom CSV portfolio, or configure arbitrary structures in the **Trade Parameters** sidebar.")
    uploaded_opts = st.file_uploader("Upload Active Options CSV", type=['csv'], key="opts_up")
    if uploaded_opts is not None:
        try:
            df_opts = pd.read_csv(uploaded_opts)
        except Exception as e:
            st.error(f"Error parsing CSV: {e}")
            
    try:
        # Use on_select to capture user clicks and drive the 3D engine
        event = st.data_editor(df_opts.style.format({
            'Open PnL': '${:.2f}', 'Short Put': '{:.1f}', 'Long Put': '{:.1f}', 'Short Call': '{:.1f}', 'Long Call': '{:.1f}'
        }).apply(lambda x: ['color: #16a34a; font-weight:bold;' if v > 0 else 'color: #dc2626; font-weight:bold;' if v < 0 else '' for v in x], subset=['Open PnL']), 
        hide_index=True, use_container_width=True, on_select="rerun", selection_mode="single-row", num_rows="dynamic")
        
        if event and len(event.selection.rows) > 0:
            sel_idx = event.selection.rows[0]
            sel_row = df_opts.iloc[sel_idx]
            
            # Update session state with the clicked row's parameters!
            if st.session_state.trade_params['k_s'] != sel_row['Short Put']: # prevent infinite loops
                st.session_state.trade_params.update({
                    'strategy': sel_row['Strategy'],
                    'ticker': sel_row['Ticker'],
                    'dte': float(sel_row['DTE']),
                    'qty': float(sel_row['Contracts']),
                    'k_s': float(sel_row['Short Put']),
                    'k_l': float(sel_row['Long Put']),
                    'k_cs': float(sel_row['Short Call']),
                    'k_cl': float(sel_row['Long Call'])
                })
                st.rerun()
    except Exception as e:
        # Fallback for older Streamlit versions without on_select
        st.dataframe(df_opts.style.format({
            'Open PnL': '${:.2f}', 'Short Put': '{:.1f}', 'Long Put': '{:.1f}', 'Short Call': '{:.1f}', 'Long Call': '{:.1f}'
        }).apply(lambda x: ['color: #16a34a; font-weight:bold;' if v > 0 else 'color: #dc2626; font-weight:bold;' if v < 0 else '' for v in x], subset=['Open PnL']), 
        hide_index=True, use_container_width=True)
        
    with st.expander("🚦 RIPE vs HOLD Signal Matrix Explained"):
        st.markdown("""
        Our quantitative engine uses real-time market data (SPY and VIX) to automatically grade the safety of entering new options structures.
        *   **🟢 RIPE:** Market conditions are optimal for this specific strategy. (e.g., For Iron Condors, IV Rank is between 30-70% and the market is non-trending).
        *   **🔵 HOLD:** You should hold existing positions but do not open new ones. This usually triggers when implied volatility is too low (premiums are cheap) or the market trend is too dangerous to fade.
        *   **🔴 BANNED (AVOID):** The mathematical probability of loss is extremely high. (e.g., Selling Bear Calls during a raging bull market where SPY is above its 50-day moving average).
        """)
        st.page_link("pages/6_🛩️_Pre_Flight_Matrix.py", label="View live market diagnostics on the Pre-Flight Matrix", icon="🛩️")
    
    st.markdown("---")
    st.markdown("### 3D Volatility Surface Stress Tester")

    st.markdown("""
    <div style="background-color: #f8fafc; border-left: 4px solid #3b82f6; padding: 12px 16px; border-radius: 4px; margin-bottom: 20px; font-size: 14px; color: #334155; box-shadow: 0 1px 2px rgba(0,0,0,0.05);">
        <b>ℹ️ Data Freshness & Controls:</b> Market data is sourced via Yahoo Finance (approx. 15-min delayed). Use the sliders below to stress-test the simulated <b>Strategy</b> against sudden Volatility (VIX) spikes and Time (Theta) decay.
    </div>
    """, unsafe_allow_html=True)

    p = st.session_state.trade_params
    strat = p.get('strategy', "VRP: Bull Put Spread")
    spot_price = p['spot']
    K_s = p['k_s']
    K_l = p['k_l']
    K_cs = p.get('k_cs', 0.0)
    K_cl = p.get('k_cl', 0.0)
    init_dte = p['dte']
    qty = p['qty']
    r_rate = 0.045

    col_s1, col_s2 = st.columns(2)
    with col_s1:
        iv_override = st.slider("🌪️ Volatility Shock (IV) Stress Tester %", min_value=5.0, max_value=150.0, value=float(p['vix'] * 1.15), step=0.5)
    with col_s2:
        days_in_trade = st.slider("⏳ Time Travel (Days in Trade)", min_value=0, max_value=int(init_dte)-1, value=0, help="Drag forward to watch Theta decay eat the premium.")

    iv_dec = iv_override / 100.0
    curr_dte = init_dte - days_in_trade

    def get_live_value(px, stg, T, r, v, ks, kl, kcs, kcl):
        if stg == "VRP: Bull Put Spread":
            ts = get_put_greeks(px, ks, T, r, v)[0]
            tl = get_put_greeks(px, kl, T, r, v)[0]
            return ts - tl
        elif stg == "VRP: Bear Call Spread":
            ts = get_call_greeks(px, ks, T, r, v)[0]
            tl = get_call_greeks(px, kl, T, r, v)[0]
            return ts - tl
        elif stg == "VRP: Iron Condor":
            tps = get_put_greeks(px, ks, T, r, v)[0]
            tpl = get_put_greeks(px, kl, T, r, v)[0]
            tcs = get_call_greeks(px, kcs, T, r, v)[0]
            tcl = get_call_greeks(px, kcl, T, r, v)[0]
            return (tps - tpl) + (tcs - tcl)
        elif stg == "Deep OTM Tail Hedge (Long Put)":
            return get_put_greeks(px, kl, T, r, v)[0]
        return 0

    def get_exp_value(px, stg, ks, kl, kcs, kcl):
        if stg == "VRP: Bull Put Spread":
            return max(ks - px, 0) - max(kl - px, 0)
        elif stg == "VRP: Bear Call Spread":
            return max(px - ks, 0) - max(px - kl, 0)
        elif stg == "VRP: Iron Condor":
            return (max(ks - px, 0) - max(kl - px, 0)) + (max(px - kcs, 0) - max(px - kcl, 0))
        elif stg == "Deep OTM Tail Hedge (Long Put)":
            return max(kl - px, 0)
        return 0

    # Calculate Entry Premium
    entry_val = get_live_value(spot_price, strat, init_dte/365.0, r_rate, iv_dec, K_s, K_l, K_cs, K_cl)

    # Calculate Margins
    if strat == "VRP: Bull Put Spread":
        margin_req = (K_s - K_l) * 100 * qty
    elif strat == "VRP: Bear Call Spread":
        margin_req = (K_cl - K_cs) * 100 * qty
    elif strat == "VRP: Iron Condor":
        margin_req = max((K_s - K_l), (K_cl - K_cs)) * 100 * qty
    else: # Tail Hedge
        margin_req = entry_val * 100 * qty

    # ==========================================
    # 6. 2D & 3D SURFACE CALCULATION
    # ==========================================
    # Dynamic plotting bounds
    if strat == "VRP: Bear Call Spread":
        min_plot = int(spot_price - 20)
        max_plot = int(max(K_cs, K_cl) + 30)
    elif strat == "VRP: Iron Condor":
        min_plot = int(min(K_s, K_l) - 30)
        max_plot = int(max(K_cs, K_cl) + 30)
    elif strat == "Deep OTM Tail Hedge (Long Put)":
        min_plot = int(K_l - 60)
        max_plot = int(spot_price + 10)
    else: # Bull Put
        min_plot = int(min(K_s, K_l) - 30)
        max_plot = int(spot_price + 20)
        
    x_vals = [px / 2.0 for px in range(int(min_plot * 2), int(max_plot * 2) + 1)]
    y_3d = list(range(int(init_dte), -1, -1))
    z_3d = []
    y_exp, y_init, y_curr = [], [], []

    for d in y_3d:
        T_3d = max(d / 365.0, 0.0001)
        z_row = []
        for px in x_vals:
            if T_3d <= 0.0001: 
                exp_cost = get_exp_value(px, strat, K_s, K_l, K_cs, K_cl)
                val = (entry_val - exp_cost) * qty * 100 if strat != "Deep OTM Tail Hedge (Long Put)" else (exp_cost - entry_val) * qty * 100
                z_row.append(val)
                if d == 0: y_exp.append(val)
            else:
                live_cost = get_live_value(px, strat, T_3d, r_rate, iv_dec, K_s, K_l, K_cs, K_cl)
                val = (entry_val - live_cost) * qty * 100 if strat != "Deep OTM Tail Hedge (Long Put)" else (live_cost - entry_val) * qty * 100
                z_row.append(val)
                if d == int(init_dte): y_init.append(val)
                if d == int(curr_dte): y_curr.append(val)
        z_3d.append(z_row)

    z_min, z_max = np.min(z_3d), np.max(z_3d)

    # ==========================================
    # 7. PLOTLY RENDERING (2D & 3D)
    # ==========================================
    col_2d, col_3d = st.columns([1, 1])

    with col_2d:
        fig_2d = go.Figure()
        
        # Highlight regions based on strategy
        if strat in ["VRP: Bull Put Spread", "VRP: Iron Condor"]:
            fig_2d.add_vrect(x0=K_s, x1=spot_price if strat=="VRP: Bull Put Spread" else K_cs, fillcolor="green", opacity=0.05, layer="below", line_width=0)    
            fig_2d.add_vrect(x0=min_plot, x1=K_l, fillcolor="red", opacity=0.05, layer="below", line_width=0)
            fig_2d.add_vline(x=K_s, line_dash="dot", line_color="green", annotation_text="Short Put", annotation_position="top left")
            fig_2d.add_vline(x=K_l, line_dash="dot", line_color="red", annotation_text="Long Put", annotation_position="top right")
        
        if strat in ["VRP: Bear Call Spread", "VRP: Iron Condor"]:
            fig_2d.add_vrect(x0=spot_price if strat=="VRP: Bear Call Spread" else K_s, x1=K_cs, fillcolor="green", opacity=0.05, layer="below", line_width=0)    
            fig_2d.add_vrect(x0=K_cl, x1=max_plot, fillcolor="red", opacity=0.05, layer="below", line_width=0)
            fig_2d.add_vline(x=K_cs, line_dash="dot", line_color="green", annotation_text="Short Call", annotation_position="top left")
            fig_2d.add_vline(x=K_cl, line_dash="dot", line_color="red", annotation_text="Long Call", annotation_position="top right")

        if strat == "Deep OTM Tail Hedge (Long Put)":
            fig_2d.add_vrect(x0=min_plot, x1=K_l, fillcolor="green", opacity=0.05, layer="below", line_width=0)
            fig_2d.add_vline(x=K_l, line_dash="dot", line_color="green", annotation_text="Long Put", annotation_position="top left")

        fig_2d.add_trace(go.Scatter(x=x_vals, y=y_exp, mode='lines', name='Expiration', line=dict(color='gray', dash='dot', width=2)))
        fig_2d.add_trace(go.Scatter(x=x_vals, y=y_init, mode='lines', name='Entry Day', line=dict(color='purple', width=8, dash='dash')))
        fig_2d.add_trace(go.Scatter(x=x_vals, y=y_curr, mode='lines', name='Today', line=dict(color='#2563eb', width=4.5)))
    
        curr_cost = get_live_value(spot_price, strat, curr_dte/365.0, r_rate, iv_dec, K_s, K_l, K_cs, K_cl)
        curr_pnl = (entry_val - curr_cost) * qty * 100 if strat != "Deep OTM Tail Hedge (Long Put)" else (curr_cost - entry_val) * qty * 100
        
        fig_2d.add_trace(go.Scatter(x=[spot_price], y=[curr_pnl], mode='markers', name='Current Price', marker=dict(color='white', size=12, line=dict(color='black', width=2))))
        fig_2d.add_hline(y=0, line_dash="dot", line_color="black")
    
        fig_2d.update_layout(title="2D Theta Decay Profile", margin=dict(l=20, r=20, t=40, b=20), height=500, legend=dict(orientation="h", y=-0.2))
        st.plotly_chart(fig_2d, width="stretch")

    with col_3d:
        fig_3d = go.Figure(data=[go.Surface(
            z=z_3d, x=x_vals, y=y_3d, 
            colorscale=[[0, '#fef2f2'],[0.2, '#fca5a5'],[0.5, 'white'],[0.8, '#86efac'],[1, '#f0fdf4']],
            opacity=0.85, contours=dict(z=dict(show=True, color='black', width=1))
        )])

        skip_days = [int(init_dte), int(curr_dte), int(init_dte / 2.0), 0]
        for idx_d, d in enumerate(y_3d):
            if int(d) not in skip_days:
                fig_3d.add_trace(go.Scatter3d(x=x_vals, y=[d]*len(x_vals), z=z_3d[idx_d], mode='lines', line=dict(color='black', width=1), showlegend=False, hoverinfo='skip'))

        time_stop = 21.0
        
        # Scaffolding Planes (Restored Red Plane)
        def draw_plane_perimeter(x_coords, y_coords, z_coords, color):
            fig_3d.add_trace(go.Scatter3d(x=x_coords, y=y_coords, z=z_coords, mode='lines', line=dict(color=color, width=4), showlegend=False, hoverinfo='skip'))

        if strat in ["VRP: Bull Put Spread", "VRP: Iron Condor"]:
            fig_3d.add_trace(go.Scatter3d(x=[K_s, K_s], y=[time_stop, time_stop], z=[z_min, z_max], mode='lines', line=dict(color='black', width=6, dash='dash'), showlegend=False, hoverinfo='skip'))
            fig_3d.add_trace(go.Surface(x=[[K_s, K_s],[K_s, K_s]], y=[[0, init_dte],[0, init_dte]], z=[[z_min, z_min],[z_max, z_max]], colorscale=[[0, 'green'],[1, 'green']], opacity=0.225, showscale=False, hoverinfo='skip'))
            draw_plane_perimeter([K_s, K_s, K_s, K_s, K_s], [0, init_dte, init_dte, 0, 0], [z_min, z_min, z_max, z_max, z_min], 'green')
            
            fig_3d.add_trace(go.Scatter3d(x=[K_l, K_l], y=[time_stop, time_stop], z=[z_min, z_max], mode='lines', line=dict(color='black', width=6, dash='dash'), showlegend=False, hoverinfo='skip'))
            fig_3d.add_trace(go.Surface(x=[[K_l, K_l],[K_l, K_l]], y=[[0, init_dte],[0, init_dte]], z=[[z_min, z_min],[z_max, z_max]], colorscale=[[0, 'red'],[1, 'red']], opacity=0.225, showscale=False, hoverinfo='skip'))
            draw_plane_perimeter([K_l, K_l, K_l, K_l, K_l], [0, init_dte, init_dte, 0, 0], [z_min, z_min, z_max, z_max, z_min], 'red')
            
        if strat in ["VRP: Bear Call Spread", "VRP: Iron Condor"]:
            fig_3d.add_trace(go.Scatter3d(x=[K_cs, K_cs], y=[time_stop, time_stop], z=[z_min, z_max], mode='lines', line=dict(color='black', width=6, dash='dash'), showlegend=False, hoverinfo='skip'))
            fig_3d.add_trace(go.Surface(x=[[K_cs, K_cs],[K_cs, K_cs]], y=[[0, init_dte],[0, init_dte]], z=[[z_min, z_min],[z_max, z_max]], colorscale=[[0, 'green'],[1, 'green']], opacity=0.225, showscale=False, hoverinfo='skip'))
            draw_plane_perimeter([K_cs, K_cs, K_cs, K_cs, K_cs], [0, init_dte, init_dte, 0, 0], [z_min, z_min, z_max, z_max, z_min], 'green')
            
            fig_3d.add_trace(go.Scatter3d(x=[K_cl, K_cl], y=[time_stop, time_stop], z=[z_min, z_max], mode='lines', line=dict(color='black', width=6, dash='dash'), showlegend=False, hoverinfo='skip'))
            fig_3d.add_trace(go.Surface(x=[[K_cl, K_cl],[K_cl, K_cl]], y=[[0, init_dte],[0, init_dte]], z=[[z_min, z_min],[z_max, z_max]], colorscale=[[0, 'red'],[1, 'red']], opacity=0.225, showscale=False, hoverinfo='skip'))
            draw_plane_perimeter([K_cl, K_cl, K_cl, K_cl, K_cl], [0, init_dte, init_dte, 0, 0], [z_min, z_min, z_max, z_max, z_min], 'red')

        fig_3d.add_trace(go.Surface(x=[[x_vals[0], x_vals[-1]], [x_vals[0], x_vals[-1]]], y=[[time_stop, time_stop],[time_stop, time_stop]], z=[[z_min, z_min],[z_max, z_max]], colorscale=[[0, 'yellow'],[1, 'yellow']], opacity=0.30, showscale=False, hoverinfo='skip'))
        draw_plane_perimeter([x_vals[0], x_vals[-1], x_vals[-1], x_vals[0], x_vals[0]], [time_stop, time_stop, time_stop, time_stop, time_stop], [z_min, z_min, z_max, z_max, z_min], 'gold')
        
        fig_3d.add_trace(go.Surface(x=[[x_vals[0], x_vals[-1]],[x_vals[0], x_vals[-1]]], y=[[0, 0],[init_dte, init_dte]], z=[[0, 0],[0, 0]], colorscale=[[0, 'gray'],[1, 'gray']], opacity=0.30, showscale=False, hoverinfo='skip'))
        draw_plane_perimeter([x_vals[0], x_vals[-1], x_vals[-1], x_vals[0], x_vals[0]], [0, 0, init_dte, init_dte, 0], [0, 0, 0, 0, 0], 'gray')

        # Intersections between Planes (Black dashed lines)
        fig_3d.add_trace(go.Scatter3d(x=[x_vals[0], x_vals[-1]], y=[time_stop, time_stop], z=[0, 0], mode='lines', line=dict(color='black', width=6, dash='dash'), showlegend=False, hoverinfo='skip')) # Yellow & Gray

        if strat in ["VRP: Bull Put Spread", "VRP: Iron Condor"]:
            fig_3d.add_trace(go.Scatter3d(x=[K_s, K_s], y=[0, init_dte], z=[0, 0], mode='lines', line=dict(color='black', width=6, dash='dash'), showlegend=False, hoverinfo='skip')) # Green & Gray (Put)
            fig_3d.add_trace(go.Scatter3d(x=[K_l, K_l], y=[0, init_dte], z=[0, 0], mode='lines', line=dict(color='black', width=6, dash='dash'), showlegend=False, hoverinfo='skip')) # Red & Gray (Put)
        if strat in ["VRP: Bear Call Spread", "VRP: Iron Condor"]:
            fig_3d.add_trace(go.Scatter3d(x=[K_cs, K_cs], y=[0, init_dte], z=[0, 0], mode='lines', line=dict(color='black', width=6, dash='dash'), showlegend=False, hoverinfo='skip')) # Green & Gray (Call)
            fig_3d.add_trace(go.Scatter3d(x=[K_cl, K_cl], y=[0, init_dte], z=[0, 0], mode='lines', line=dict(color='black', width=6, dash='dash'), showlegend=False, hoverinfo='skip')) # Red & Gray (Call)
        if strat == "Deep OTM Tail Hedge (Long Put)":
            fig_3d.add_trace(go.Scatter3d(x=[K_l, K_l], y=[0, init_dte], z=[0, 0], mode='lines', line=dict(color='black', width=6, dash='dash'), showlegend=False, hoverinfo='skip'))

        # Breakeven Roots (The Grey Cross)
        roots_by_day = []
        for idx_d, d in enumerate(y_3d):
            z_row = z_3d[idx_d]
            day_roots = []
            for i in range(len(x_vals)-1):
                if (z_row[i] * z_row[i+1]) <= 0:
                    z1, z2 = z_row[i], z_row[i+1]
                    p1, p2 = x_vals[i], x_vals[i+1]
                    p_be = p1 - z1 * (p2 - p1) / (z2 - z1) if z2 != z1 else p1
                    day_roots.append(p_be)
            roots_by_day.append((d, day_roots))

        max_roots = max([len(r) for d, r in roots_by_day]) if roots_by_day else 0
        for r_idx in range(max_roots):
            be_x, be_y, be_z = [], [], []
            for d, roots in roots_by_day:
                if r_idx < len(roots):
                    be_x.append(roots[r_idx])
                    be_y.append(d)
                    be_z.append(0)
            fig_3d.add_trace(go.Scatter3d(x=be_x, y=be_y, z=be_z, mode='lines', name='Breakeven ($0)', line=dict(color='gray', width=10), showlegend=False, hoverinfo='skip'))
            
        # Yellow Plane Intersection (21-DTE Time Stop)
        z_yellow = []
        for px in x_vals:
            v_yellow = get_live_value(px, strat, time_stop/365.0, r_rate, iv_dec, K_s, K_l, K_cs, K_cl)
            pnl_yellow = (entry_val - v_yellow) * qty * 100 if strat != "Deep OTM Tail Hedge (Long Put)" else (v_yellow - entry_val) * qty * 100
            z_yellow.append(pnl_yellow)
        fig_3d.add_trace(go.Scatter3d(x=x_vals, y=[time_stop]*len(x_vals), z=z_yellow, mode='lines', line=dict(color='gold', width=10), showlegend=False, hoverinfo='skip'))
        
        # Green & Red Plane Intersections (Strikes)
        def plot_strike_intersection(strike, color):
            z_strike = []
            for d in y_3d:
                v_strike = get_live_value(strike, strat, d/365.0, r_rate, iv_dec, K_s, K_l, K_cs, K_cl)
                pnl_strike = (entry_val - v_strike) * qty * 100 if strat != "Deep OTM Tail Hedge (Long Put)" else (v_strike - entry_val) * qty * 100
                z_strike.append(pnl_strike)
            fig_3d.add_trace(go.Scatter3d(x=[strike]*len(y_3d), y=y_3d, z=z_strike, mode='lines', line=dict(color=color, width=10), showlegend=False, hoverinfo='skip'))
            
        if strat in ["VRP: Bull Put Spread", "VRP: Iron Condor"]:
            plot_strike_intersection(K_s, 'green')
            plot_strike_intersection(K_l, 'red')
        if strat in ["VRP: Bear Call Spread", "VRP: Iron Condor"]:
            plot_strike_intersection(K_cs, 'green')
            plot_strike_intersection(K_cl, 'red')
        if strat == "Deep OTM Tail Hedge (Long Put)":
            plot_strike_intersection(K_l, 'green') # For tail hedge, the long put is the primary asset plane

        # Theta Glide Path
        y_glide = [d for d in y_3d if d <= curr_dte]
        z_glide = []
        for d in y_glide:
            T_glide = max(d / 365.0, 0.0001)
            lc = get_live_value(spot_price, strat, T_glide, r_rate, iv_dec, K_s, K_l, K_cs, K_cl)
            z_glide.append((entry_val - lc) * qty * 100 if strat != "Deep OTM Tail Hedge (Long Put)" else (lc - entry_val) * qty * 100)
            
        fig_3d.add_trace(go.Scatter3d(x=[spot_price] * len(y_glide), y=y_glide, z=z_glide, mode='lines', name='Theta Glide Path', line=dict(color='cyan', width=8, dash='dashdot')))

        # Entry Day, 50% DTE, and Today lines
        half_dte = init_dte / 2.0
        y_half = []
        for px in x_vals:
            lc_h = get_live_value(px, strat, half_dte/365.0, r_rate, iv_dec, K_s, K_l, K_cs, K_cl)
            y_half.append((entry_val - lc_h) * qty * 100 if strat != "Deep OTM Tail Hedge (Long Put)" else (lc_h - entry_val) * qty * 100)

        fig_3d.add_trace(go.Scatter3d(x=x_vals, y=[init_dte]*len(x_vals), z=y_init, mode='lines', name='Entry Day', line=dict(color='purple', width=10, dash='dash')))
        fig_3d.add_trace(go.Scatter3d(x=x_vals, y=[half_dte]*len(x_vals), z=y_half, mode='lines', name='50% DTE', line=dict(color='orange', width=6, dash='dash')))
        fig_3d.add_trace(go.Scatter3d(x=x_vals, y=[curr_dte]*len(x_vals), z=y_curr, mode='lines', name='Today', line=dict(color='#2563eb', width=7)))
        fig_3d.add_trace(go.Scatter3d(x=x_vals, y=[0]*len(x_vals), z=y_exp, mode='lines', name='Expiration Day', line=dict(color='gray', width=10, dash='dot')))

        # Current Price Anchor
        fig_3d.add_trace(go.Scatter3d(x=[spot_price], y=[curr_dte], z=[curr_pnl], mode='markers', name='Current Price', marker=dict(color='white', size=8, line=dict(color='black', width=2))))
        fig_3d.add_trace(go.Scatter3d(x=[spot_price, spot_price], y=[curr_dte, curr_dte], z=[0, curr_pnl], mode='lines', name='Anchor Line', line=dict(color='white', width=3, dash='dot'), showlegend=False, hoverinfo='skip'))

        fig_3d.update_layout(
            title=f"3D Volatility Surface: {strat}", margin=dict(l=0, r=0, b=0, t=40), height=500, 
            scene=dict(
                xaxis_title='Underlying Price (USD)', yaxis_title='Days to Expiration (DTE)', zaxis_title='Unrealized P&L (USD)', 
                yaxis=dict(autorange='reversed'), camera=dict(eye=dict(x=-1.25, y=-1.25, z=1.25))
            ),
            legend=dict(orientation="h", yanchor="top", y=-0.05, xanchor="left", x=0)
        )
        st.plotly_chart(fig_3d, width="stretch")

    st.markdown("""
    <div style="display: flex; justify-content: center; gap: 20px; font-size: 12px; color: #94a3b8; margin-top: -10px; margin-bottom: 20px; flex-wrap: wrap;">
        <div style="display: flex; align-items: center; gap: 6px;"><div style="width: 12px; height: 12px; background-color: rgba(34, 197, 94, 0.4); border: 1px solid green;"></div> <b>Green Plane:</b> Short Strike Zone</div>
        <div style="display: flex; align-items: center; gap: 6px;"><div style="width: 12px; height: 12px; background-color: rgba(239, 68, 68, 0.4); border: 1px solid red;"></div> <b>Red Plane:</b> Max Loss Zone</div>
        <div style="display: flex; align-items: center; gap: 6px;"><div style="width: 12px; height: 12px; background-color: rgba(250, 204, 21, 0.4); border: 1px solid gold;"></div> <b>Yellow Plane:</b> 21-DTE Time Stop (Gamma Cliff)</div>
        <div style="display: flex; align-items: center; gap: 6px;"><div style="width: 12px; height: 12px; background-color: rgba(156, 163, 175, 0.4); border: 1px solid gray;"></div> <b>Grey Plane:</b> USD 0 Breakeven Floor</div>
    </div>
    """, unsafe_allow_html=True)
    
    # Dynamic Educational Footer
    st.markdown("---")
    if strat == "VRP: Bull Put Spread":
        st.info("**Strategy Analysis (Bull Put Spread):** This is a bullish/neutral credit spread. You collect a premium upfront by selling a Put option, and cap your catastrophic risk by buying a deeper OTM Put. The trade profits as long as the underlying asset stays above your Short Put strike (Green Plane). Time decay (Theta) works in your favor.")
    elif strat == "VRP: Bear Call Spread":
        st.info("**Strategy Analysis (Bear Call Spread):** This is a bearish/neutral credit spread. You collect a premium upfront by selling a Call option, and cap your upside risk by buying a further OTM Call. The trade profits as long as the asset stays below your Short Call strike (Green Plane). Time decay works in your favor.")
    elif strat == "VRP: Iron Condor":
        st.info("**Strategy Analysis (Iron Condor):** This is a market-neutral strategy composed of a Bull Put Spread and a Bear Call Spread. You collect premium on both sides, creating a 'profit tent' between the two Green Planes. The trade profits if the asset trades flat and remains rangebound. This strategy benefits heavily from Time decay and Volatility crush.")
    elif strat == "Deep OTM Tail Hedge (Long Put)":
        st.info("**Strategy Analysis (Tail Hedge):** This is a catastrophic insurance policy. You pay a debit upfront to buy a deep Out-of-the-Money Put. Notice how the Theta Glide path is negative (it bleeds money every day). However, if the market crashes (moving violently to the left), the Delta and Gamma explode, yielding massive convex returns to offset portfolio losses.")

# ==========================================
# 9. EDUCATIONAL CONTENT & EXPECTANCY CHART
# ==========================================
with tab2:
    st.markdown("---")
    st.markdown("### 📊 The Mathematical Edge: Closed Trade Expectancy")
    st.markdown("This dashboard represents real-world performance of the Volatility Risk Premium (VRP) strategy.")
    
    df = st.session_state.portfolio_df
    
    if df is not None and not df.empty:
        wins = df[df['RealizedPnL'] > 0]
        losses = df[df['RealizedPnL'] <= 0]
        
        win_rate = (len(wins) / len(df)) * 100 if len(df) > 0 else 0
        avg_win = wins['RealizedPnL'].mean() if len(wins) > 0 else 0
        avg_loss = losses['RealizedPnL'].mean() if len(losses) > 0 else 0
        gross_profit = wins['RealizedPnL'].sum()
        gross_loss = abs(losses['RealizedPnL'].sum())
        profit_factor = gross_profit / gross_loss if gross_loss != 0 else float('inf')
        math_expectancy = df['RealizedPnL'].mean() if len(df) > 0 else 0
        
        col_e1, col_e2, col_e3, col_e4 = st.columns(4)
        col_e1.markdown(f"<div class='info-box' style='text-align:center;'><span style='font-size:12px; color:#64748b; font-weight:bold;'>WIN RATE</span><br><span style='font-size:24px; font-weight:900; color:#16a34a;'>{win_rate:.1f}%</span></div>", unsafe_allow_html=True)
        col_e2.markdown(f"<div class='info-box' style='text-align:center;'><span style='font-size:12px; color:#64748b; font-weight:bold;'>AVERAGE WIN VS LOSS</span><br><span style='font-size:16px; font-weight:bold; color:#16a34a;'>+${avg_win:,.0f}</span> <span style='color:#64748b;'>/</span> <span style='font-size:16px; font-weight:bold; color:#dc2626;'>-${abs(avg_loss):,.0f}</span></div>", unsafe_allow_html=True)
        col_e3.markdown(f"<div class='info-box' style='text-align:center;'><span style='font-size:12px; color:#64748b; font-weight:bold;'>PROFIT FACTOR</span><br><span style='font-size:24px; font-weight:900; color:#16a34a;'>{profit_factor:.2f}</span></div>", unsafe_allow_html=True)
        col_e4.markdown(f"<div class='info-box' style='text-align:center; border-bottom: 3px solid #16a34a;'><span style='font-size:12px; color:#64748b; font-weight:bold;'>MATH EXPECTANCY ⓘ</span><br><span style='font-size:24px; font-weight:900; color:#16a34a;'>${math_expectancy:,.2f}</span></div>", unsafe_allow_html=True)
        
        fig_exp = go.Figure(go.Scatter(
            x=df['CloseDate'], y=df['ROC'], mode='markers',
            text=df.apply(lambda row: f"Symbol: {row['Symbol']}<br>PnL: ${row['RealizedPnL']:.2f}<br>Days Held: {row['DaysHeld']}", axis=1),
            hoverinfo="text",
            marker=dict(
                size=df['RealizedPnL'].abs(), sizemode='area', sizeref=2.*max(df['RealizedPnL'].abs())/(40.**2), sizemin=8,
                color=df['DaysHeld'], colorscale='RdYlBu', showscale=True, colorbar=dict(title="Holding Time (Days)"),
                line=dict(width=1.5, color='black')
            )
        ))
        fig_exp.add_hline(y=0, line_color="black", line_width=2)
        fig_exp.update_layout(title="Behavioral Bubble Chart (Size = Abs PnL | Color = Days in Trade)", yaxis_title="Return on Capital (ROC) %", height=400, plot_bgcolor='rgba(0,0,0,0)', margin=dict(l=0, r=0, t=40, b=0))
        st.plotly_chart(fig_exp, width="stretch")
        
    else:
        st.info("👈 Please load the Golden Path Demo Data or upload a Flex Query from the sidebar to view portfolio performance.")
        
    st.markdown("---")
    col_edu1, col_edu2 = st.columns(2)

    with col_edu1:
        st.markdown("### What is the Volatility Risk Premium (VRP)?")
        st.markdown("""
        The VRP is a persistent market anomaly where the implied volatility (IV) priced into options contracts is historically higher than the actual realized volatility of the underlying asset. 
        
        In simple terms: **Market participants consistently overpay for crash insurance.** By systematically selling Out-of-the-Money (OTM) put spreads on the S&P 500, we act as the insurance company, collecting the premium as it decays over time (Theta).
        """)
        
        st.markdown("### How We Enhanced It (The Convexity Barbell)")
        st.markdown("""
        Selling insurance is profitable until a Black Swan event occurs. To prevent catastrophic ruin, we employ two strict enhancements:
        1. **The 21-DTE Time Stop:** We never hold short options into expiration. We mechanically close trades at 21 Days to Expiration to avoid the "Gamma Cliff" (where price sensitivity explodes).
        2. **The Tail Hedge:** We take 10% of our VRP winnings and purchase deep OTM 120-DTE puts. If the market crashes 30%, our short puts hit a defined max loss, but our Tail Hedges explode in value, covering the liability.
        """)

    with col_edu2:
        st.markdown("""
        <div style="background-color: #eff6ff; border: 1px solid #bfdbfe; border-radius: 12px; padding: 24px; color: #2352d9; font-size: 14px; height: 100%;">
            <h4 style="font-weight: bold; font-size: 16px; margin-bottom: 12px; text-transform: uppercase; letter-spacing: 0.05em;">Reference Guide: The Greeks Explained</h4>
            <p style="margin-bottom: 12px;"><strong style="color: #1d4ed8; background-color: #dbeafe; padding: 2px 4px; border-radius: 4px;">Delta (Direction):</strong> Measures directional exposure. A Net Delta of 15 means your position gains USD 15 if the index goes up 1 point. In credit spreads, Delta also acts as your probability gauge (e.g., selling a 20 Delta strike equates to an 80% chance of success).</p>
            <p style="margin-bottom: 12px;"><strong style="color: #1d4ed8; background-color: #dbeafe; padding: 2px 4px; border-radius: 4px;">Gamma (Acceleration):</strong> Measures the rate of change of Delta. High Gamma means your risk is accelerating uncontrollably (which peaks near expiration). This is exactly why we mechanically close trades at 21 DTE—to avoid Gamma explosions.</p>
            <p style="margin-bottom: 12px;"><strong style="color: #1d4ed8; background-color: #dbeafe; padding: 2px 4px; border-radius: 4px;">Theta (Time Decay):</strong> Your daily salary. This positive number represents the dollar amount deposited into your unrealized P&L simply because one day passed, assuming all other market conditions remain totally flat.</p>
            <p><strong style="color: #1d4ed8; background-color: #dbeafe; padding: 2px 4px; border-radius: 4px;">Vega (Fear Premium):</strong> Measures sensitivity to Implied Volatility (VIX). Because you sold insurance, your Net Vega is negative. This means if Implied Volatility drops by 1%, your portfolio instantly gains that dollar amount in profit (Volatility Crush).</p>
        </div>
        """, unsafe_allow_html=True)

    st.markdown("---")
    st.markdown("<div style='text-align: center; color: #64748b; font-size: 12px;'><b>Academic Foundation:</b> The quantitative edge demonstrated above is rooted in peer-reviewed financial science. For a deep dive into the mechanics of the VRP, read AQR Capital Management's seminal paper: <a href='https://www.aqr.com/-/media/AQR/Documents/White-Papers/Understanding-the-Volatility-Risk-Premium.pdf' target='_blank'>Understanding the Volatility Risk Premium</a>.</div>", unsafe_allow_html=True)
