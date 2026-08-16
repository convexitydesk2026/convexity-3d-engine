"""
=============================================================================
Script Name: dashboard_v3.py
Purpose: The Streamlit Frontend (Module 3).
         Adds Target Portfolio Composition and Daily PnL per Silo panels.
=============================================================================
"""

import streamlit as st
import pandas as pd
import sqlite3
import numpy as np
import plotly.graph_objects as go
import yfinance as yf
import os
import datetime

st.set_page_config(page_title="Estate Master Dashboard", layout="wide")
DB_NAME = "estate_data.db"
TARGET_DIR = r"C:\Users\donca\Desktop\Desktop HP Envy x360 al 22Abr24\Docs Manuel\IBKR_Options"
DB_PATH = os.path.join(TARGET_DIR, DB_NAME)

SILO_MAP = {
    'U23144948': ('Silo A', 'Persons 1 and 2 • U*****948', '#93c5fd'),
    'U23139264': ('Silo B', 'Persons 1 and 2 • U*****264', '#d8b4fe'),
    'U23154199': ('Silo C', 'Persons 1 and 3 • U*****199', '#86efac'),
    'U25218481': ('Silo D', 'Persons 1 and 4 • U*****481', '#fde047')
}

def calculate_xirr(dates, cfs):
    try:
        def xnpv(rate):
            if rate <= -1.0: return float('inf')
            t0 = dates.iloc[0]
            return sum([cf / (1 + rate)**((d - t0).days / 365.0) for cf, d in zip(cfs, dates)])
        rate = 0.10 
        for _ in range(100):
            val = xnpv(rate)
            deriv = (xnpv(rate + 0.0001) - val) / 0.0001
            if abs(deriv) < 1e-8: break
            rate_new = rate - val / deriv
            if abs(rate_new - rate) < 1e-6: return rate_new
            rate = rate_new
        if rate > 10.0 or rate < -1.0: return 0.0
        return rate
    except: return 0.0

def process_metrics(df_acc):
    if df_acc.empty or df_acc['nav'].max() == 0:
        return {"irr": 0, "sharpe": 0, "pnl": 0, "max_dd": 0, "roc": 0, "nav": 0, "dd_days": 0}
        
    df_acc = df_acc[df_acc['nav'] > 0].copy().reset_index(drop=True)
    if len(df_acc) < 2:
        return {"irr": 0, "sharpe": 0, "pnl": 0, "max_dd": 0, "roc": 0, "nav": df_acc['nav'].iloc[-1] if not df_acc.empty else 0, "dd_days": 0}

    df_acc['prev_nav'] = df_acc['nav'].shift(1)
    df_acc['daily_return'] = (df_acc['nav'] - df_acc['cash_flow'] - df_acc['prev_nav']) / df_acc['prev_nav'].replace(0, np.nan)
    df_acc['daily_return'] = df_acc['daily_return'].fillna(0)
    df_acc['daily_pnl'] = df_acc['nav'] - df_acc['cash_flow'] - df_acc['prev_nav'].fillna(df_acc['nav'] - df_acc['cash_flow'])
    
    final_nav = df_acc['nav'].iloc[-1]
    total_deposits = df_acc['cash_flow'].sum()
    total_pnl = final_nav - total_deposits
    
    daily_rf = 0.045 / 252 
    excess_returns = df_acc['daily_return'] - daily_rf
    sharpe = np.sqrt(252) * (excess_returns.mean() / df_acc['daily_return'].std()) if df_acc['daily_return'].std() > 0 else 0

    cum_idx = (1 + df_acc['daily_return']).cumprod()
    peak = cum_idx.cummax()
    drawdown = (cum_idx - peak) / peak
    max_dd = drawdown.min() * 100
    
    peak_date = df_acc['date'].iloc[0]
    max_dd_days = 0
    for idx, row in df_acc.iterrows():
        if cum_idx.iloc[idx] >= peak.iloc[idx]: peak_date = row['date']
        else:
            duration = (row['date'] - peak_date).days
            if duration > max_dd_days: max_dd_days = duration
    
    cfs = (-df_acc['cash_flow']).tolist()
    dates = df_acc['date'].tolist()
    cfs.append(final_nav)
    dates.append(dates[-1])
    irr = calculate_xirr(pd.to_datetime(pd.Series(dates)), cfs) * 100

    df_acc['cum_cf'] = df_acc['cash_flow'].cumsum()
    max_cap = df_acc['cum_cf'].max()
    if max_cap <= 0: max_cap = df_acc['nav'].max() - total_pnl
    roc = (total_pnl / max_cap) * 100 if max_cap > 0 else 0

    return {"irr": irr, "sharpe": sharpe, "pnl": total_pnl, "max_dd": max_dd, "roc": roc, "nav": final_nav, "dd_days": max_dd_days}

@st.cache_data(ttl=3600)
def load_and_process_data():
    conn = sqlite3.connect(DB_PATH)
    df = pd.read_sql_query("SELECT * FROM daily_balances", conn)
    df['date'] = pd.to_datetime(df['date'])
    df.rename(columns={'total_cash': 'cash_flow', 'net_liquidation': 'nav'}, inplace=True)
    
    global_df = df.groupby('date').agg({'nav': 'sum', 'cash_flow': 'sum'}).reset_index()
    global_metrics = process_metrics(global_df)
    global_df = global_df[global_df['nav'] > 0].copy() 
    
    global_df['prev_nav'] = global_df['nav'].shift(1)
    global_df['daily_return'] = (global_df['nav'] - global_df['cash_flow'] - global_df['prev_nav']) / global_df['prev_nav'].replace(0, np.nan)
    global_df['cum_return'] = (1 + global_df['daily_return'].fillna(0)).cumprod() - 1
    global_df['daily_pnl'] = global_df['nav'] - global_df['cash_flow'] - global_df['prev_nav'].fillna(global_df['nav'] - global_df['cash_flow'])
    global_df['cum_pnl'] = global_df['daily_pnl'].cumsum()
    
    silo_metrics = {}
    silo_dfs = {}
    for acc in SILO_MAP.keys():
        acc_df = df[df['account'] == acc].copy().sort_values('date')
        silo_metrics[acc] = process_metrics(acc_df)
        acc_df = acc_df[acc_df['nav'] > 0].copy()
        if not acc_df.empty:
            acc_df['prev_nav'] = acc_df['nav'].shift(1)
            acc_df['daily_return'] = (acc_df['nav'] - acc_df['cash_flow'] - acc_df['prev_nav']) / acc_df['prev_nav'].replace(0, np.nan)
            acc_df['cum_return'] = (1 + acc_df['daily_return'].fillna(0)).cumprod() - 1
            acc_df['daily_pnl'] = acc_df['nav'] - acc_df['cash_flow'] - acc_df['prev_nav'].fillna(acc_df['nav'] - acc_df['cash_flow'])
        silo_dfs[acc] = acc_df

    # Load Live Positions for the "Target Portfolio" module
    live_date = df['date'].max()
    pos_df = pd.read_sql_query(f"SELECT account, symbol, sec_type, position, market_value FROM daily_positions WHERE date = '{live_date.strftime('%Y-%m-%d')}'", conn)

    return global_df, global_metrics, silo_dfs, silo_metrics, pos_df

@st.cache_data(ttl=3600)
def load_benchmarks(start_date, end_date):
    data = yf.download(["SPY", "QQQ"], start=start_date, end=end_date + datetime.timedelta(days=1), progress=False, auto_adjust=False)
    close_data = data['Close'].ffill()
    bench_df = close_data.reset_index()
    bench_df.rename(columns={'Date': 'date'}, inplace=True)
    bench_df['date'] = pd.to_datetime(bench_df['date']).dt.tz_localize(None)
    bench_df['spy_cum'] = (1 + bench_df['SPY'].pct_change().fillna(0)).cumprod() - 1
    bench_df['qqq_cum'] = (1 + bench_df['QQQ'].pct_change().fillna(0)).cumprod() - 1
    return bench_df

# --- UI RENDERING ---
st.title("Estate Master Dashboard")
st.markdown(f"**Data Pipeline:** Live IBKR Sync via SQLite (`{DB_NAME}`) • **Last Refresh:** {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
st.divider()

global_df, global_metrics, silo_dfs, silo_metrics, pos_df = load_and_process_data()
bench_df = load_benchmarks(global_df['date'].min(), global_df['date'].max())

chart_df = pd.merge(global_df[['date', 'cum_return', 'cum_pnl']], bench_df[['date', 'spy_cum', 'qqq_cum']], on='date', how='left').ffill().fillna(0)

# --- SECTION 1: MASTER METRICS ---
st.subheader("Master Estate Aggregation")
col1, col2, col3, col4, col5 = st.columns(5)
col1.metric("Static Balance (USD)", f"${global_metrics['nav']:,.2f}")
col2.metric("IRR", f"{global_metrics['irr']:.2f}%")
col3.metric("Global P&L", f"${global_metrics['pnl']:,.2f}")
col4.metric("Estate Sharpe", f"{global_metrics['sharpe']:.2f}")
col5.metric("Max Drawdown", f"{global_metrics['max_dd']:.2f}%")

st.divider()

# --- SECTION 2: BENCHMARK CHART ---
st.subheader("1. Estate vs Benchmarks (Cumulative Return %)")
fig = go.Figure()
fig.add_trace(go.Scatter(x=chart_df['date'], y=chart_df['cum_return']*100, mode='lines', name='Estate', line=dict(color='black', width=3)))
fig.add_trace(go.Scatter(x=chart_df['date'], y=chart_df['spy_cum']*100, mode='lines', name='SPY', line=dict(color='#3b82f6', width=2)))
fig.add_trace(go.Scatter(x=chart_df['date'], y=chart_df['qqq_cum']*100, mode='lines', name='QQQ', line=dict(color='#dc2626', width=2)))
fig.update_layout(yaxis_ticksuffix="%", margin=dict(l=20, r=20, t=30, b=20), legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1))
fig.update_xaxes(showgrid=True, gridwidth=1, gridcolor='LightGray')
fig.update_yaxes(showgrid=True, gridwidth=1, gridcolor='LightGray', zeroline=True, zerolinecolor='black')
st.plotly_chart(fig, width='stretch')

st.divider()

# --- SECTION 3: SILO PANELS ---
cols = st.columns(4)
for idx, acc in enumerate(SILO_MAP.keys()):
    name, desc, color = SILO_MAP[acc]
    m = silo_metrics[acc]
    with cols[idx]:
        st.markdown(f"### {name}")
        st.caption(desc)
        st.markdown(f"**Bal: ${m['nav']:,.2f}**")
        
        if not silo_dfs[acc].empty:
            s_chart = pd.merge(silo_dfs[acc][['date', 'cum_return']], bench_df[['date', 'spy_cum', 'qqq_cum']], on='date', how='left').ffill().fillna(0)
            fig_mini = go.Figure()
            fig_mini.add_trace(go.Scatter(x=s_chart['date'], y=s_chart['cum_return']*100, mode='lines', line=dict(color='black', width=2), showlegend=False))
            fig_mini.add_trace(go.Scatter(x=s_chart['date'], y=s_chart['spy_cum']*100, mode='lines', line=dict(color='#3b82f6', width=1), showlegend=False))
            fig_mini.add_trace(go.Scatter(x=s_chart['date'], y=s_chart['qqq_cum']*100, mode='lines', line=dict(color='#dc2626', width=1), showlegend=False))
            fig_mini.update_layout(height=150, margin=dict(l=0, r=0, t=0, b=0), plot_bgcolor=color, paper_bgcolor='rgba(0,0,0,0)')
            fig_mini.update_xaxes(visible=False); fig_mini.update_yaxes(visible=False)
            st.plotly_chart(fig_mini, width='stretch')
        
        c1, c2 = st.columns(2)
        c1.write(f"**IRR:** {m['irr']:.2f}%")
        c2.write(f"**Sharpe:** {m['sharpe']:.2f}")
        c1.write(f"**P&L:** ${m['pnl']:,.0f}")
        c2.write(f"**Max DD:** {m['max_dd']:.2f}%")
        c1.write(f"**DD Days:** {m['dd_days']}")
        c2.write(f"**ROC:** {m['roc']:.2f}%")

st.divider()

# --- SECTION 4: TARGET PORTFOLIO COMPOSITION ---
st.subheader("2. Live Portfolio Composition (from TWS)")
comp_cols = st.columns(4)
for idx, acc in enumerate(SILO_MAP.keys()):
    name, _, color = SILO_MAP[acc]
    acc_pos = pos_df[pos_df['account'] == acc].copy()
    
    with comp_cols[idx]:
        st.markdown(f"**{name}**")
        if not acc_pos.empty:
            acc_nav = silo_metrics[acc]['nav']
            acc_pos['Allocation %'] = (acc_pos['market_value'] / acc_nav) * 100 if acc_nav > 0 else 0
            
            # Format nicely for display
            display_df = acc_pos[['symbol', 'market_value', 'Allocation %']].sort_values('market_value', ascending=False)
            display_df.columns = ['Asset', 'Value ($)', 'Alloc (%)']
            st.dataframe(display_df.style.format({'Value ($)': '{:,.0f}', 'Alloc (%)': '{:.1f}%'}), hide_index=True, use_container_width=True)
        else:
            st.write("No active positions.")

st.divider()

# --- SECTION 5: DAILY PNL HISTOGRAM ---
st.subheader("3. Daily PnL per Silo")
fig_pnl = go.Figure()

for acc in SILO_MAP.keys():
    name, _, color = SILO_MAP[acc]
    if not silo_dfs[acc].empty:
        fig_pnl.add_trace(go.Bar(x=silo_dfs[acc]['date'], y=silo_dfs[acc]['daily_pnl'], name=name, marker_color=color))

fig_pnl.add_trace(go.Scatter(x=chart_df['date'], y=chart_df['cum_pnl'], name='Estate (Cum PnL)', mode='lines', line=dict(color='black', width=3), yaxis='y2'))

fig_pnl.update_layout(
    barmode='relative',
    margin=dict(l=20, r=20, t=30, b=20),
    plot_bgcolor='rgba(0,0,0,0)',
    legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
    yaxis=dict(title='Daily PnL (USD)', showgrid=True, gridcolor='LightGray', zeroline=True, zerolinecolor='black'),
    yaxis2=dict(title='Cumulative PnL (USD)', overlaying='y', side='right', showgrid=False)
)
st.plotly_chart(fig_pnl, width='stretch')