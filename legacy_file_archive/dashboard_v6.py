"""
=============================================================================
Script Name: dashboard_v6.py
Purpose: The Streamlit Frontend (Module 6).
         - Adds Regime logic (Green/Yellow/Red) natively via YFinance SMAs.
         - Adds PnL Attribution Panel & Capital Velocity.
         - Enhances Monte Carlo visibility.
         - Consolidates redundant charts & adds footers.
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
    
    # Load Attribution Data
    attr_df = pd.read_sql_query("SELECT * FROM daily_attribution", conn)
    if not attr_df.empty:
        attr_df['date'] = pd.to_datetime(attr_df['date'])
        
    return global_df, global_metrics, silo_dfs, silo_metrics, pos_df, attr_df

@st.cache_data(ttl=3600)
def load_benchmarks(start_date, end_date):
    # Added ^VIX for Regime Calculation
    data = yf.download(["SPY", "QQQ", "^VIX"], start=start_date - datetime.timedelta(days=40), end=end_date + datetime.timedelta(days=1), progress=False, auto_adjust=False)
    close_data = data['Close'].ffill()
    bench_df = close_data.reset_index()
    bench_df.rename(columns={'Date': 'date'}, inplace=True)
    bench_df['date'] = pd.to_datetime(bench_df['date']).dt.tz_localize(None)
    
    # Calculate SMAs for Regime
    bench_df['sma_10'] = bench_df['SPY'].rolling(window=10).mean()
    bench_df['sma_20'] = bench_df['SPY'].rolling(window=20).mean()
    
    # Crop back to actual start date
    bench_df = bench_df[bench_df['date'] >= pd.to_datetime(start_date)].copy()
    
    # Determine Regime Status
    def get_regime(row):
        if pd.isna(row['sma_10']) or pd.isna(row['sma_20']): return 'Yellow'
        if row['^VIX'] > 25: return 'Red'
        if row['SPY'] > row['sma_10'] and row['sma_10'] > row['sma_20']: return 'Green'
        if row['SPY'] < row['sma_20'] and row['sma_20'] < row['sma_10']: return 'Red'
        return 'Yellow'
        
    bench_df['regime'] = bench_df.apply(get_regime, axis=1)
    
    bench_df['spy_ret'] = bench_df['SPY'].pct_change().fillna(0)
    bench_df['qqq_ret'] = bench_df['QQQ'].pct_change().fillna(0)
    bench_df['spy_cum'] = (1 + bench_df['spy_ret']).cumprod() - 1
    bench_df['qqq_cum'] = (1 + bench_df['qqq_ret']).cumprod() - 1
    return bench_df

# --- UI RENDERING ---
st.title("Estate Master Dashboard")
st.markdown(f"**Data Pipeline:** Live IBKR Sync via SQLite (`{DB_NAME}`) • **Last Refresh:** {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
st.divider()

global_df, global_metrics, silo_dfs, silo_metrics, pos_df, attr_df = load_and_process_data()
bench_df = load_benchmarks(global_df['date'].min(), global_df['date'].max())
chart_df = pd.merge(global_df, bench_df, on='date', how='left').ffill().fillna(0)

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

# --- SECTION 1: MASTER METRICS (HTML STYLING) ---
def col_html(val, good_thresh=None):
    if "N/A" in str(val): return "color: #4b5563;"
    if isinstance(val, (int, float)):
        if good_thresh is not None:
            return "color: #15803d;" if val >= good_thresh else "color: #b91c1c;"
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
        <span style="margin-right: 15px;">IRR: >10%</span>
        <span style="margin-right: 15px;">Sharpe: 1.0 to 2.0+</span>
        <span style="margin-right: 15px;">Max DD: > -15%</span>
        <span style="margin-right: 15px;">Calmar: > 1.0</span>
        <span style="margin-right: 15px;">Alpha: > 0%</span>
        <span>Corr: 0.30 to 0.60</span>
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

# --- SECTION 3: TARGET PORTFOLIO COMPOSITION ---
st.subheader("1. Live Portfolio Composition (from TWS)")
comp_cols = st.columns(4)
for idx, acc in enumerate(SILO_MAP.keys()):
    name, _, color = SILO_MAP[acc]
    acc_pos = pos_df[pos_df['account'] == acc].copy()
    
    with comp_cols[idx]:
        st.markdown(f"**{name}**")
        if not acc_pos.empty:
            acc_nav = silo_metrics[acc]['nav']
            acc_pos['Allocation %'] = (acc_pos['market_value'] / acc_nav) * 100 if acc_nav > 0 else 0
            display_df = acc_pos[['symbol', 'market_value', 'Allocation %']].sort_values('market_value', ascending=False)
            display_df.columns = ['Asset', 'Value ($)', 'Alloc (%)']
            st.dataframe(display_df.style.format({'Value ($)': '{:,.0f}', 'Alloc (%)': '{:.1f}%'}), hide_index=True, height=(len(display_df) + 1) * 35 + 3, width='stretch')
        else:
            st.write("No active positions.")

st.divider()

# --- SECTION 4: DAILY PNL HISTOGRAM ---
st.subheader("2. Daily PnL per Silo")
spy_usd_pnl =[]
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
        fig_pnl.add_trace(go.Bar(x=silo_dfs[acc]['date'], y=silo_dfs[acc]['daily_pnl'], name=name, marker_color=color))

fig_pnl.add_trace(go.Scatter(x=chart_df['date'], y=chart_df['cum_pnl'], name='Estate (Cum PnL USD)', mode='lines', line=dict(color='black', width=4), yaxis='y2'))
fig_pnl.add_trace(go.Scatter(x=chart_df['date'], y=chart_df['spy_usd_cum'], name='SPY (Cum PnL USD)', mode='lines', line=dict(color='#3b82f6', width=2), yaxis='y2'))
fig_pnl.add_trace(go.Scatter(x=chart_df['date'], y=chart_df['qqq_usd_cum'], name='QQQ (Cum PnL USD)', mode='lines', line=dict(color='#dc2626', width=2), yaxis='y2'))

# Add Regime Markers dynamically!
regime_colors = {'Green': '#22c55e', 'Yellow': '#eab308', 'Red': '#ef4444'}
chart_df['regime_color'] = chart_df['regime'].map(regime_colors)
fig_pnl.add_trace(go.Scatter(
    x=chart_df['date'], y=[0]*len(chart_df), mode='markers', 
    marker=dict(color=chart_df['regime_color'], symbol='square', size=8),
    name='Market Regime', showlegend=False, yaxis='y3'
))

fig_pnl.update_layout(
    barmode='relative', margin=dict(l=20, r=20, t=30, b=20),
    plot_bgcolor='rgba(0,0,0,0)', legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
    yaxis=dict(title='Daily PnL (USD)', showgrid=True, gridcolor='LightGray', zeroline=True, zerolinecolor='black'),
    yaxis2=dict(title='Cumulative PnL (USD)', overlaying='y', side='right', showgrid=False),
    yaxis3=dict(overlaying='y', visible=False, range=[-1, 20]) # Pin regimes to the bottom
)
st.plotly_chart(fig_pnl, width='stretch')

# Add the Regime Footer
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

# --- SECTION 5: PNL ATTRIBUTION ---
st.subheader("3. PnL Attribution & Capital Velocity")
if not attr_df.empty:
    attr_df = attr_df.sort_values('date').reset_index(drop=True)
    
    # Calculate Totals for Bar Chart
    tot_a1 = attr_df['a1_yield'].sum()
    tot_a2 = attr_df['a2_beta'].sum()
    tot_a3 = attr_df['a3_vrp'].sum()
    tot_a4 = attr_df['a4_alpha'].sum()
    tot_a5 = attr_df['a5_fees'].sum()
    
    col_bar, col_line = st.columns(2)
    
    with col_bar:
        fig_attr_bar = go.Figure(data=[go.Bar(
            x=['Yield (a1)', 'Beta (a2)', 'VRP (a3)', 'Alpha (a4)', 'Fees (a5)'],
            y=[tot_a1, tot_a2, tot_a3, tot_a4, tot_a5],
            text=[f"${v:,.0f}" for v in[tot_a1, tot_a2, tot_a3, tot_a4, tot_a5]],
            textposition='auto',
            marker_color=['#3b82f6', '#f97316', '#86efac', '#a855f7', '#ef4444']
        )])
        fig_attr_bar.update_layout(title="Absolute PnL by Strategy", plot_bgcolor='rgba(0,0,0,0)', margin=dict(l=20, r=20, t=40, b=20), yaxis=dict(zeroline=True, zerolinecolor='black', gridcolor='LightGray'))
        st.plotly_chart(fig_attr_bar, width='stretch')
        
    with col_line:
        fig_attr_line = go.Figure()
        fig_attr_line.add_trace(go.Scatter(x=attr_df['date'], y=attr_df['a1_yield'].cumsum(), name='Yield', line=dict(color='#3b82f6', width=2)))
        fig_attr_line.add_trace(go.Scatter(x=attr_df['date'], y=attr_df['a2_beta'].cumsum(), name='Beta', line=dict(color='#f97316', width=2)))
        fig_attr_line.add_trace(go.Scatter(x=attr_df['date'], y=attr_df['a3_vrp'].cumsum(), name='VRP', line=dict(color='#86efac', width=2)))
        fig_attr_line.add_trace(go.Scatter(x=attr_df['date'], y=attr_df['a4_alpha'].cumsum(), name='Alpha', line=dict(color='#a855f7', width=2)))
        fig_attr_line.add_trace(go.Scatter(x=attr_df['date'], y=attr_df['a5_fees'].cumsum(), name='Fees', line=dict(color='#ef4444', width=2)))
        fig_attr_line.update_layout(title="Cumulative Trajectory", plot_bgcolor='rgba(0,0,0,0)', margin=dict(l=20, r=20, t=40, b=20), yaxis=dict(zeroline=True, zerolinecolor='black', gridcolor='LightGray'), legend=dict(orientation="h", yanchor="bottom", y=-0.2, xanchor="center", x=0.5))
        st.plotly_chart(fig_attr_line, width='stretch')
        
    st.markdown("""
    <div style="background-color: #f9fafb; padding: 10px; border-radius: 8px; border: 1px solid #e5e7eb; font-size: 11px; color: #4b5563;">
        <span style="color: #3b82f6; font-weight: bold;">Risk-Free Yield (a1):</span> T-Bill Interest (IB01/Cash).<br>
        <span style="color: #f97316; font-weight: bold;">Core Beta (a2):</span> Long-term physical equities (CSPX/CNDX).<br>
        <span style="color: #22c55e; font-weight: bold;">VRP Engine (a3):</span> Options premium (Silos A & C XSP/XND Puts).<br>
        <span style="color: #a855f7; font-weight: bold;">Active Alpha (a4):</span> Swing/Momentum plays & explicit regional ETFs.<br>
        <span style="color: #ef4444; font-weight: bold;">Commissions & Fees (a5):</span> Explicit friction pulled directly from IBKR Ledger.
    </div>
    """, unsafe_allow_html=True)
else:
    st.write("Attribution data not found. Please ensure migration completed successfully.")

st.divider()

# --- SECTION 6: MONTE CARLO SIMULATION ---
st.subheader("4. Estate Montecarlo PnL Simulation - Projections vs History")
daily_pnl_array = global_df['daily_pnl'].dropna().values
sim_length = len(daily_pnl_array)

if sim_length > 0:
    sim_data = np.random.choice(daily_pnl_array, size=(10000, sim_length), replace=True)
    cum_sim = np.cumsum(sim_data, axis=1)
    
    peaks = np.maximum.accumulate(cum_sim, axis=1)
    drawdowns = peaks - cum_sim
    max_dds = np.max(drawdowns, axis=1)
    
    mc_avg_dd = np.mean(max_dds)
    mc_best_dd = np.min(max_dds)
    mc_worst_dd = np.max(max_dds)
    mc_avg_path = np.mean(cum_sim, axis=0)
    
    orig_cum = np.cumsum(daily_pnl_array)
    orig_peaks = np.maximum.accumulate(orig_cum)
    orig_dd = np.max(orig_peaks - orig_cum)
    
    mc_fig = go.Figure()
    
    # ENHANCED SPAGHETTI LINES (Darker Grey, 30% Opacity)
    for i in range(100):
        mc_fig.add_trace(go.Scatter(y=cum_sim[i], mode='lines', line=dict(color='rgba(100, 100, 100, 0.3)', width=1), showlegend=False, hoverinfo='skip'))
    
    mc_fig.add_trace(go.Scatter(y=mc_avg_path, name='Avg Path (Stable)', mode='lines', line=dict(color='blue', width=3)))
    
    # ENHANCED ORIGINAL HISTORY (Double Width)
    mc_fig.add_trace(go.Scatter(y=orig_cum, name='Original History', mode='lines', line=dict(color='black', width=5)))
    
    stats_text = (f"<b>ORIGINAL HISTORY:</b><br>Max Drawdown: ${orig_dd:,.2f}<br><br>"
                  f"<b>SIMULATION (10,000 runs):</b><br>Best Case DD: ${mc_best_dd:,.2f}<br>"
                  f"Worst Case DD: ${mc_worst_dd:,.2f}<br>Avg Drawdown: ${mc_avg_dd:,.2f}")
                  
    mc_fig.add_annotation(
        x=0.02, y=0.95, xref='paper', yref='paper',
        text=stats_text, showarrow=False, align='left',
        bgcolor='rgba(255, 255, 255, 0.9)', bordercolor='black', borderwidth=1, font=dict(size=11)
    )
    
    mc_fig.update_layout(
        margin=dict(l=20, r=20, t=30, b=20), plot_bgcolor='rgba(0,0,0,0)', xaxis_title='Trading Days Forward',
        yaxis=dict(title='Cumulative Net Profit (USD)', showgrid=True, gridcolor='LightGray', zeroline=True, zerolinecolor='black'),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
    )
    mc_fig.update_xaxes(showgrid=True, gridwidth=1, gridcolor='LightGray')
    
    st.plotly_chart(mc_fig, width='stretch')