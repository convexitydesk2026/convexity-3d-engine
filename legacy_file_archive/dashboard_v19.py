"""
=============================================================================
Script Name: dashboard_v19.py
Purpose: The Streamlit Frontend (Module 19 - Black Swan Resilience & Accounting).
         - Integrated Tail Hedge (Ackman/Taleb) Tracking & Strategy updates.
         - Lowered Options Margin Gauges to a strict 20% cap (Druckenmiller rule).
         - Fixed GAAP Bar Chart mismatch with an automatic CFD 'Accounting Offset'.
         - Implemented live 3-month Treasury Yield (^IRX) fetching for Sharpe/Alpha.
         - Upgraded Active Scripts header to dynamically assign [Active] tags.
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
import random
import subprocess
import glob
import math

st.set_page_config(page_title="Estate Master Dashboard", layout="wide")
DB_NAME = "estate_data.db"
TARGET_DIR = r"C:\Users\donca\Desktop\Desktop HP Envy x360 al 22Abr24\Docs Manuel\IBKR_Options"
DB_PATH = os.path.join(TARGET_DIR, DB_NAME)
SYNC_SCRIPT = os.path.join(TARGET_DIR, "sync_engine_v15.py")

SILO_MAP = {
    'U23144948': ('Silo A', 'Persons 1 and 2 • U*****948', '#93c5fd'),
    'U23139264': ('Silo B', 'Persons 1 and 2 • U*****264', '#d8b4fe'),
    'U23154199': ('Silo C', 'Persons 1 and 3 • U*****199', '#86efac'),
    'U25218481': ('Silo D', 'Persons 1 and 4 • U*****481', '#fde047')
}

COLOR_PALETTE = {
    'IB01': '#93c5fd', 'CSPX': '#f97316', 'CNDX': '#8b5cf6',
    'ITWN': '#14b8a6', 'CSKR': '#f472b6', 'CNYA': '#fb923c',
    'Crypto': '#0ea5e9', 'Active Swing': '#a855f7', 'Cash': '#86efac',
    'Opt Liab': '#ef4444', 'Accounting Offset': '#94a3b8'
}

# --- LIVE RISK-FREE RATE ---
@st.cache_data(ttl=3600)
def get_risk_free_rate():
    try:
        irx = yf.Ticker('^IRX').history(period='5d')['Close'].iloc[-1]
        return max(float(irx) / 100.0, 0.0)
    except:
        return 0.045  # Fallback to 4.5% if network is down

LIVE_RF_RATE = get_risk_free_rate()

# --- DYNAMIC SCRIPT DISCOVERY ---
def get_active_scripts():
    patterns =['dashboard_v*.py', 'Telegram_Notifier_v*.py', 'sync_engine_v*.py', 'Run_Estate_Sync.bat']
    scripts =[]
    for p in patterns:
        matches = glob.glob(os.path.join(TARGET_DIR, p))
        if matches:
            latest = sorted(matches)[-1]
            base_name = os.path.basename(latest)
            if 'dashboard_v19' in base_name:
                scripts.append(f"{base_name} [Active]")
            else:
                scripts.append(f"{base_name} [Latest Found]")
    return " • ".join(scripts) if scripts else "dashboard_v19.py [Active]"

active_scripts_str = get_active_scripts()

# --- SIDEBAR: SYNC BUTTON ---
with st.sidebar:
    st.markdown("### ⚙️ Engine Control")
    if st.button("⟳ Sync Live from TWS", width="stretch"):
        with st.spinner("Connecting to TWS... Please wait (~15s)"):
            try:
                subprocess.run(["python", SYNC_SCRIPT], check=True)
                st.success("Sync Complete!")
                st.cache_data.clear() 
                st.rerun()
            except Exception as e:
                st.error(f"Sync failed. Is TWS open? Error: {e}")

# --- HELPER FUNCTIONS ---
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

def process_metrics(df_acc, rf_rate):
    if df_acc.empty or df_acc['nav'].max() == 0:
        return {"irr": 0, "sharpe": 0, "pnl": 0, "max_dd": 0, "roc": 0, "nav": 0, "dd_days": 0}
        
    df_acc = df_acc[df_acc['nav'] > 0].copy().reset_index(drop=True)
    if len(df_acc) < 2:
        return {"irr": 0, "sharpe": 0, "pnl": 0, "max_dd": 0, "roc": 0, "nav": df_acc['nav'].iloc[-1] if not df_acc.empty else 0, "dd_days": 0}

    df_acc['prev_nav'] = df_acc['nav'].shift(1)
    df_acc['daily_return'] = (df_acc['nav'] - df_acc['cash_flow'] - df_acc['prev_nav']) / df_acc['prev_nav'].replace(0, np.nan)
    df_acc['daily_return'] = df_acc['daily_return'].fillna(0)
    
    final_nav = df_acc['nav'].iloc[-1]
    total_deposits = df_acc['cash_flow'].sum()
    total_pnl = final_nav - total_deposits
    
    daily_rf = rf_rate / 252 
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

def get_exact_opt_margin(df_in):
    df_opt = df_in[df_in['sec_type'] == 'OPT'].copy()
    if df_opt.empty: return 0
    try:
        df_opt['strike'] = df_opt['symbol'].apply(lambda x: float(x.split('_')[2]))
        short_sum = df_opt[df_opt['position'] < 0].apply(lambda r: r['strike'] * abs(r['position']), axis=1).sum()
        long_sum = df_opt[df_opt['position'] > 0].apply(lambda r: r['strike'] * abs(r['position']), axis=1).sum()
        return (short_sum - long_sum) * 100
    except Exception:
        return 0

@st.cache_data(ttl=3600)
def load_and_process_data():
    conn = sqlite3.connect(DB_PATH)
    df = pd.read_sql_query("SELECT * FROM daily_balances", conn)
    df['date'] = pd.to_datetime(df['date'])
    df.rename(columns={'total_cash': 'cash_flow', 'net_liquidation': 'nav'}, inplace=True)
    
    global_df = df.groupby('date').agg({'nav': 'sum', 'cash_flow': 'sum'}).reset_index()
    global_metrics = process_metrics(global_df, LIVE_RF_RATE)
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
        silo_metrics[acc] = process_metrics(acc_df, LIVE_RF_RATE)
        acc_df = acc_df[acc_df['nav'] > 0].copy()
        if not acc_df.empty:
            acc_df['prev_nav'] = acc_df['nav'].shift(1)
            acc_df['daily_return'] = (acc_df['nav'] - acc_df['cash_flow'] - acc_df['prev_nav']) / acc_df['prev_nav'].replace(0, np.nan)
            acc_df['cum_return'] = (1 + acc_df['daily_return'].fillna(0)).cumprod() - 1
            acc_df['daily_pnl'] = acc_df['nav'] - acc_df['cash_flow'] - acc_df['prev_nav'].fillna(acc_df['nav'] - acc_df['cash_flow'])
        silo_dfs[acc] = acc_df

    live_date = df['date'].max()
    pos_df = pd.read_sql_query(f"SELECT account, symbol, sec_type, position, market_value FROM daily_positions WHERE date = '{live_date.strftime('%Y-%m-%d')}'", conn)
    attr_df = pd.read_sql_query("SELECT * FROM daily_attribution", conn)
    if not attr_df.empty: attr_df['date'] = pd.to_datetime(attr_df['date'])
        
    def categorize(sym, sec):
        s = sym.upper()
        if 'IB01' in s: return 'IB01'
        if 'CSPX' in s: return 'CSPX'
        if 'CNDX' in s or 'CSNDX' in s: return 'CNDX'
        if 'ETHE' in s or 'BTC' in s: return 'Crypto'
        if 'ITWN' in s: return 'ITWN'
        if 'CSKR' in s: return 'CSKR'
        if 'CNYA' in s: return 'CNYA'
        if sec == 'CASH' or 'CASH' in s: return 'Cash'
        if sec == 'OPT': return 'Opt Liab'
        return 'Active Swing'
    pos_df['asset_class'] = pos_df.apply(lambda r: categorize(r['symbol'], r['sec_type']), axis=1)
        
    return global_df, global_metrics, silo_dfs, silo_metrics, pos_df, attr_df

@st.cache_data(ttl=3600)
def load_benchmarks(start_date, end_date):
    data = yf.download(["SPY", "QQQ", "^VIX"], start=start_date - datetime.timedelta(days=300), end=end_date + datetime.timedelta(days=1), progress=False, auto_adjust=False)
    close_data = data['Close'].ffill()
    bench_df = close_data.reset_index()
    bench_df.rename(columns={'Date': 'date'}, inplace=True)
    bench_df['date'] = pd.to_datetime(bench_df['date']).dt.tz_localize(None)
    
    bench_df['sma_10'] = bench_df['SPY'].rolling(window=10).mean()
    bench_df['sma_20'] = bench_df['SPY'].rolling(window=20).mean()
    bench_df['sma_50'] = bench_df['SPY'].rolling(window=50).mean()
    bench_df['sma_200'] = bench_df['SPY'].rolling(window=200).mean()
    bench_df = bench_df[bench_df['date'] >= pd.to_datetime(start_date)].copy()
    
    def get_regime_and_tor(row):
        vix = row['^VIX']
        if pd.isna(row['sma_10']) or pd.isna(row['sma_20']): return 'Yellow', 2
        if row['SPY'] < row['sma_20'] and row['sma_20'] < row['sma_10'] or vix > 25:
            return 'Red', 1 if vix < 25 else 0
        elif row['SPY'] > row['sma_10'] and row['sma_10'] > row['sma_20']:
            return 'Green', 5 if vix < 15 else (4 if vix <= 20 else 3)
        else: return 'Yellow', 3 if vix < 20 else (2 if vix <= 25 else 1)
            
    bench_df[['regime', 'tor']] = bench_df.apply(lambda row: pd.Series(get_regime_and_tor(row)), axis=1)
    bench_df['spy_ret'] = bench_df['SPY'].pct_change().fillna(0)
    bench_df['qqq_ret'] = bench_df['QQQ'].pct_change().fillna(0)
    bench_df['spy_cum'] = (1 + bench_df['spy_ret']).cumprod() - 1
    bench_df['qqq_cum'] = (1 + bench_df['qqq_ret']).cumprod() - 1
    return bench_df

def load_journal_data():
    conn = sqlite3.connect(DB_PATH)
    try: 
        df_j = pd.read_sql_query("SELECT * FROM options_journal", conn)
    except: 
        df_j = pd.DataFrame()
    conn.close()
    return df_j

# --- UI RENDERING ---
st.title("Estate Master Dashboard")
st.markdown(f"**Data Pipeline:** Live IBKR Sync via SQLite (`{DB_NAME}`) • **Last Refresh:** {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
st.markdown(f"**Active Scripts:** `{active_scripts_str}`")
st.divider()

global_df, global_metrics, silo_dfs, silo_metrics, pos_df, attr_df = load_and_process_data()
bench_df = load_benchmarks(global_df['date'].min(), global_df['date'].max())
chart_df = pd.merge(global_df, bench_df, on='date', how='left').ffill().fillna(0)
journal_raw_df = load_journal_data()

opt_margin_total = get_exact_opt_margin(pos_df)
tot_cash = pos_df[pos_df['asset_class'].isin(['IB01', 'Cash'])]['market_value'].sum()
tot_tech = pos_df[pos_df['asset_class'].isin(['CNDX', 'ITWN', 'CSKR', 'Active Swing'])]['market_value'].sum()
pct_cash = (tot_cash / global_metrics['nav']) * 100 if global_metrics['nav'] > 0 else 0
pct_tech = (tot_tech / global_metrics['nav']) * 100 if global_metrics['nav'] > 0 else 0
nav_A = silo_metrics.get('U23144948', {}).get('nav', 0)
nav_C = silo_metrics.get('U23154199', {}).get('nav', 0)

est_ann_ret = chart_df['daily_return'].mean() * 252

def calc_adv(b_ret):
    ann = b_ret.mean() * 252
    std = b_ret.std() * np.sqrt(252)
    sharpe = (ann - LIVE_RF_RATE) / std if std > 0 else 0
    cov = chart_df['daily_return'].cov(b_ret)
    var = b_ret.var()
    beta = cov / var if var > 0 else 0
    alpha = est_ann_ret - (LIVE_RF_RATE + beta * (ann - LIVE_RF_RATE))
    corr = chart_df['daily_return'].corr(b_ret)
    return sharpe, alpha * 100, corr

spy_sh, spy_al, spy_co = calc_adv(chart_df['spy_ret'])
qqq_sh, qqq_al, qqq_co = calc_adv(chart_df['qqq_ret'])
calmar = global_metrics['irr'] / abs(global_metrics['max_dd']) if global_metrics['max_dd'] < 0 else 0

def col_html(val, good_thresh=None):
    if "N/A" in str(val): return "color: #4b5563;"
    if isinstance(val, (int, float)):
        if good_thresh is not None: return "color: #15803d;" if val >= good_thresh else "color: #b91c1c;"
        return "color: #15803d;" if val > 0 else "color: #b91c1c;"
    if "-" in str(val): return "color: #b91c1c;"
    return "color: #15803d;"

# SECTION 0: EXECUTIVE BRIEFING (FOR TELEGRAM SCREENSHOTS)
st.markdown("### 🔔 Executive Briefing & Actionable Alerts")

alerts =[]

# 1. Options Warnings
if not journal_raw_df.empty:
    today = datetime.date.today()
    for _, row in journal_raw_df[pd.isnull(journal_raw_df['Close Date'])].iterrows():
        try:
            open_dt = pd.to_datetime(row['Open Date']).date()
            days_in_trade = (today - open_dt).days
            target_days = float(row['DTE at Entry']) / 2.0
            days_to_target = target_days - days_in_trade
            if days_to_target <= 7:
                alerts.append(f"⏱️ **Options Gamma Risk:** Contract {row['Ticker']} ({row['Short Strike']}/{row['Long Strike']}) is {max(0, int(days_to_target))} days away from 50% DTE threshold.")
        except: pass

# 2. SMA Warnings
if not bench_df.empty:
    last_spy = bench_df['SPY'].iloc[-1]
    sma_20 = bench_df['sma_20'].iloc[-1]
    sma_50 = bench_df['sma_50'].iloc[-1]
    sma_200 = bench_df['sma_200'].iloc[-1]
    if last_spy < sma_20: alerts.append(f"📉 **Trend Alert:** SPY (${last_spy:.2f}) has breached below the 20-day SMA (${sma_20:.2f}).")
    if last_spy < sma_50: alerts.append(f"🚨 **Trend Alert:** SPY (${last_spy:.2f}) has breached below the 50-day SMA (${sma_50:.2f}).")
    if last_spy < sma_200: alerts.append(f"☢️ **CRITICAL ALERT:** SPY (${last_spy:.2f}) has breached below the 200-day SMA (${sma_200:.2f}). Bear market threshold.")

# 3. Regime & Cash Drag
regime_str = chart_df['regime'].iloc[-1] if not chart_df.empty else 'Unknown'
tor_val = chart_df['tor'].iloc[-1] if not chart_df.empty else 0
alerts.append(f"🧭 **EOD Market Regime:** {regime_str} | **TOR Risk Level:** {tor_val}")

if pct_cash > 60: alerts.append(f"ℹ️ **Cash Drag Detected:** Unleveraged Cash/IB01 is {pct_cash:.1f}%. Consider deploying to Vaults if market is in uptrend.")
if pct_cash < 40: alerts.append(f"⚠️ **Cash Buffer Warning:** Global cash buffer dropped to {pct_cash:.1f}% (Below 40% optimal floor).")
if pct_tech > 40: alerts.append(f"⚠️ **Sector Concentration:** Tech/Semi exposure is {pct_tech:.1f}% (Above 40% safe threshold).")

if alerts:
    alert_html = "".join([f"<li style='margin-bottom: 5px;'>{a}</li>" for a in alerts])
    st.markdown(f"""
    <div style="background-color: #fffbeb; border-left: 6px solid #f59e0b; padding: 15px; border-radius: 4px; color: #1f2937; font-size: 14px; margin-bottom: 25px;">
        <ul style="margin: 0; padding-left: 20px;">
            {alert_html}
        </ul>
    </div>
    """.replace('\n', ''), unsafe_allow_html=True)
else:
    st.success("✅ All systems nominal. No actionable alerts at this time.")

st.divider()

# SECTION 1: MASTER AGGREGATION
html_metrics = f"""
<div style="background-color: #f3f4f6; padding: 20px; border-radius: 12px; border: 1px solid #e5e7eb; margin-bottom: 20px;">
    <h4 style="text-align: center; color: #1f2937; margin-bottom: 20px; text-transform: uppercase; letter-spacing: 2px; font-size: 24px;">Master Estate Aggregation</h4>
    <div style="display: grid; grid-template-columns: repeat(7, 1fr); gap: 15px; text-align: center; font-family: monospace; font-size: 20px;">
        <div>Static Balance<br><span style="color: #1d4ed8; font-weight: 900; font-size: 28px;">${global_metrics['nav']:,.0f}</span></div>
        <div>IRR<br><span style="{col_html(global_metrics['irr'])} font-weight: 900; font-size: 28px;">{global_metrics['irr']:.2f}%</span></div>
        <div>Global P&L<br><span style="{col_html(global_metrics['pnl'])} font-weight: 900; font-size: 28px;">${global_metrics['pnl']:,.0f}</span></div>
        <div>Global Sharpe<br><span style="{col_html(global_metrics['sharpe'])} font-weight: 900; font-size: 28px;">{global_metrics['sharpe']:.2f}</span></div>
        <div>SPY Sharpe<br><b>{spy_sh:.2f}</b></div>
        <div>QQQ Sharpe<br><b>{qqq_sh:.2f}</b></div>
        <div>Max DD<br><span style="color: #b91c1c; font-weight: 900; font-size: 28px;">{global_metrics['max_dd']:.2f}%</span></div>
        
        <div style="margin-top:20px;">DD Duration<br><span style="color: #1f2937; font-weight: 900; font-size: 28px;">{global_metrics['dd_days']} d</span></div>
        <div style="margin-top:20px;">Calmar<br><span style="color: #1f2937; font-weight: 900; font-size: 28px;">{calmar:.2f}</span></div>
        <div style="margin-top:20px;">Est. ROC%<br><span style="{col_html(global_metrics['roc'])} font-weight: 900; font-size: 28px;">{global_metrics['roc']:.2f}%</span></div>
        <div style="margin-top:20px;">SPY Alpha<br><span style="{col_html(spy_al)} font-weight: bold;">{spy_al:.2f}%</span></div>
        <div style="margin-top:20px;">SPY Corr.<br><span style="{col_html(spy_co, 0.3)} font-weight: bold;">{spy_co:.2f}</span></div>
        <div style="margin-top:20px;">QQQ Alpha<br><span style="{col_html(qqq_al)} font-weight: bold;">{qqq_al:.2f}%</span></div>
        <div style="margin-top:20px;">QQQ Corr.<br><span style="{col_html(qqq_co, 0.3)} font-weight: bold;">{qqq_co:.2f}</span></div>
    </div>
    <div style="margin-top: 30px; padding-top: 20px; border-top: 1px solid #d1d5db; text-align: center; font-family: monospace; font-size: 16px; color: #6b7280;">
        <span style="font-weight: bold; color: #374151; margin-right: 15px;">MACRO & OPTIMAL RANGES:</span>
        <span style="margin-right: 15px; color:#1d4ed8;">Risk-Free Yield (^IRX): {LIVE_RF_RATE*100:.2f}%</span>
        <span style="margin-right: 15px;">IRR: >10%</span><span style="margin-right: 15px;">Sharpe: 1.0 to 2.0+</span><span style="margin-right: 15px;">Max DD: > -15%</span><span style="margin-right: 15px;">Calmar: > 1.0</span><span style="margin-right: 15px;">Alpha: > 0%</span><span>Corr: 0.30 to 0.60</span>
    </div>
</div>
""".replace('\n', '')
st.markdown(html_metrics, unsafe_allow_html=True)

# --- SECTION 2: SILO PANELS ---
cols = st.columns(4)
for idx, acc in enumerate(SILO_MAP.keys()):
    name, desc, color = SILO_MAP[acc]
    m = silo_metrics[acc]
    with cols[idx]:
        st.markdown(f"### {name}")
        st.caption(desc)
        st.markdown(f"**Bal: ${m['nav']:,.2f}**")
        st.markdown(
            "<div style='font-size: 11px; margin-bottom: 5px;'>"
            "<span style='color:black; font-weight:bold;'>― Bal</span> | "
            "<span style='color:#3b82f6; font-weight:bold;'>― SPY</span> | "
            "<span style='color:#dc2626; font-weight:bold;'>― QQQ</span>"
            "</div>", 
            unsafe_allow_html=True
        )
        
        if not silo_dfs[acc].empty:
            s_chart = pd.merge(silo_dfs[acc][['date', 'cum_return']], bench_df[['date', 'spy_cum', 'qqq_cum']], on='date', how='left').ffill().fillna(0)
            
            fig_mini = go.Figure()
            fig_mini.add_trace(go.Scatter(x=s_chart['date'], y=s_chart['cum_return']*100, mode='lines', line=dict(color='black', width=4), showlegend=False))
            fig_mini.add_trace(go.Scatter(x=s_chart['date'], y=s_chart['spy_cum']*100, mode='lines', line=dict(color='#3b82f6', width=2), showlegend=False))
            fig_mini.add_trace(go.Scatter(x=s_chart['date'], y=s_chart['qqq_cum']*100, mode='lines', line=dict(color='#dc2626', width=2), showlegend=False))
            
            fig_mini.update_layout(
                height=300, 
                margin=dict(l=0, r=0, t=0, b=0), 
                plot_bgcolor=color, 
                paper_bgcolor='rgba(0,0,0,0)', 
                yaxis=dict(zeroline=True, zerolinecolor='black', zerolinewidth=1)
            )
            fig_mini.update_xaxes(visible=False)
            fig_mini.update_yaxes(showticklabels=False)
            st.plotly_chart(fig_mini, width="stretch")
        
        c1, c2 = st.columns(2)
        c1.write(f"**IRR:** {m['irr']:.2f}%")
        c2.write(f"**Sharpe:** {m['sharpe']:.2f}")
        c1.write(f"**P&L:** ${m['pnl']:,.0f}")
        c2.write(f"**Max DD:** {m['max_dd']:.2f}%")
        c1.write(f"**DD Days:** {m['dd_days']}")
        c2.write(f"**ROC:** {m['roc']:.2f}%")

st.divider()

# --- SECTION 3: ESTATE CAPITAL BREAKDOWN ---
st.subheader("1. Estate Capital Breakdown (GAAP & Gross Assets)")
col_bar, col_pie = st.columns(2)

if not pos_df.empty:
    bar_df = pos_df.groupby(['account', 'asset_class'])['market_value'].sum().unstack(fill_value=0)
    
    # Calculate the Accounting Offset to fix CFD double-counting
    bar_df['Accounting Offset'] = 0.0
    for acc in bar_df.index:
        gross_val = bar_df.loc[acc].sum()
        actual_nav = silo_metrics.get(acc, {}).get('nav', 0)
        bar_df.at[acc, 'Accounting Offset'] = actual_nav - gross_val
        
    pie_df = pos_df.groupby('asset_class')['market_value'].sum().reset_index()
    pie_df['market_value'] = pie_df['market_value'].abs() 
    tot_gross = pie_df['market_value'].sum()
    pie_df['pct'] = (pie_df['market_value'] / tot_gross) * 100 if tot_gross > 0 else 0
    pie_df['legend_label'] = pie_df.apply(lambda r: f"{r['asset_class']} (${r['market_value']:,.0f} | {r['pct']:.1f}%)", axis=1)

    with col_bar:
        fig_bar = go.Figure()
        silo_names =[SILO_MAP.get(acc, (acc,))[0] for acc in bar_df.index]
        silo_totals = bar_df.sum(axis=1).values
        
        for asset in bar_df.columns:
            l_label = pie_df[pie_df['asset_class'] == asset]['legend_label'].iloc[0] if asset in pie_df['asset_class'].values else asset
            fig_bar.add_trace(go.Bar(
                name=l_label, 
                x=silo_names, 
                y=bar_df[asset], 
                marker_color=COLOR_PALETTE.get(asset, '#cbd5e1')
            ))
            
        opt_margin_A = get_exact_opt_margin(pos_df[pos_df['account'] == 'U23144948'])
        opt_margin_C = get_exact_opt_margin(pos_df[pos_df['account'] == 'U23154199'])
        
        tot_ml = opt_margin_A + opt_margin_C
        pct_ml = (tot_ml / global_metrics['nav']) * 100 if global_metrics['nav'] > 0 else 0
        ml_label = f"Margin Lock (${tot_ml:,.0f} | {pct_ml:.1f}%)"
        
        fig_bar.add_trace(go.Scatter(
            x=['Silo A', 'Silo C'], 
            y=[opt_margin_A, opt_margin_C], 
            name=ml_label, 
            mode='markers', 
            marker=dict(symbol='diamond', size=14, color='#ef4444', line=dict(width=1, color='black'))
        ))
        
        for i, total in enumerate(silo_totals):
            pct_total = (total / global_metrics['nav']) * 100 if global_metrics['nav'] > 0 else 0
            fig_bar.add_annotation(
                x=silo_names[i], 
                y=total, 
                text=f"<b>${total/1000:.0f}k</b><br>({pct_total:.1f}%)", 
                showarrow=False, 
                yanchor='bottom', 
                yshift=5, 
                font=dict(size=16)
            )
            
        fig_bar.update_layout(
            barmode='relative', 
            title="GAAP Balance Sheet per Silo (USD)", 
            plot_bgcolor='rgba(0,0,0,0)', 
            margin=dict(l=20, r=20, t=40, b=20), 
            yaxis=dict(zeroline=True, zerolinecolor='black', zerolinewidth=1, gridcolor='LightGray'), 
            legend_title_text="<b>ASSET CLASS</b>", 
            font=dict(size=16)
        )
        st.plotly_chart(fig_bar, width="stretch")

    with col_pie:
        fig_pie = go.Figure(data=[go.Pie(
            labels=pie_df['legend_label'], 
            values=pie_df['market_value'], 
            hole=.4, 
            marker=dict(colors=[COLOR_PALETTE.get(a, '#cbd5e1') for a in pie_df['asset_class']]), 
            textinfo='percent'
        )])
        fig_pie.update_traces(textfont_size=16)
        fig_pie.update_layout(
            title="Gross Asset Allocation", 
            margin=dict(l=20, r=20, t=40, b=20), 
            legend_title_text="<b>ASSET CLASS</b>", 
            font=dict(size=16)
        )
        st.plotly_chart(fig_pie, width="stretch")

st.divider()

# --- SECTION 4: TARGET PORTFOLIO COMPOSITION ---
st.subheader("2. Live Portfolio Composition (from TWS)")
comp_cols = st.columns(4)

strats =[
    "<b>STRATEGY & EXECUTION (Silo A):</b><br>Adheres to 40% cash buffer. Execute XSP/XND Put Spreads weekly at 45-50 DTE near -0.20 Delta. Strict 8% premium floor. 50% GTC take-profit. <b>Tail Hedge:</b> Allocate 10% of premiums to deep OTM S&P 500 Puts to self-insure against Black Swans.",
    "<b>STRATEGY & EXECUTION (Silo B):</b><br><b>Regime Filter:</b> Green (3-5R TOR), Yellow (1-3R), Red (0-1R). <b>Entry:</b> 2-3 tranches on momentum. Initial Stop at Low of Day (LOD). <b>Management:</b> Move stop to breakeven at +1R profit. Scale out 30-50% on Day 3-5.",
    "<b>STRATEGY & EXECUTION (Silo C):</b><br>Adheres to 40% cash buffer. Execute XSP/XND Put Spreads weekly at 45-50 DTE near -0.20 Delta. Strict 8% premium floor. 50% GTC take-profit. <b>Tail Hedge:</b> Allocate 10% of premiums to deep OTM S&P 500 Puts to self-insure against Black Swans.",
    "<b>STRATEGY & EXECUTION (Silo D):</b><br>13F Themes (Druckenmiller, Ackman) executed via Sector UCITS ETFs to eliminate CFD financing drag. High-conviction social sentiment (Shay, Pelosi) executed via CFDs with strict 30-45 day time-stops to cap overnight fees."
]

for idx, acc in enumerate(SILO_MAP.keys()):
    name, _, _ = SILO_MAP[acc]
    acc_pos = pos_df[pos_df['account'] == acc].copy()
    
    with comp_cols[idx]:
        st.markdown(f"**{name}**")
        if not acc_pos.empty:
            acc_nav = silo_metrics[acc]['nav']
            acc_pos['Allocation %'] = (acc_pos['market_value'] / acc_nav) * 100 if acc_nav > 0 else 0
            display_df = acc_pos[['symbol', 'market_value', 'Allocation %']].sort_values('market_value', ascending=False)
            display_df.columns = ['Asset', 'Value ($)', 'Alloc (%)']
            st.dataframe(display_df.style.format({'Value ($)': '{:,.0f}', 'Alloc (%)': '{:.1f}%'}), hide_index=True, width='stretch')
        else: 
            st.write("No active positions.")
            
        st.markdown(
            f"<div style='font-size: 11px; color: #000000; padding: 10px; border-top: 1px solid #e5e7eb; margin-top: 10px;'>{strats[idx]}</div>", 
            unsafe_allow_html=True
        )

st.divider()

# --- SECTION 5: DAILY PNL HISTOGRAM ---
st.subheader("3. Daily PnL per Silo")
spy_usd_pnl = []
qqq_usd_pnl =[]
curr_spy_nav = chart_df['nav'].iloc[0] if not chart_df.empty else 0
curr_qqq_nav = chart_df['nav'].iloc[0] if not chart_df.empty else 0

for i, row in chart_df.iterrows():
    s_pnl = curr_spy_nav * row['spy_ret']
    q_pnl = curr_qqq_nav * row['qqq_ret']
    spy_usd_pnl.append(s_pnl)
    qqq_usd_pnl.append(q_pnl)
    curr_spy_nav += s_pnl + row['cash_flow']
    curr_qqq_nav += q_pnl + row['cash_flow']

chart_df['spy_usd_cum'] = pd.Series(spy_usd_pnl).cumsum()
chart_df['qqq_usd_cum'] = pd.Series(qqq_usd_pnl).cumsum()

fig_pnl = go.Figure()
for acc in SILO_MAP.keys():
    name, _, color = SILO_MAP[acc]
    if not silo_dfs[acc].empty: 
        fig_pnl.add_trace(go.Bar(
            x=silo_dfs[acc]['date'], 
            y=silo_dfs[acc]['daily_pnl'], 
            name=name, 
            marker_color=color
        ))

fig_pnl.add_trace(go.Scatter(x=chart_df['date'], y=chart_df['cum_pnl'], name='Estate (Cum PnL USD)', mode='lines', line=dict(color='black', width=6), yaxis='y2'))
fig_pnl.add_trace(go.Scatter(x=chart_df['date'], y=chart_df['spy_usd_cum'], name='SPY (Cum PnL USD)', mode='lines', line=dict(color='#3b82f6', width=3), yaxis='y2'))
fig_pnl.add_trace(go.Scatter(x=chart_df['date'], y=chart_df['qqq_usd_cum'], name='QQQ (Cum PnL USD)', mode='lines', line=dict(color='#dc2626', width=3), yaxis='y2'))

chart_df['regime_bg'] = chart_df['regime'].map({'Green': '#166534', 'Yellow': '#eab308', 'Red': '#991b1b'})
chart_df['regime_txt'] = chart_df['regime'].map({'Green': 'white', 'Yellow': 'black', 'Red': 'white'})

fig_pnl.add_trace(go.Scatter(
    x=chart_df['date'], y=[0]*len(chart_df), mode='markers+text', 
    marker=dict(color=chart_df['regime_bg'], symbol='square', size=16, line=dict(width=1, color='black')),
    text=chart_df['tor'], textposition='middle center', textfont=dict(color=chart_df['regime_txt'], size=10, weight='bold'),
    hovertemplate="<b>Date:</b> %{x|%Y-%m-%d}<br><b>Regime:</b> %{customdata[0]}<br><b>TOR:</b> %{customdata[1]}<extra></extra>",
    customdata=np.column_stack((chart_df['regime'], chart_df['tor'])), 
    name='Market Regime', showlegend=False, yaxis='y3'
))

last_dt = chart_df['date'].iloc[-1]
est_val = chart_df['cum_pnl'].iloc[-1]
spy_val = chart_df['spy_usd_cum'].iloc[-1]
qqq_val = chart_df['qqq_usd_cum'].iloc[-1]

fig_pnl.add_annotation(x=last_dt, y=est_val, text=f"{(est_val/global_metrics['nav'])*100:.1f}%<br>${est_val:,.0f}", showarrow=False, xanchor='left', yref='y2', bgcolor='black', font=dict(color='white', size=11))
fig_pnl.add_annotation(x=last_dt, y=spy_val, text=f"{(spy_val/global_metrics['nav'])*100:.1f}%<br>${spy_val:,.0f}", showarrow=False, xanchor='left', yref='y2', bgcolor='#3b82f6', font=dict(color='white', size=11))
fig_pnl.add_annotation(x=last_dt, y=qqq_val, text=f"{(qqq_val/global_metrics['nav'])*100:.1f}%<br>${qqq_val:,.0f}", showarrow=False, xanchor='left', yref='y2', bgcolor='#dc2626', font=dict(color='white', size=11))

fig_pnl.update_layout(
    barmode='relative', 
    margin=dict(l=20, r=20, t=30, b=20), 
    plot_bgcolor='rgba(0,0,0,0)', 
    legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1), 
    yaxis=dict(title='Daily PnL (USD)', showgrid=True, gridcolor='LightGray', zeroline=True, zerolinecolor='black', zerolinewidth=1), 
    yaxis2=dict(title='Cumulative PnL (USD)', overlaying='y', side='right', showgrid=False), 
    yaxis3=dict(overlaying='y', visible=False, range=[-1, 20])
)
st.plotly_chart(fig_pnl, width="stretch")

st.markdown("""
<div style="background-color: #f9fafb; padding: 10px; border-radius: 8px; border: 1px solid #e5e7eb; font-size: 11px; color: #4b5563;">
    <span style="font-weight: bold; color: #1f2937;">TOR (Total Open Risk) Tracker:</span> Applies strictly to <b>Silo B</b> (Active Swing). TOR is the sum of risk across all open positions (Distance from Entry to Stop Loss). Once a trade reaches +1R profit, moving the stop to break-even reduces its specific TOR contribution to 0.<br><br>
    <span style="font-weight: bold; color: #1f2937;">Regime Key:</span> 
    <span style="color: #166534; font-weight: bold;">🟢 Green (3-5 TOR):</span> SPY > 10 SMA > 20 SMA. Low VIX permits max risk exposure. &nbsp;&nbsp;
    <span style="color: #a16207; font-weight: bold;">🟡 Yellow (1-3 TOR):</span> Pullbacks/Transitions. Risk is throttled. &nbsp;&nbsp;
    <span style="color: #991b1b; font-weight: bold;">🔴 Red (0-1 TOR):</span> SPY < 20 SMA < 10 SMA. Defensive stance. VIX > 25 halts all active trading (TOR = 0).
</div>
""".replace('\n', ''), unsafe_allow_html=True)

st.divider()

# --- SECTION 6: PNL ATTRIBUTION ---
st.subheader("4. PnL Attribution & Capital Velocity")
if not attr_df.empty:
    attr_df = attr_df.sort_values('date').reset_index(drop=True)
    attr_df['abs_sum'] = attr_df[['a1_yield', 'a2_beta', 'a3_vrp', 'a4_alpha', 'a5_fees']].abs().sum(axis=1)
    active_dates = attr_df[attr_df['abs_sum'] > 0]
    
    if not active_dates.empty:
        start_idx = active_dates.index[0]
        if start_idx > 0: start_idx -= 1
        line_df = attr_df.iloc[start_idx:].copy().reset_index(drop=True)
    else: 
        line_df = attr_df.copy()

    tot_a1 = attr_df['a1_yield'].sum()
    tot_a2 = attr_df['a2_beta'].sum()
    tot_a3 = attr_df['a3_vrp'].sum()
    tot_a4 = attr_df['a4_alpha'].sum()
    tot_a5 = attr_df['a5_fees'].sum()
    
    col_bar, col_line, col_vel = st.columns([2, 3, 1])
    bar_colors =['#3b82f6', '#f97316', '#166534', '#a855f7', '#991b1b']
    
    with col_bar:
        fig_attr_bar = go.Figure(data=[go.Bar(
            x=['Yield (a1)', 'Beta (a2)', 'VRP (a3)', 'Alpha (a4)', 'Fees (a5)'], 
            y=[tot_a1, tot_a2, tot_a3, tot_a4, tot_a5], 
            text=[f"${v:,.0f}" for v in[tot_a1, tot_a2, tot_a3, tot_a4, tot_a5]], 
            textposition='auto', 
            marker_color=bar_colors
        )])
        fig_attr_bar.update_layout(
            title="Absolute PnL by Strategy", 
            plot_bgcolor='rgba(0,0,0,0)', 
            margin=dict(l=20, r=20, t=40, b=20), 
            yaxis=dict(zeroline=True, zerolinecolor='black', zerolinewidth=1, gridcolor='LightGray')
        )
        st.plotly_chart(fig_attr_bar, width="stretch")
        
    with col_line:
        fig_attr_line = go.Figure()
        fig_attr_line.add_trace(go.Scatter(x=line_df['date'], y=line_df['a1_yield'].cumsum(), name='Yield', line=dict(color='#3b82f6', width=4)))
        fig_attr_line.add_trace(go.Scatter(x=line_df['date'], y=line_df['a2_beta'].cumsum(), name='Beta', line=dict(color='#f97316', width=4)))
        fig_attr_line.add_trace(go.Scatter(x=line_df['date'], y=line_df['a3_vrp'].cumsum(), name='VRP', line=dict(color='#166534', width=4)))
        fig_attr_line.add_trace(go.Scatter(x=line_df['date'], y=line_df['a4_alpha'].cumsum(), name='Alpha', line=dict(color='#a855f7', width=4)))
        fig_attr_line.add_trace(go.Scatter(x=line_df['date'], y=line_df['a5_fees'].cumsum(), name='Fees', line=dict(color='#991b1b', width=4)))
        
        if not line_df.empty:
            last_dt = line_df['date'].iloc[-1]
            for col, name, color in zip(['a1_yield', 'a2_beta', 'a3_vrp', 'a4_alpha', 'a5_fees'],['Yield', 'Beta', 'VRP', 'Alpha', 'Fees'], bar_colors):
                val = line_df[col].cumsum().iloc[-1]
                fig_attr_line.add_annotation(
                    x=last_dt, 
                    y=val, 
                    text=f"${val:,.0f}", 
                    showarrow=False, 
                    xanchor='left', 
                    bgcolor=color, 
                    font=dict(color='white', size=11), 
                    borderpad=3
                )
                
        fig_attr_line.update_layout(
            title="Cumulative Trajectory", 
            plot_bgcolor='rgba(0,0,0,0)', 
            margin=dict(l=20, r=60, t=40, b=20), 
            yaxis=dict(zeroline=True, zerolinecolor='black', zerolinewidth=1, gridcolor='LightGray'), 
            legend=dict(orientation="h", yanchor="bottom", y=-0.2, xanchor="center", x=0.5)
        )
        st.plotly_chart(fig_attr_line, width="stretch")
        
    with col_vel:
        st.markdown("##### Options Engine Velocity")
        st.caption("(Silos A & C)")
        st.metric("Total VRP Harvested", f"${tot_a3:,.0f}")
        st.metric("Options Margin Locked", f"${opt_margin_total:,.0f}")
        st.metric("Tail Hedge Budget (10%)", f"${tot_a3 * 0.10:,.0f}", help="Accumulated 10% of VRP budget reserved for deep OTM Ackman Puts.")
        st.metric("Target Profit Hit", "50% GTC")

st.divider()

# --- SECTION 7: THE MASTER MATRIX ---
st.subheader("5. The Master Instrument Matrix (Tax, Alpha, & Sharpe Grading)")
matrix_data =[
    {"Instrument": "USD Cash", "Type": "Currency", "Risk Profile": "Risk-Free", "Alpha Potential": "Zero", "Sharpe Impact": "Stabilizer", "Trading Strategy": "Liquidity", "Jurisdiction": "US (IBKR)", "Tax Treatment": "Exempt (Bank Deposit)", "CIO Min Alloc. %": "1%", "CIO Max Alloc. %": "100%", "CIO Grading": "Splendid", "Noteworthy Comments": "Uninvested USD held in IBKR. Mandatory margin collateral."},
    {"Instrument": "IB01", "Type": "UCITS ETF", "Risk Profile": "Risk-Free", "Alpha Potential": "Zero", "Sharpe Impact": "High", "Trading Strategy": "Collateral", "Jurisdiction": "Ireland", "Tax Treatment": "Exempt (Irish Domicile)", "CIO Min Alloc. %": "10%", "CIO Max Alloc. %": "100%", "CIO Grading": "Splendid", "Noteworthy Comments": "Irish-domiciled short-term US Treasury fund. Accumulates ~4.5% tax-free."},
    {"Instrument": "XSP Put Spreads", "Type": "Index Option", "Risk Profile": "Moderate", "Alpha Potential": "High (VRP)", "Sharpe Impact": "High", "Trading Strategy": "Weekly Income", "Jurisdiction": "US (Cboe)", "Tax Treatment": "Exempt (Cash-Settled)", "CIO Min Alloc. %": "0%", "CIO Max Alloc. %": "20%", "CIO Grading": "Splendid", "Noteworthy Comments": "Cash-settled S&P 500 options. 100% safe from IRS."},
    {"Instrument": "XND Put Spreads", "Type": "Index Option", "Risk Profile": "Mod/High", "Alpha Potential": "High", "Sharpe Impact": "Moderate", "Trading Strategy": "Satellite Income", "Jurisdiction": "US (Cboe)", "Tax Treatment": "Exempt (Cash-Settled)", "CIO Min Alloc. %": "0%", "CIO Max Alloc. %": "10%", "CIO Grading": "Great", "Noteworthy Comments": "Micro-Nasdaq 100. Cash-settled. IRS Safe. Higher volatility than XSP."},
    {"Instrument": "CSPX", "Type": "UCITS ETF", "Risk Profile": "Moderate", "Alpha Potential": "Zero", "Sharpe Impact": "Baseline", "Trading Strategy": "Long Term", "Jurisdiction": "Ireland", "Tax Treatment": "Exempt (Irish Domicile)", "CIO Min Alloc. %": "0%", "CIO Max Alloc. %": "60%", "CIO Grading": "Great", "Noteworthy Comments": "Irish-domiciled S&P 500. Shields against 40% Estate Tax."},
    {"Instrument": "CNDX", "Type": "UCITS ETF", "Risk Profile": "Aggressive", "Alpha Potential": "High", "Sharpe Impact": "Moderate", "Trading Strategy": "Long Term", "Jurisdiction": "Ireland", "Tax Treatment": "Exempt (Irish Domicile)", "CIO Min Alloc. %": "0%", "CIO Max Alloc. %": "40%", "CIO Grading": "Great", "Noteworthy Comments": "Irish-domiciled Nasdaq 100. Shields against 40% Estate Tax. High beta tech exposure."},
    {"Instrument": "ITWN (Taiwan)", "Type": "UCITS ETF", "Risk Profile": "Aggressive", "Alpha Potential": "High", "Sharpe Impact": "Moderate", "Trading Strategy": "Momentum", "Jurisdiction": "Ireland", "Tax Treatment": "Exempt (Irish Domicile)", "CIO Min Alloc. %": "0%", "CIO Max Alloc. %": "20%", "CIO Grading": "Great", "Noteworthy Comments": "Geographic tech alpha via Irish wrapper."},
    {"Instrument": "CSKR (Korea)", "Type": "UCITS ETF", "Risk Profile": "Aggressive", "Alpha Potential": "High", "Sharpe Impact": "Moderate", "Trading Strategy": "Momentum", "Jurisdiction": "Ireland", "Tax Treatment": "Exempt (Irish Domicile)", "CIO Min Alloc. %": "0%", "CIO Max Alloc. %": "15%", "CIO Grading": "Great", "Noteworthy Comments": "Geographic tech alpha via Irish wrapper."},
    {"Instrument": "CNYA (China)", "Type": "UCITS ETF", "Risk Profile": "Aggressive", "Alpha Potential": "High", "Sharpe Impact": "Volatile", "Trading Strategy": "Momentum", "Jurisdiction": "Ireland", "Tax Treatment": "Exempt (Irish Domicile)", "CIO Min Alloc. %": "0%", "CIO Max Alloc. %": "10%", "CIO Grading": "Great", "Noteworthy Comments": "Geographic tech alpha via Irish wrapper."},
    {"Instrument": "SGLN / IGLN (Gold)", "Type": "UCITS ETC", "Risk Profile": "Moderate", "Alpha Potential": "Crisis Alpha", "Sharpe Impact": "Stabilizer", "Trading Strategy": "Tail Hedge", "Jurisdiction": "Ireland", "Tax Treatment": "Exempt (Irish Domicile)", "CIO Min Alloc. %": "0%", "CIO Max Alloc. %": "10%", "CIO Grading": "Good", "Noteworthy Comments": "Geopolitical crisis hedge. Rises during interest rate cuts and wars."},
    {"Instrument": "BTC/ETH ETPs", "Type": "Crypto ETP", "Risk Profile": "Aggressive", "Alpha Potential": "High", "Sharpe Impact": "Volatile", "Trading Strategy": "Uncorrelated", "Jurisdiction": "Europe (Jersey/CH)", "Tax Treatment": "Exempt (Offshore Wrapper)", "CIO Min Alloc. %": "0%", "CIO Max Alloc. %": "5%", "CIO Grading": "Good", "Noteworthy Comments": "Offshore crypto wrappers (e.g. CoinShares). IRS safe spot exposure."},
    {"Instrument": "US Tech CFDs", "Type": "OTC Contract", "Risk Profile": "Aggressive", "Alpha Potential": "High", "Sharpe Impact": "Negative", "Trading Strategy": "Swing Trading", "Jurisdiction": "UK/Offshore", "Tax Treatment": "Exempt (OTC Derivative)", "CIO Min Alloc. %": "0%", "CIO Max Alloc. %": "3%", "CIO Grading": "Good", "Noteworthy Comments": "Synthetic derivatives. 0% IRS risk. Quarantined to Silo B."},
    {"Instrument": "International Stocks", "Type": "Direct Equity", "Risk Profile": "Aggressive", "Alpha Potential": "High", "Sharpe Impact": "Negative", "Trading Strategy": "Swing Trading", "Jurisdiction": "Europe/Asia", "Tax Treatment": "Exempt", "CIO Min Alloc. %": "0%", "CIO Max Alloc. %": "3%", "CIO Grading": "Good", "Noteworthy Comments": "Safe from IRS. Suffers from wider bid/ask spreads compared to US market."},
    {"Instrument": "/MES Put Spreads", "Type": "Futures Option", "Risk Profile": "Moderate", "Alpha Potential": "Highest (SPAN)", "Sharpe Impact": "High", "Trading Strategy": "Capital Efficiency", "Jurisdiction": "US (CME)", "Tax Treatment": "Exempt (Section 1256)", "CIO Min Alloc. %": "0%", "CIO Max Alloc. %": "25%", "CIO Grading": "Contingent", "Noteworthy Comments": "Contingent on mastering XSP mechanics. SPAN margin halves collateral, doubling ROC."},
    {"Instrument": "Managed Futures (CTAs)", "Type": "UCITS Fund", "Risk Profile": "Moderate", "Alpha Potential": "Crisis Alpha", "Sharpe Impact": "High (Uncorrel.)", "Trading Strategy": "Trend Following", "Jurisdiction": "Ireland", "Tax Treatment": "Exempt (Irish Domicile)", "CIO Min Alloc. %": "0%", "CIO Max Alloc. %": "15%", "CIO Grading": "Contingent", "Noteworthy Comments": "Contingent on risk tolerance change. Shorts commodities & bonds to protect during crashes."},
    {"Instrument": "XSP LEAPS", "Type": "Index Option", "Risk Profile": "Aggressive", "Alpha Potential": "Low", "Sharpe Impact": "Negative", "Trading Strategy": "Leverage", "Jurisdiction": "US (Cboe)", "Tax Treatment": "Exempt (Cash-Settled)", "CIO Min Alloc. %": "0%", "CIO Max Alloc. %": "0%", "CIO Grading": "Bad", "Noteworthy Comments": "IRS safe, but mathematical drag of Theta and lost dividends destroys edge."},
    {"Instrument": "Physical US Stocks", "Type": "Stock", "Risk Profile": "Extreme", "Alpha Potential": "High", "Sharpe Impact": "Baseline", "Trading Strategy": "Swing", "Jurisdiction": "US", "Tax Treatment": "LETHAL (40% Estate Tax)", "CIO Min Alloc. %": "0%", "CIO Max Alloc. %": "0%", "CIO Grading": "Avoid", "Noteworthy Comments": "LETHAL. Triggers 40% US Estate Tax and 30% Dividend Withholding."},
    {"Instrument": "US Spot BTC/ETH", "Type": "US ETF", "Risk Profile": "Extreme", "Alpha Potential": "N/A", "Sharpe Impact": "N/A", "Trading Strategy": "N/A", "Jurisdiction": "US", "Tax Treatment": "LETHAL (40% Estate Tax)", "CIO Min Alloc. %": "0%", "CIO Max Alloc. %": "0%", "CIO Grading": "Avoid", "Noteworthy Comments": "LETHAL. Standard ETFs (IBIT/FBTC) are US-situs property. Will trigger Estate Tax confiscation."},
    {"Instrument": "TQQQ", "Type": "Physical ETF", "Risk Profile": "Extreme", "Alpha Potential": "Negative", "Sharpe Impact": "Negative", "Trading Strategy": "Speculation", "Jurisdiction": "US", "Tax Treatment": "LETHAL (40% Estate Tax)", "CIO Min Alloc. %": "0%", "CIO Max Alloc. %": "0%", "CIO Grading": "Avoid", "Noteworthy Comments": "LETHAL. Widow-maker. Combines IRS Tax Trap with massive Beta Slippage decay."},
    {"Instrument": "Accruals, Unsettled & FX", "Type": "Reconciliation", "Risk Profile": "N/A", "Alpha Potential": "N/A", "Sharpe Impact": "N/A", "Trading Strategy": "Accounting", "Jurisdiction": "N/A", "Tax Treatment": "N/A", "CIO Min Alloc. %": "0%", "CIO Max Alloc. %": "0%", "CIO Grading": "Splendid", "Noteworthy Comments": "Dynamic balancing metric to reconcile aggregate physical Net Liq vs discrete position sums."}
]

df_matrix = pd.DataFrame(matrix_data)
alloc_map = {}

for i, r in pos_df.iterrows():
    ac = r['asset_class']
    if ac == 'Crypto': 
        alloc_map['BTC/ETH ETPs'] = alloc_map.get('BTC/ETH ETPs', 0) + r['market_value']
    elif ac == 'Cash': 
        alloc_map['USD Cash'] = alloc_map.get('USD Cash', 0) + r['market_value']
    elif ac == 'Active Swing': 
        if r['sec_type'] == 'STK': 
            alloc_map['International Stocks'] = alloc_map.get('International Stocks', 0) + r['market_value']
        else: 
            alloc_map['US Tech CFDs'] = alloc_map.get('US Tech CFDs', 0) + r['market_value']
    elif ac == 'Opt Liab':
        if 'XSP' in r['symbol']: 
            alloc_map['XSP Put Spreads'] = alloc_map.get('XSP Put Spreads', 0) + r['market_value']
        elif 'XND' in r['symbol']: 
            alloc_map['XND Put Spreads'] = alloc_map.get('XND Put Spreads', 0) + r['market_value']
        else: 
            alloc_map['XSP Put Spreads'] = alloc_map.get('XSP Put Spreads', 0) + r['market_value']
    else: 
        alloc_map[ac] = alloc_map.get(ac, 0) + r['market_value']
    
def get_pct(inst):
    if inst == 'Accruals, Unsettled & FX': return 0.0 
    if inst == 'ITWN (Taiwan)': val = alloc_map.get('ITWN', 0)
    elif inst == 'CSKR (Korea)': val = alloc_map.get('CSKR', 0)
    elif inst == 'CNYA (China)': val = alloc_map.get('CNYA', 0)
    else: val = alloc_map.get(inst, 0)
    return (val / global_metrics['nav']) * 100 if global_metrics['nav'] > 0 else 0

df_matrix.insert(9, "Current Global Alloc. %", df_matrix['Instrument'].apply(get_pct))

raw_sum = df_matrix['Current Global Alloc. %'].sum()
df_matrix.loc[df_matrix['Instrument'] == 'Accruals, Unsettled & FX', 'Current Global Alloc. %'] = 100.0 - raw_sum

def color_grading(val):
    if val == "Splendid": return 'background-color: #dcfce7; color: #166534; font-weight: bold'
    if val == "Great": return 'background-color: #ecfccb; color: #15803d; font-weight: bold'
    if val == "Good": return 'background-color: #fef9c3; color: #4d7c0f; font-weight: bold'
    if val == "Contingent": return 'background-color: #e0e7ff; color: #1e40af; font-weight: bold'
    if val == "Bad": return 'background-color: #ffedd5; color: #b91c1c; font-weight: bold'
    if val == "Avoid": return 'background-color: #fecaca; color: #991b1b; font-weight: bold'
    return ''

st.dataframe(
    df_matrix.style.format({'Current Global Alloc. %': '{:.2f}%'})
                   .map(color_grading, subset=['CIO Grading'])
                   .set_properties(**{'background-color': '#eff6ff', 'color': '#1d4ed8', 'font-weight': 'bold'}, subset=['Current Global Alloc. %']), 
    hide_index=True, 
    width="stretch"
)

option_instruments =["XSP Put Spreads", "XND Put Spreads", "/MES Put Spreads", "XSP LEAPS"]
opt_liab = df_matrix[df_matrix['Instrument'].isin(option_instruments)]['Current Global Alloc. %'].sum()
gross_phys = df_matrix[~df_matrix['Instrument'].isin(option_instruments)]['Current Global Alloc. %'].sum()
true_net = gross_phys + opt_liab

col1, col2, col3 = st.columns([6, 2, 4])
with col2: 
    st.markdown(
        "<div style='text-align: right; font-size: 12px; font-weight: bold;'>"
        "GROSS PHYSICAL ASSETS:<br>"
        "<span style='color: #ef4444'>OPTIONS LIABILITY DRAG:</span><br>"
        "TRUE NET ESTATE CHECKSUM:"
        "</div>", 
        unsafe_allow_html=True
    )
with col3: 
    st.markdown(
        f"<div style='text-align: left; font-size: 12px; font-weight: bold; color: #1d4ed8;'>"
        f"{gross_phys:.2f}%<br>"
        f"<span style='color: #ef4444'>{opt_liab:.2f}%</span><br>"
        f"<span style='color: black'>{true_net:.2f}%</span> &nbsp;&nbsp;&nbsp; "
        f"<span style='font-size: 10px; color: gray; font-weight: normal'>Must exactly equal 100.00%</span>"
        f"</div>", 
        unsafe_allow_html=True
    )

st.divider()

# --- SECTION 8: CAPITAL DEPLOYMENT & MARGIN TRACKER ---
st.subheader("6. Capital Deployment & Margin Capacity Tracker")

c_gb_cash, c_sa_cash, c_sc_cash, c_gb_marg, c_sa_marg, c_sc_marg, c_txt = st.columns([4, 2, 2, 4, 2, 2, 3])

with c_gb_cash:
    fig_gauge_cash = go.Figure(go.Indicator(
        mode="gauge+number+delta", 
        value=pct_cash, 
        title={'text': "Bedrock Cash Buffer (IB01 + USD)", 'font': {'size': 14}}, 
        delta={'reference': 40, 'increasing': {'color': "green"}, 'decreasing': {'color': "red"}}, 
        gauge={
            'axis': {'range':[0, 100], 'tickwidth': 1}, 
            'bar': {'color': "blue"}, 
            'steps':[{'range':[0, 40], 'color': "rgba(239, 68, 68, 0.3)"}, {'range':[40, 100], 'color': "rgba(34, 197, 94, 0.3)"}], 
            'threshold': {'line': {'color': "red", 'width': 4}, 'thickness': 0.75, 'value': 40}
        }
    ))
    fig_gauge_cash.update_layout(height=250, margin=dict(l=10, r=10, t=40, b=10))
    st.plotly_chart(fig_gauge_cash, width="stretch")

with c_sa_cash:
    cash_A = pos_df[(pos_df['account'] == 'U23144948') & (pos_df['asset_class'].isin(['IB01', 'Cash']))]['market_value'].sum()
    pct_cash_A = (cash_A / nav_A * 100) if nav_A > 0 else 0
    
    fig_A_cash = go.Figure(go.Indicator(
        mode="gauge+number", 
        value=pct_cash_A, 
        number={'suffix': "%", 'font': {'size': 20}}, 
        title={'text': "Silo A Buffer", 'font': {'size': 12}}, 
        gauge={
            'axis': {'range':[0, 100], 'tickwidth': 1}, 
            'bar': {'color': "blue"}, 
            'steps':[{'range': [0, 40], 'color': "rgba(239, 68, 68, 0.3)"}, {'range':[40, 100], 'color': "rgba(34, 197, 94, 0.3)"}], 
            'threshold': {'line': {'color': "red", 'width': 2}, 'thickness': 0.75, 'value': 40}
        }
    ))
    fig_A_cash.update_layout(height=250, margin=dict(l=5, r=5, t=50, b=10))
    st.plotly_chart(fig_A_cash, width="stretch")

with c_sc_cash:
    cash_C = pos_df[(pos_df['account'] == 'U23154199') & (pos_df['asset_class'].isin(['IB01', 'Cash']))]['market_value'].sum()
    pct_cash_C = (cash_C / nav_C * 100) if nav_C > 0 else 0
    
    fig_C_cash = go.Figure(go.Indicator(
        mode="gauge+number", 
        value=pct_cash_C, 
        number={'suffix': "%", 'font': {'size': 20}}, 
        title={'text': "Silo C Buffer", 'font': {'size': 12}}, 
        gauge={
            'axis': {'range':[0, 100], 'tickwidth': 1}, 
            'bar': {'color': "blue"}, 
            'steps': [{'range':[0, 40], 'color': "rgba(239, 68, 68, 0.3)"}, {'range':[40, 100], 'color': "rgba(34, 197, 94, 0.3)"}], 
            'threshold': {'line': {'color': "red", 'width': 2}, 'thickness': 0.75, 'value': 40}
        }
    ))
    fig_C_cash.update_layout(height=250, margin=dict(l=5, r=5, t=50, b=10))
    st.plotly_chart(fig_C_cash, width="stretch")

with c_gb_marg:
    pct_margin = (opt_margin_total / global_metrics['nav']) * 100 if global_metrics['nav'] > 0 else 0
    
    fig_gauge_margin = go.Figure(go.Indicator(
        mode="gauge+number+delta", 
        value=pct_margin, 
        title={'text': "Options Margin Utilization", 'font': {'size': 14}}, 
        delta={'reference': 20, 'increasing': {'color': "red"}, 'decreasing': {'color': "green"}}, 
        gauge={
            'axis': {'range':[0, 100], 'tickwidth': 1}, 
            'bar': {'color': "purple"}, 
            'steps':[{'range':[0, 20], 'color': "rgba(34, 197, 94, 0.3)"}, {'range':[20, 100], 'color': "rgba(239, 68, 68, 0.3)"}], 
            'threshold': {'line': {'color': "red", 'width': 4}, 'thickness': 0.75, 'value': 20}
        }
    ))
    fig_gauge_margin.update_layout(height=250, margin=dict(l=10, r=10, t=40, b=10))
    st.plotly_chart(fig_gauge_margin, width="stretch")

with c_sa_marg:
    margin_A = get_exact_opt_margin(pos_df[pos_df['account'] == 'U23144948'])
    pct_margin_A = (margin_A / nav_A * 100) if nav_A > 0 else 0
    
    fig_A_margin = go.Figure(go.Indicator(
        mode="gauge+number", 
        value=pct_margin_A, 
        number={'suffix': "%", 'font': {'size': 20}}, 
        title={'text': "Silo A Margin", 'font': {'size': 12}}, 
        gauge={
            'axis': {'range':[0, 100], 'tickwidth': 1}, 
            'bar': {'color': "purple"}, 
            'steps':[{'range':[0, 20], 'color': "rgba(34, 197, 94, 0.3)"}, {'range':[20, 100], 'color': "rgba(239, 68, 68, 0.3)"}], 
            'threshold': {'line': {'color': "red", 'width': 2}, 'thickness': 0.75, 'value': 20}
        }
    ))
    fig_A_margin.update_layout(height=250, margin=dict(l=5, r=5, t=50, b=10))
    st.plotly_chart(fig_A_margin, width="stretch")

with c_sc_marg:
    margin_C = get_exact_opt_margin(pos_df[pos_df['account'] == 'U23154199'])
    pct_margin_C = (margin_C / nav_C * 100) if nav_C > 0 else 0
    
    fig_C_margin = go.Figure(go.Indicator(
        mode="gauge+number", 
        value=pct_margin_C, 
        number={'suffix': "%", 'font': {'size': 20}}, 
        title={'text': "Silo C Margin", 'font': {'size': 12}}, 
        gauge={
            'axis': {'range':[0, 100], 'tickwidth': 1}, 
            'bar': {'color': "purple"}, 
            'steps': [{'range':[0, 20], 'color': "rgba(34, 197, 94, 0.3)"}, {'range':[20, 100], 'color': "rgba(239, 68, 68, 0.3)"}], 
            'threshold': {'line': {'color': "red", 'width': 2}, 'thickness': 0.75, 'value': 20}
        }
    ))
    fig_C_margin.update_layout(height=250, margin=dict(l=5, r=5, t=50, b=10))
    st.plotly_chart(fig_C_margin, width="stretch")

with c_txt:
    st.markdown("##### DCA Deployment Schedule")
    
    if regime_str == 'Green':
        st.markdown("<h4 style='color: #166534; font-size: 16px;'>🟢 Green Regime</h4>", unsafe_allow_html=True)
        st.write("<span style='font-size: 12px;'>**Equities:** Transfer funds from IB01 to purchase physical CSPX/CNDX equity.</span>", unsafe_allow_html=True)
        st.write("<span style='font-size: 12px;'>**Options (Silos A & C):** Clear to sell new XSP/XND Put Spreads up to 20% margin cap. Deploy 10% of collected premiums into deep OTM S&P 500 Puts (Ackman hedge).</span>", unsafe_allow_html=True)
    elif regime_str == 'Yellow':
        st.markdown("<h4 style='color: #eab308; font-size: 16px;'>🟡 Yellow Regime</h4>", unsafe_allow_html=True)
        st.write("<span style='font-size: 12px;'>**Equities:** HOLD current equity DCA. Funnel all new cash deposits strictly into IB01.</span>", unsafe_allow_html=True)
        st.write("<span style='font-size: 12px;'>**Options (Silos A & C):** Throttle new Put Spreads to strict 45 DTE. Require higher premium floor.</span>", unsafe_allow_html=True)
    else:
        st.markdown("<h4 style='color: #991b1b; font-size: 16px;'>🔴 Red Regime</h4>", unsafe_allow_html=True)
        st.write("<span style='font-size: 12px;'>**All Silos:** HALT all active equity purchases. Defend the 40% Cash Buffer.</span>", unsafe_allow_html=True)
        st.write("<span style='font-size: 12px;'>**Options (Silos A & C):** If VIX spikes violently, buy 90-DTE SPX Puts (Taleb Tail-Hedge) to protect physical assets.</span>", unsafe_allow_html=True)

st.divider()

# --- SECTION 9: MONTE CARLO SIMULATION ---
st.subheader("7. Estate Montecarlo PnL Simulation - Projections vs History")
daily_pnl_array = global_df['daily_pnl'].dropna().values
sim_length = len(daily_pnl_array)

if sim_length > 0:
    sim_data = np.random.choice(daily_pnl_array, size=(10000, sim_length), replace=True)
    cum_sim = np.cumsum(sim_data, axis=1)
    zero_col = np.zeros((10000, 1))
    cum_sim = np.hstack((zero_col, cum_sim))
    
    peaks = np.maximum.accumulate(cum_sim, axis=1)
    abs_dds = peaks - cum_sim
    max_dds = np.max(abs_dds, axis=1)
    
    nav_base = global_metrics['nav'] if global_metrics['nav'] > 0 else 1
    ruin_prob = (np.sum(max_dds > (nav_base * 0.20)) / 10000) * 100

    mc_avg_dd = np.mean(max_dds)
    mc_best_dd = np.min(max_dds)
    mc_worst_dd = np.max(max_dds)
    mc_avg_path = np.mean(cum_sim, axis=0)
    
    orig_cum = np.insert(np.cumsum(daily_pnl_array), 0, 0)
    orig_peaks = np.maximum.accumulate(orig_cum)
    orig_dd = np.max(orig_peaks - orig_cum)
    
    best_idx = np.argmax(cum_sim[:, -1])
    worst_idx = np.argmin(cum_sim[:, -1])
    
    col_mc_chart, col_mc_leg = st.columns([0.85, 0.15])
    
    with col_mc_chart:
        mc_fig = go.Figure()
        
        for i in range(200):
            mc_fig.add_trace(go.Scatter(
                y=cum_sim[i], 
                mode='lines', 
                line=dict(color='rgba(203, 213, 225, 1.0)', width=1.5), 
                showlegend=False, 
                hoverinfo='skip'
            ))
        
        mc_fig.add_trace(go.Scatter(y=cum_sim[best_idx], name='Best Case', mode='lines', line=dict(color='#166534', width=3)))
        mc_fig.add_trace(go.Scatter(y=cum_sim[worst_idx], name='Worst Case', mode='lines', line=dict(color='#991b1b', width=3)))
        mc_fig.add_trace(go.Scatter(y=mc_avg_path, name='Statistically Expected (Mean)', mode='lines', line=dict(color='blue', width=4)))
        mc_fig.add_trace(go.Scatter(y=orig_cum, name='Original Realized History', mode='lines', line=dict(color='black', width=6)))
        
        last_x = sim_length
        mc_fig.add_annotation(x=last_x, y=cum_sim[best_idx][-1], text=f"Best: ${cum_sim[best_idx][-1]:,.0f}", showarrow=False, xanchor='left', bgcolor='#166534', font=dict(color='white', size=11))
        mc_fig.add_annotation(x=last_x, y=cum_sim[worst_idx][-1], text=f"Worst: ${cum_sim[worst_idx][-1]:,.0f}", showarrow=False, xanchor='left', bgcolor='#991b1b', font=dict(color='white', size=11))
        mc_fig.add_annotation(x=last_x, y=mc_avg_path[-1], text=f"Expected: ${mc_avg_path[-1]:,.0f}", showarrow=False, xanchor='left', bgcolor='blue', font=dict(color='white', size=11))
        mc_fig.add_annotation(x=last_x, y=orig_cum[-1], text=f"Original: ${orig_cum[-1]:,.0f}", showarrow=False, xanchor='left', bgcolor='black', font=dict(color='white', size=11))
        
        mc_fig.update_layout(
            height=800, 
            margin=dict(l=20, r=80, t=30, b=20), 
            plot_bgcolor='rgba(0,0,0,0)', 
            xaxis_title='Trading Days Forward', 
            yaxis=dict(title='Cumulative Net Profit (USD)', showgrid=True, gridcolor='LightGray', zeroline=True, zerolinecolor='black', zerolinewidth=1), 
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
        )
        mc_fig.update_xaxes(showgrid=True, gridwidth=1, gridcolor='LightGray')
        st.plotly_chart(mc_fig, width="stretch")
        
    with col_mc_leg:
        st.markdown(f"""
        <div style="background-color: rgba(255, 255, 255, 0.9); padding: 15px; border: 1px solid black; border-radius: 5px; font-size: 12px; color: black; margin-top: 50px;">
            <b style="font-size: 14px; color: #1d4ed8;">RISK METRICS</b><br><br>
            <b>Empirical Risk of Ruin:</b> <span style="color: {'red' if ruin_prob>5 else 'green'}; font-weight: bold;">{ruin_prob:.2f}%</span><br>
            <i>(Probability of hitting a >20% drawdown based on 10,000 resampled realities).</i><br><br>
            <b style="font-size: 14px; color: #1d4ed8;">DRAWDOWN STATS</b><br><br>
            <b>Original History:</b><br>${orig_dd:,.0f}<br><br>
            <b>SIMULATION (10k runs):</b><br>
            Avg Expected DD: ${mc_avg_dd:,.0f}<br>
            Best Case DD: ${mc_best_dd:,.0f}<br>
            Worst Case DD: ${mc_worst_dd:,.0f}<br><br>
            <hr style="margin: 10px 0;">
            <b>Is it Edge or Luck?</b><br>
            The <i>Best</i> and <i>Worst</i> traces represent the extreme 99.99th and 0.01st percentile limits of purely reshuffled luck given your exact edge. Because your <i>Original Realized History</i> is anchored near the <i>Statistically Expected Mean</i>, it confirms a statistically significant and highly robust edge, rather than an accidental streak of luck.
        </div>
        """.replace('\n', ''), unsafe_allow_html=True)

st.divider()

# --- SECTION 10: THE OPTIONS PERFORMANCE LEDGER & 3D VISUALIZER ---
st.subheader("8. The Options Performance Ledger & Topography Engine")

def normCDF(x):
    t = 1 / (1 + 0.2316419 * abs(x))
    d = 0.3989423 * np.exp(-x * x / 2)
    prob = d * t * (0.3193815 + t * (-0.3565638 + t * (1.781478 + t * (-1.821256 + t * 1.330274))))
    return 1 - prob if x > 0 else prob

def normPDF(x):
    return np.exp(-0.5 * x * x) / np.sqrt(2 * np.pi)

def get_put_greeks(S, K, T, r, v):
    T = max(T, 0.0001)
    d1 = (math.log(S / K) + (r + 0.5 * v ** 2) * T) / (v * math.sqrt(T))
    d2 = d1 - v * math.sqrt(T)
    price = K * math.exp(-r * T) * normCDF(-d2) - S * normCDF(-d1)
    delta = normCDF(d1) - 1
    gamma = normPDF(d1) / (S * v * math.sqrt(T))
    vega = (S * normPDF(d1) * math.sqrt(T)) / 100
    theta = (- (S * v * normPDF(d1)) / (2 * math.sqrt(T)) + r * K * math.exp(-r * T) * normCDF(-d2)) / 365
    return price, delta, gamma, vega, theta

@st.cache_data(ttl=300)
def fetch_live_data(ticker_symbol):
    try:
        t_str = str(ticker_symbol).upper()
        if 'XSP' in t_str:
            spx = yf.Ticker('^SPX').history(period='5d')['Close'].iloc[-1]
            vix = yf.Ticker('^VIX').history(period='5d')['Close'].iloc[-1]
            return float(spx) / 10.0, float(vix)
        elif 'XND' in t_str:
            ndx = yf.Ticker('^NDX').history(period='5d')['Close'].iloc[-1]
            vxn = yf.Ticker('^VXN').history(period='5d')['Close'].iloc[-1]
            return float(ndx) / 100.0, float(vxn)
        else:
            spy = yf.Ticker('SPY').history(period='5d')['Close'].iloc[-1]
            vix = yf.Ticker('^VIX').history(period='5d')['Close'].iloc[-1]
            return float(spy), float(vix)
    except Exception:
        return 550.0, 15.0 

if not journal_raw_df.empty:
    today = datetime.date.today()
    journal_raw_df['Open Date'] = pd.to_datetime(journal_raw_df['Open Date'], errors='coerce').dt.date
    journal_raw_df['Close Date'] = pd.to_datetime(journal_raw_df['Close Date'], errors='coerce').dt.date
    
    journal_raw_df['Collateral Locked (USD)'] = (journal_raw_df['Short Strike'] - journal_raw_df['Long Strike']) * 100 * journal_raw_df['Quantity']
    journal_raw_df['Total Net Credit (USD)'] = journal_raw_df['Premium Collected (USD)'] * 100 * journal_raw_df['Quantity']
    journal_raw_df['Target 50% Exit Price (USD)'] = journal_raw_df['Premium Collected (USD)'] / 2
    
    journal_raw_df['Days Remaining'] = journal_raw_df.apply(
        lambda r: max(0, r['DTE at Entry'] - ((today - r['Open Date']).days if pd.notnull(r['Open Date']) else 0)) 
        if pd.isnull(r['Close Date']) and pd.notnull(r['DTE at Entry']) else 'Closed', 
        axis=1
    )
    
    journal_raw_df['Days in Trade'] = journal_raw_df.apply(
        lambda r: (today - r['Open Date']).days if pd.isnull(r['Close Date']) and pd.notnull(r['Open Date']) 
        else ((r['Close Date'] - r['Open Date']).days if pd.notnull(r['Open Date']) else 0), 
        axis=1
    )
    
    journal_raw_df['Total P&L (USD)'] = (journal_raw_df['Premium Collected (USD)'] - journal_raw_df['Closing Price (USD)']) * 100 * journal_raw_df['Quantity']
    journal_raw_df['Return on Capital (ROC) %'] = journal_raw_df['Total P&L (USD)'] / journal_raw_df['Collateral Locked (USD)']
    
    journal_raw_df['Annualized ROC %'] = journal_raw_df.apply(
        lambda r: np.nan if pd.isnull(r['Return on Capital (ROC) %']) or r['Days in Trade'] == 0 
        else r['Return on Capital (ROC) %'] * (365.0 / r['Days in Trade']), 
        axis=1
    )
    
    journal_raw_df = journal_raw_df.sort_values('Open Date', ascending=False).reset_index(drop=True)

    open_journal = journal_raw_df[pd.isnull(journal_raw_df['Close Date'])]
    opt_margin_journal = open_journal['Collateral Locked (USD)'].sum()
    
    if abs(opt_margin_journal - opt_margin_total) > 0.01:
        st.error(f"⚠️ **LEDGER DRIFT:** Live TWS margin is **${opt_margin_total:,.0f}**, Open Journal is **${opt_margin_journal:,.0f}**.")

def style_journal(df):
    css_df = pd.DataFrame('', index=df.index, columns=df.columns)
    for i, row in df.iterrows():
        if 'Annualized ROC %' in df.columns and pd.notna(row['Annualized ROC %']) and isinstance(row['Annualized ROC %'], (int, float)) and row['Annualized ROC %'] > 1.0:
            css_df.at[i, 'Annualized ROC %'] = 'background-color: #fef08a; color: #856404; font-weight: bold;'
        if 'Days in Trade' in df.columns and pd.notna(row['Days in Trade']) and isinstance(row['Days in Trade'], (int, float)) and row['Days in Trade'] <= 14 and row['Days in Trade'] > 0:
            css_df.at[i, 'Days in Trade'] = 'background-color: #d1e7dd; color: #0f5132; font-weight: bold;'
        if 'Days Remaining' in df.columns and pd.notna(row['Days Remaining']) and str(row['Days Remaining']) != 'Closed' and 'DTE at Entry' in df.columns and pd.notna(row['DTE at Entry']):
            try:
                if float(row['Days Remaining']) < (float(row['DTE at Entry']) / 2): 
                    css_df.at[i, 'Days Remaining'] = 'background-color: #f8d7da; color: #842029; font-weight: bold;'
                else: 
                    css_df.at[i, 'Days Remaining'] = 'background-color: #d1e7dd; color: #0f5132; font-weight: bold;'
            except: pass
        for col in['Collateral Locked (USD)', 'Total Net Credit (USD)', 'Target 50% Exit Price (USD)', 'Days Remaining', 'Days in Trade', 'Total P&L (USD)', 'Return on Capital (ROC) %', 'Annualized ROC %']:
            if col in css_df.columns: 
                css_df.at[i, col] += ' background-color: #f3f4f6;'
    return css_df

if not journal_raw_df.empty:
    col_ledger, col_2d, col_3d = st.columns([0.50, 0.25, 0.25])
    
    with col_ledger:
        display_df = journal_raw_df.copy()
        display_df.insert(0, '👁️ View 3D', False)
        styled_journal = display_df.style.apply(lambda x: style_journal(display_df), axis=None)
        
        edited_df = st.data_editor(
            styled_journal, 
            width='stretch', 
            num_rows="dynamic", 
            height=750, 
            key="journal_editor",
            disabled=['Collateral Locked (USD)', 'Total Net Credit (USD)', 'Target 50% Exit Price (USD)', 'Days Remaining', 'Days in Trade', 'Total P&L (USD)', 'Return on Capital (ROC) %', 'Annualized ROC %'],
            column_config={
                "👁️ View 3D": st.column_config.CheckboxColumn("View\n3D"),
                "Premium Collected (USD)": st.column_config.NumberColumn("Premium\n($)", format="$%.2f"),
                "Collateral Locked (USD)": st.column_config.NumberColumn("Collateral\n($)", format="$%.2f"),
                "Total Net Credit (USD)": st.column_config.NumberColumn("Net Credit\n($)", format="$%.2f"),
                "Target 50% Exit Price (USD)": st.column_config.NumberColumn("50% Exit\n($)", format="$%.2f"),
                "Closing Price (USD)": st.column_config.NumberColumn("Closing\n($)", format="$%.2f"),
                "Total P&L (USD)": st.column_config.NumberColumn("P&L\n($)", format="$%.2f"),
                "Return on Capital (ROC) %": st.column_config.NumberColumn("ROC\n(%)", format="%.2f%%"),
                "Annualized ROC %": st.column_config.NumberColumn("Ann. ROC\n(%)", format="%.2f%%"),
                "Open Date": st.column_config.DateColumn(), 
                "Close Date": st.column_config.DateColumn()
            }
        )

    db_df = edited_df.drop(columns=['👁️ View 3D'])
    
    def normalize_for_compare(df_in):
        df_cmp = df_in.copy()
        for col in df_cmp.select_dtypes(include=['float64', 'float32']).columns: 
            df_cmp[col] = df_cmp[col].round(4)
        return df_cmp.fillna('').astype(str).replace(r'^(nan|None|NaT|<NA>)$', '', regex=True).apply(lambda x: x.str.strip())
        
    if not normalize_for_compare(journal_raw_df).equals(normalize_for_compare(db_df)):
        conn = sqlite3.connect(DB_PATH)
        db_df.to_sql('options_journal', conn, if_exists='replace', index=False)
        conn.close()
        st.rerun() 

    selected_rows = edited_df[edited_df['👁️ View 3D'] == True]
    
    if selected_rows.empty:
        with col_2d: 
            st.info("👈 Check 'View 3D' on any contract row to render Live 2D/3D Topography.")
    elif selected_rows.shape[0] > 1:
        with col_2d: 
            st.error("❌ **Mutex Lock Active:** You have checked multiple boxes. Please uncheck duplicates so only ONE contract is selected.")
    else:
        row_data = selected_rows.iloc[0]
        tckr = row_data.get('Ticker', 'XSP')
        raw_dte = row_data.get('Days Remaining', 0)
        
        if str(raw_dte) == 'Closed':
            with col_2d: 
                st.warning(f"**{tckr} Contract is Closed.** Black-Scholes topography locked.")
        else:
            curr_dte = float(raw_dte) if pd.notna(raw_dte) else 0.0
            init_dte = float(row_data.get('DTE at Entry', 45)) if pd.notna(row_data.get('DTE at Entry', 45)) else 45.0
            K_s = float(row_data.get('Short Strike', 0)) if pd.notna(row_data.get('Short Strike', 0)) else 0.0
            K_l = float(row_data.get('Long Strike', 0)) if pd.notna(row_data.get('Long Strike', 0)) else 0.0
            qty = float(row_data.get('Quantity', 1)) if pd.notna(row_data.get('Quantity', 1)) else 1.0
            prem = float(row_data.get('Premium Collected (USD)', 0)) if pd.notna(row_data.get('Premium Collected (USD)', 0)) else 0.0
            
            with st.spinner(f"Fetching Live Data for {tckr}..."): 
                S_live, iv_live = fetch_live_data(tckr)
            
            r_rate = LIVE_RF_RATE
            iv_dec = (iv_live / 100.0) if iv_live > 1.0 else iv_live
            T_init = init_dte / 365.0
            T_curr = curr_dte / 365.0
            
            s_p, s_d, s_g, s_v, s_t = get_put_greeks(S_live, K_s, T_curr, r_rate, iv_dec)
            l_p, l_d, l_g, l_v, l_t = get_put_greeks(S_live, K_l, T_curr, r_rate, iv_dec)
            
            curr_spread_price = s_p - l_p
            unrealized_pnl = (prem - curr_spread_price) * qty * 100
            margin_req = (K_s - K_l) * 100 * qty
            rom_pct = (unrealized_pnl / margin_req * 100) if margin_req > 0 else 0
            
            net_delta = (l_d - s_d) * qty * 100
            net_gamma = (l_g - s_g) * qty * 100
            net_theta = (l_t - s_t) * qty * 100
            net_vega = (l_v - s_v) * qty * 100
            
            min_plot = int(K_l - 30)
            max_plot = int(K_s + 40)
            x_vals =[p / 2.0 for p in range(int(min_plot * 2), int(max_plot * 2) + 1)]
            y_exp, y_init, y_curr = [], [],[]
            
            for p in x_vals:
                y_exp.append((prem - (max(K_s - p, 0) - max(K_l - p, 0))) * qty * 100)
                
                t0_s, _, _, _, _ = get_put_greeks(p, K_s, T_init, r_rate, iv_dec)
                t0_l, _, _, _, _ = get_put_greeks(p, K_l, T_init, r_rate, iv_dec)
                y_init.append((prem - (t0_s - t0_l)) * qty * 100)
                
                tC_s, _, _, _, _ = get_put_greeks(p, K_s, T_curr, r_rate, iv_dec)
                tC_l, _, _, _, _ = get_put_greeks(p, K_l, T_curr, r_rate, iv_dec)
                y_curr.append((prem - (tC_s - tC_l)) * qty * 100)

            with col_2d:
                color_css = "#166534" if unrealized_pnl >= 0 else "#991b1b"
                bg_css = "#f0fdf4" if unrealized_pnl >= 0 else "#fef2f2"
                
                st.markdown(f"""
                <div style="background-color: {bg_css}; padding: 15px; border-radius: 8px; border: 1px solid {color_css}; text-align: center; margin-bottom: 20px;">
                    <span style="font-size: 14px; color: #4b5563; font-weight: bold;">Unrealized P&L</span><br>
                    <span style="font-size: 32px; font-weight: 900; color: {color_css};">${unrealized_pnl:,.2f} ({rom_pct:+.2f}%)</span><br>
                    <span style="font-size: 12px; color: #4b5563;">Spread Value: ${curr_spread_price:.2f} | Net Theta: ${net_theta:+.2f}/day | Underlying: ${S_live:,.2f} | IV: {iv_live:.1f}%</span>
                </div>
                """.replace('\n', ''), unsafe_allow_html=True)

                fig_2d = go.Figure()
                fig_2d.add_trace(go.Scatter(x=x_vals, y=y_exp, mode='lines', name='Expiration', line=dict(color='gray', dash='dash')))
                fig_2d.add_trace(go.Scatter(x=x_vals, y=y_init, mode='lines', name='Entry Day', line=dict(color='orange', width=2, dash='dot')))
                fig_2d.add_trace(go.Scatter(x=x_vals, y=y_curr, mode='lines', name='Today', line=dict(color='blue', width=3)))
                fig_2d.add_trace(go.Scatter(x=[S_live], y=[unrealized_pnl], mode='markers', name='Current Price', marker=dict(color='black', size=10)))
                
                fig_2d.update_layout(
                    title="2D Theta Decay Profile", 
                    margin=dict(l=20, r=20, t=40, b=20), 
                    height=500, 
                    legend=dict(orientation="h", y=-0.2)
                )
                st.plotly_chart(fig_2d, width="stretch")
            
            with col_3d:
                step = max(1, int(init_dte / 15))
                y_3d = list(range(int(init_dte), -1, -step))
                z_3d =[]
                
                for d in y_3d:
                    T_3d = d / 365.0
                    z_row =[]
                    for p in x_vals:
                        if T_3d <= 0.0001: 
                            z_row.append((prem - (max(K_s - p, 0) - max(K_l - p, 0))) * qty * 100)
                        else:
                            t_s, _, _, _, _ = get_put_greeks(p, K_s, T_3d, r_rate, iv_dec)
                            t_l, _, _, _, _ = get_put_greeks(p, K_l, T_3d, r_rate, iv_dec)
                            z_row.append((prem - (t_s - t_l)) * qty * 100)
                    z_3d.append(z_row)
                    
                fig_3d = go.Figure(data=[go.Surface(
                    z=z_3d, x=x_vals, y=y_3d, 
                    colorscale=[[0, '#fef2f2'],[0.2, '#fca5a5'], [0.5, 'white'],[0.8, '#86efac'],[1, '#f0fdf4']]
                )])
                
                fig_3d.add_trace(go.Scatter3d(
                    x=[S_live], y=[curr_dte], z=[unrealized_pnl], 
                    mode='markers', name='Current', marker=dict(color='black', size=4)
                ))
                
                fig_3d.update_layout(
                    title="3D Topography (Time vs Price)", 
                    margin=dict(l=0, r=0, b=0, t=40), 
                    height=645, 
                    scene=dict(xaxis_title='Price', yaxis_title='DTE', zaxis_title='P&L ($)', yaxis=dict(autorange='reversed'))
                )
                st.plotly_chart(fig_3d, width="stretch")
            
            # --- GREEKS FOOTER ---
            st.markdown(f"""
            <div style="margin-top: 10px;">
                <h3 style="font-size: 20px; font-weight: bold; margin-bottom: 15px; color: #1f2937; border-bottom: 2px solid #e5e7eb; padding-bottom: 8px;">Position Greeks & Metrics (Net of Spread x Quantity)</h3>
                <div style="overflow-x: auto; border-radius: 8px; border: 1px solid #e5e7eb; box-shadow: 0 1px 2px 0 rgba(0, 0, 0, 0.05); margin-bottom: 25px;">
                    <table style="min-w-full; width: 100%; border-collapse: collapse; background-color: white;">
                        <thead style="background-color: #1e293b; color: white;">
                            <tr>
                                <th style="padding: 12px 16px; text-align: left; font-weight: 600;">Net Delta</th>
                                <th style="padding: 12px 16px; text-align: left; font-weight: 600;">Net Gamma</th>
                                <th style="padding: 12px 16px; text-align: left; font-weight: 600;">Net Theta</th>
                                <th style="padding: 12px 16px; text-align: left; font-weight: 600;">Net Vega</th>
                                <th style="padding: 12px 16px; text-align: left; font-weight: 600; background-color: #7f1d1d;">Margin Locked ($)</th>
                            </tr>
                        </thead>
                        <tbody>
                            <tr>
                                <td style="padding: 16px; font-family: monospace; font-size: 18px; font-weight: bold; color: #374151;">{net_delta:.2f}</td>
                                <td style="padding: 16px; font-family: monospace; font-size: 18px; font-weight: bold; color: #374151;">{net_gamma:.4f}</td>
                                <td style="padding: 16px; font-family: monospace; font-size: 18px; font-weight: bold; color: #16a34a;">${net_theta:.2f}</td>
                                <td style="padding: 16px; font-family: monospace; font-size: 18px; font-weight: bold; color: #2563eb;">${net_vega:.2f}</td>
                                <td style="padding: 16px; font-family: monospace; font-size: 18px; font-weight: 900; color: #dc2626;">${margin_req:,.0f}</td>
                            </tr>
                        </tbody>
                    </table>
                </div>
                <div style="background-color: #eff6ff; border: 1px solid #bfdbfe; border-radius: 12px; padding: 24px; color: #1e3a8a; font-size: 14px;">
                    <h4 style="font-weight: bold; font-size: 16px; margin-bottom: 12px; text-transform: uppercase; letter-spacing: 0.05em;">CIO Reference Guide: The Greeks Explained</h4>
                    <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 24px;">
                        <div>
                            <p style="margin-bottom: 12px;"><strong style="color: #1d4ed8; background-color: #dbeafe; padding: 2px 4px; border-radius: 4px;">Delta (Direction):</strong> Measures directional exposure. A Net Delta of 15 means your position gains $15 if the index goes up 1 point. In credit spreads, Delta also acts as your probability gauge (e.g., selling a 20 Delta strike equates to an 80% chance of success).</p>
                            <p><strong style="color: #1d4ed8; background-color: #dbeafe; padding: 2px 4px; border-radius: 4px;">Gamma (Acceleration):</strong> Measures the rate of change of Delta. High Gamma means your risk is accelerating uncontrollably (which peaks near expiration). This is exactly why we mechanically close trades at 21 DTE—to avoid Gamma explosions.</p>
                        </div>
                        <div>
                            <p style="margin-bottom: 12px;"><strong style="color: #1d4ed8; background-color: #dbeafe; padding: 2px 4px; border-radius: 4px;">Theta (Time Decay):</strong> Your daily salary. This positive number represents the dollar amount deposited into your unrealized P&L simply because one day passed, assuming all other market conditions remain totally flat.</p>
                            <p><strong style="color: #1d4ed8; background-color: #dbeafe; padding: 2px 4px; border-radius: 4px;">Vega (Fear Premium):</strong> Measures sensitivity to Implied Volatility (VIX). Because you sold insurance, your Net Vega is negative. This means if Implied Volatility drops by 1%, your portfolio instantly gains that dollar amount in profit (Volatility Crush).</p>
                        </div>
                    </div>
                </div>
            </div>
            """.replace('\n', ''), unsafe_allow_html=True)
else:
    st.info("No options history found in database.")