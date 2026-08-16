"""
=============================================================================
Script Name: dashboard_v13.py
Purpose: The Streamlit Frontend (Module 13 - The Master Ledger).
         - Integrated the Live Options Performance Ledger (Panel 8).
         - Active Drift Detector (Ledger vs. Broker Checksum).
         - Interactive SQLite Data Editor with Excel-style conditional formatting.
         - Mathematical firewall: Calculated columns are strictly Python-enforced.
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
    'Opt Liab': '#ef4444'
}

# --- SIDEBAR: SYNC BUTTON ---
with st.sidebar:
    st.markdown("### ⚙️ Engine Control")
    if st.button("⟳ Sync Live from TWS", use_container_width=True):
        with st.spinner("Connecting to TWS... Please wait (~15s)"):
            try:
                # Runs the sync engine in the background
                subprocess.run(["python", SYNC_SCRIPT], check=True)
                st.success("Sync Complete!")
                st.cache_data.clear() # Clears cache to force data reload
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

def process_metrics(df_acc):
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
    data = yf.download(["SPY", "QQQ", "^VIX"], start=start_date - datetime.timedelta(days=40), end=end_date + datetime.timedelta(days=1), progress=False, auto_adjust=False)
    close_data = data['Close'].ffill()
    bench_df = close_data.reset_index()
    bench_df.rename(columns={'Date': 'date'}, inplace=True)
    bench_df['date'] = pd.to_datetime(bench_df['date']).dt.tz_localize(None)
    
    bench_df['sma_10'] = bench_df['SPY'].rolling(window=10).mean()
    bench_df['sma_20'] = bench_df['SPY'].rolling(window=20).mean()
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

# --- UN-CACHED DYNAMIC JOURNAL LOAD ---
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
st.markdown(f"**Script version:** `dashboard_v13.py`")
st.divider()

global_df, global_metrics, silo_dfs, silo_metrics, pos_df, attr_df = load_and_process_data()
bench_df = load_benchmarks(global_df['date'].min(), global_df['date'].max())
chart_df = pd.merge(global_df, bench_df, on='date', how='left').ffill().fillna(0)
journal_raw_df = load_journal_data()

# RISK ALERTS LOGIC
tot_cash = pos_df[pos_df['asset_class'].isin(['IB01', 'Cash'])]['market_value'].sum()
tot_tech = pos_df[pos_df['asset_class'].isin(['CNDX', 'ITWN', 'CSKR', 'Active Swing'])]['market_value'].sum()
pct_cash = (tot_cash / global_metrics['nav']) * 100 if global_metrics['nav'] > 0 else 0
pct_tech = (tot_tech / global_metrics['nav']) * 100 if global_metrics['nav'] > 0 else 0

if pct_cash > 60:
    st.info(f"ℹ️ **CASH DRAG:** Unleveraged Cash/IB01 is {pct_cash:.1f}%. Consider deploying to Vaults if market is in uptrend.")
if pct_tech > 40:
    st.warning(f"⚠️ **SECTOR RADAR:** Tech/Semi concentration is {pct_tech:.1f}% (>40% safe threshold). Vulnerability to Nasdaq crash detected.")

est_ann_ret = chart_df['daily_return'].mean() * 252
rf = 0.045
def calc_adv(b_ret):
    ann = b_ret.mean() * 252
    std = b_ret.std() * np.sqrt(252)
    sharpe = (ann - rf) / std if std > 0 else 0
    cov = chart_df['daily_return'].cov(b_ret)
    var = b_ret.var()
    beta = cov / var if var > 0 else 0
    alpha = est_ann_ret - (rf + beta * (ann - rf))
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

html_metrics = f"""
<div style="background-color: #f3f4f6; padding: 20px; border-radius: 12px; border: 1px solid #e5e7eb; margin-bottom: 20px;">
    <h4 style="text-align: center; color: #1f2937; margin-bottom: 15px; text-transform: uppercase; letter-spacing: 2px;">Master Estate Aggregation</h4>
    <div style="display: grid; grid-template-columns: repeat(7, 1fr); gap: 10px; text-align: center; font-family: monospace; font-size: 14px;">
        <div>Static Balance<br><span style="color: #1d4ed8; font-weight: 900; font-size: 18px;">${global_metrics['nav']:,.0f}</span></div>
        <div>IRR<br><span style="{col_html(global_metrics['irr'])} font-weight: 900; font-size: 18px;">{global_metrics['irr']:.2f}%</span></div>
        <div>Global P&L<br><span style="{col_html(global_metrics['pnl'])} font-weight: 900; font-size: 18px;">${global_metrics['pnl']:,.0f}</span></div>
        <div>Global Sharpe<br><span style="{col_html(global_metrics['sharpe'])} font-weight: 900; font-size: 18px;">{global_metrics['sharpe']:.2f}</span></div>
        <div>SPY Sharpe<br><b>{spy_sh:.2f}</b></div>
        <div>QQQ Sharpe<br><b>{qqq_sh:.2f}</b></div>
        <div>Max DD<br><span style="color: #b91c1c; font-weight: 900; font-size: 18px;">{global_metrics['max_dd']:.2f}%</span></div>
        <div style="margin-top:15px;">DD Duration<br><span style="color: #1f2937; font-weight: 900; font-size: 18px;">{global_metrics['dd_days']} d</span></div>
        <div style="margin-top:15px;">Calmar<br><span style="color: #1f2937; font-weight: 900; font-size: 18px;">{calmar:.2f}</span></div>
        <div style="margin-top:15px;">Est. ROC%<br><span style="{col_html(global_metrics['roc'])} font-weight: 900; font-size: 18px;">{global_metrics['roc']:.2f}%</span></div>
        <div style="margin-top:15px;">SPY Alpha<br><span style="{col_html(spy_al)} font-weight: bold;">{spy_al:.2f}%</span></div>
        <div style="margin-top:15px;">SPY Corr.<br><span style="{col_html(spy_co, 0.3)} font-weight: bold;">{spy_co:.2f}</span></div>
        <div style="margin-top:15px;">QQQ Alpha<br><span style="{col_html(qqq_al)} font-weight: bold;">{qqq_al:.2f}%</span></div>
        <div style="margin-top:15px;">QQQ Corr.<br><span style="{col_html(qqq_co, 0.3)} font-weight: bold;">{qqq_co:.2f}</span></div>
    </div>
    <div style="margin-top: 20px; padding-top: 15px; border-top: 1px solid #d1d5db; text-align: center; font-family: monospace; font-size: 11px; color: #6b7280;">
        <span style="font-weight: bold; color: #374151; margin-right: 15px;">OPTIMAL RANGES:</span>
        <span style="margin-right: 15px;">IRR: >10%</span><span style="margin-right: 15px;">Sharpe: 1.0 to 2.0+</span><span style="margin-right: 15px;">Max DD: > -15%</span><span style="margin-right: 15px;">Calmar: > 1.0</span><span style="margin-right: 15px;">Alpha: > 0%</span><span>Corr: 0.30 to 0.60</span>
    </div>
</div>
"""
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
        
        if not silo_dfs[acc].empty:
            s_chart = pd.merge(silo_dfs[acc][['date', 'cum_return']], bench_df[['date', 'spy_cum', 'qqq_cum']], on='date', how='left').ffill().fillna(0)
            fig_mini = go.Figure()
            fig_mini.add_trace(go.Scatter(x=s_chart['date'], y=s_chart['cum_return']*100, mode='lines', line=dict(color='black', width=4), showlegend=False))
            fig_mini.add_trace(go.Scatter(x=s_chart['date'], y=s_chart['spy_cum']*100, mode='lines', line=dict(color='#3b82f6', width=2), showlegend=False))
            fig_mini.add_trace(go.Scatter(x=s_chart['date'], y=s_chart['qqq_cum']*100, mode='lines', line=dict(color='#dc2626', width=2), showlegend=False))
            
            fig_mini.update_layout(height=150, margin=dict(l=0, r=0, t=0, b=0), plot_bgcolor=color, paper_bgcolor='rgba(0,0,0,0)',
                                   yaxis=dict(zeroline=True, zerolinecolor='black', zerolinewidth=1))
            fig_mini.update_xaxes(visible=False); fig_mini.update_yaxes(showticklabels=False)
            st.plotly_chart(fig_mini, width='stretch')
        
        c1, c2 = st.columns(2)
        c1.write(f"**IRR:** {m['irr']:.2f}%")
        c2.write(f"**Sharpe:** {m['sharpe']:.2f}")
        c1.write(f"**P&L:** ${m['pnl']:,.0f}")
        c2.write(f"**Max DD:** {m['max_dd']:.2f}%")
        c1.write(f"**DD Days:** {m['dd_days']}")
        c2.write(f"**ROC:** {m['roc']:.2f}%")

st.divider()

# --- SECTION 3: ESTATE CAPITAL BREAKDOWN (GAAP & GROSS ASSETS) ---
st.subheader("1. Estate Capital Breakdown (GAAP & Gross Assets)")
col_bar, col_pie = st.columns(2)

if not pos_df.empty:
    bar_df = pos_df.groupby(['account', 'asset_class'])['market_value'].sum().unstack(fill_value=0)
    
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
            fig_bar.add_trace(go.Bar(name=l_label, x=silo_names, y=bar_df[asset], marker_color=COLOR_PALETTE.get(asset, '#cbd5e1')))
            
        opt_margin_A = (pos_df[(pos_df['account'] == 'U23144948') & (pos_df['sec_type'] == 'OPT')]['position'].abs().sum() / 2) * 2500
        opt_margin_C = (pos_df[(pos_df['account'] == 'U23154199') & (pos_df['sec_type'] == 'OPT')]['position'].abs().sum() / 2) * 2500
        
        tot_ml = opt_margin_A + opt_margin_C
        pct_ml = (tot_ml / global_metrics['nav']) * 100 if global_metrics['nav'] > 0 else 0
        ml_label = f"Margin Lock (${tot_ml:,.0f} | {pct_ml:.1f}%)"
        
        fig_bar.add_trace(go.Scatter(
            x=['Silo A', 'Silo C'], y=[opt_margin_A, opt_margin_C],
            name=ml_label, mode='markers',
            marker=dict(symbol='diamond', size=14, color='#ef4444', line=dict(width=1, color='black'))
        ))
        
        for i, total in enumerate(silo_totals):
            pct_total = (total / global_metrics['nav']) * 100 if global_metrics['nav'] > 0 else 0
            fig_bar.add_annotation(x=silo_names[i], y=total, text=f"<b>${total/1000:.0f}k</b><br>({pct_total:.1f}%)", showarrow=False, yanchor='bottom', yshift=5)
            
        fig_bar.update_layout(
            barmode='relative', title="GAAP Balance Sheet per Silo (USD)", plot_bgcolor='rgba(0,0,0,0)', 
            margin=dict(l=20, r=20, t=40, b=20), yaxis=dict(zeroline=True, zerolinecolor='black', zerolinewidth=1, gridcolor='LightGray'),
            legend_title_text="<b>ASSET CLASS</b>"
        )
        st.plotly_chart(fig_bar, width='stretch')

    with col_pie:
        fig_pie = go.Figure(data=[go.Pie(
            labels=pie_df['legend_label'], values=pie_df['market_value'], hole=.4, 
            marker=dict(colors=[COLOR_PALETTE.get(a, '#cbd5e1') for a in pie_df['asset_class']]),
            textinfo='percent'
        )])
        fig_pie.update_layout(title="Gross Asset Allocation", margin=dict(l=20, r=20, t=40, b=20), legend_title_text="<b>ASSET CLASS</b>")
        st.plotly_chart(fig_pie, width='stretch')

st.divider()

# --- SECTION 4: TARGET PORTFOLIO COMPOSITION ---
st.subheader("2. Live Portfolio Composition (from TWS)")
comp_cols = st.columns(4)

strats =[
    "<b>STRATEGY & EXECUTION:</b><br>No stop-losses on broad index ETFs as long as Global Cash/IB01 > 40%. The cash buffer naturally absorbs systemic shocks. DCA systematically every 2 weeks. Accelerate/Double the DCA amount during SPY pullbacks (Yellow/Red regimes).",
    "<b>STRATEGY & EXECUTION:</b><br><b>Regime Filter:</b> Green (3-5R TOR), Yellow (1-3R), Red (0-1R). <b>Entry:</b> 2-3 tranches on momentum. Initial Stop at Low of Day (LOD). <b>Management:</b> Move stop to breakeven at +1R profit. Scale out 30-50% on Day 3-5 (Afzal) and trail the runner with the 10/20 SMA.",
    "<b>STRATEGY & EXECUTION:</b><br>Adheres to Silo A's 40% cash buffer. Execute XSP/XND spreads weekly at 45-50 DTE near -0.20 Delta. Strict 8% premium floor. 50% GTC take-profit set instantly. Never manually close before 21 DTE to avoid Gamma risk.",
    "<b>STRATEGY & EXECUTION:</b><br>13F Themes (Druckenmiller, Ackman) executed via Sector UCITS ETFs to eliminate CFD financing drag. High-conviction social sentiment (Shay, Pelosi, UncleAlpha) executed via CFDs with strict 30-45 day time-stops to cap overnight fees. Ruthlessly cut losers."
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
            display_df.columns =['Asset', 'Value ($)', 'Alloc (%)']
            st.dataframe(display_df.style.format({'Value ($)': '{:,.0f}', 'Alloc (%)': '{:.1f}%'}), hide_index=True, height=(len(display_df) + 1) * 35 + 3, width='stretch')
        else: st.write("No active positions.")
        
        st.markdown(f"<div style='font-size: 11px; color: #4b5563; padding: 10px; border-top: 1px solid #e5e7eb; margin-top: 10px;'>{strats[idx]}</div>", unsafe_allow_html=True)

st.divider()

# --- SECTION 5: DAILY PNL HISTOGRAM ---
st.subheader("3. Daily PnL per Silo")
spy_usd_pnl =[]; qqq_usd_pnl =[]
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
        fig_pnl.add_trace(go.Bar(x=silo_dfs[acc]['date'], y=silo_dfs[acc]['daily_pnl'], name=name, marker_color=color))

fig_pnl.add_trace(go.Scatter(x=chart_df['date'], y=chart_df['cum_pnl'], name='Estate (Cum PnL USD)', mode='lines', line=dict(color='black', width=6), yaxis='y2'))
fig_pnl.add_trace(go.Scatter(x=chart_df['date'], y=chart_df['spy_usd_cum'], name='SPY (Cum PnL USD)', mode='lines', line=dict(color='#3b82f6', width=3), yaxis='y2'))
fig_pnl.add_trace(go.Scatter(x=chart_df['date'], y=chart_df['qqq_usd_cum'], name='QQQ (Cum PnL USD)', mode='lines', line=dict(color='#dc2626', width=3), yaxis='y2'))

regime_bg_colors = {'Green': '#166534', 'Yellow': '#eab308', 'Red': '#991b1b'}
regime_text_colors = {'Green': 'white', 'Yellow': 'black', 'Red': 'white'}
chart_df['regime_bg'] = chart_df['regime'].map(regime_bg_colors)
chart_df['regime_txt'] = chart_df['regime'].map(regime_text_colors)

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

fig_pnl.add_annotation(x=last_dt, y=est_val, text=f"{(est_val/global_metrics['nav'])*100:.1f}%", showarrow=False, xanchor='left', yref='y2', bgcolor='black', font=dict(color='white', size=11))
fig_pnl.add_annotation(x=last_dt, y=spy_val, text=f"{(spy_val/global_metrics['nav'])*100:.1f}%", showarrow=False, xanchor='left', yref='y2', bgcolor='#3b82f6', font=dict(color='white', size=11))
fig_pnl.add_annotation(x=last_dt, y=qqq_val, text=f"{(qqq_val/global_metrics['nav'])*100:.1f}%", showarrow=False, xanchor='left', yref='y2', bgcolor='#dc2626', font=dict(color='white', size=11))

fig_pnl.update_layout(
    barmode='relative', margin=dict(l=20, r=20, t=30, b=20), plot_bgcolor='rgba(0,0,0,0)', legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
    yaxis=dict(title='Daily PnL (USD)', showgrid=True, gridcolor='LightGray', zeroline=True, zerolinecolor='black', zerolinewidth=1),
    yaxis2=dict(title='Cumulative PnL (USD)', overlaying='y', side='right', showgrid=False),
    yaxis3=dict(overlaying='y', visible=False, range=[-1, 20])
)
st.plotly_chart(fig_pnl, width='stretch')

st.markdown("""
<div style="background-color: #f9fafb; padding: 10px; border-radius: 8px; border: 1px solid #e5e7eb; font-size: 11px; color: #4b5563;">
    <span style="font-weight: bold; color: #1f2937;">TOR (Total Open Risk) Tracker:</span> Applies strictly to <b>Silo B</b> (Active Swing). TOR is the sum of risk across all open positions (Distance from Entry to Stop Loss). Once a trade reaches +1R profit, moving the stop to break-even reduces its specific TOR contribution to 0.<br><br>
    <span style="font-weight: bold; color: #1f2937;">Regime Key:</span> 
    <span style="color: #166534; font-weight: bold;">🟢 Green (3-5 TOR):</span> SPY > 10 SMA > 20 SMA. Low VIX permits max risk exposure. &nbsp;&nbsp;
    <span style="color: #a16207; font-weight: bold;">🟡 Yellow (1-3 TOR):</span> Pullbacks/Transitions. Risk is throttled. &nbsp;&nbsp;
    <span style="color: #991b1b; font-weight: bold;">🔴 Red (0-1 TOR):</span> SPY < 20 SMA < 10 SMA. Defensive stance. VIX > 25 halts all active trading (TOR = 0).
</div>
""", unsafe_allow_html=True)

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
    else: line_df = attr_df.copy()

    tot_a1 = attr_df['a1_yield'].sum()
    tot_a2 = attr_df['a2_beta'].sum()
    tot_a3 = attr_df['a3_vrp'].sum()
    tot_a4 = attr_df['a4_alpha'].sum()
    tot_a5 = attr_df['a5_fees'].sum()
    
    col_bar, col_line, col_vel = st.columns([2, 3, 1])
    
    bar_colors =['#3b82f6', '#f97316', '#166534', '#a855f7', '#ef4444']
    
    with col_bar:
        fig_attr_bar = go.Figure(data=[go.Bar(
            x=['Yield (a1)', 'Beta (a2)', 'VRP (a3)', 'Alpha (a4)', 'Fees (a5)'],
            y=[tot_a1, tot_a2, tot_a3, tot_a4, tot_a5],
            text=[f"${v:,.0f}" for v in[tot_a1, tot_a2, tot_a3, tot_a4, tot_a5]],
            textposition='auto', marker_color=bar_colors
        )])
        fig_attr_bar.update_layout(title="Absolute PnL by Strategy", plot_bgcolor='rgba(0,0,0,0)', margin=dict(l=20, r=20, t=40, b=20), yaxis=dict(zeroline=True, zerolinecolor='black', zerolinewidth=1, gridcolor='LightGray'))
        st.plotly_chart(fig_attr_bar, width='stretch')
        
    with col_line:
        fig_attr_line = go.Figure()
        fig_attr_line.add_trace(go.Scatter(x=line_df['date'], y=line_df['a1_yield'].cumsum(), name='Yield', line=dict(color='#3b82f6', width=4)))
        fig_attr_line.add_trace(go.Scatter(x=line_df['date'], y=line_df['a2_beta'].cumsum(), name='Beta', line=dict(color='#f97316', width=4)))
        fig_attr_line.add_trace(go.Scatter(x=line_df['date'], y=line_df['a3_vrp'].cumsum(), name='VRP', line=dict(color='#166534', width=4)))
        fig_attr_line.add_trace(go.Scatter(x=line_df['date'], y=line_df['a4_alpha'].cumsum(), name='Alpha', line=dict(color='#a855f7', width=4)))
        fig_attr_line.add_trace(go.Scatter(x=line_df['date'], y=line_df['a5_fees'].cumsum(), name='Fees', line=dict(color='#ef4444', width=4)))
        fig_attr_line.update_layout(title="Cumulative Trajectory", plot_bgcolor='rgba(0,0,0,0)', margin=dict(l=20, r=20, t=40, b=20), yaxis=dict(zeroline=True, zerolinecolor='black', zerolinewidth=1, gridcolor='LightGray'), legend=dict(orientation="h", yanchor="bottom", y=-0.2, xanchor="center", x=0.5))
        st.plotly_chart(fig_attr_line, width='stretch')
        
    with col_vel:
        st.markdown("##### Options Engine Velocity")
        st.caption("(Silos A & C)")
        opt_margin_total = (pos_df[pos_df['sec_type'] == 'OPT']['position'].abs().sum() / 2) * 2500 if not pos_df.empty else 0
        st.metric("Total VRP Harvested", f"${tot_a3:,.0f}", help="Absolute sum of the Volatility Risk Premium (a3) captured to date.")
        st.metric("Options Margin Locked", f"${opt_margin_total:,.0f}", help="Current collateral deployed for open Option Spreads.")
        st.metric("Target Profit Hit", "50% GTC", help="Automated take-profit trigger.")

    st.markdown("""
    <div style="background-color: #f9fafb; padding: 10px; border-radius: 8px; border: 1px solid #e5e7eb; font-size: 11px; color: #4b5563;">
        <span style="color: #3b82f6; font-weight: bold;">Risk-Free Yield (a1):</span> T-Bill Interest (IB01/Cash).<br>
        <span style="color: #f97316; font-weight: bold;">Core Beta (a2):</span> Long-term physical equities (CSPX/CNDX), regional ETFs (ITWN, CSKR, CNYA), Crypto ETFs (ETHEUSD).<br>
        <span style="color: #166534; font-weight: bold;">VRP Engine (a3):</span> Options premium (Silos A & C XSP/XND Puts).<br>
        <span style="color: #a855f7; font-weight: bold;">Active Alpha (a4):</span> Swing trades isolated in Silo B.<br>
        <span style="color: #ef4444; font-weight: bold;">Commissions & Fees (a5):</span> Explicit friction pulled directly from IBKR Ledger.
    </div>
    """, unsafe_allow_html=True)

st.divider()

# --- SECTION 7: THE MASTER MATRIX ---
st.subheader("5. The Master Instrument Matrix (Tax, Alpha, & Sharpe Grading)")
matrix_data =[
    {"Instrument": "USD Cash", "Type": "Currency", "Risk Profile": "Risk-Free", "Alpha Potential": "Zero", "Sharpe Impact": "Stabilizer", "Trading Strategy": "Liquidity", "Jurisdiction": "US (IBKR)", "Tax Treatment": "Exempt (Bank Deposit)", "CIO Min Alloc. %": "1%", "CIO Max Alloc. %": "100%", "CIO Grading": "Splendid", "Noteworthy Comments": "Uninvested USD held in IBKR. Mandatory margin collateral."},
    {"Instrument": "IB01", "Type": "UCITS ETF", "Risk Profile": "Risk-Free", "Alpha Potential": "Zero", "Sharpe Impact": "High", "Trading Strategy": "Collateral", "Jurisdiction": "Ireland", "Tax Treatment": "Exempt (Irish Domicile)", "CIO Min Alloc. %": "10%", "CIO Max Alloc. %": "100%", "CIO Grading": "Splendid", "Noteworthy Comments": "Irish-domiciled short-term US Treasury fund. Accumulates ~4.5% tax-free."},
    {"Instrument": "XSP Put Spreads", "Type": "Index Option", "Risk Profile": "Moderate", "Alpha Potential": "High (VRP)", "Sharpe Impact": "High", "Trading Strategy": "Weekly Income", "Jurisdiction": "US (Cboe)", "Tax Treatment": "Exempt (Cash-Settled)", "CIO Min Alloc. %": "0%", "CIO Max Alloc. %": "25%", "CIO Grading": "Splendid", "Noteworthy Comments": "Cash-settled S&P 500 options. 100% safe from IRS."},
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
    if ac == 'Crypto': alloc_map['BTC/ETH ETPs'] = alloc_map.get('BTC/ETH ETPs', 0) + r['market_value']
    elif ac == 'Cash': alloc_map['USD Cash'] = alloc_map.get('USD Cash', 0) + r['market_value']
    elif ac == 'Active Swing': 
        if r['sec_type'] == 'STK': 
            alloc_map['International Stocks'] = alloc_map.get('International Stocks', 0) + r['market_value']
        elif r['sec_type'] == 'CFD': 
            alloc_map['US Tech CFDs'] = alloc_map.get('US Tech CFDs', 0) + r['market_value']
        else:
            alloc_map['US Tech CFDs'] = alloc_map.get('US Tech CFDs', 0) + r['market_value']
    elif ac == 'Opt Liab':
        if 'XSP' in r['symbol']: alloc_map['XSP Put Spreads'] = alloc_map.get('XSP Put Spreads', 0) + r['market_value']
        elif 'XND' in r['symbol']: alloc_map['XND Put Spreads'] = alloc_map.get('XND Put Spreads', 0) + r['market_value']
        else: alloc_map['XSP Put Spreads'] = alloc_map.get('XSP Put Spreads', 0) + r['market_value']
    else: alloc_map[ac] = alloc_map.get(ac, 0) + r['market_value']
    
def get_pct(inst):
    if inst == 'Accruals, Unsettled & FX': return 0.0 
    if inst == 'ITWN (Taiwan)': val = alloc_map.get('ITWN', 0)
    elif inst == 'CSKR (Korea)': val = alloc_map.get('CSKR', 0)
    elif inst == 'CNYA (China)': val = alloc_map.get('CNYA', 0)
    else: val = alloc_map.get(inst, 0)
    return (val / global_metrics['nav']) * 100 if global_metrics['nav'] > 0 else 0

df_matrix.insert(9, "Current Global Alloc. %", df_matrix['Instrument'].apply(get_pct))

raw_sum = df_matrix['Current Global Alloc. %'].sum()
recon_pct = 100.0 - raw_sum
df_matrix.loc[df_matrix['Instrument'] == 'Accruals, Unsettled & FX', 'Current Global Alloc. %'] = recon_pct

def color_grading(val):
    if val == "Splendid": return 'background-color: #dcfce7; color: #166534; font-weight: bold'
    if val == "Great": return 'background-color: #ecfccb; color: #15803d; font-weight: bold'
    if val == "Good": return 'background-color: #fef9c3; color: #4d7c0f; font-weight: bold'
    if val == "Contingent": return 'background-color: #e0e7ff; color: #1e40af; font-weight: bold'
    if val == "Bad": return 'background-color: #ffedd5; color: #b91c1c; font-weight: bold'
    if val == "Avoid": return 'background-color: #fecaca; color: #991b1b; font-weight: bold'
    return ''

st.dataframe(df_matrix.style.format({'Current Global Alloc. %': '{:.2f}%'})\
            .applymap(color_grading, subset=['CIO Grading'])\
            .set_properties(**{'background-color': '#eff6ff', 'color': '#1d4ed8', 'font-weight': 'bold'}, subset=['Current Global Alloc. %']), 
            hide_index=True, use_container_width=True)

option_instruments =["XSP Put Spreads", "XND Put Spreads", "/MES Put Spreads", "XSP LEAPS"]
opt_liab = df_matrix[df_matrix['Instrument'].isin(option_instruments)]['Current Global Alloc. %'].sum()
gross_phys = df_matrix[~df_matrix['Instrument'].isin(option_instruments)]['Current Global Alloc. %'].sum()
true_net = gross_phys + opt_liab

col1, col2, col3 = st.columns([6, 2, 4])
with col2:
    st.markdown(f"""
    <div style='text-align: right; font-size: 12px; font-weight: bold;'>
        GROSS PHYSICAL ASSETS:<br>
        <span style='color: #ef4444'>OPTIONS LIABILITY DRAG:</span><br>
        TRUE NET ESTATE CHECKSUM:
    </div>
    """, unsafe_allow_html=True)
with col3:
    st.markdown(f"""
    <div style='text-align: left; font-size: 12px; font-weight: bold; color: #1d4ed8;'>
        {gross_phys:.2f}%<br>
        <span style='color: #ef4444'>{opt_liab:.2f}%</span><br>
        <span style='color: black'>{true_net:.2f}%</span> &nbsp;&nbsp;&nbsp; <span style='font-size: 10px; color: gray; font-weight: normal'>Must exactly equal 100.00%</span>
    </div>
    """, unsafe_allow_html=True)

st.divider()

# --- SECTION 8: CAPITAL DEPLOYMENT & MARGIN TRACKER ---
st.subheader("6. Capital Deployment & Margin Capacity Tracker")
c1, c2, c3 = st.columns(3)

with c1:
    fig_gauge_cash = go.Figure(go.Indicator(
        mode = "gauge+number+delta",
        value = pct_cash,
        title = {'text': "Bedrock Cash Buffer (IB01 + USD)", 'font': {'size': 14}},
        delta = {'reference': 40, 'increasing': {'color': "green"}, 'decreasing': {'color': "red"}},
        gauge = {
            'axis': {'range':[0, 100], 'tickwidth': 1},
            'bar': {'color': "blue"},
            'steps': [
                {'range':[0, 40], 'color': "rgba(239, 68, 68, 0.3)"},
                {'range':[40, 100], 'color': "rgba(34, 197, 94, 0.3)"}],
            'threshold': {'line': {'color': "red", 'width': 4}, 'thickness': 0.75, 'value': 40}
        }
    ))
    fig_gauge_cash.update_layout(height=250, margin=dict(l=10, r=10, t=40, b=10))
    st.plotly_chart(fig_gauge_cash, use_container_width=True)
    if pct_cash >= 40: st.success(f"**✓ SAFE:** Buffer is optimal.")
    else: st.error(f"**⚠️ WARNING:** Buffer breached 40% floor. Halt all Equity DCA.")

with c2:
    opt_margin_total = (pos_df[pos_df['sec_type'] == 'OPT']['position'].abs().sum() / 2) * 2500 if not pos_df.empty else 0
    pct_margin = (opt_margin_total / global_metrics['nav']) * 100 if global_metrics['nav'] > 0 else 0
    
    fig_gauge_margin = go.Figure(go.Indicator(
        mode = "gauge+number+delta",
        value = pct_margin,
        title = {'text': "Options Margin Utilization", 'font': {'size': 14}},
        delta = {'reference': 25, 'increasing': {'color': "red"}, 'decreasing': {'color': "green"}},
        gauge = {
            'axis': {'range':[0, 100], 'tickwidth': 1},
            'bar': {'color': "purple"},
            'steps': [
                {'range':[0, 25], 'color': "rgba(34, 197, 94, 0.3)"},
                {'range':[25, 100], 'color': "rgba(239, 68, 68, 0.3)"}],
            'threshold': {'line': {'color': "red", 'width': 4}, 'thickness': 0.75, 'value': 25}
        }
    ))
    fig_gauge_margin.update_layout(height=250, margin=dict(l=10, r=10, t=40, b=10))
    st.plotly_chart(fig_gauge_margin, use_container_width=True)
    if pct_margin <= 25: st.success(f"**✓ OPTIMAL:** Remaining capacity is healthy.")
    else: st.error(f"**⚠️ CAP BREACHED:** Close spreads immediately.")

with c3:
    st.markdown("##### DCA Deployment Schedule")
    regime_str = chart_df['regime'].iloc[-1]
    if regime_str == 'Green':
        st.markdown("<h4 style='color: #166534;'>🟢 Green Regime (Risk On)</h4>", unsafe_allow_html=True)
        st.write("**Silos A & C (Equities):** Transfer funds from IB01 to purchase physical CSPX/CNDX equity.")
        st.write("**Silo C (Options):** Clear to sell new XSP/XND Put Spreads up to 25% margin cap.")
    elif regime_str == 'Yellow':
        st.markdown("<h4 style='color: #eab308;'>🟡 Yellow Regime (Transition)</h4>", unsafe_allow_html=True)
        st.write("**Silos A & C (Equities):** HOLD current equity DCA. Funnel all new cash deposits strictly into IB01.")
        st.write("**Silo C (Options):** Throttle new Put Spreads to strict 45 DTE. Require higher premium floor.")
    else:
        st.markdown("<h4 style='color: #991b1b;'>🔴 Red Regime (Defense)</h4>", unsafe_allow_html=True)
        st.write("**All Silos:** HALT all active equity purchases. Defend the 40% Cash Buffer.")
        st.write("**Silo C (Options):** If VIX spikes violently, buy 90-DTE SPX Puts (Taleb Tail-Hedge) to protect physical assets.")

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
    drawdowns = peaks - cum_sim
    max_dds = np.max(drawdowns, axis=1)
    
    mc_avg_dd = np.mean(max_dds)
    mc_best_dd = np.min(max_dds)
    mc_worst_dd = np.max(max_dds)
    mc_avg_path = np.mean(cum_sim, axis=0)
    
    orig_cum = np.insert(np.cumsum(daily_pnl_array), 0, 0)
    orig_peaks = np.maximum.accumulate(orig_cum)
    orig_dd = np.max(orig_peaks - orig_cum)
    
    mc_fig = go.Figure()
    
    for i in range(200):
        r, g, b = random.randint(50, 200), random.randint(50, 200), random.randint(50, 200)
        mc_fig.add_trace(go.Scatter(y=cum_sim[i], mode='lines', line=dict(color=f'rgba({r}, {g}, {b}, 0.40)', width=2), showlegend=False, hoverinfo='skip'))
    
    mc_fig.add_trace(go.Scatter(y=mc_avg_path, name='Avg Path (Stable)', mode='lines', line=dict(color='blue', width=4)))
    mc_fig.add_trace(go.Scatter(y=orig_cum, name='Original History', mode='lines', line=dict(color='black', width=7)))
    
    stats_text = (f"<b>ORIGINAL HISTORY:</b><br>Max Drawdown: ${orig_dd:,.2f}<br><br>"
                  f"<b>SIMULATION (10,000 runs):</b><br>Best Case DD: ${mc_best_dd:,.2f}<br>"
                  f"Worst Case DD: ${mc_worst_dd:,.2f}<br>Avg Drawdown: ${mc_avg_dd:,.2f}")
                  
    mc_fig.add_annotation(
        x=0.02, y=0.95, xref='paper', yref='paper',
        text=stats_text, showarrow=False, align='left',
        bgcolor='rgba(255, 255, 255, 0.9)', bordercolor='black', borderwidth=1, font=dict(size=11)
    )
    
    mc_fig.update_layout(
        height=800,
        margin=dict(l=20, r=20, t=30, b=20), plot_bgcolor='rgba(0,0,0,0)', xaxis_title='Trading Days Forward',
        yaxis=dict(title='Cumulative Net Profit (USD)', showgrid=True, gridcolor='LightGray', zeroline=True, zerolinecolor='black', zerolinewidth=1),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
    )
    mc_fig.update_xaxes(showgrid=True, gridwidth=1, gridcolor='LightGray')
    
    st.plotly_chart(mc_fig, width='stretch')

st.divider()

# --- SECTION 10: THE OPTIONS PERFORMANCE LEDGER ---
st.subheader("8. The Options Performance Ledger (Live Database)")

# 1. Math Enforcement Engine
if not journal_raw_df.empty:
    today = datetime.date.today()
    
    # Convert dates safely
    journal_raw_df['Open Date'] = pd.to_datetime(journal_raw_df['Open Date'], errors='coerce').dt.date
    journal_raw_df['Close Date'] = pd.to_datetime(journal_raw_df['Close Date'], errors='coerce').dt.date
    
    # Python-enforced math (Overrides any manual typos in formula columns)
    journal_raw_df['Collateral Locked (USD)'] = (journal_raw_df['Short Strike'] - journal_raw_df['Long Strike']) * 100 * journal_raw_df['Quantity']
    journal_raw_df['Total Net Credit (USD)'] = journal_raw_df['Premium Collected (USD)'] * 100 * journal_raw_df['Quantity']
    journal_raw_df['Target 50% Exit Price (USD)'] = journal_raw_df['Premium Collected (USD)'] / 2
    
    def calc_days_rem(r):
        if pd.isnull(r['Close Date']):
            elapsed = (today - r['Open Date']).days if pd.notnull(r['Open Date']) else 0
            return max(0, r['DTE at Entry'] - elapsed) if pd.notnull(r['DTE at Entry']) else 0
        return 'Closed'
    journal_raw_df['Days Remaining'] = journal_raw_df.apply(calc_days_rem, axis=1)
    
    def calc_days_trade(r):
        if pd.isnull(r['Close Date']):
            return (today - r['Open Date']).days if pd.notnull(r['Open Date']) else 0
        return (r['Close Date'] - r['Open Date']).days if pd.notnull(r['Open Date']) else 0
    journal_raw_df['Days in Trade'] = journal_raw_df.apply(calc_days_trade, axis=1)
    
    journal_raw_df['Total P&L (USD)'] = (journal_raw_df['Premium Collected (USD)'] - journal_raw_df['Closing Price (USD)']) * 100 * journal_raw_df['Quantity']
    journal_raw_df['Return on Capital (ROC) %'] = journal_raw_df['Total P&L (USD)'] / journal_raw_df['Collateral Locked (USD)']
    
    def calc_ann_roc(r):
        if pd.isnull(r['Return on Capital (ROC) %']) or r['Days in Trade'] == 0:
            return np.nan
        return r['Return on Capital (ROC) %'] * (365.0 / r['Days in Trade'])
    journal_raw_df['Annualized ROC %'] = journal_raw_df.apply(calc_ann_roc, axis=1)
    
    # Sort newest trades to the top
    journal_raw_df = journal_raw_df.sort_values('Open Date', ascending=False).reset_index(drop=True)

# 2. The Drift Detector (Ledger vs TWS Firewall)
if not journal_raw_df.empty:
    open_journal = journal_raw_df[pd.isnull(journal_raw_df['Close Date'])]
    opt_margin_journal = open_journal['Collateral Locked (USD)'].sum()
    
    drift_delta = opt_margin_journal - opt_margin_total
    if abs(drift_delta) > 0.01:
        st.error(f"⚠️ **LEDGER DRIFT DETECTED:** Your live TWS margin footprint is **${opt_margin_total:,.0f}**, but your Open Journal positions total **${opt_margin_journal:,.0f}**. You have a **${-drift_delta:,.0f}** discrepancy. Please check your open strikes and quantities for typos.")

# 3. Excel Conditional Formatting Engine
def style_journal(df):
    css_df = pd.DataFrame('', index=df.index, columns=df.columns)
    for i, row in df.iterrows():
        # Gold for >100% Ann ROC
        if pd.notna(row['Annualized ROC %']) and row['Annualized ROC %'] > 1.0:
            css_df.at[i, 'Annualized ROC %'] = 'background-color: #fef08a; color: #856404; font-weight: bold;'
        
        # Green for fast exits <= 14 days
        if pd.notna(row['Days in Trade']) and row['Days in Trade'] <= 14 and row['Days in Trade'] > 0:
            css_df.at[i, 'Days in Trade'] = 'background-color: #d1e7dd; color: #0f5132; font-weight: bold;'
            
        # Red/Green Time stop alarms for Days Remaining
        if pd.notna(row['Days Remaining']) and str(row['Days Remaining']) != 'Closed' and pd.notna(row['DTE at Entry']):
            try:
                if float(row['Days Remaining']) < (float(row['DTE at Entry']) / 2):
                    css_df.at[i, 'Days Remaining'] = 'background-color: #f8d7da; color: #842029; font-weight: bold;'
                else:
                    css_df.at[i, 'Days Remaining'] = 'background-color: #d1e7dd; color: #0f5132; font-weight: bold;'
            except: pass
            
        # Light gray for disabled formula columns
        formula_cols =['Collateral Locked (USD)', 'Total Net Credit (USD)', 'Target 50% Exit Price (USD)', 'Days Remaining', 'Days in Trade', 'Total P&L (USD)', 'Return on Capital (ROC) %', 'Annualized ROC %']
        for col in formula_cols:
            css_df.at[i, col] += ' background-color: #f3f4f6;'
    return css_df

# 4. Streamlit Interactive Editor
if not journal_raw_df.empty:
    styled_journal = journal_raw_df.style.apply(lambda x: style_journal(journal_raw_df), axis=None)
    
    # Lock the math columns from human tampering
    disabled_cols =['Collateral Locked (USD)', 'Total Net Credit (USD)', 'Target 50% Exit Price (USD)', 'Days Remaining', 'Days in Trade', 'Total P&L (USD)', 'Return on Capital (ROC) %', 'Annualized ROC %']
    
    edited_df = st.data_editor(
        styled_journal,
        use_container_width=True,
        num_rows="dynamic",
        disabled=disabled_cols,
        height=600,
        column_config={
            "Premium Collected (USD)": st.column_config.NumberColumn(format="$%.2f"),
            "Collateral Locked (USD)": st.column_config.NumberColumn(format="$%.2f"),
            "Total Net Credit (USD)": st.column_config.NumberColumn(format="$%.2f"),
            "Target 50% Exit Price (USD)": st.column_config.NumberColumn(format="$%.2f"),
            "Closing Price (USD)": st.column_config.NumberColumn(format="$%.2f"),
            "Total P&L (USD)": st.column_config.NumberColumn(format="$%.2f"),
            "Return on Capital (ROC) %": st.column_config.NumberColumn(format="%.2f%%"),
            "Annualized ROC %": st.column_config.NumberColumn(format="%.2f%%"),
            "Open Date": st.column_config.DateColumn(),
            "Close Date": st.column_config.DateColumn()
        }
    )

    # 5. Database Auto-Save Engine
    # Fills NaNs with empty string to prevent false-positive change detections
    if not journal_raw_df.fillna('').equals(edited_df.fillna('')):
        conn = sqlite3.connect(DB_PATH)
        edited_df.to_sql('options_journal', conn, if_exists='replace', index=False)
        conn.close()
        st.rerun() # Instantly refreshes dashboard to recalculate new math
else:
    st.info("No options history found in database.")