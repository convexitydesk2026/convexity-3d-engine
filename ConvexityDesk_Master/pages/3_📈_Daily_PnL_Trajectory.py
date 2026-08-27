import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import yfinance as yf
import datetime

st.set_page_config(page_title="Daily PnL Trajectory | Convexity Desk", layout="wide")

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



st.title("Daily PnL Trajectory")
st.markdown("Replicate and analyze institutional equity curve trajectories.")

import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent))
from public_core_math import compute_daily_trajectory, init_global_state, render_master_ledger_control_panel, render_page_footer

# Initialize Global State & Render UI Panel
init_global_state()
render_master_ledger_control_panel(expanded=True)

master_df = st.session_state.master_ledger
equity_df = master_df[master_df['Class'] == 'Equity'].copy()

if equity_df.empty:
    st.warning("⚠️ No physical equity positions found in Master Ledger. The PnL Trajectory is in Standby Mode.")
    st.stop()

df = compute_daily_trajectory(equity_df)
if df.empty:
    st.error("Error generating trajectory. Ensure valid stock tickers.")
    st.stop()

# Calculate scaling for USD lines (Assume starting NAV of $100k)
initial_nav = 100000
df['spy_usd_cum'] = df['spy_cum'] * initial_nav
df['qqq_usd_cum'] = df['qqq_cum'] * initial_nav
df['rsp_usd_cum'] = df['rsp_cum'] * initial_nav
df['cum_return'] = df['cum_pnl'] / initial_nav

st.markdown("### Portfolio vs Benchmarks (1-Year Trajectory)")
privacy_mode = False

fig_pnl = go.Figure()

if not privacy_mode:
    # Add Silo Bars dynamically based on presence of data
    if (df['silo_d_pnl'] != 0).any():
        fig_pnl.add_trace(go.Bar(x=df['date'], y=df['silo_d_pnl'], name='Silo D', marker_color='#c084fc'))
    if (df['silo_a_pnl'] != 0).any():
        fig_pnl.add_trace(go.Bar(x=df['date'], y=df['silo_a_pnl'], name='Silo A', marker_color='#60a5fa'))
    if (df['silo_b_pnl'] != 0).any():
        fig_pnl.add_trace(go.Bar(x=df['date'], y=df['silo_b_pnl'], name='Silo B', marker_color='#fb923c'))
    if (df['silo_c_pnl'] != 0).any():
        fig_pnl.add_trace(go.Bar(x=df['date'], y=df['silo_c_pnl'], name='Silo C', marker_color='#4ade80'))
    
    # Add Cumulative Lines
    fig_pnl.add_trace(go.Scatter(x=df['date'], y=df['cum_pnl'], name='Portfolio (Cum PnL USD)', mode='lines', line=dict(color='black', width=6), yaxis='y2'))
    fig_pnl.add_trace(go.Scatter(x=df['date'], y=df['spy_usd_cum'], name='SPY (Cum PnL USD)', mode='lines', line=dict(color='#3b82f6', width=3), yaxis='y2'))
    fig_pnl.add_trace(go.Scatter(x=df['date'], y=df['qqq_usd_cum'], name='QQQ (Cum PnL USD)', mode='lines', line=dict(color='#dc2626', width=3), yaxis='y2'))
    fig_pnl.add_trace(go.Scatter(x=df['date'], y=df['rsp_usd_cum'], name='RSP (Cum PnL USD)', mode='lines', line=dict(color='#16a34a', width=3), yaxis='y2'))
else:
    # Pure Percentages in Privacy Mode
    fig_pnl.add_trace(go.Scatter(x=df['date'], y=df['spy_cum']*100, name='SPY (Cum Return %)', mode='lines', line=dict(color='#3b82f6', width=3), yaxis='y2'))
    fig_pnl.add_trace(go.Scatter(x=df['date'], y=df['qqq_cum']*100, name='QQQ (Cum Return %)', mode='lines', line=dict(color='#dc2626', width=3), yaxis='y2'))
    fig_pnl.add_trace(go.Scatter(x=df['date'], y=df['rsp_cum']*100, name='RSP (Cum Return %)', mode='lines', line=dict(color='#16a34a', width=3), yaxis='y2'))

# Formatting for Alpha Gear and Options Engine
df['alpha_bg'] = df['alpha_gear'].map({5: '#14532d', 4: '#22c55e', 3: '#84cc16', 2: '#eab308', 1: '#f97316', 0: '#991b1b'})
df['alpha_txt'] = df['alpha_gear'].map({5: 'white', 4: 'black', 3: 'black', 2: 'black', 1: 'black', 0: 'white'})
df['opt_bg'] = df['opt_dir'].map({'Bull': '#166534', 'Bear': '#991b1b'})

# Alpha Engine (Squares)
fig_pnl.add_trace(go.Scatter(
    x=df['date'], y=[0]*len(df), mode='markers+text', 
    marker=dict(color=df['alpha_bg'], symbol='square', size=16, line=dict(width=1, color='black')),
    text=df['alpha_gear'], textposition='middle center', textfont=dict(color=df['alpha_txt'], size=10, weight='bold'),
    hovertemplate="<b>Date:</b> %{x|%Y-%m-%d}<br><b>Alpha Gear:</b> %{customdata}<extra></extra>",
    customdata=df['alpha_gear'], 
    name='Alpha Engine', showlegend=False, yaxis='y3'
))

# Options Engine (Circles) - Hidden in Privacy Mode
if not privacy_mode:
    fig_pnl.add_trace(go.Scatter(
        x=df['date'], y=[-1]*len(df), mode='markers', 
        marker=dict(color=df['opt_bg'], symbol='circle', size=12, line=dict(width=1, color='black')),
        hovertemplate="<b>Date:</b> %{x|%Y-%m-%d}<br><b>Options Trend:</b> %{customdata}<extra></extra>",
        customdata=df['opt_dir'], 
        name='Options Engine', showlegend=False, yaxis='y3'
    ))

last_dt = df['date'].iloc[-1]

if not privacy_mode:
    est_val = df['cum_pnl'].iloc[-1]
    spy_val = df['spy_usd_cum'].iloc[-1]
    qqq_val = df['qqq_usd_cum'].iloc[-1]
    rsp_val = df['rsp_usd_cum'].iloc[-1]
    
    est_pct = df['cum_return'].iloc[-1] * 100
    spy_pct = df['spy_cum'].iloc[-1] * 100
    qqq_pct = df['qqq_cum'].iloc[-1] * 100
    rsp_pct = df['rsp_cum'].iloc[-1] * 100
    
    fig_pnl.add_annotation(x=last_dt, y=est_val, text=f"{est_pct:.1f}%<br>${est_val:,.0f}", showarrow=False, xanchor='left', yref='y2', bgcolor='black', font=dict(color='white', size=11))
    fig_pnl.add_annotation(x=last_dt, y=spy_val, text=f"{spy_pct:.1f}%<br>${spy_val:,.0f}", showarrow=False, xanchor='left', yref='y2', bgcolor='#3b82f6', font=dict(color='white', size=11))
    fig_pnl.add_annotation(x=last_dt, y=qqq_val, text=f"{qqq_pct:.1f}%<br>${qqq_val:,.0f}", showarrow=False, xanchor='left', yref='y2', bgcolor='#dc2626', font=dict(color='white', size=11))
    fig_pnl.add_annotation(x=last_dt, y=rsp_val, text=f"{rsp_pct:.1f}%<br>${rsp_val:,.0f}", showarrow=False, xanchor='left', yref='y2', bgcolor='#16a34a', font=dict(color='white', size=11))

fig_pnl.update_layout(
    height=600,
    margin=dict(l=0, r=40, t=10, b=0),
    legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
    yaxis=dict(title='Daily PnL (USD)', side='left', showgrid=False, zeroline=True, zerolinecolor='lightgrey', domain=[0.1, 1]),
    yaxis2=dict(title='Cumulative PnL (USD)' if not privacy_mode else 'Cumulative Return (%)', side='right', overlaying='y', showgrid=True, gridcolor='#f1f5f9', zeroline=False),
    yaxis3=dict(domain=[0, 0.08], showgrid=False, zeroline=False, showticklabels=False),
    barmode='relative',
    plot_bgcolor='white',
    paper_bgcolor='white'
)

st.plotly_chart(fig_pnl, use_container_width=True)

st.markdown("""
<div style='font-size: 12px; color: #64748b; margin-top: -15px; margin-bottom: 20px; text-align: center;'>
    <b>Legend:</b> The numbered squares represent the <b>Alpha Engine (Regime Gear 0-5)</b>, determining aggressive vs. defensive posture. 
    The colored circles underneath represent the <b>Options Engine</b> trend (Green = Bullish, Red = Bearish Volatility Structure).
</div>
""", unsafe_allow_html=True)

render_page_footer("The Daily PnL Trajectory engine overlays your realized PnL curve on top of the Alpha Engine's regime shifts. It exposes exactly how your portfolio scales (or fails) in distinct market environments.")
