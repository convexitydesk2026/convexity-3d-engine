import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import datetime

st.set_page_config(page_title="Physical Equity Risk Ledger | Convexity Desk", layout="wide")
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



st.title("📊 Educational Risk Ledger Sandbox")
st.markdown("Track absolute notional risk across all dummy physical equity and options positions.")

import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent))
from public_core_math import render_global_sidebar, init_global_state, render_page_footer
render_global_sidebar()
import yfinance as yf

# Initialize Global State
init_global_state()

st.info("💡 **Educational Sandbox:** Edit the table below to simulate portfolio entries. Changes update the global state for the Monte Carlo simulator. Data is temporary and vanishes on refresh.")

# Educational Sandbox Grid
edited_df = st.data_editor(
    st.session_state.master_ledger, 
    num_rows="dynamic", 
    use_container_width=True,
    column_config={
        "Class": st.column_config.SelectboxColumn("Class", options=["Equity", "Option"], required=True),
        "Silo": st.column_config.SelectboxColumn("Silo", options=["A", "B", "C", "D"], required=True),
        "Entry Date": st.column_config.DateColumn("Entry Date", format="YYYY-MM-DD"),
        "Exit Date": st.column_config.DateColumn("Exit Date", format="YYYY-MM-DD")
    }
)

if not edited_df.equals(st.session_state.master_ledger):
    st.session_state.master_ledger = edited_df
    st.rerun()
# Filter Master Ledger for active physical equities (no exit date/price)
master_df = st.session_state.master_ledger
equity_df = master_df[(master_df['Class'] == 'Equity') & (master_df['Exit Price'].isna() | (master_df['Exit Price'] == ''))].copy()

if equity_df.empty:
    st.warning("⚠️ No active physical equity positions found in Master Ledger. The Risk Ledger is in Standby Mode.")
    st.stop()

# Build the Alpha Dataframe dynamically from Master Ledger
@st.cache_data(ttl=3600)
def compute_live_ledger(df_input):
    tickers = df_input['Ticker'].unique().tolist()
    if not tickers:
        return pd.DataFrame()
        
    try:
        hist_data = yf.download(tickers, period="60d", progress=False, auto_adjust=False)['Close']
        if len(tickers) == 1:
            hist_data = pd.DataFrame({tickers[0]: hist_data})
    except Exception:
        hist_data = pd.DataFrame()
        
    data = []
    for _, row in df_input.iterrows():
        ticker = row['Ticker']
        shares = float(row['Shares'])
        entry = float(row['Entry Price'])
        sl = float(row['Stop Loss']) if pd.notna(row['Stop Loss']) else 0.0
        
        spot = entry # Default
        sma20, sma50 = entry, entry
        if not hist_data.empty and ticker in hist_data.columns:
            series = hist_data[ticker].dropna()
            if not series.empty:
                spot = float(series.iloc[-1])
                sma20 = float(series.rolling(20).mean().iloc[-1]) if len(series) >= 20 else spot
                sma50 = float(series.rolling(50).mean().iloc[-1]) if len(series) >= 50 else spot
                
        cost = shares * entry
        mkt_val = shares * spot
        total_sl = shares * sl
        open_risk = total_sl - cost if sl > 0 else -cost
        unlocked_profit = mkt_val - cost
        
        r_mult = 0.0
        if open_risk < 0:
            r_mult = unlocked_profit / abs(open_risk)
            
        # Entry date days active
        try:
            entry_dt = pd.to_datetime(row['Entry Date']).date()
            days_active = (datetime.date.today() - entry_dt).days
        except:
            days_active = 0

        data.append({
            'Ticker': ticker,
            'Global Portfolio %': 0.0, # Will compute below
            'Earnings': 'N/A',
            'Shares': shares,
            'Spot Price': spot,
            'Market Value': mkt_val,
            'Cost': cost,
            'Avg SL': sl,
            '20 SMA': sma20,
            '50 SMA': sma50,
            'Open Risk': open_risk,
            'Locked Profit': 0,
            'Unlocked Profit': unlocked_profit,
            'Total Profit': unlocked_profit,
            'Live R-Mult': r_mult,
            'Days Active': days_active,
            'Total SL Value': total_sl
        })
        
    res_df = pd.DataFrame(data)
    if not res_df.empty:
        global_nav = 1000000 # Dummy global NAV
        res_df['Global Portfolio %'] = (res_df['Market Value'] / global_nav) * 100
    return res_df

df_alpha = compute_live_ledger(equity_df)
st.markdown("---")
global_nav = 972000  # Approximated from 2.55% of 24.7k

# UI Construction
expander = st.expander("📉 View Physical Equity Risk Ledger", expanded=True)

with expander:
    c_chart, c_ctrl = st.columns([8, 1])
    with c_ctrl:
        st.markdown("<br><br><br>", unsafe_allow_html=True)
        use_log = st.toggle("Logarithmic Scale", value=False)
    
    # Plotly Chart Construction
    fig_alpha = go.Figure()
    
    base_vals = np.minimum(df_alpha['Market Value'], df_alpha['Cost'])
    green_tops = np.maximum(0, df_alpha['Market Value'] - df_alpha['Cost'])
    red_tops = np.maximum(0, df_alpha['Cost'] - df_alpha['Market Value'])
    
    x_pos = np.arange(len(df_alpha))
    
    fig_alpha.add_trace(go.Bar(
        x=x_pos, y=base_vals, name='Base Value', 
        marker_color='#e2e8f0', hovertemplate='Base Value: $%{y:,.0f}<extra></extra>'
    ))
    fig_alpha.add_trace(go.Bar(
        x=x_pos, y=green_tops, name='Unrealized Profit', 
        marker_color='#bbf7d0', hovertemplate='Profit: $%{y:,.0f}<extra></extra>'
    ))
    fig_alpha.add_trace(go.Bar(
        x=x_pos, y=red_tops, name='Unrealized Loss', 
        marker_color='#fecaca', hovertemplate='Loss: $%{y:,.0f}<extra></extra>'
    ))
    
    # Dummy traces to populate the Legend correctly
    fig_alpha.add_trace(go.Scatter(x=[None], y=[None], mode='lines', line=dict(color='blue', width=3), name='Cost Basis'))
    fig_alpha.add_trace(go.Scatter(x=[None], y=[None], mode='markers+lines', marker=dict(color='black', size=10), line=dict(color='black', width=2), name='Stop Loss'))
    
    # Custom Shapes for Cost, Val, and SL lines
    for i, r in df_alpha.iterrows():
        # Thick Blue Line for Cost Value
        fig_alpha.add_shape(type="line", x0=i-0.4, x1=i+0.4, y0=r['Cost'], y1=r['Cost'], line=dict(color="blue", width=3))
        
        # Thin Dashed Line for Current Value (Top of Bar)
        fig_alpha.add_shape(type="line", x0=i-0.4, x1=i+0.4, y0=r['Market Value'], y1=r['Market Value'], line=dict(color="gray", width=1, dash="dash"))
        
        # Stop Loss Line and Thick Black Dot (Left aligned)
        if r['Total SL Value'] > 0.01:
            sl_val = r['Total SL Value']
            fig_alpha.add_shape(type="line", x0=i-0.5, x1=i+0.4, y0=sl_val, y1=sl_val, line=dict(color="black", width=2))
            fig_alpha.add_trace(go.Scatter(x=[i-0.5], y=[sl_val], mode='markers', marker=dict(color='black', size=10), showlegend=False, hovertemplate=f"Stop Loss Val: ${sl_val:,.0f}<extra></extra>"))
        else:
            fig_alpha.add_annotation(x=i, y=0, text="SL=0", showarrow=False, yshift=-15, font=dict(color="#b91c1c", size=11, weight="bold"))

        # Column Header Annotations (mktv, tpro, cost)
        mkt_str = f"mktv={r['Market Value']/1000:.1f}k"
        tpro_str = f"tpro={r['Total Profit']/1000:+.1f}k"
        cost_str = f"cost={r['Cost']/1000:.1f}k"
        
        fig_alpha.add_annotation(
            x=i, y=max(r['Market Value'], r['Cost']),
            text=f"{mkt_str}<br>{tpro_str}<br>{cost_str}",
            showarrow=False, yshift=35,
            font=dict(size=9, color="#475569"), align="center"
        )
        
    y_layout = dict(gridcolor='LightGray', zeroline=True, zerolinecolor='black')
    if use_log:
        y_layout['type'] = 'log'
        y_layout['dtick'] = 1
        
    fig_alpha.update_layout(
        barmode='stack', title="Global Physical Equity Risk Profiles (Absolute Notional Value)",
        plot_bgcolor='white', paper_bgcolor='white', yaxis=y_layout,
        margin=dict(l=20, r=20, t=65, b=40), height=500,
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
    )
    
    tick_texts = df_alpha.apply(lambda r: f"{r['Ticker']}<br><span style='font-size:10px;color:gray;'>{r['Global Portfolio %']:.2f}%</span>", axis=1)
    fig_alpha.update_xaxes(tickmode='array', tickvals=x_pos, ticktext=tick_texts)

    with c_chart:
        st.plotly_chart(fig_alpha, use_container_width=True)

    # Calculate Summaries
    global_tor = df_alpha['Open Risk'].sum()
    global_lp = df_alpha['Locked Profit'].sum()
    tor_pct = (global_tor / global_nav * 100) if global_nav > 0 else 0
    
    st.markdown(f"""
    <div style='display:flex; justify-content:space-between; background-color:#f8fafc; padding:15px; border-radius:8px; border:1px solid #cbd5e1; margin-bottom:15px;'>
        <div><span style='color:#475569; font-size:14px;'>Global Portfolio %:</span> <span style='font-size:18px; font-weight:bold; color:#dc2626;'>${global_tor:,.0f} ({tor_pct:.1f}% NAV)</span></div>
        <div><span style='color:#475569; font-size:14px;'>Global Locked Profit:</span> <span style='font-size:18px; font-weight:bold; color:#16a34a;'>+${global_lp:,.0f}</span></div>
    </div>
    """, unsafe_allow_html=True)

    def style_alpha_row(row):
        styles = pd.Series([''] * len(row), index=row.index)
        
        if row['Open Risk'] < 0:
            styles['Open Risk'] = 'color: #dc2626; font-weight:bold;'
        for col in ['Locked Profit', 'Unlocked Profit', 'Total Profit', 'Live R-Mult']:
            if pd.notna(row[col]) and isinstance(row[col], (int, float)):
                if row[col] > 0:
                    styles[col] = 'color: #16a34a; font-weight:bold;'
                elif row[col] < 0:
                    styles[col] = 'color: #dc2626; font-weight:bold;'
                    
        # Earnings Warning (Red if past/negative, Orange if soon)
        if isinstance(row['Earnings'], str) and '(' in row['Earnings']:
            try:
                days_str = row['Earnings'].split('(')[1].replace('d)', '')
                if int(days_str) <= 5:
                    styles['Earnings'] = 'background-color: #fecaca; color: #991b1b; font-weight:bold;'
                elif int(days_str) <= 14:
                    styles['Earnings'] = 'color: #d97706; font-weight:bold;'
            except: pass
            
        return styles

    display_cols = ['Ticker', 'Global Portfolio %', 'Earnings', 'Shares', 'Spot Price', 'Market Value', 'Cost', 'Avg SL', '20 SMA', '50 SMA', 'Open Risk', 'Locked Profit', 'Unlocked Profit', 'Total Profit', 'Live R-Mult', 'Days Active']
    display_df = df_alpha[display_cols]
    
    st.dataframe(display_df.style.format({
        'Global Portfolio %': '{:.2f}%', 'Shares': '{:,.0f}', 'Spot Price': '${:,.2f}', 
        'Market Value': '${:,.0f}', 'Cost': '${:,.0f}', 'Avg SL': '${:,.2f}', 
        '20 SMA': '${:,.2f}', '50 SMA': '${:,.2f}',
        'Open Risk': '${:,.0f}', 'Locked Profit': '${:,.0f}', 'Unlocked Profit': '${:,.0f}', 
        'Total Profit': '${:,.0f}', 'Live R-Mult': '{:+.2f}R', 'Days Active': '{:.0f}'
    }).apply(style_alpha_row, axis=1), hide_index=True, use_container_width=True)



render_page_footer("The Physical Equity Risk Ledger visualizes your exact absolute notional risk in the market at any given time. This strictly mathematical layout ensures you are never exposed to catastrophic ruin due to an out-of-control, over-leveraged position.")
