"""
=============================================================================
Script Name: dashboard_v1.py
Purpose: The Streamlit Frontend (Module 1).
         Reads from estate_data.db, calculates Global metrics, and 
         renders the top-level Estate vs Benchmarks chart.
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

# --- CONFIGURATION ---
st.set_page_config(page_title="Estate Master Dashboard", layout="wide")
DB_NAME = "estate_data.db"
TARGET_DIR = r"C:\Users\donca\Desktop\Desktop HP Envy x360 al 22Abr24\Docs Manuel\IBKR_Options"
DB_PATH = os.path.join(TARGET_DIR, DB_NAME)

# --- HELPER FUNCTIONS ---
def calculate_xirr(dates, cfs):
    """Calculates the Internal Rate of Return (IRR)."""
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
    except:
        return 0.0

@st.cache_data(ttl=3600) # Caches data for 1 hour so UI loads instantly
def load_and_process_data():
    conn = sqlite3.connect(DB_PATH)
    
    # Load Balances
    df = pd.read_sql_query("SELECT * FROM daily_balances", conn)
    df['date'] = pd.to_datetime(df['date'])
    
    # Aggregate Global Estate
    global_df = df.groupby('date').agg({'net_liquidation': 'sum', 'total_cash': 'sum'}).reset_index()
    # In our historical migration, we stored CashFlow in 'total_cash'. Let's rename it for clarity.
    global_df.rename(columns={'total_cash': 'cash_flow', 'net_liquidation': 'nav'}, inplace=True)
    
    # Calculate Returns
    global_df['prev_nav'] = global_df['nav'].shift(1)
    global_df['daily_return'] = (global_df['nav'] - global_df['cash_flow'] - global_df['prev_nav']) / global_df['prev_nav'].replace(0, np.nan)
    global_df['daily_return'] = global_df['daily_return'].fillna(0)
    global_df['cum_return'] = (1 + global_df['daily_return']).cumprod() - 1
    
    # Metrics
    final_nav = global_df['nav'].iloc[-1]
    total_deposits = global_df['cash_flow'].sum()
    total_pnl = final_nav - total_deposits
    
    # Sharpe
    daily_rf = 0.045 / 252 
    excess_returns = global_df['daily_return'] - daily_rf
    sharpe = np.sqrt(252) * (excess_returns.mean() / global_df['daily_return'].std()) if global_df['daily_return'].std() > 0 else 0

    # Drawdown
    cum_idx = (1 + global_df['daily_return']).cumprod()
    peak = cum_idx.cummax()
    drawdown = (cum_idx - peak) / peak
    max_dd = drawdown.min() * 100
    
    # IRR
    cfs = (-global_df['cash_flow']).tolist()
    dates = global_df['date'].tolist()
    cfs.append(final_nav)
    dates.append(dates[-1])
    irr = calculate_xirr(pd.to_datetime(pd.Series(dates)), cfs) * 100

    metrics = {
        "nav": final_nav,
        "pnl": total_pnl,
        "sharpe": sharpe,
        "max_dd": max_dd,
        "irr": irr
    }
    
    return global_df, metrics

@st.cache_data(ttl=3600)
def load_benchmarks(start_date, end_date):
    """Fetches SPY and QQQ data cleanly via yfinance"""
    data = yf.download(["SPY", "QQQ"], start=start_date, end=end_date + datetime.timedelta(days=1), progress=False)
    close_data = data['Close'].ffill()
    
    bench_df = close_data.reset_index()
    bench_df.rename(columns={'Date': 'date'}, inplace=True)
    bench_df['date'] = pd.to_datetime(bench_df['date']).dt.tz_localize(None)
    
    bench_df['spy_ret'] = bench_df['SPY'].pct_change().fillna(0)
    bench_df['spy_cum'] = (1 + bench_df['spy_ret']).cumprod() - 1
    
    bench_df['qqq_ret'] = bench_df['QQQ'].pct_change().fillna(0)
    bench_df['qqq_cum'] = (1 + bench_df['qqq_ret']).cumprod() - 1
    
    return bench_df

# --- UI RENDERING ---
st.title("Estate Master Dashboard")
st.markdown(f"**Data Pipeline:** Live IBKR Sync via SQLite (`{DB_NAME}`) • **Last Refresh:** {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
st.divider()

# Load Data
global_df, metrics = load_and_process_data()
bench_df = load_benchmarks(global_df['date'].min(), global_df['date'].max())

# Merge Estate and Benchmark data for charting
chart_df = pd.merge(global_df[['date', 'cum_return']], bench_df[['date', 'spy_cum', 'qqq_cum']], on='date', how='left').ffill().fillna(0)

# --- SECTION 1: MASTER METRICS ---
st.subheader("Master Estate Aggregation")
col1, col2, col3, col4, col5 = st.columns(5)

col1.metric("Static Balance (USD)", f"${metrics['nav']:,.2f}")
col2.metric("IRR", f"{metrics['irr']:.2f}%")
col3.metric("Global P&L", f"${metrics['pnl']:,.2f}")
col4.metric("Estate Sharpe", f"{metrics['sharpe']:.2f}")
col5.metric("Max Drawdown", f"{metrics['max_dd']:.2f}%")

st.divider()

# --- SECTION 2: BENCHMARK CHART ---
st.subheader("Estate vs Benchmarks (Cumulative Return %)")

fig = go.Figure()
fig.add_trace(go.Scatter(x=chart_df['date'], y=chart_df['cum_return']*100, mode='lines', name='Estate', line=dict(color='black', width=3)))
fig.add_trace(go.Scatter(x=chart_df['date'], y=chart_df['spy_cum']*100, mode='lines', name='SPY', line=dict(color='blue', width=2)))
fig.add_trace(go.Scatter(x=chart_df['date'], y=chart_df['qqq_cum']*100, mode='lines', name='QQQ', line=dict(color='red', width=2)))

fig.update_layout(
    yaxis_ticksuffix="%",
    margin=dict(l=20, r=20, t=30, b=20),
    plot_bgcolor='rgba(0,0,0,0)',
    legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
)
fig.update_xaxes(showgrid=True, gridwidth=1, gridcolor='LightGray')
fig.update_yaxes(showgrid=True, gridwidth=1, gridcolor='LightGray', zeroline=True, zerolinecolor='black')

st.plotly_chart(fig, use_container_width=True)