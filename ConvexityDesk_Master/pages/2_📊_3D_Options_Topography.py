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
            /* Hide the main Streamlit interface entirely */
            .stApp > header { display: none !important; }
            section.main > div.block-container { display: none !important; }
            
            /* Show the full-screen blocker */
            .mobile-blocker { 
                display: flex !important; 
                flex-direction: column; 
                justify-content: center; 
                align-items: center; 
                height: 100vh; 
                width: 100vw; 
                background-color: #0e1117; 
                color: white; 
                text-align: center; 
                padding: 40px; 
                position: fixed; 
                top: 0; 
                left: 0; 
                z-index: 999999; 
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
    .locked-feature { opacity: 0.5; pointer-events: none; filter: grayscale(100%); }
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

@st.cache_data(ttl=3600)
def get_live_market_data(ticker="SPY"):
    try:
        spot = float(yf.Ticker(ticker).history(period="1d")['Close'].iloc[-1])
        vix = float(yf.Ticker("^VIX").history(period="1d")['Close'].iloc[-1])
        return spot, vix
    except:
        return 550.0, 15.0


def load_portfolio_data(file_or_path):
    import pandas as pd
    import numpy as np
    try:
        df = pd.read_csv(file_or_path)
        df['CloseDate'] = pd.to_datetime(df['CloseDate'])
        df['EntryDate'] = pd.to_datetime(df['EntryDate'])
        df['DaysHeld'] = (df['CloseDate'] - df['EntryDate']).dt.days
        df['ROC'] = (df['RealizedPnL'] / df['CapitalAtRisk']) * 100
        return df
    except Exception as e:
        import streamlit as st
        st.error(f"Error loading data: {e}")
        return None

# ==========================================
# 3. SESSION STATE & FUNNEL LOGIC
# ==========================================
if 'customizations' not in st.session_state: st.session_state.customizations = 0
if 'unlocked' not in st.session_state: st.session_state.unlocked = False

if 'portfolio_df' not in st.session_state: st.session_state.portfolio_df = None

if 'trade_params' not in st.session_state:
    init_spot, init_vix = get_live_market_data("SPY")
    st.session_state.trade_params = {
        'ticker': 'SPY', 'dte': 45.0, 'k_s': float(round(init_spot * 0.95)),
        'k_l': float(round(init_spot * 0.95)) - 5.0, 'qty': 10.0, 'spot': init_spot, 'vix': init_vix
    }

# ==========================================
# 4. SIDEBAR: THE PLG FUNNEL GATE
# ==========================================
with st.sidebar:
    st.markdown("### ⚙️ Trade Parameters")
    is_locked = st.session_state.customizations >= 1 and not st.session_state.unlocked
    
    with st.form("trade_form"):
        tckr_input = st.text_input("Ticker Symbol", value=st.session_state.trade_params['ticker'], disabled=is_locked)
        dte_input = st.number_input("Days to Expiration (DTE)", value=float(st.session_state.trade_params['dte']), disabled=is_locked)
        ks_input = st.number_input("Short Put Strike", value=float(st.session_state.trade_params['k_s']), disabled=is_locked)
        kl_input = st.number_input("Long Put Strike", value=float(st.session_state.trade_params['k_l']), disabled=is_locked)
        qty_input = st.number_input("Contracts", value=float(st.session_state.trade_params['qty']), disabled=is_locked)
        
        btn_text = "Render Custom Topography" if st.session_state.customizations == 0 else ("Locked" if is_locked else "Update Topography")
        submit = st.form_submit_button(btn_text, type="primary", disabled=is_locked)
        
        if submit and not is_locked:
            new_spot, new_vix = get_live_market_data(tckr_input)
            st.session_state.trade_params = {
                'ticker': tckr_input.upper(), 'dte': dte_input, 'k_s': ks_input, 
                'k_l': kl_input, 'qty': qty_input, 'spot': new_spot, 'vix': new_vix
            }
            st.session_state.customizations += 1
            st.rerun()

    if is_locked:
        st.markdown("---")
        st.markdown("### 🔒 Premium Feature")
        st.caption("You have used your free customization. Join the Convexity Desk to unlock unlimited access.")
        st.link_button("🔓 Subscribe Now", "https://convexitydesk.com/#/portal/signup", type="primary", use_container_width=True)

    with st.expander("🔑 Developer Access"):
        dev_code = st.text_input("Enter Code", type="password")
        if st.button("Unlock"):
            if dev_code == "ESTATE2026":
                st.session_state.unlocked = True
                st.success("Unlocked!")
                st.rerun()
            else:
                st.error("Invalid code.")


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

tab1, tab2 = st.tabs(["🕹️ Live Trade Simulator", "📈 Portfolio Dashboard"])

with tab1:
    st.markdown("""
    <div class='premium-banner'>
        <h2 style='margin:0; color:white;'>Institutional Options Topography Engine</h2>
        <p style='margin:5px 0 0 0; color:#94a3b8;'>Visualizing the Gamma Cliff and Theta Glide Path of a Live Credit Spread.</p>
    </div>
    """, unsafe_allow_html=True)

    st.markdown("""
    <div style="background-color: #f8fafc; border-left: 4px solid #3b82f6; padding: 12px 16px; border-radius: 4px; margin-bottom: 20px; font-size: 14px; color: #334155; box-shadow: 0 1px 2px rgba(0,0,0,0.05);">
        <b>ℹ️ Data Freshness & Controls:</b> Market data is sourced via Yahoo Finance (approx. 15-min delayed) and cached hourly to ensure server stability. Use the sliders below to stress-test the live position against sudden Volatility (VIX) spikes and Time (Theta) decay.
    </div>
    """, unsafe_allow_html=True)

    p = st.session_state.trade_params
    spot_price = p['spot']
    K_s = p['k_s']
    K_l = p['k_l']
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

    t0_s_price, _, _, _, _ = get_put_greeks(spot_price, K_s, init_dte/365.0, r_rate, iv_dec)
    t0_l_price, _, _, _, _ = get_put_greeks(spot_price, K_l, init_dte/365.0, r_rate, iv_dec)
    prem_collected = t0_s_price - t0_l_price

    # ==========================================
    # 6. 2D & 3D SURFACE CALCULATION
    # ==========================================
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
                val = (prem_collected - (max(K_s - px, 0) - max(K_l - px, 0))) * qty * 100
                z_row.append(val)
                if d == 0: y_exp.append(val)
            else:
                t_s, _, _, _, _ = get_put_greeks(px, K_s, T_3d, r_rate, iv_dec)
                t_l, _, _, _, _ = get_put_greeks(px, K_l, T_3d, r_rate, iv_dec)
                val = (prem_collected - (t_s - t_l)) * qty * 100
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
        fig_2d.add_vrect(x0=K_s, x1=max_plot, fillcolor="green", opacity=0.05, layer="below", line_width=0)    
        fig_2d.add_vrect(x0=min_plot, x1=K_l, fillcolor="red", opacity=0.05, layer="below", line_width=0)
        fig_2d.add_vline(x=K_s, line_dash="dot", line_color="green", annotation_text="Short", annotation_position="top left")
        fig_2d.add_vline(x=K_l, line_dash="dot", line_color="red", annotation_text="Long", annotation_position="top right")

        fig_2d.add_trace(go.Scatter(x=x_vals, y=y_exp, mode='lines', name='Expiration', line=dict(color='gray', dash='dot', width=2)))
        fig_2d.add_trace(go.Scatter(x=x_vals, y=y_init, mode='lines', name='Entry Day', line=dict(color='purple', width=8, dash='dash')))
        fig_2d.add_trace(go.Scatter(x=x_vals, y=y_curr, mode='lines', name='Today', line=dict(color='#2563eb', width=4.5)))
    
        tC_s, _, _, _, _ = get_put_greeks(spot_price, K_s, curr_dte/365.0, r_rate, iv_dec)
        tC_l, _, _, _, _ = get_put_greeks(spot_price, K_l, curr_dte/365.0, r_rate, iv_dec)
        curr_pnl = (prem_collected - (tC_s - tC_l)) * qty * 100
        fig_2d.add_trace(go.Scatter(x=[spot_price], y=[curr_pnl], mode='markers', name='Current Price', marker=dict(color='white', size=12, line=dict(color='black', width=2))))
    
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

        # Scaffolding Planes
        z_green, z_red = [], []
        for d in y_3d:
            T_3d = max(d / 365.0, 0.0001)
            t_s_g, _, _, _, _ = get_put_greeks(K_s, K_s, T_3d, r_rate, iv_dec)
            t_l_g, _, _, _, _ = get_put_greeks(K_s, K_l, T_3d, r_rate, iv_dec)
            z_green.append((prem_collected - (t_s_g - t_l_g)) * qty * 100)
            t_s_r, _, _, _, _ = get_put_greeks(K_l, K_s, T_3d, r_rate, iv_dec)
            t_l_r, _, _, _, _ = get_put_greeks(K_l, K_l, T_3d, r_rate, iv_dec)
            z_red.append((prem_collected - (t_s_r - t_l_r)) * qty * 100)
        
        time_stop = 21.0
        T_stop = max(time_stop / 365.0, 0.0001)
        z_yellow = []
        for px in x_vals:
            t_s_y, _, _, _, _ = get_put_greeks(px, K_s, T_stop, r_rate, iv_dec)
            t_l_y, _, _, _, _ = get_put_greeks(px, K_l, T_stop, r_rate, iv_dec)
            z_yellow.append((prem_collected - (t_s_y - t_l_y)) * qty * 100)

        fig_3d.add_trace(go.Scatter3d(x=[K_s]*len(y_3d), y=y_3d, z=z_green, mode='lines', name='Short Strike Limit', line=dict(color='green', width=6), showlegend=False, hoverinfo='skip'))
        fig_3d.add_trace(go.Scatter3d(x=[K_l]*len(y_3d), y=y_3d, z=z_red, mode='lines', name='Max Loss Limit', line=dict(color='red', width=6), showlegend=False, hoverinfo='skip'))
        fig_3d.add_trace(go.Scatter3d(x=x_vals, y=[time_stop]*len(x_vals), z=z_yellow, mode='lines', name='21-DTE Time Stop Limit', line=dict(color='gold', width=6), showlegend=False, hoverinfo='skip'))

        fig_3d.add_trace(go.Surface(x=[[K_s, K_s],[K_s, K_s]], y=[[0, init_dte],[0, init_dte]], z=[[z_min, z_min],[z_max, z_max]], colorscale=[[0, 'green'],[1, 'green']], opacity=0.225, showscale=False, hoverinfo='skip'))
        fig_3d.add_trace(go.Surface(x=[[K_l, K_l],[K_l, K_l]], y=[[0, init_dte],[0, init_dte]], z=[[z_min, z_min],[z_max, z_max]], colorscale=[[0, 'red'],[1, 'red']], opacity=0.225, showscale=False, hoverinfo='skip'))
        fig_3d.add_trace(go.Surface(x=[[x_vals[0], x_vals[-1]], [x_vals[0], x_vals[-1]]], y=[[time_stop, time_stop],[time_stop, time_stop]], z=[[z_min, z_min],[z_max, z_max]], colorscale=[[0, 'yellow'],[1, 'yellow']], opacity=0.30, showscale=False, hoverinfo='skip'))
        fig_3d.add_trace(go.Surface(x=[[x_vals[0], x_vals[-1]],[x_vals[0], x_vals[-1]]], y=[[0, 0],[init_dte, init_dte]], z=[[0, 0],[0, 0]], colorscale=[[0, 'gray'],[1, 'gray']], opacity=0.30, showscale=False, hoverinfo='skip'))

        # Wireframes
        fig_3d.add_trace(go.Scatter3d(x=[K_s, K_s], y=[time_stop, time_stop], z=[z_min, z_max], mode='lines', line=dict(color='black', width=6, dash='dash'), showlegend=False, hoverinfo='skip'))
        fig_3d.add_trace(go.Scatter3d(x=[K_l, K_l], y=[time_stop, time_stop], z=[z_min, z_max], mode='lines', line=dict(color='black', width=6, dash='dash'), showlegend=False, hoverinfo='skip'))
        fig_3d.add_trace(go.Scatter3d(x=[K_s, K_s, K_s, K_s, K_s], y=[0, init_dte, init_dte, 0, 0], z=[z_min, z_min, z_max, z_max, z_min], mode='lines', line=dict(color='green', width=3), showlegend=False, hoverinfo='skip'))
        fig_3d.add_trace(go.Scatter3d(x=[K_l, K_l, K_l, K_l, K_l], y=[0, init_dte, init_dte, 0, 0], z=[z_min, z_min, z_max, z_max, z_min], mode='lines', line=dict(color='red', width=3), showlegend=False, hoverinfo='skip'))
        fig_3d.add_trace(go.Scatter3d(x=[x_vals[0], x_vals[-1], x_vals[-1], x_vals[0], x_vals[0]], y=[time_stop, time_stop, time_stop, time_stop, time_stop], z=[z_min, z_min, z_max, z_max, z_min], mode='lines', line=dict(color='yellow', width=3), showlegend=False, hoverinfo='skip'))
        fig_3d.add_trace(go.Scatter3d(x=[x_vals[0], x_vals[-1], x_vals[-1], x_vals[0], x_vals[0]], y=[0, 0, init_dte, init_dte, 0], z=[0, 0, 0, 0, 0], mode='lines', line=dict(color='gray', width=3), showlegend=False, hoverinfo='skip'))

        # Breakeven Roots
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

        # Targets & Stops
        target_pnl = (prem_collected / 2.0) * qty * 100
        fig_3d.add_trace(go.Scatter3d(x=[spot_price], y=[curr_dte], z=[target_pnl], mode='markers', name='50% Target', marker=dict(color='#16a34a', size=15, symbol='cross')))
        stop_loss_pnl = -(abs(prem_collected) * 2.0) * qty * 100 
        fig_3d.add_trace(go.Scatter3d(x=[spot_price], y=[curr_dte], z=[stop_loss_pnl], mode='markers', name='200% Stop Loss', marker=dict(color='#dc2626', size=15, symbol='cross')))

        # Theta Glide Path
        y_glide = [d for d in y_3d if d <= curr_dte]
        z_glide = []
        for d in y_glide:
            T_glide = max(d / 365.0, 0.0001)
            t_s_glide, _, _, _, _ = get_put_greeks(spot_price, K_s, T_glide, r_rate, iv_dec)
            t_l_glide, _, _, _, _ = get_put_greeks(spot_price, K_l, T_glide, r_rate, iv_dec)
            z_glide.append((prem_collected - (t_s_glide - t_l_glide)) * qty * 100)
        fig_3d.add_trace(go.Scatter3d(x=[spot_price] * len(y_glide), y=y_glide, z=z_glide, mode='lines', name='Theta Glide Path', line=dict(color='cyan', width=8, dash='dashdot')))

        # Entry Day, 50% DTE, and Today lines
        half_dte = init_dte / 2.0
        y_half = []
        for px in x_vals:
            tH_s, _, _, _, _ = get_put_greeks(px, K_s, half_dte/365.0, r_rate, iv_dec)
            tH_l, _, _, _, _ = get_put_greeks(px, K_l, half_dte/365.0, r_rate, iv_dec)
            y_half.append((prem_collected - (tH_s - tH_l)) * qty * 100)

        fig_3d.add_trace(go.Scatter3d(x=x_vals, y=[init_dte]*len(x_vals), z=y_init, mode='lines', name='Entry Day', line=dict(color='purple', width=10, dash='dash')))
        fig_3d.add_trace(go.Scatter3d(x=x_vals, y=[half_dte]*len(x_vals), z=y_half, mode='lines', name='50% DTE', line=dict(color='orange', width=6, dash='dash')))
        fig_3d.add_trace(go.Scatter3d(x=x_vals, y=[curr_dte]*len(x_vals), z=y_curr, mode='lines', name='Today', line=dict(color='#2563eb', width=7)))

        # Current Price Anchor
        fig_3d.add_trace(go.Scatter3d(x=[spot_price], y=[curr_dte], z=[curr_pnl], mode='markers', name='Current Price', marker=dict(color='white', size=8, line=dict(color='black', width=2))))
        fig_3d.add_trace(go.Scatter3d(x=[spot_price, spot_price], y=[curr_dte, curr_dte], z=[0, curr_pnl], mode='lines', name='Anchor Line', line=dict(color='white', width=3, dash='dot'), showlegend=False, hoverinfo='skip'))
        fig_3d.add_trace(go.Scatter3d(x=[spot_price], y=[curr_dte], z=[0], mode='markers', name='Zero Floor Anchor', marker=dict(color='white', size=5, symbol='cross'), showlegend=False, hoverinfo='skip'))            

        fig_3d.update_layout(
            title="3D Volatility Surface", margin=dict(l=0, r=0, b=0, t=40), height=500, 
            scene=dict(
                xaxis_title='Underlying Price (USD)', yaxis_title='Days to Expiration (DTE)', zaxis_title='Unrealized P&L (USD)', 
                yaxis=dict(autorange='reversed'), camera=dict(eye=dict(x=-1.25, y=-1.25, z=1.25))
            ),
            legend=dict(orientation="h", yanchor="top", y=-0.05, xanchor="left", x=0)
        )
        st.plotly_chart(fig_3d, width="stretch")

    st.markdown("""
    <div style="display: flex; justify-content: center; gap: 20px; font-size: 12px; color: #94a3b8; margin-top: -10px; margin-bottom: 20px; flex-wrap: wrap;">
        <div style="display: flex; align-items: center; gap: 6px;"><div style="width: 12px; height: 12px; background-color: rgba(34, 197, 94, 0.4); border: 1px solid green;"></div> <b>Green Plane:</b> Short Strike (Max Profit Zone)</div>
        <div style="display: flex; align-items: center; gap: 6px;"><div style="width: 12px; height: 12px; background-color: rgba(239, 68, 68, 0.4); border: 1px solid red;"></div> <b>Red Plane:</b> Long Strike (Max Loss Zone)</div>
        <div style="display: flex; align-items: center; gap: 6px;"><div style="width: 12px; height: 12px; background-color: rgba(250, 204, 21, 0.4); border: 1px solid gold;"></div> <b>Yellow Plane:</b> 21-DTE Time Stop (Gamma Cliff)</div>
        <div style="display: flex; align-items: center; gap: 6px;"><div style="width: 12px; height: 12px; background-color: rgba(156, 163, 175, 0.4); border: 1px solid gray;"></div> <b>Grey Plane:</b> USD 0 Breakeven Floor</div>
    </div>
    """, unsafe_allow_html=True)

    # ==========================================
    # 8. GREEKS & METRICS TABLE
    # ==========================================
    tC_s_d, tC_s_g, tC_s_t, tC_s_v = get_put_greeks(spot_price, K_s, curr_dte/365.0, r_rate, iv_dec)[1:]
    tC_l_d, tC_l_g, tC_l_t, tC_l_v = get_put_greeks(spot_price, K_l, curr_dte/365.0, r_rate, iv_dec)[1:]

    net_delta = (tC_l_d - tC_s_d) * qty * 100
    net_theta = (tC_l_t - tC_s_t) * qty * 100
    net_vega = (tC_l_v - tC_s_v) * qty * 100
    margin_req = (K_s - K_l) * 100 * qty

    st.markdown(f"""
    <div style="overflow-x: auto; border-radius: 8px; border: 1px solid #e5e7eb; box-shadow: 0 1px 2px 0 rgba(0, 0, 0, 0.05); margin-top: 20px; margin-bottom: 30px;">
        <table style="min-w-full; width: 100%; border-collapse: collapse; background-color: white; text-align: center;">
            <thead style="background-color: #1e293b; color: white;">
                <tr>
                    <th style="padding: 12px; font-weight: 600;">Live Spot Price</th>
                    <th style="padding: 12px; font-weight: 600;">Net Delta</th>
                    <th style="padding: 12px; font-weight: 600;">Net Theta (Daily)</th>
                    <th style="padding: 12px; font-weight: 600;">Net Vega</th>
                    <th style="padding: 12px; font-weight: 600; background-color: #7f1d1d;">Margin Locked</th>
                </tr>
            </thead>
            <tbody>
                <tr>
                    <td style="padding: 16px; font-family: monospace; font-size: 18px; font-weight: bold; color: #374151;">USD {spot_price:.2f}</td>
                    <td style="padding: 16px; font-family: monospace; font-size: 18px; font-weight: bold; color: #374151;">{net_delta:.2f}</td>
                    <td style="padding: 16px; font-family: monospace; font-size: 18px; font-weight: bold; color: #16a34a;">USD {net_theta:+.2f}</td>
                    <td style="padding: 16px; font-family: monospace; font-size: 18px; font-weight: bold; color: #2563eb;">USD {net_vega:+.2f}</td>
                    <td style="padding: 16px; font-family: monospace; font-size: 18px; font-weight: 900; color: #dc2626;">USD {margin_req:,.0f}</td>
                </tr>
            </tbody>
        </table>
    </div>
    """, unsafe_allow_html=True)

    
# ==========================================
# 9. EDUCATIONAL CONTENT & EXPECTANCY CHART
# ==========================================
with tab2:
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
        
        st.markdown("### How We Enhanced It (The Estate Barbell)")
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
