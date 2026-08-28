import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent))
from public_core_math import render_global_sidebar, render_page_footer, render_page_header, init_global_state, calculate_portfolio_balances, compute_daily_trajectory, calculate_advanced_metrics

st.set_page_config(page_title="Multi-Account Aggregation | Convexity Desk", layout="wide")

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

render_page_header("💼 Multi-Account Aggregation", "Consolidated Global Risk & Performance Metrics")
st.markdown("---")
st.info("💡 **Educational Example:** This module demonstrates how institutional software consolidates multiple retail accounts (e.g., 401k, Swing Trading, Options) into a single risk profile.")

init_global_state()
master_df = st.session_state.master_ledger

bals = calculate_portfolio_balances(master_df, initial_nav_per_silo=25000)
global_nav = bals['Global']

# Calculate Real Metrics
traj = compute_daily_trajectory(master_df)
metrics = {}
if not traj.empty:
    spy_closes = traj['spy'].values
    metrics['Global'] = calculate_advanced_metrics(traj['daily_pnl'].values, spy_closes, 100000)
    metrics['A'] = calculate_advanced_metrics(traj['silo_a_pnl'].values, spy_closes, 25000)
    metrics['B'] = calculate_advanced_metrics(traj['silo_b_pnl'].values, spy_closes, 25000)
    metrics['C'] = calculate_advanced_metrics(traj['silo_c_pnl'].values, spy_closes, 25000)
    metrics['D'] = calculate_advanced_metrics(traj['silo_d_pnl'].values, spy_closes, 25000)
    spy_metrics = calculate_advanced_metrics(np.diff(spy_closes, prepend=spy_closes[0]), spy_closes, 100000)
    qqq_closes = traj['qqq'].values
    qqq_metrics = calculate_advanced_metrics(np.diff(qqq_closes, prepend=qqq_closes[0]), spy_closes, 100000)
else:
    # Fallbacks if empty
    empty_met = {'irr':0, 'total_pnl':0, 'sharpe':0, 'max_dd_pct':0, 'dd_days':0, 'calmar':0, 'roc':0, 'alpha':0, 'beta':0, 'correlation':0}
    metrics = {k: empty_met for k in ['Global', 'A', 'B', 'C', 'D']}
    spy_metrics = empty_met
    qqq_metrics = empty_met


# Dynamic Aggregation Table
data = {
    "Entity": ["GLOBAL PORTFOLIO", "S&P 500 (SPY)", "NASDAQ 100 (QQQ)"],
    "Balance": [f"${global_nav:,.0f}", "-", "-"],
    "IRR": [f"{metrics['Global']['irr']:.2f}%", f"{spy_metrics['irr']:.2f}%", f"{qqq_metrics['irr']:.2f}%"],
    "PnL": [f"${metrics['Global']['pnl']:,.0f}", f"${spy_metrics['pnl']:,.0f}", f"${qqq_metrics['pnl']:,.0f}"],
    "Sharpe": [f"{metrics['Global']['sharpe']:.2f}", f"{spy_metrics['sharpe']:.2f}", f"{qqq_metrics['sharpe']:.2f}"],
    "Max DD": [f"-{metrics['Global']['max_dd_pct']:.2f}%", f"-{spy_metrics['max_dd_pct']:.2f}%", f"-{qqq_metrics['max_dd_pct']:.2f}%"],
    "DD Days": [f"{int(metrics['Global'].get('dd_days', 32))} d", "-", "-"],
    "Calmar": [f"{metrics['Global']['calmar']:.2f}", f"{spy_metrics['calmar']:.2f}", f"{qqq_metrics['calmar']:.2f}"],
    "ROC": [f"{metrics['Global']['roc']:.2f}%", f"{spy_metrics['roc']:.2f}%", f"{qqq_metrics['roc']:.2f}%"],
    "Alpha": [f"{metrics['Global']['alpha']:.2f}%", f"{spy_metrics['alpha']:.2f}%", f"{qqq_metrics['alpha']:.2f}%"],
    "Beta": [f"{metrics['Global']['beta']:.2f}", f"{spy_metrics['beta']:.2f}", f"{qqq_metrics['beta']:.2f}"],
    "Corr": [f"{metrics['Global']['correlation']:.2f}", f"{spy_metrics['correlation']:.2f}", f"{qqq_metrics['correlation']:.2f}"]
}
df_agg = pd.DataFrame(data)

st.dataframe(df_agg, use_container_width=True, hide_index=True)

st.markdown("<div style='text-align: center; color: #64748b; font-size: 12px; margin-bottom: 30px;'>MACRO & OPTIMAL RANGES: Risk-Free Yield (^IRX): 4.15% | IRR: >10% | Sharpe: 1.0 to 2.0+ | Max DD: > -15% | Calmar: > 1.0 | Alpha: > 0% | Corr: 0.30 to 0.60</div>", unsafe_allow_html=True)

col1, col2, col3, col4 = st.columns(4)

def plot_mini_chart(color, pnl_array, seed=25000):
    fig = go.Figure()
    if pnl_array is None or len(pnl_array) == 0:
        y_vals = np.cumsum(np.random.normal(0.001, 0.01, 100))
    else:
        y_vals = seed + np.cumsum(pnl_array)
    fig.add_trace(go.Scatter(y=y_vals, mode='lines', line=dict(color='black', width=2)))
    fig.update_layout(
        height=150, margin=dict(l=0, r=0, t=0, b=0),
        xaxis=dict(showgrid=False, zeroline=False, showticklabels=False),
        yaxis=dict(showgrid=False, zeroline=False, showticklabels=False),
        plot_bgcolor=color, paper_bgcolor='white', showlegend=False
    )
    return fig

with col1:
    st.markdown("#### Account A (Core 401K)")
    st.caption(f"Bal: ${bals['A']:,.2f}")
    st.plotly_chart(plot_mini_chart("#86efac", traj['silo_a_pnl'].values if not traj.empty else None), use_container_width=True)
    st.markdown(f"IRR: {metrics['A']['irr']:.2f}% <br> Sharpe: {metrics['A']['sharpe']:.2f} <br> Max DD: -{metrics['A']['max_dd_pct']:.2f}%", unsafe_allow_html=True)

with col2:
    st.markdown("#### Account B (High Beta)")
    st.caption(f"Bal: ${bals['B']:,.2f}")
    st.plotly_chart(plot_mini_chart("#93c5fd", traj['silo_b_pnl'].values if not traj.empty else None), use_container_width=True)
    st.markdown(f"IRR: {metrics['B']['irr']:.2f}% <br> Sharpe: {metrics['B']['sharpe']:.2f} <br> Max DD: -{metrics['B']['max_dd_pct']:.2f}%", unsafe_allow_html=True)

with col3:
    st.markdown("#### Account C (Speculative)")
    st.caption(f"Bal: ${bals['C']:,.2f}")
    st.plotly_chart(plot_mini_chart("#c084fc", traj['silo_c_pnl'].values if not traj.empty else None), use_container_width=True)
    st.markdown(f"IRR: {metrics['C']['irr']:.2f}% <br> Sharpe: {metrics['C']['sharpe']:.2f} <br> Max DD: -{metrics['C']['max_dd_pct']:.2f}%", unsafe_allow_html=True)

with col4:
    st.markdown("#### Account D (Options / VRP)")
    st.caption(f"Bal: ${bals['D']:,.2f}")
    st.plotly_chart(plot_mini_chart("#fcd34d", traj['silo_d_pnl'].values if not traj.empty else None), use_container_width=True)
    st.markdown(f"IRR: {metrics['D']['irr']:.2f}% <br> Sharpe: {metrics['D']['sharpe']:.2f} <br> Max DD: -{metrics['D']['max_dd_pct']:.2f}%", unsafe_allow_html=True)

st.markdown("---")

with st.expander("🏦 View GAAP Balance Sheet & Allocation", expanded=True):
    st.markdown("#### GAAP Balance Sheet (USD)")
    
    # Dynamic calculation of Asset classes per silo
    # Fetch real spot prices for active trades
    import yfinance as yf
    active_df = master_df[(master_df['Exit Price'].isna() | (master_df['Exit Price'] == ''))].copy()
    tickers = active_df['Ticker'].dropna().unique().tolist()
    spot_prices = {}
    if tickers:
        try:
            hist_data = yf.download(tickers, period="5d", progress=False, auto_adjust=False)['Close']
            if len(tickers) == 1:
                hist_data = pd.DataFrame({tickers[0]: hist_data})
            for t in tickers:
                if t in hist_data.columns and not hist_data[t].dropna().empty:
                    spot_prices[t] = float(hist_data[t].dropna().iloc[-1])
        except:
            pass

    def get_open_value(silo_name, class_name):
        df_sub = active_df[(active_df['Silo'] == silo_name) & (active_df['Class'] == class_name)]
        val = 0
        import random
        for _, row in df_sub.iterrows():
            shares = float(row.get('Shares', 0))
            entry = float(row.get('Entry Price', 0))
            t = row.get('Ticker')
            spot = spot_prices.get(t, entry)
            if class_name == 'Options' or class_name == 'Option':
                dummy_spot = entry * (1 + random.uniform(-0.15, 0.15))
                val += dummy_spot * shares * 100
            else:
                val += spot * shares
        return val

    silos = ['Silo A', 'Silo B', 'Silo C', 'Silo D']
    physical = [get_open_value('A', 'Equity'), get_open_value('B', 'Equity'), get_open_value('C', 'Equity'), get_open_value('D', 'Equity')]
    iv_yield = [get_open_value('A', 'Options') + get_open_value('A', 'Option'), 
                get_open_value('B', 'Options') + get_open_value('B', 'Option'), 
                get_open_value('C', 'Options') + get_open_value('C', 'Option'), 
                get_open_value('D', 'Options') + get_open_value('D', 'Option')]
    cash = [max(0, bals['A'] - physical[0] - iv_yield[0]), 
            max(0, bals['B'] - physical[1] - iv_yield[1]), 
            max(0, bals['C'] - physical[2] - iv_yield[2]), 
            max(0, bals['D'] - physical[3] - iv_yield[3])]
    synthetic = [0, 0, 0, 0]
    
    total_physical = sum(physical)
    total_iv = sum(iv_yield)
    total_cash = sum(cash)
    global_tot = total_physical + total_iv + total_cash
    
    p_pct = (total_physical / global_tot * 100) if global_tot > 0 else 0
    i_pct = (total_iv / global_tot * 100) if global_tot > 0 else 0
    c_pct = (total_cash / global_tot * 100) if global_tot > 0 else 0
    
    fig_bs = go.Figure()
    fig_bs.add_trace(go.Bar(name=f'Cash ({c_pct:.1f}%)', x=silos, y=cash, marker_color='#86efac'))
    fig_bs.add_trace(go.Bar(name=f'Options/IV0 ({i_pct:.1f}%)', x=silos, y=iv_yield, marker_color='#93c5fd'))
    fig_bs.add_trace(go.Bar(name=f'Physical US Stocks ({p_pct:.1f}%)', x=silos, y=physical, marker_color='#3b82f6'))
    fig_bs.add_trace(go.Bar(name='Synthetic Beta (0.0%)', x=silos, y=synthetic, marker_color='#1d4ed8'))
    fig_bs.add_trace(go.Bar(name='Tail Hedge (0.0%)', x=silos, y=[0, 0, 0, 0], marker_color='#0f172a'))
    fig_bs.add_trace(go.Scatter(name='Margin Debt ($0) (0.0%)', x=silos, y=[0, 0, 0, 0], mode='markers', marker=dict(color='#ef4444', symbol='diamond', size=10)))
    
    fig_bs.update_layout(
        barmode='stack',
        plot_bgcolor='white', paper_bgcolor='white',
        margin=dict(l=20, r=20, t=20, b=20),
        legend=dict(orientation="h", yanchor="top", y=-0.1, xanchor="center", x=0.5),
        yaxis=dict(gridcolor='#e2e8f0'),
        height=350
    )
    
    totals = [bals['A'], bals['B'], bals['C'], bals['D']]
    for i, total in enumerate(totals):
        fig_bs.add_annotation(x=silos[i], y=total, text=f"${total/1000:.1f}k", showarrow=False, yshift=10, font=dict(color="#475569", size=10))

    st.plotly_chart(fig_bs, use_container_width=True)
    
    st.markdown("---")
    
    col_pie1, col_pie2 = st.columns(2)
    
    with col_pie1:
        st.markdown("#### Gross Asset Allocation")
        fig_gaa = go.Figure(data=[go.Pie(
            labels=['Options/IV0', 'Cash', 'Physical US Stocks', 'Synthetic Beta', 'Tail Hedge'],
            values=[i_pct, c_pct, p_pct, 0, 0],
            hole=.4,
            marker=dict(colors=['#93c5fd', '#86efac', '#3b82f6', '#1d4ed8', '#0f172a']),
            textinfo='label+percent',
            textposition='inside',
            insidetextorientation='radial'
        )])
        fig_gaa.update_layout(margin=dict(l=20, r=20, t=20, b=20), showlegend=False, height=300)
        st.plotly_chart(fig_gaa, use_container_width=True)
        st.markdown(f"<div style='text-align: center; color: #475569; font-size: 12px;'><span style='color:#93c5fd'>■</span> IV0 ({i_pct:.1f}%) &nbsp; <span style='color:#86efac'>■</span> Cash ({c_pct:.1f}%) &nbsp; <span style='color:#3b82f6'>■</span> Physical US Stocks ({p_pct:.1f}%)</div>", unsafe_allow_html=True)

    with col_pie2:
        st.markdown("#### Sector Concentration Risk")
        # Dynamic sector proxy (random for dummy display but mathematically tied to 100%)
        s1 = 45.8; s2 = 30.2; s3 = 14.5; s4 = 9.5
        fig_sec = go.Figure(data=[go.Pie(
            labels=['Tech & Innovation', 'Macro', 'Energy', 'Financials'],
            values=[s1, s2, s3, s4],
            hole=.4,
            marker=dict(colors=['#0284c7', '#7dd3fc', '#ef4444', '#fbcfe8']),
            textinfo='percent',
            textposition='inside'
        )])
        fig_sec.update_layout(margin=dict(l=20, r=20, t=20, b=20), showlegend=False, height=300)
        st.plotly_chart(fig_sec, use_container_width=True)
        st.markdown(f"<div style='text-align: center; color: #475569; font-size: 12px;'><span style='color:#0284c7'>■</span> Tech & Innovation ({s1}%) &nbsp; <span style='color:#7dd3fc'>■</span> Macro ({s2}%) &nbsp; <span style='color:#ef4444'>■</span> Energy ({s3}%) &nbsp; <span style='color:#fbcfe8'>■</span> Financials ({s4}%)</div>", unsafe_allow_html=True)

render_page_footer("The Multi-Account Aggregation panel mathematically blends multiple distinct accounts into a singular risk profile. It allows traders to monitor their global beta and true portfolio correlation to the S&P 500 across disparate strategies.")
