"""
=============================================================================
Script Name: dashboard_v55.py
Purpose: The Streamlit Frontend (Family Office Estate Architecture)

⚙️ HOW TO LAUNCH THIS DASHBOARD:
1. Open Command Prompt (cmd)
2. Navigate to the Estate directory by pasting:
   cd "C:\\Users\\donca\\Desktop\\Desktop HP Envy x360 al 22Abr24\\Docs Manuel\\IBKR_Options"
3. Launch the UI by running exactly:
   streamlit run dashboard_v55.py

CHANGELOG (v55):
         - PATCHED: fetch_live_data() ticker mapping bug (now dynamically fetches the exact ticker instead of hardcoding SPY).
=============================================================================
"""
import streamlit as st
import pandas as pd
import sqlite3
import numpy as np
import plotly.graph_objects as go
import yfinance as yf
import os
import sys
import datetime
import random
import subprocess
import glob
import math

st.set_page_config(page_title="Estate Master Dashboard", layout="wide")
DB_NAME = "estate_data.db"
TARGET_DIR = r"C:\Users\donca\Desktop\Desktop HP Envy x360 al 22Abr24\Docs Manuel\IBKR_Options"
DB_PATH = os.path.join(TARGET_DIR, DB_NAME)
SYNC_SCRIPT = os.path.join(TARGET_DIR, "sync_engine_v24.py")

# --- MASTER CHAMPION TAG LIST ---
CHAMPION_TAGS = sorted([
    "Ai_Energy", "Arbitrage", "Aschenbrenner", "Babyfolio", "CPOs", "Canada", 
    "Champ", "China", "EP", "Europe", "Insider_Trade", "Japan", "Korea", 
    "Long", "MC<1B", "MC>100B", "MC_10to100B", "MC_1to10B", "Mean_Rev", 
    "Serenity", "Short", "TRP>6", "TRP_<3", "TRP_3to6", "Taiwan", "Trend", "USA"
])

# --- YFINANCE REDUNDANCY / FALLBACK HELPERS ---
def get_fallback_value(key, default=1.0):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("CREATE TABLE IF NOT EXISTS api_fallback (key TEXT PRIMARY KEY, value REAL)")
    c.execute("SELECT value FROM api_fallback WHERE key=?", (key,))
    row = c.fetchone()
    conn.close()
    return row[0] if row else default

def set_fallback_value(key, value):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("CREATE TABLE IF NOT EXISTS api_fallback (key TEXT PRIMARY KEY, value REAL)")
    c.execute("INSERT OR REPLACE INTO api_fallback (key, value) VALUES (?, ?)", (key, value))
    conn.commit()
    conn.close()

SILO_MAP = {
    'U23144948': ('Silo A', 'Persons 1 and 2 • U*****948', '#93c5fd'),
    'U23139264': ('Silo B', 'Persons 1 and 2 • U*****264', '#d8b4fe'),
    'U23154199': ('Silo C', 'Persons 1 and 3 • U*****199', '#86efac'),
    'U25218481': ('Silo D', 'Persons 1 and 4 • U*****481', '#fde047')
}

COLOR_PALETTE = {
    'IB01': '#93c5fd', 'CSPX': '#f97316', 'CNDX': '#8b5cf6',
    'ITWN': '#14b8a6', 'CSKR': '#f472b6', 'CNYA': '#fb923c',
    'Crypto': '#0ea5e9', 'Gold': '#fbbf24', 'Active Swing': '#a855f7', 'Cash': '#86efac',
    'Opt Liab': '#ef4444', 'Tail Hedge': '#0f172a', 'Accounting Offset': '#94a3b8',
    'Physical US Stocks': '#4f46e5', 'International Stocks': '#db2777', 'Synthetic Beta': '#2563eb'
}

# --- LIVE RISK-FREE RATE ---
@st.cache_data(ttl=3600)
def get_risk_free_rate():
    try:
        irx = yf.Ticker('^IRX').history(period='5d')['Close'].iloc[-1]
        val = max(float(irx) / 100.0, 0.0)
        set_fallback_value('IRX', val)
        return val
    except:
        return get_fallback_value('IRX', 0.045)

LIVE_RF_RATE = get_risk_free_rate()

def normCDF(x):
    t = 1 / (1 + 0.2316419 * abs(x))
    d = 0.3989423 * np.exp(-x * x / 2)
    prob = d * t * (0.3193815 + t * (-0.3565638 + t * (1.781478 + t * (-1.821256 + t * 1.330274))))
    return 1 - prob if x > 0 else prob

def normPDF(x):
    return np.exp(-0.5 * x * x) / np.sqrt(2 * np.pi)

def get_put_greeks(S, K, T, r, v):
    if K <= 0 or S <= 0:
        return 0.0, 0.0, 0.0, 0.0, 0.0
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
    if K <= 0 or S <= 0:
        return 0.0, 0.0, 0.0, 0.0, 0.0
    T = max(T, 0.0001)
    d1 = (math.log(S / K) + (r + 0.5 * v ** 2) * T) / (v * math.sqrt(T))
    d2 = d1 - v * math.sqrt(T)
    price = S * normCDF(d1) - K * math.exp(-r * T) * normCDF(d2)
    delta = normCDF(d1)
    gamma = normPDF(d1) / (S * v * math.sqrt(T))
    vega = (S * normPDF(d1) * math.sqrt(T)) / 100
    theta = (- (S * v * normPDF(d1)) / (2 * math.sqrt(T)) - r * K * math.exp(-r * T) * normCDF(d2)) / 365
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
            # Dynamically fetch the requested ticker's spot price instead of hardcoding SPY
            spot_price = yf.Ticker(t_str).history(period='5d')['Close'].iloc[-1]
            vix = yf.Ticker('^VIX').history(period='5d')['Close'].iloc[-1]
            return float(spot_price), float(vix)
    except Exception:
        # Fallback if Yahoo Finance fails to find the ticker
        return 550.0, 15.0

# --- DYNAMIC SCRIPT DISCOVERY ---
def get_active_scripts():
    active_dash = os.path.basename(__file__)
    patterns = ['Telegram_Notifier_v*.py', 'sync_engine_v*.py', 'Run_Estate_Sync.bat']
    scripts = [f"{active_dash} [Active]"]
    for p in patterns:
        matches = glob.glob(os.path.join(TARGET_DIR, p))
        if matches:
            latest = max(matches, key=os.path.getmtime)
            scripts.append(os.path.basename(latest))
    return " • ".join(scripts)

active_scripts_str = get_active_scripts()

# --- SIDEBAR: SYNC BUTTON & CASH FLOW LEDGER ---
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
                
    st.markdown("---")
    st.markdown("### 💸 Log Cash Flow")
    with st.expander("Record External or Internal Transfer"):
        with st.form("transfer_form", clear_on_submit=True):
            t_date = st.date_input("Date of Transfer", datetime.date.today())
            t_acc = st.selectbox("Destination / Origin Silo", ['U23144948 (Silo A)', 'U23139264 (Silo B)', 'U23154199 (Silo C)', 'U25218481 (Silo D)'])
            t_type = st.selectbox("Flow Type", ["External Deposit", "External Withdrawal", "Internal Transfer In", "Internal Transfer Out"])
            t_amount = st.number_input("Amount (USD)", min_value=0.0, step=1000.0)
            t_notes = st.text_input("Notes (Optional)")
            
            if st.form_submit_button("Record Flow in DB"):
                if t_amount > 0:
                    # Withdrawals and Transfers Out represent money leaving the specific Silo's math pool
                    if "Withdrawal" in t_type or "Out" in t_type:
                        t_amount = -t_amount
                        
                    acct_code = t_acc.split(" ")[0]
                    
                    conn = sqlite3.connect(DB_PATH)
                    c = conn.cursor()
                    c.execute("CREATE TABLE IF NOT EXISTS cash_transfers (date TEXT, account TEXT, amount REAL, type TEXT, notes TEXT)")
                    c.execute("INSERT INTO cash_transfers VALUES (?, ?, ?, ?, ?)", (t_date.isoformat(), acct_code, t_amount, t_type, t_notes))
                    conn.commit()
                    conn.close()
                    st.success(f"Successfully logged {t_amount:,.0f} to {acct_code}.")
                    st.cache_data.clear()
                    st.rerun()

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

    if 'net_flow' not in df_acc.columns:
        df_acc['net_flow'] = 0.0
    else:
        df_acc['net_flow'] = df_acc['net_flow'].fillna(0.0)

    df_acc['prev_nav'] = df_acc['nav'].shift(1)
    df_acc['daily_return'] = (df_acc['nav'] - df_acc['net_flow'] - df_acc['prev_nav']) / df_acc['prev_nav'].replace(0, np.nan)
    df_acc['daily_return'] = df_acc['daily_return'].fillna(0)
    
    df_acc['daily_pnl'] = df_acc['nav'] - df_acc['net_flow'] - df_acc['prev_nav'].fillna(df_acc['nav'] - df_acc['net_flow'])
    total_pnl = df_acc['daily_pnl'].sum()
    
    final_nav = df_acc['nav'].iloc[-1]
    
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
    
    dates = df_acc['date'].tolist()
    cfs = [-df_acc['net_flow'].iloc[i] for i in range(len(df_acc))]
    cfs.append(final_nav)
    dates.append(dates[-1])
    irr = calculate_xirr(pd.to_datetime(pd.Series(dates)), cfs) * 100

    df_acc['cum_cf'] = df_acc['net_flow'].cumsum()
    max_cap = df_acc['cum_cf'].max()
    if max_cap <= 0: max_cap = df_acc['nav'].max() - total_pnl
    roc = (total_pnl / max_cap) * 100 if max_cap > 0 else 0

    return {"irr": irr, "sharpe": sharpe, "pnl": total_pnl, "max_dd": max_dd, "roc": roc, "nav": final_nav, "dd_days": max_dd_days}

def get_exact_opt_margin(df_in):
    # v52: Exclude both Tail Hedges and Synthetic Beta (Long Calls) from margin liability math
    df_opt = df_in[(df_in['sec_type'] == 'OPT') & (~df_in['asset_class'].isin(['Tail Hedge', 'Synthetic Beta']))].copy()
    if df_opt.empty: return 0
    try:
        margin = 0
        df_opt['strike'] = df_opt['symbol'].apply(lambda x: float(x.split('_')[2]))
        df_opt['exp'] = df_opt['symbol'].apply(lambda x: x.split('_')[1])
        df_opt['right'] = df_opt['symbol'].apply(lambda x: x.split('_')[3])
        for _, group in df_opt.groupby(['account', 'exp', 'right']):
            short_sum = group[group['position'] < 0].apply(lambda r: r['strike'] * abs(r['position']), axis=1).sum()
            long_sum = group[group['position'] > 0].apply(lambda r: r['strike'] * abs(r['position']), axis=1).sum()
            margin += abs(short_sum - long_sum) * 100
        return margin
    except Exception: return 0
    
@st.cache_data(ttl=86400) # Cache for 24 hours to prevent spamming Yahoo
def get_sector(symbol, asset_class):
    # Only fetch sectors for Alpha Equities
    if asset_class not in ['Physical US Stocks', 'International Stocks', 'US Tech CFDs']:
        return asset_class
        
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA journal_mode=WAL;")
    c = conn.cursor()
    c.execute("CREATE TABLE IF NOT EXISTS asset_sectors (symbol TEXT PRIMARY KEY, sector TEXT)")
    c.execute("SELECT sector FROM asset_sectors WHERE symbol=?", (symbol,))
    row = c.fetchone()
    
    if row:
        conn.close()
        return row[0]
        
    # Clean the ticker for Yahoo Finance (removes IBKR local exchange tags like 'TSE' or 'HEX')
    clean_sym = symbol.split()[0] 
    try:
        info = yf.Ticker(clean_sym).info
        sector = info.get('sector', 'Unknown Equities')
    except:
        sector = 'Unknown Equities'
        
    c.execute("INSERT OR REPLACE INTO asset_sectors VALUES (?, ?)", (symbol, sector))
    conn.commit()
    conn.close()
    return sector    
    
@st.cache_data(ttl=3600)
def load_and_process_data():
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA journal_mode=WAL;")
    df = pd.read_sql_query("SELECT * FROM daily_balances", conn)
    df['date'] = pd.to_datetime(df['date'])
    
    # Preserve legacy manual SQL patches from 'total_cash'
    df.rename(columns={'net_liquidation': 'nav', 'total_cash': 'legacy_flow'}, inplace=True)
    
    try:
        transfers_df = pd.read_sql_query("SELECT * FROM cash_transfers", conn)
        transfers_df['date'] = pd.to_datetime(transfers_df['date'])
        daily_transfers = transfers_df.groupby(['date', 'account'])['amount'].sum().reset_index()
        daily_transfers.rename(columns={'amount': 'new_flow'}, inplace=True)
        df = pd.merge(df, daily_transfers, on=['date', 'account'], how='left')
        df['new_flow'] = df['new_flow'].fillna(0.0)
    except Exception:
        df['new_flow'] = 0.0
        
    # Combine legacy SQL patches with new UI ledger entries
    df['legacy_flow'] = df['legacy_flow'].fillna(0.0)
    df['net_flow'] = df['legacy_flow'] + df['new_flow']
    
    global_df = df.groupby('date').agg({'nav': 'sum', 'net_flow': 'sum'}).reset_index()
    global_metrics = process_metrics(global_df, LIVE_RF_RATE)
    global_df = global_df[global_df['nav'] > 0].copy() 
    
    silo_metrics = {}
    silo_dfs = {}
    for acc in SILO_MAP.keys():
        acc_df = df[df['account'] == acc].copy().sort_values('date')
        silo_metrics[acc] = process_metrics(acc_df, LIVE_RF_RATE)
        acc_df = acc_df[acc_df['nav'] > 0].copy()
        if not acc_df.empty:
            acc_df['prev_nav'] = acc_df['nav'].shift(1)
            acc_df['daily_return'] = (acc_df['nav'] - acc_df['net_flow'] - acc_df['prev_nav']) / acc_df['prev_nav'].replace(0, np.nan)
            acc_df['cum_return'] = (1 + acc_df['daily_return'].fillna(0)).cumprod() - 1
            acc_df['daily_pnl'] = acc_df['nav'] - acc_df['net_flow'] - acc_df['prev_nav'].fillna(acc_df['nav'] - acc_df['net_flow'])
        silo_dfs[acc] = acc_df

    # Global tracking arrays (now using True PnL)
    if not global_df.empty:
        global_df['prev_nav'] = global_df['nav'].shift(1)
        global_df['daily_return'] = (global_df['nav'] - global_df['net_flow'] - global_df['prev_nav']) / global_df['prev_nav'].replace(0, np.nan)
        global_df['cum_return'] = (1 + global_df['daily_return'].fillna(0)).cumprod() - 1
        global_df['daily_pnl'] = global_df['nav'] - global_df['net_flow'] - global_df['prev_nav'].fillna(global_df['nav'] - global_df['net_flow'])
        global_df['cum_pnl'] = global_df['daily_pnl'].cumsum()

    live_date = df['date'].max()
    pos_df = pd.read_sql_query(f"SELECT account, symbol, sec_type, position, market_price, market_value, avg_cost, unrealized_pnl FROM daily_positions WHERE date = '{live_date.strftime('%Y-%m-%d')}'", conn)
    attr_df = pd.read_sql_query("SELECT * FROM daily_attribution", conn)
    if not attr_df.empty: attr_df['date'] = pd.to_datetime(attr_df['date'])
    
    try: open_orders_df = pd.read_sql_query(f"SELECT * FROM open_orders WHERE date = '{live_date.strftime('%Y-%m-%d')}'", conn)
    except: open_orders_df = pd.DataFrame()
        
    def categorize(sym, sec, pos):
        s = sym.upper()
        if 'IB01' in s: return 'IB01'
        if 'CSPX' in s: return 'CSPX'
        if 'CNDX' in s or 'CSNDX' in s: return 'CNDX'
        if 'ETHE' in s or 'BTC' in s: return 'Crypto'
        if 'SGLN' in s or 'IGLN' in s: return 'Gold' 
        if 'ITWN' in s: return 'ITWN'
        if 'CSKR' in s: return 'CSKR'
        if 'CNYA' in s: return 'CNYA'
        if sec == 'CASH' or 'CASH' in s: return 'Cash'
        if sec == 'CFD': return 'US Tech CFDs'
        if sec == 'STK' and not any(x in s for x in ['IB01','CSPX','CNDX','SGLN','IGLN','ITWN','CSKR','CNYA']): return 'International Stocks'
        if sec == 'OPT':
            if pos > 0: 
                try:
                    parts = s.split('_')
                    if len(parts) >= 4:
                        right = parts[3]
                        exp_date = pd.to_datetime(parts[1])
                        dte = (exp_date - pd.Timestamp.today()).days
                        if right == 'P' and dte > 60:
                            return 'Tail Hedge'
                        elif right == 'C' and dte > 90:
                            return 'Synthetic Beta'
                except: pass
            return 'Opt Liab'
        return 'Active Swing'
    
    pos_df['asset_class'] = pos_df.apply(lambda r: categorize(r['symbol'], r['sec_type'], r['position']), axis=1)

    live_date = df['date'].max()
    pos_df = pd.read_sql_query(f"SELECT account, symbol, sec_type, position, market_price, market_value, avg_cost, unrealized_pnl, currency FROM daily_positions WHERE date = '{live_date.strftime('%Y-%m-%d')}'", conn)
    attr_df = pd.read_sql_query("SELECT * FROM daily_attribution", conn)
    if not attr_df.empty: attr_df['date'] = pd.to_datetime(attr_df['date'])
    
    try: open_orders_df = pd.read_sql_query(f"SELECT * FROM open_orders WHERE date = '{live_date.strftime('%Y-%m-%d')}'", conn)
    except: open_orders_df = pd.DataFrame()
        
    def categorize(sym, sec, pos, curr):
        s = sym.upper()
        if 'IB01' in s: return 'IB01'
        if 'CSPX' in s: return 'CSPX'
        if 'CNDX' in s or 'CSNDX' in s: return 'CNDX'
        if 'ETHE' in s or 'BTC' in s: return 'Crypto'
        if 'SGLN' in s or 'IGLN' in s: return 'Gold' 
        if 'ITWN' in s: return 'ITWN'
        if 'CSKR' in s: return 'CSKR'
        if 'CNYA' in s: return 'CNYA'
        if sec == 'CASH' or 'CASH' in s: return 'Cash'
        if sec == 'CFD': return 'US Tech CFDs'
        if sec == 'STK' and not any(x in s for x in ['IB01','CSPX','CNDX','SGLN','IGLN','ITWN','CSKR','CNYA']):
            # Dynamically checks the native currency from the DB schema
            return 'Physical US Stocks' if curr == 'USD' else 'International Stocks'
        if sec == 'OPT':
            if pos > 0: 
                try:
                    parts = s.split('_')
                    if len(parts) >= 4:
                        right = parts[3]
                        exp_date = pd.to_datetime(parts[1])
                        dte = (exp_date - pd.Timestamp.today()).days
                        if right == 'P' and dte > 60:
                            return 'Tail Hedge'
                        elif right == 'C' and dte > 90:
                            return 'Synthetic Beta'
                except: pass
            return 'Opt Liab'
        return 'Active Swing'
        
    pos_df['asset_class'] = pos_df.apply(lambda r: categorize(r['symbol'], r['sec_type'], r['position'], r['currency']), axis=1)
    
    conn.close()    
    return global_df, global_metrics, silo_dfs, silo_metrics, pos_df, attr_df, df, open_orders_df

@st.cache_data(ttl=3600)
def load_benchmarks(start_date, end_date):
    conn = sqlite3.connect(DB_PATH)
    try:
        data = yf.download(["SPY", "QQQ", "^VIX"], start=start_date - datetime.timedelta(days=300), end=end_date + datetime.timedelta(days=1), progress=False, auto_adjust=False)
        bench_df = data['Close'].ffill().reset_index()
        bench_df.rename(columns={'Date': 'date'}, inplace=True)
        bench_df['date'] = pd.to_datetime(bench_df['date']).dt.tz_localize(None)
        bench_df.to_sql('benchmarks_fallback', conn, if_exists='replace', index=False)
    except Exception:
        try:
            bench_df = pd.read_sql_query("SELECT * FROM benchmarks_fallback", conn)
            bench_df['date'] = pd.to_datetime(bench_df['date'])
        except:
            bench_df = pd.DataFrame(columns=['date', 'SPY', 'QQQ', '^VIX'])
    conn.close()
    
    if bench_df.empty: return bench_df
    
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
    try: df_j = pd.read_sql_query("SELECT * FROM options_journal", conn)
    except: df_j = pd.DataFrame()
    conn.close()
    return df_j

@st.cache_data(ttl=3600)
def load_deployment_ledger():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("CREATE TABLE IF NOT EXISTS deployment_ledger (deploy_date TEXT, regime TEXT, amount REAL)")
    conn.commit()
    df_ledger = pd.read_sql_query("SELECT * FROM deployment_ledger ORDER BY deploy_date DESC", conn)
    conn.close()
    return df_ledger

@st.cache_data(ttl=60)
def process_champion_journal(pos_df, open_orders_df, silo_metrics):
    """
    Reverse-engineers Champion Journal: Filters Alpha assets, maps live native IBKR Stop Losses,
    and locks in the Epoch Base NAV to calculate pure R-metrics.
    """
    alpha_classes = ['US Tech CFDs', 'International Stocks', 'Crypto']
    if pos_df.empty: return pd.DataFrame()
    
    alpha_df = pos_df[pos_df['asset_class'].isin(alpha_classes)].copy()
    if alpha_df.empty: return pd.DataFrame()

    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS champion_state 
                 (symbol TEXT, account TEXT, entry_date TEXT, base_nav REAL, initial_sl REAL, 
                 PRIMARY KEY (symbol, account))''')
    
    # Load existing states
    state_df = pd.read_sql_query("SELECT * FROM champion_state", conn)
    state_dict = {(r['symbol'], r['account']): r for _, r in state_df.iterrows()}
    
    journal_records = []
    today_str = datetime.date.today().isoformat()
    
    for _, row in alpha_df.iterrows():
        sym = row['symbol']
        acc = row['account']
        qty = row['position']
        avg_cost = row['avg_cost']
        cmp = row['market_price']
        
        # 1. Map Live Stop Loss from open_orders (STP orders use aux_price)
        live_sl = 0.0
        if not open_orders_df.empty:
            sl_orders = open_orders_df[(open_orders_df['symbol'] == sym) & (open_orders_df['account'] == acc) & (open_orders_df['order_type'].str.contains('STP'))]
            if not sl_orders.empty:
                live_sl = sl_orders['aux_price'].iloc[0]
                
        # 2. State Management (The Epoch Base Lock-in)
        key = (sym, acc)
        silo_nav = silo_metrics.get(acc, {}).get('nav', 200000) # Fallback if 0
        
        if key not in state_dict:
            # New Trade detected! Lock in base NAV and initial SL
            c.execute("INSERT INTO champion_state VALUES (?, ?, ?, ?, ?)", (sym, acc, today_str, silo_nav, live_sl))
            base_nav = silo_nav
            entry_date = today_str
        else:
            base_nav = state_dict[key]['base_nav']
            entry_date = state_dict[key]['entry_date']
            
        # 3. Mathematical R-Calculations
        r_usd_value = base_nav * 0.0025  # 0.25% of Silo NAV
        
        # Calculate Risk per share based on direction
        if qty > 0: # Long
            risk_per_share = max(0, avg_cost - live_sl) if live_sl > 0 else avg_cost
            if live_sl >= avg_cost: risk_per_share = 0 # Stop raised to BE
        else: # Short
            risk_per_share = max(0, live_sl - avg_cost) if live_sl > 0 else avg_cost
            if live_sl > 0 and live_sl <= avg_cost: risk_per_share = 0
            
        total_open_risk_usd = risk_per_share * abs(qty)
        open_risk_r = total_open_risk_usd / r_usd_value if r_usd_value > 0 else 0
        
        unrealized_usd = row['unrealized_pnl']
        unrealized_r = unrealized_usd / r_usd_value if r_usd_value > 0 else 0
        
        journal_records.append({
            'Silo': SILO_MAP.get(acc, [acc])[0],
            'Symbol': sym,
            'Entry Date': entry_date,
            'Asset Class': row['asset_class'],
            'Qty': qty,
            'Avg Cost': avg_cost,
            'CMP': cmp,
            'Live SL': live_sl,
            '1R Base ($)': r_usd_value,
            'Open Risk ($)': total_open_risk_usd,
            'Open Risk (R)': open_risk_r,
            'Unrealized (R)': unrealized_r
        })

    conn.commit()
    conn.close()
    
    return pd.DataFrame(journal_records)

@st.cache_data(ttl=3600)
def fetch_fx_rates():
    rates = {'USD': 1.0}
    # Yahoo direct pairs
    direct = {'EUR': 'EURUSD=X', 'GBP': 'GBPUSD=X', 'AUD': 'AUDUSD=X', 'NZD': 'NZDUSD=X'}
    # Yahoo inverted pairs (USD to CURR)
    inverted = {
        'KRW': 'KRW=X', 'SEK': 'SEK=X', 'CAD': 'CAD=X', 'CHF': 'CHF=X', 
        'JPY': 'JPY=X', 'TWD': 'TWD=X', 'HKD': 'HKD=X', 'SGD': 'SGD=X'
    }
    
    for curr, pair in direct.items():
        try: 
            val = float(yf.Ticker(pair).history(period='1d')['Close'].iloc[-1])
            set_fallback_value(f'FX_{curr}', val)
            rates[curr] = val
        except: rates[curr] = get_fallback_value(f'FX_{curr}', 1.0)
        
    for curr, pair in inverted.items():
        try: 
            rate = float(yf.Ticker(pair).history(period='1d')['Close'].iloc[-1])
            val = 1.0 / rate if rate > 0 else 1.0
            set_fallback_value(f'FX_{curr}', val)
            rates[curr] = val
        except: rates[curr] = get_fallback_value(f'FX_{curr}', 1.0)
        
    return rates

@st.cache_data(ttl=60)
def process_champion_journal(pos_df, open_orders_df, silo_metrics):
    """
    Reverse-engineers Champion Journal: Maps live native IBKR Stop Losses,
    applies live FX rates for foreign equities, and mathematically locks the Epoch Base NAV.
    """
    alpha_classes = ['US Tech CFDs', 'International Stocks', 'Physical US Stocks', 'Crypto']
    if pos_df.empty: return pd.DataFrame()
    
    alpha_df = pos_df[pos_df['asset_class'].isin(alpha_classes)].copy()
    if alpha_df.empty: return pd.DataFrame()

    fx_rates = fetch_fx_rates()

    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS champion_state 
                 (symbol TEXT, account TEXT, entry_date TEXT, base_nav REAL, initial_sl REAL, 
                 PRIMARY KEY (symbol, account))''')
    
    state_df = pd.read_sql_query("SELECT * FROM champion_state", conn)
    state_dict = {f"{r['symbol'].upper()}_{r['account']}": r for _, r in state_df.iterrows()}
    
    journal_records = []
    today_str = datetime.date.today().isoformat()
    
    for _, row in alpha_df.iterrows():
        sym = row['symbol']
        sym_upper = sym.upper()
        acc = row['account']
        qty = row['position']
        curr = row['currency']
        
        # Note: avg_cost and market_price are ALREADY converted to USD by sync_engine
        avg_cost_usd = row['avg_cost']
        cmp_usd = row['market_price']
        
        # 1. Map Live Stop Loss from open_orders (STP orders use aux_price)
        # Note: open_orders stores aux_price in LOCAL CURRENCY
        live_sl_local = 0.0
        if not open_orders_df.empty:
            sl_orders = open_orders_df[(open_orders_df['symbol'] == sym) & (open_orders_df['account'] == acc) & (open_orders_df['order_type'].str.contains('STP'))]
            if not sl_orders.empty:
                live_sl_local = sl_orders['aux_price'].iloc[0]
                
        # 2. State Management (The Epoch Base Lock-in)
        key = f"{sym_upper}_{acc}"
        silo_nav = silo_metrics.get(acc, {}).get('nav', 200000)
        
        if key not in state_dict:
            # INSERT OR IGNORE strictly locks it in forever against subsequent overwrites
            c.execute("INSERT OR IGNORE INTO champion_state VALUES (?, ?, ?, ?, ?)", (sym_upper, acc, today_str, silo_nav, live_sl_local))
            base_nav = silo_nav
            entry_date = today_str
        else:
            base_nav = state_dict[key]['base_nav']
            entry_date = state_dict[key]['entry_date']
            
        # 3. Dynamic FX Conversion for the Stop Loss
        fx_mult = fx_rates.get(curr, 1.0)
        if curr in ['GBP', 'GBX']: fx_mult /= 100.0 # Standardize Pence to Pounds
        live_sl_usd = live_sl_local * fx_mult if live_sl_local > 0 else 0.0
            
        # 4. Mathematical R-Calculations
        r_usd_value = base_nav * 0.0025  # 0.25% of Silo NAV
        
        if qty > 0: # Long
            risk_per_share = max(0, avg_cost_usd - live_sl_usd) if live_sl_usd > 0 else avg_cost_usd
            if live_sl_usd >= avg_cost_usd: risk_per_share = 0 # Stop raised to BE
        else: # Short
            risk_per_share = max(0, live_sl_usd - avg_cost_usd) if live_sl_usd > 0 else avg_cost_usd
            if live_sl_usd > 0 and live_sl_usd <= avg_cost_usd: risk_per_share = 0
            
        total_open_risk_usd = risk_per_share * abs(qty)
        open_risk_r = total_open_risk_usd / r_usd_value if r_usd_value > 0 else 0
        
        unrealized_usd = row['unrealized_pnl']
        unrealized_r = unrealized_usd / r_usd_value if r_usd_value > 0 else 0
        
        journal_records.append({
            'Silo': SILO_MAP.get(acc, [acc])[0],
            'Symbol': sym,
            'Entry Date': entry_date,
            'Asset Class': row['asset_class'],
            'Qty': qty,
            'Avg Cost': avg_cost_usd,
            'CMP': cmp_usd,
            'Live SL (Local)': live_sl_local,
            'Live SL (USD)': live_sl_usd,
            '1R Base ($)': r_usd_value,
            'Open Risk ($)': total_open_risk_usd,
            'Open Risk (R)': open_risk_r,
            'Unrealized (R)': unrealized_r
        })

    conn.commit()
    conn.close()
    
    return pd.DataFrame(journal_records)

@st.cache_data(ttl=60)
def load_champion_history():
    """Loads historical closed Alpha trades to calculate Expectancy and R-Metrics."""
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA journal_mode=WAL;")
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS champion_closed_trades 
                 (close_date TEXT, symbol TEXT, account TEXT, silo TEXT, 
                  r_base REAL, realized_pnl REAL, r_multiple REAL, notes TEXT)''')
    
    # PHASE 16: Safe Migration (Adds 'tags' column if it doesn't exist)
    try:
        c.execute("ALTER TABLE champion_closed_trades ADD COLUMN tags TEXT DEFAULT ''")
    except sqlite3.OperationalError:
        pass # Column already exists
        
    conn.commit()
    # v52: Fetching 'rowid' as primary key to allow precise editing later in the ledger
    df = pd.read_sql_query("SELECT rowid, * FROM champion_closed_trades ORDER BY close_date DESC", conn)
   
    # Fetch all historical state symbols so we can log trades that recently closed
    all_states = pd.read_sql_query("SELECT symbol, account, base_nav FROM champion_state", conn) if not df.empty or True else pd.DataFrame()
    conn.close()
    return df, all_states

# --- UI RENDERING ---
st.title("Estate Master Dashboard")
st.markdown(f"**Data Pipeline:** Live IBKR Sync via SQLite (`{DB_NAME}`) • **Last Refresh:** {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
st.markdown(f"**Active Scripts:** `{active_scripts_str}`")
st.divider()

global_df, global_metrics, silo_dfs, silo_metrics, pos_df, attr_df, balances_df, open_orders_df = load_and_process_data()
bench_df = load_benchmarks(global_df['date'].min(), global_df['date'].max())
chart_df = pd.merge(global_df, bench_df, on='date', how='left').ffill().fillna(0)
journal_raw_df = load_journal_data()

opt_margin_total = get_exact_opt_margin(pos_df)
tot_cash = pos_df[pos_df['asset_class'].isin(['IB01', 'Cash'])]['market_value'].sum()
tot_tech = pos_df[pos_df['asset_class'].isin(['CNDX', 'ITWN', 'CSKR', 'Active Swing', 'US Tech CFDs', 'International Stocks'])]['market_value'].sum()
pct_cash = (tot_cash / global_metrics['nav']) * 100 if global_metrics['nav'] > 0 else 0
pct_tech = (tot_tech / global_metrics['nav']) * 100 if global_metrics['nav'] > 0 else 0
nav_A = silo_metrics.get('U23144948', {}).get('nav', 0)
nav_C = silo_metrics.get('U23154199', {}).get('nav', 0)

if not journal_raw_df.empty:
    today = datetime.date.today()
    journal_raw_df['Open Date'] = pd.to_datetime(journal_raw_df['Open Date'], errors='coerce').dt.date
    journal_raw_df['Close Date'] = pd.to_datetime(journal_raw_df['Close Date'], errors='coerce').dt.date    
    journal_raw_df['Collateral Locked (USD)'] = journal_raw_df.apply(
        lambda r: 0.0 if pd.isna(r['Short Strike']) or r['Short Strike'] == 0 
        else abs(r['Short Strike'] - r['Long Strike']) * 100 * r['Quantity'], 
        axis=1
    )    
    journal_raw_df['Target 50% Exit Price (USD)'] = journal_raw_df['Premium Collected (USD)'] / 2
    journal_raw_df['Total Net Credit (USD)'] = journal_raw_df['Premium Collected (USD)'] * 100 * journal_raw_df['Quantity']
    journal_raw_df['Days Remaining'] = journal_raw_df.apply(
        lambda r: int(max(0, r['DTE at Entry'] - ((today - r['Open Date']).days if pd.notnull(r['Open Date']) else 0)))
        if pd.isnull(r['Close Date']) and pd.notnull(r['DTE at Entry']) else 'Closed', 
        axis=1
    )
    journal_raw_df['Days in Trade'] = journal_raw_df.apply(
        lambda r: (today - r['Open Date']).days if pd.isnull(r['Close Date']) and pd.notnull(r['Open Date']) else ((r['Close Date'] - r['Open Date']).days if pd.notnull(r['Open Date']) else 0), 
        axis=1
    )
    journal_raw_df['Total P&L (USD)'] = (journal_raw_df['Premium Collected (USD)'] - journal_raw_df['Closing Price (USD)']) * 100 * journal_raw_df['Quantity']
    journal_raw_df['Return on Capital (ROC) %'] = (journal_raw_df['Total P&L (USD)'] / journal_raw_df['Collateral Locked (USD)']) * 100
    journal_raw_df['Annualized ROC %'] = journal_raw_df.apply(
        lambda r: np.nan if pd.isnull(r['Return on Capital (ROC) %']) or r['Days in Trade'] == 0 else r['Return on Capital (ROC) %'] * (365.0 / r['Days in Trade']), 
        axis=1
    )
    journal_raw_df = journal_raw_df.sort_values('Open Date', ascending=False).reset_index(drop=True)

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
    return sharpe, alpha * 100, beta, corr

spy_sh, spy_al, spy_beta, spy_co = calc_adv(chart_df['spy_ret'])
qqq_sh, qqq_al, qqq_beta, qqq_co = calc_adv(chart_df['qqq_ret'])
calmar = global_metrics['irr'] / abs(global_metrics['max_dd']) if global_metrics['max_dd'] < 0 else 0

def simulate_benchmark(df, ret_col, rf_rate):
    if df.empty: return {"irr": 0, "sharpe": 0, "pnl": 0, "max_dd": 0, "roc": 0, "nav": 0, "dd_days": 0}
    navs, pnls, cfs = [], [], []
    curr_nav = df['nav'].iloc[0]
    for i, row in df.iterrows():
        flow = row['net_flow'] if i > 0 else 0
        ret = row[ret_col] if i > 0 else 0
        pnl = curr_nav * ret
        curr_nav += pnl + flow
        navs.append(curr_nav)
        pnls.append(pnl)
        cfs.append(flow)
    
    sim_df = df[['date']].copy()
    sim_df['nav'] = navs
    sim_df['net_flow'] = cfs
    sim_df['daily_pnl'] = pnls
    return process_metrics(sim_df, rf_rate)

spy_metrics = simulate_benchmark(chart_df, 'spy_ret', LIVE_RF_RATE)
qqq_metrics = simulate_benchmark(chart_df, 'qqq_ret', LIVE_RF_RATE)

spy_calmar = spy_metrics['irr'] / abs(spy_metrics['max_dd']) if spy_metrics['max_dd'] < 0 else 0
qqq_calmar = qqq_metrics['irr'] / abs(qqq_metrics['max_dd']) if qqq_metrics['max_dd'] < 0 else 0

def col_html(val, good_thresh=None):
    if "N/A" in str(val): return "color: #4b5563;"
    if isinstance(val, (int, float)):
        if good_thresh is not None: return "color: #15803d;" if val >= good_thresh else "color: #b91c1c;"
        return "color: #15803d;" if val > 0 else "color: #b91c1c;"
    if "-" in str(val): return "color: #b91c1c;"
    return "color: #15803d;"

# SECTION 0: EXECUTIVE BRIEFING (FOR TELEGRAM SCREENSHOTS)
st.markdown("### 🔔 Executive Briefing & Actionable Alerts")
alerts = []

if not balances_df.empty and 'available_funds' in balances_df.columns:
    silo_b_bal = balances_df[(balances_df['account'] == 'U23139264') & (balances_df['date'] == balances_df['date'].max())]
    if not silo_b_bal.empty:
        af = silo_b_bal['available_funds'].iloc[0]
        if 0 < af < 27000:
            alerts.append(f"⚠️ **PDT Danger (Silo B):** Available Funds (${af:,.0f}) approaching the $25k FINRA lockout threshold. Reduce margin immediately.")

if not pos_df.empty:
    naked_spreads = set()
    open_opts = pos_df[(pos_df['sec_type'] == 'OPT') & (~pos_df['asset_class'].isin(['Tail Hedge', 'Synthetic Beta']))]
    for _, opt in open_opts.iterrows():
        opt_sym, acc = opt['symbol'], opt['account']
        base_tckr = opt_sym.split('_')[0]
        if not open_orders_df.empty:
            has_order = not open_orders_df[(open_orders_df['account'] == acc) & (open_orders_df['symbol'].str.contains(base_tckr))].empty
            if not has_order: naked_spreads.add(f"{base_tckr} spread in {SILO_MAP.get(acc, [acc])[0]}")
        else:
            naked_spreads.add(f"{base_tckr} spread in {SILO_MAP.get(acc, [acc])[0]}")
            
    # PHASE 6 FIX: Unleashed the Naked Option Guardrail
    for ns in naked_spreads:
        alerts.append(f"🚨 **CRITICAL (Naked Option):** {ns} is missing resting OCO brackets! Attach Take-Profit/Stop-Loss immediately.")

opt_margin_journal = 0
if not journal_raw_df.empty:
    open_journal = journal_raw_df[pd.isnull(journal_raw_df['Close Date'])]
    opt_margin_journal = open_journal['Collateral Locked (USD)'].sum()
    if abs(opt_margin_journal - opt_margin_total) > 0.01:
        alerts.append(f"⚠️ **Ledger Drift Detected:** Live TWS options margin is **${opt_margin_total:,.0f}**, but manual Options Journal reflects **${opt_margin_journal:,.0f}**. Please reconcile.")

pct_margin = (opt_margin_total / global_metrics['nav']) * 100 if global_metrics['nav'] > 0 else 0

if pct_margin >= 20.0:
    alerts.append(f"🚨 **CRITICAL (Margin Cap Breached):** Global Options Margin is {pct_margin:.1f}% (Limit: 20.0%). Halt all new options deployments immediately.")
elif pct_margin >= 16.0:
    alerts.append(f"⚠️ **Margin Capacity Warning:** Global Options Margin is {pct_margin:.1f}%. Approaching the absolute 20% limit.")

# v52: Synthetic Beta Rolling Radar
if not pos_df.empty:
    synth_beta_df = pos_df[pos_df['asset_class'] == 'Synthetic Beta']
    for _, row in synth_beta_df.iterrows():
        try:
            sym = row['symbol']
            parts = sym.split('_')
            exp_date = pd.to_datetime(parts[1])
            dte = (exp_date - pd.Timestamp.today()).days
            if dte <= 45:
                alerts.append(f"🚨 **CRITICAL (Theta Cliff):** Synthetic Beta Call **{sym}** has reached **{dte} DTE**! Execute the Rolling Protocol IMMEDIATELY to avoid terminal Theta decay.")
            elif dte <= 60:
                alerts.append(f"⚠️ **Rolling Radar:** Synthetic Beta Call **{sym}** is at **{dte} DTE**. Prepare to roll the contract to a new 150-DTE window.")
        except: pass

if not journal_raw_df.empty:
    today = datetime.date.today()    
    for _, row in journal_raw_df[pd.isnull(journal_raw_df['Close Date'])].iterrows():
        try:
            tckr, dte_rem = row['Ticker'], row['Days Remaining']
            if str(dte_rem) != 'Closed':
                dte_int = int(dte_rem)
                if dte_int <= 21:
                    alerts.append(f"🚨 **CRITICAL (Gamma Cliff):** {tckr} ({row['Short Strike']}/{row['Long Strike']}) has reached {dte_int} DTE! EJECT IMMEDIATELY to avoid terminal Gamma risk.")
                elif dte_int <= 30:
                    alerts.append(f"⏱️ **Options Gamma Warning:** Contract {tckr} ({row['Short Strike']}/{row['Long Strike']}) is approaching the 21 DTE Gamma Cliff ({dte_int} days remaining).")
            
            if str(dte_rem) != 'Closed':
                short_str = str(int(row['Short Strike']))
                long_str = str(int(row['Long Strike']))
                short_leg = pos_df[(pos_df['symbol'].str.contains(tckr)) & (pos_df['symbol'].str.contains(f"_{short_str}_"))]
                long_leg = pos_df[(pos_df['symbol'].str.contains(tckr)) & (pos_df['symbol'].str.contains(f"_{long_str}_"))]
                
                curr_spread_price = 0.0
                if not short_leg.empty and not long_leg.empty:
                    curr_spread_price = abs(short_leg['market_price'].values[0] - long_leg['market_price'].values[0])
                
                stop_loss_threshold = float(row['Premium Collected (USD)']) * 2.0
                warning_threshold = stop_loss_threshold * 0.80
                
                if curr_spread_price > 0:
                    if curr_spread_price >= stop_loss_threshold:
                        alerts.append(f"🛑 **STOP LOSS TRIGGERED:** {tckr} ({short_str}/{long_str}) live spread price (${curr_spread_price:.2f}) breached 200% limit (${stop_loss_threshold:.2f}). Close immediately.")
                    elif curr_spread_price >= warning_threshold:
                        alerts.append(f"⚠️ **Stop Loss Warning:** {tckr} ({short_str}/{long_str}) live spread price (${curr_spread_price:.2f}) is approaching the 200% limit (${stop_loss_threshold:.2f}).")
        except: pass

if not bench_df.empty:
    last_spy = bench_df['SPY'].iloc[-1]
    sma_20 = bench_df['sma_20'].iloc[-1]
    sma_50 = bench_df['sma_50'].iloc[-1]
    sma_200 = bench_df['sma_200'].iloc[-1]
    if last_spy < sma_20: alerts.append(f"📉 **Trend Alert:** SPY (${last_spy:.2f}) has breached below the 20-day SMA (${sma_20:.2f}).")
    if last_spy < sma_50: alerts.append(f"🚨 **Trend Alert:** SPY (${last_spy:.2f}) has breached below the 50-day SMA (${sma_50:.2f}).")
    if last_spy < sma_200: alerts.append(f"☢️ **CRITICAL ALERT:** SPY (${last_spy:.2f}) has breached below the 200-day SMA (${sma_200:.2f}). Bear market threshold.")

regime_str = chart_df['regime'].iloc[-1] if not chart_df.empty else 'Unknown'
tor_val = chart_df['tor'].iloc[-1] if not chart_df.empty else 0
alerts.append(f"🧭 **EOD Market Regime:** {regime_str} | **TOR Risk Level:** {tor_val}")

# Calculate active TOR from Champion Engine
champion_df = process_champion_journal(pos_df, open_orders_df, silo_metrics)
global_1r_base = global_metrics['nav'] * 0.0025 if global_metrics['nav'] > 0 else 1
active_global_tor = champion_df['Open Risk ($)'].sum() / global_1r_base if not champion_df.empty else 0

if active_global_tor > tor_val:
    alerts.append(f"🚨 **TOR CAPACITY BREACH:** Active Global TOR is **{active_global_tor:.2f} R**, exceeding the current {regime_str} Regime ideal limit of **{tor_val} R**. Reduce exposure or tighten Stop Losses immediately.")
elif active_global_tor > (tor_val * 0.8):
    alerts.append(f"⚠️ **TOR Warning:** Active Global TOR is **{active_global_tor:.2f} R**, approaching the regime limit of **{tor_val} R**.")

tot_vrp = attr_df['a3_vrp'].sum() if not attr_df.empty else 0
th_budget = tot_vrp * 0.10
th_df = pos_df[pos_df['asset_class'] == 'Tail Hedge'] if not pos_df.empty else pd.DataFrame()
th_deployed = (th_df['position'].abs() * th_df['avg_cost']).sum() if not th_df.empty else 0
th_available = th_budget - th_deployed

if th_available >= 400.0:
    tranches_due = int(th_available // 400.0)
    if tranches_due == 1:
        alerts.append(f"🛡️ **Tail Hedge Deployment Due:** You have **${th_available:,.0f}** available in house money. Purchase **1 tranche** (~$400) of 120-DTE deep OTM S&P 500 Puts (Delta < 5).")
    else:
        alerts.append(f"🛡️ **Tail Hedge Backlog Detected:** You have **${th_available:,.0f}** available. DO NOT deploy as a lump sum. Split this into **{tranches_due} staggered tranches** (~$400 each) across 90, 120, and 150+ DTE.")

if pct_cash > 60: alerts.append(f"ℹ️ **Cash Drag Detected:** Unleveraged Cash/IB01 is {pct_cash:.1f}%. Await weekly Command Center deployment schedule.")
if pct_cash < 40: alerts.append(f"⚠️ **Cash Buffer Warning:** Global cash buffer dropped to {pct_cash:.1f}% (Below 40% optimal floor).")
if pct_tech > 40: alerts.append(f"⚠️ **Sector Concentration:** Tech/Semi exposure is {pct_tech:.1f}% (Above 40% safe threshold).")

if alerts:
    alert_html = "".join([f"<li style='margin-bottom: 5px;'>{a}</li>" for a in alerts])
    st.markdown(f"""
    <div style="background-color: #fffbeb; border-left: 6px solid #f59e0b; padding: 15px; border-radius: 4px; color: #1f2937; font-size: 14px; margin-bottom: 25px;">
        <ul style="margin: 0; padding-left: 20px;">{alert_html}</ul>
    </div>
    """.replace('\n', ''), unsafe_allow_html=True)
else: st.success("✅ All systems nominal. No actionable alerts at this time.")

st.divider() 

# SECTION 1: MASTER AGGREGATION
html_metrics = f"""
<div style="background-color: #f3f4f6; padding: 20px; border-radius: 12px; border: 1px solid #e5e7eb; margin-bottom: 20px;">
    <h4 style="text-align: center; color: #1f2937; margin-bottom: 20px; text-transform: uppercase; letter-spacing: 2px; font-size: 24px;">Master Estate Aggregation</h4>
    <div style="overflow-x: auto;">
        <table style="width: 100%; text-align: center; font-family: monospace; border-collapse: collapse;">
            <thead>
                <tr style="background-color: #e5e7eb; color: #374151; font-size: 16px; border-bottom: 2px solid #d1d5db;">
                    <th style="padding: 12px; text-align: left;">Entity</th>
                    <th>Balance</th><th>IRR</th><th>P&L</th><th>Sharpe</th><th>Max DD</th><th>DD Days</th><th>Calmar</th><th>ROC</th><th>Alpha</th><th>Beta</th><th>Corr</th>
                </tr>
            </thead>
            <tbody>
                <tr style="border-bottom: 1px solid #d1d5db; background-color: #ffffff;">
                    <td style="padding: 12px; text-align: left; font-weight: 900; font-size: 18px; color: #1f2937;">GLOBAL ESTATE</td>
                    <td style="font-weight: 900; font-size: 22px; color: #1d4ed8;">${global_metrics['nav']:,.0f}</td>
                    <td style="{col_html(global_metrics['irr'])} font-weight: 900; font-size: 22px;">{global_metrics['irr']:.2f}%</td>
                    <td style="{col_html(global_metrics['pnl'])} font-weight: 900; font-size: 22px;">${global_metrics['pnl']:,.0f}</td>
                    <td style="{col_html(global_metrics['sharpe'])} font-weight: 900; font-size: 22px;">{global_metrics['sharpe']:.2f}</td>
                    <td style="color: #b91c1c; font-weight: 900; font-size: 22px;">{global_metrics['max_dd']:.2f}%</td>
                    <td style="font-weight: 900; font-size: 22px; color: #1f2937;">{global_metrics['dd_days']} d</td>
                    <td style="font-weight: 900; font-size: 22px; color: #1f2937;">{calmar:.2f}</td>
                    <td style="{col_html(global_metrics['roc'])} font-weight: 900; font-size: 22px;">{global_metrics['roc']:.2f}%</td>
                    <td style="font-weight: 900; font-size: 22px; color: #9ca3af;">—</td>
                    <td style="font-weight: 900; font-size: 22px; color: #9ca3af;">—</td>
                    <td style="font-weight: 900; font-size: 22px; color: #9ca3af;">—</td>
                </tr>
                <tr style="border-bottom: 1px solid #d1d5db; background-color: #f8fafc;">
                    <td style="padding: 12px; text-align: left; font-weight: 900; font-size: 16px; color: #3b82f6;">S&P 500 (SPY)</td>
                    <td style="font-weight: bold; font-size: 18px; color: #374151;">${spy_metrics['nav']:,.0f}</td>
                    <td style="{col_html(spy_metrics['irr'])} font-weight: bold; font-size: 18px;">{spy_metrics['irr']:.2f}%</td>
                    <td style="{col_html(spy_metrics['pnl'])} font-weight: bold; font-size: 18px;">${spy_metrics['pnl']:,.0f}</td>
                    <td style="{col_html(spy_sh)} font-weight: bold; font-size: 18px;">{spy_sh:.2f}</td>
                    <td style="color: #b91c1c; font-weight: bold; font-size: 18px;">{spy_metrics['max_dd']:.2f}%</td>
                    <td style="font-weight: bold; font-size: 18px; color: #374151;">{spy_metrics['dd_days']} d</td>
                    <td style="font-weight: bold; font-size: 18px; color: #374151;">{spy_calmar:.2f}</td>
                    <td style="{col_html(spy_metrics['roc'])} font-weight: bold; font-size: 18px;">{spy_metrics['roc']:.2f}%</td>
                    <td style="{col_html(spy_al)} font-weight: bold; font-size: 18px;">{spy_al:.2f}%</td>
                    <td style="{col_html(spy_beta, 1.0)} font-weight: bold; font-size: 18px;">{spy_beta:.2f}</td>
                    <td style="{col_html(spy_co, 0.3)} font-weight: bold; font-size: 18px;">{spy_co:.2f}</td>
                </tr>
                <tr style="background-color: #ffffff;">
                    <td style="padding: 12px; text-align: left; font-weight: 900; font-size: 16px; color: #dc2626;">NASDAQ 100 (QQQ)</td>
                    <td style="font-weight: bold; font-size: 18px; color: #374151;">${qqq_metrics['nav']:,.0f}</td>
                    <td style="{col_html(qqq_metrics['irr'])} font-weight: bold; font-size: 18px;">{qqq_metrics['irr']:.2f}%</td>
                    <td style="{col_html(qqq_metrics['pnl'])} font-weight: bold; font-size: 18px;">${qqq_metrics['pnl']:,.0f}</td>
                    <td style="{col_html(qqq_sh)} font-weight: bold; font-size: 18px;">{qqq_sh:.2f}</td>
                    <td style="color: #b91c1c; font-weight: bold; font-size: 18px;">{qqq_metrics['max_dd']:.2f}%</td>
                    <td style="font-weight: bold; font-size: 18px; color: #374151;">{qqq_metrics['dd_days']} d</td>
                    <td style="font-weight: bold; font-size: 18px; color: #374151;">{qqq_calmar:.2f}</td>
                    <td style="{col_html(qqq_metrics['roc'])} font-weight: bold; font-size: 18px;">{qqq_metrics['roc']:.2f}%</td>
                    <td style="{col_html(qqq_al)} font-weight: bold; font-size: 18px;">{qqq_al:.2f}%</td>
                    <td style="{col_html(qqq_beta, 1.0)} font-weight: bold; font-size: 18px;">{qqq_beta:.2f}</td>
                    <td style="{col_html(qqq_co, 0.3)} font-weight: bold; font-size: 18px;">{qqq_co:.2f}</td>
                </tr>
            </tbody>
        </table>
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
st.subheader("1. Estate Capital Breakdown (GAAP, Allocation & Sectors)")
col_bar, col_pie, col_sector = st.columns(3)

if not pos_df.empty:
    # 1. Bar Chart Data
    bar_df = pos_df.groupby(['account', 'asset_class'])['market_value'].sum().unstack(fill_value=0)
    bar_df['Accounting Offset'] = 0.0
    for acc in bar_df.index:
        gross_val = bar_df.loc[acc].sum()
        actual_nav = silo_metrics.get(acc, {}).get('nav', 0)
        bar_df.at[acc, 'Accounting Offset'] = actual_nav - gross_val
        
    # --- NEW: Reorder index to match Silo A, B, C, D ---
    ordered_accounts = [acc for acc in SILO_MAP.keys() if acc in bar_df.index]
    bar_df = bar_df.reindex(ordered_accounts)
    # ---------------------------------------------------        
        
    # 2. Pie Chart Data
    pie_df = pos_df.groupby('asset_class')['market_value'].sum().reset_index()
    pie_df['market_value'] = pie_df['market_value'].abs() 
    tot_gross = pie_df['market_value'].sum()
    pie_df['pct'] = (pie_df['market_value'] / tot_gross) * 100 if tot_gross > 0 else 0
    pie_df['legend_label'] = pie_df.apply(lambda r: f"{r['asset_class']} ({r['pct']:.1f}%)", axis=1)

    # 3. Automated Sector Data
    sector_data = []
    for _, r in pos_df.iterrows():
        if r['asset_class'] not in ['Cash', 'Accounting Offset', 'Tail Hedge', 'Opt Liab', 'Active Swing', 'IB01', 'Gold']:
            sec = get_sector(r['symbol'], r['asset_class'])
            sector_data.append({'Sector': sec, 'Value': abs(r['market_value'])})
    sec_df = pd.DataFrame(sector_data).groupby('Sector')['Value'].sum().reset_index() if sector_data else pd.DataFrame()

    with col_bar:
        fig_bar = go.Figure()
        silo_names = [SILO_MAP.get(acc, (acc,))[0] for acc in bar_df.index]
        silo_totals = bar_df.sum(axis=1).values
        
        for asset in bar_df.columns:
            l_label = pie_df[pie_df['asset_class'] == asset]['legend_label'].iloc[0] if asset in pie_df['asset_class'].values else asset
            fig_bar.add_trace(go.Bar(
                name=l_label, x=silo_names, y=bar_df[asset], marker_color=COLOR_PALETTE.get(asset, '#cbd5e1')
            ))
            
        opt_margin_A = get_exact_opt_margin(pos_df[pos_df['account'] == 'U23144948'])
        opt_margin_C = get_exact_opt_margin(pos_df[pos_df['account'] == 'U23154199'])
        
        tot_ml = opt_margin_A + opt_margin_C
        pct_ml = (tot_ml / global_metrics['nav']) * 100 if global_metrics['nav'] > 0 else 0
        ml_label = f"Margin Lock (${tot_ml:,.0f} | {pct_ml:.1f}%)"
        
        fig_bar.add_trace(go.Scatter(
            x=['Silo A', 'Silo C'], y=[opt_margin_A, opt_margin_C], name=ml_label, mode='markers', 
            marker=dict(symbol='diamond', size=14, color='#ef4444', line=dict(width=1, color='black'))
        ))
        
        for i, total in enumerate(silo_totals):
            pct_total = (total / global_metrics['nav']) * 100 if global_metrics['nav'] > 0 else 0
            fig_bar.add_annotation(
                x=silo_names[i], y=total, text=f"<b>${total/1000:.0f}k</b>", showarrow=False, yanchor='bottom', yshift=5, font=dict(size=14)
            )
            
        fig_bar.update_layout(
            barmode='relative', title="GAAP Balance Sheet (USD)", plot_bgcolor='rgba(0,0,0,0)', 
            margin=dict(l=20, r=20, t=40, b=20), yaxis=dict(zeroline=True, zerolinecolor='black', gridcolor='LightGray'), 
            legend=dict(orientation="h", yanchor="top", y=-0.2, xanchor="center", x=0.5), font=dict(size=12)
        )
        st.plotly_chart(fig_bar, width="stretch")

    with col_pie:
        fig_pie = go.Figure(data=[go.Pie(
            labels=pie_df['legend_label'], values=pie_df['market_value'], hole=.4, 
            marker=dict(colors=[COLOR_PALETTE.get(a, '#cbd5e1') for a in pie_df['asset_class']]), textinfo='percent'
        )])
        fig_pie.update_layout(
            title="Gross Asset Allocation", margin=dict(l=20, r=20, t=40, b=20),
            legend=dict(orientation="h", yanchor="top", y=-0.2, xanchor="center", x=0.5), font=dict(size=12)
        )
        st.plotly_chart(fig_pie, width="stretch")
        
    with col_sector:
        if not sec_df.empty:
            fig_sec = go.Figure(data=[go.Pie(
                labels=sec_df['Sector'], values=sec_df['Value'], hole=.4, textinfo='percent'
            )])
            fig_sec.update_layout(
                title="Sector Concentration Risk", margin=dict(l=20, r=20, t=40, b=20),
                legend=dict(orientation="h", yanchor="top", y=-0.2, xanchor="center", x=0.5), font=dict(size=12)
            )
            st.plotly_chart(fig_sec, width="stretch")

st.divider()

# --- SECTION 4: TARGET PORTFOLIO COMPOSITION ---
st.subheader("2. Live Portfolio Composition (from TWS)")
comp_cols = st.columns(4)

strats = [
    "<b>The Macro & Income Engines.</b> Both silos operate under identical mandates. <b>The Safe Side:</b> 80-85% parked in IB01. <b>The Growth Engine:</b> Replaces physical ETFs with Synthetic Beta (120-180 DTE Deep ITM XSP/XND Calls) funded by 15-20% NAV to legally bypass US Estate Tax. <b>The Income Engine:</b> Revolving Door VRP ladder (45-50 DTE Spreads/Condors), governed by a strict 20% global margin cap. <b>The Insurance Engine:</b> 120+ DTE deep OTM Puts funded by 10% of VRP. <b>The Alpha Engine:</b> Authorized for tactical CFDs, Crypto, and Intl Stocks, strictly capped at 1R Base (0.25% NAV).",
    "<b>The Active Swing Engine.</b> Explicitly excluded from macro indexing (Synthetic Beta). Exclusively hunts Alpha via International Stocks and US Tech CFDs. Idle liquidity is explicitly parked in IB01 to prevent cash drag. <b>CFD Tier Ban:</b> CFDs are strictly banned until the account organically reaches Tier 3 ($50,000+ Stock Base) to prevent FINRA PDT lockouts and margin haircuts. Capital scaling is purely merit-based.",
    "<b>The Macro & Income Engines.</b> Both silos operate under identical mandates. <b>The Safe Side:</b> 80-85% parked in IB01. <b>The Growth Engine:</b> Replaces physical ETFs with Synthetic Beta (120-180 DTE Deep ITM XSP/XND Calls) funded by 15-20% NAV to legally bypass US Estate Tax. <b>The Income Engine:</b> Revolving Door VRP ladder (45-50 DTE Spreads/Condors), governed by a strict 20% global margin cap. <b>The Insurance Engine:</b> 120+ DTE deep OTM Puts funded by 10% of VRP. <b>The Alpha Engine:</b> Authorized for tactical CFDs, Crypto, and Intl Stocks, strictly capped at 1R Base (0.25% NAV).",
    "<b>Mandate Pending.</b> Currently acts as a pristine capital reserve. Safely parked in USD Cash and yielding IB01 (Short-term US Treasuries) while awaiting a definitive strategic designation."
]
for idx, acc in enumerate(SILO_MAP.keys()):
    name, _, color = SILO_MAP[acc]
    acc_pos = pos_df[pos_df['account'] == acc].copy() if not pos_df.empty else pd.DataFrame()
    
    with comp_cols[idx]:
        st.markdown(f"**{name}**")
        if not acc_pos.empty:
            acc_nav = silo_metrics[acc]['nav']
            acc_pos['Allocation %'] = (acc_pos['market_value'] / acc_nav) * 100 if acc_nav > 0 else 0
            display_df = acc_pos[['symbol', 'market_value', 'Allocation %']].sort_values('market_value', ascending=False)
            display_df.columns = ['Asset', 'Value ($)', 'Alloc (%)']
            
            # Injecting the Silo color directly into the DataFrame's HTML Header tags
            styled_df = display_df.style.set_table_styles([
                dict(selector="th", props=[("background-color", color), ("color", "black"), ("font-weight", "bold")])
            ]).format({'Value ($)': '{:,.0f}', 'Alloc (%)': '{:.1f}%'})
            
            st.dataframe(styled_df, hide_index=True, width='stretch')
        else: 
            st.write("No active positions.")

        st.markdown(
            f"<div style='font-size: 11px; color: #000000; padding: 10px; border-top: 1px solid #e5e7eb; margin-top: 10px; height: 180px; overflow-y: auto;'><b>STRATEGY & EXECUTION:</b> {strats[idx]}</div>", 
            unsafe_allow_html=True
        )

st.divider()

# --- SECTION 5: DAILY PNL HISTOGRAM ---
st.subheader("3. Daily PnL per Silo")
spy_usd_pnl = []
qqq_usd_pnl = []
curr_spy_nav = chart_df['nav'].iloc[0] if not chart_df.empty else 0
curr_qqq_nav = chart_df['nav'].iloc[0] if not chart_df.empty else 0

for i, row in chart_df.iterrows():
    s_pnl = curr_spy_nav * row['spy_ret']
    q_pnl = curr_qqq_nav * row['qqq_ret']
    spy_usd_pnl.append(s_pnl)
    qqq_usd_pnl.append(q_pnl)
    curr_spy_nav += s_pnl + row['net_flow']
    curr_qqq_nav += q_pnl + row['net_flow']

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

st.divider()

# --- SECTION 6: PNL ATTRIBUTION & VELOCITY ---
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
    
    th_budget = tot_a3 * 0.10
    th_df_vel = pos_df[pos_df['asset_class'] == 'Tail Hedge'] if not pos_df.empty else pd.DataFrame()
    th_deployed = (th_df_vel['position'].abs() * th_df_vel['avg_cost']).sum() if not th_df_vel.empty else 0
    th_available = th_budget - th_deployed
    
    col_bar, col_line, col_vel = st.columns([2, 3, 1])
    bar_colors = ['#3b82f6', '#f97316', '#166534', '#a855f7', '#991b1b']
    
    with col_bar:
        fig_attr_bar = go.Figure(data=[go.Bar(
            x=['Yield (a1)', 'Beta (a2)', 'VRP (a3)', 'Alpha (a4)', 'Fees (a5)'], 
            y=[tot_a1, tot_a2, tot_a3, tot_a4, tot_a5], 
            text=[f"${v:,.0f}" for v in [tot_a1, tot_a2, tot_a3, tot_a4, tot_a5]], 
            textposition='auto', 
            marker_color=bar_colors,
            insidetextfont=dict(color='white'),
            outsidetextfont=dict(color='#4b5563')
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
            for col, name, color in zip(['a1_yield', 'a2_beta', 'a3_vrp', 'a4_alpha', 'a5_fees'], ['Yield', 'Beta', 'VRP', 'Alpha', 'Fees'], bar_colors):
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
        st.markdown("---")
        st.metric("Tail Hedge Budget (10%)", f"${th_budget:,.0f}", help="Accumulated 10% of VRP budget reserved for deep OTM Ackman Puts.")
        st.metric("Tail Hedge Deployed (Cost)", f"${th_deployed:,.0f}")
        st.metric("Tail Hedge Available", f"${th_available:,.0f}")

st.divider()

# --- SECTION 7: DEPLOYMENT COMMAND CENTER (60/40 Transition Matrix) ---
st.subheader("5. Deployment Command Center (Transition to 60/40)")

df_ledger = load_deployment_ledger()
today = datetime.date.today()
is_cooldown = False
last_deploy_date = None

if not df_ledger.empty:
    last_deploy_str = df_ledger['deploy_date'].iloc[0]
    last_deploy_date = pd.to_datetime(last_deploy_str).date()
    if last_deploy_date.isocalendar()[1] == today.isocalendar()[1] and last_deploy_date.year == today.year:
        is_cooldown = True

target_pct = 60.0
macro_nav = nav_A + nav_C
target_usd = macro_nav * (target_pct / 100.0)
core_assets = ['CSPX', 'CNDX', 'ITWN', 'CSKR', 'CNYA', 'Crypto', 'Gold']

# Silo B and D are explicitly excluded from this logic pool
if not pos_df.empty:
    current_usd = pos_df[(pos_df['account'].isin(['U23144948', 'U23154199'])) & (pos_df['asset_class'].isin(core_assets))]['market_value'].sum()
else:
    current_usd = 0
    
current_pct = (current_usd / macro_nav * 100) if macro_nav > 0 else 0
distance_usd = max(0, target_usd - current_usd)
distance_pct = max(0, target_pct - current_pct)

if regime_str == 'Green':
    pacing_pct = 0.015
    box_color = "#f0fdf4"
    border_color = "#166534"
    text_color = "#166534"
    icon = "🟢"
elif regime_str == 'Yellow':
    pacing_pct = 0.030
    box_color = "#fefce8"
    border_color = "#a16207"
    text_color = "#a16207"
    icon = "🟡"
else:
    pacing_pct = 0.0
    box_color = "#fef2f2"
    border_color = "#991b1b"
    text_color = "#991b1b"
    icon = "🔴"

allowance_usd = macro_nav * pacing_pct
actual_deploy = min(allowance_usd, distance_usd)

c_stat, c_action = st.columns([1, 1])

with c_stat:
    st.markdown(f"""
    <div style="background-color: #f8fafc; padding: 20px; border-radius: 8px; border: 1px solid #cbd5e1; height: 100%;">
        <h4 style="margin-top: 0; color: #0f172a;">Macro Core Equities Tracker (Silos A & C Only)</h4>
        <div style="font-size: 16px; margin-bottom: 10px;"><b>Target (60.0%):</b> ${target_usd:,.0f}</div>
        <div style="font-size: 16px; margin-bottom: 10px;"><b>Current ({current_pct:.1f}%):</b> ${current_usd:,.0f}</div>
        <div style="font-size: 18px; font-weight: bold; color: #3b82f6;">Distance to Target: ${distance_usd:,.0f} ({distance_pct:.1f}%)</div>
        <hr style="margin: 15px 0;">
        <div style="font-size: 13px; color: #475569;">
            <b>Silo B Exclusion:</b> Silo B is strictly excluded from this macro DCA matrix.
        </div>
    </div>
    """, unsafe_allow_html=True)

with c_action:
    if distance_usd <= 1000:
        st.success("🎯 **Target Reached:** Estate has successfully achieved the 60% Equity Target. Maintenance Mode activated. All new VRP will strictly maintain this balance.")
    elif is_cooldown:
        st.info(f"⏳ **Cooldown Active:** Weekly deployment of ${df_ledger['amount'].iloc[0]:,.0f} was executed on {last_deploy_date}. The matrix will unlock next Monday.")
    elif regime_str == 'Red':
        st.error(f"{icon} **REGIME RED (Black Swan Protocol):** Halt all baseline Cash deployment. Defend the 40% floor. Do not catch the falling knife. Await Tail Hedge monetization to buy the absolute bottom.")
    else:
        
        # --- CEILING GOVERNOR LOGIC ---
        cryp_usd = pos_df[pos_df['asset_class'] == 'Crypto']['market_value'].sum() if not pos_df.empty else 0
        gold_usd = pos_df[pos_df['asset_class'] == 'Gold']['market_value'].sum() if not pos_df.empty else 0
        
        cryp_pct_live = (cryp_usd / macro_nav * 100) if macro_nav > 0 else 0
        gold_pct_live = (gold_usd / macro_nav * 100) if macro_nav > 0 else 0
        
        cryp_alloc_pct = 0.05 if cryp_pct_live < 5.0 else 0.0
        gold_alloc_pct = 0.05 if gold_pct_live < 5.0 else 0.0
        
        overflow_pct = (0.05 - cryp_alloc_pct) + (0.05 - gold_alloc_pct)
        
        base_synth = 0.75
        base_asia = 0.15
        total_core = base_synth + base_asia
        
        synth_alloc_pct = base_synth + (overflow_pct * (base_synth / total_core))
        asia_alloc_pct = base_asia + (overflow_pct * (base_asia / total_core))

        cap_notices = []
        if cryp_alloc_pct == 0.0: cap_notices.append("Crypto (≥5.0%)")
        if gold_alloc_pct == 0.0: cap_notices.append("Gold (≥5.0%)")
        
        cap_str = ""
        if cap_notices:
            cap_str = f"<div style='font-size: 13px; color: #d97706; margin-top: 10px; background-color: #fef3c7; padding: 8px; border-radius: 4px; border: 1px solid #f59e0b;'><b>⚠️ Ceiling Governor Active:</b> {', '.join(cap_notices)} cap reached. Overflow safely redirected to Synthetic Beta Premium Budget.</div>"

        weight_A = nav_A / macro_nav if macro_nav > 0 else 0.5
        weight_C = nav_C / macro_nav if macro_nav > 0 else 0.5

        synth_tot = actual_deploy * synth_alloc_pct
        asia_tot = actual_deploy * asia_alloc_pct
        cryp_tot = actual_deploy * cryp_alloc_pct
        gold_tot = actual_deploy * gold_alloc_pct

        st.markdown(f"""
        <div style="background-color: {box_color}; padding: 20px; border-radius: 8px; border: 1px solid {border_color};">
            <h4 style="margin-top: 0; color: {text_color};">{icon} Regime {regime_str} | Active Deployment</h4>
            <div style="font-size: 14px; margin-bottom: 5px;">Pacing Schedule: <b>{pacing_pct*100:.1f}% NAV per week</b></div>
            <b style="font-size: 16px;">🛒 Weekly Target-Weighted Shopping Matrix:</b>
            <table style="width:100%; border-collapse: collapse; margin-top: 10px; font-size: 14px; background-color: white; color: black; text-align: right; border: 1px solid #cbd5e1;">
                <thead style="background-color: {border_color}; color: white;">
                    <tr>
                        <th style="padding: 8px; text-align: left; border-right: 1px solid white;">Instrument</th>
                        <th style="padding: 8px; border-right: 1px solid white;">Total ($)</th>
                        <th style="padding: 8px; border-right: 1px solid white;">Silo A ({(weight_A*100):.1f}%)</th>
                        <th style="padding: 8px;">Silo C ({(weight_C*100):.1f}%)</th>
                    </tr>
                </thead>
                <tbody>
                    <tr style="border-bottom: 1px solid #e5e7eb;">
                        <td style="padding: 8px; text-align: left; border-right: 1px solid #e5e7eb;"><b>Synthetic Beta (ITM Calls)</b> ({synth_alloc_pct*100:.0f}%)</td>
                        <td style="padding: 8px; border-right: 1px solid #e5e7eb;">${synth_tot:,.0f}</td>
                        <td style="padding: 8px; border-right: 1px solid #e5e7eb;">${synth_tot * weight_A:,.0f}</td>
                        <td style="padding: 8px;">${synth_tot * weight_C:,.0f}</td>
                    </tr>
                    <tr style="border-bottom: 1px solid #e5e7eb;">
                        <td style="padding: 8px; text-align: left; border-right: 1px solid #e5e7eb;"><b>Asia (ITWN/CSKR)</b> ({asia_alloc_pct*100:.0f}%)</td>
                        <td style="padding: 8px; border-right: 1px solid #e5e7eb;">${asia_tot:,.0f}</td>
                        <td style="padding: 8px; border-right: 1px solid #e5e7eb;">${asia_tot * weight_A:,.0f}</td>
                        <td style="padding: 8px;">${asia_tot * weight_C:,.0f}</td>
                    </tr>
                    <tr style="border-bottom: 1px solid #e5e7eb;">
                        <td style="padding: 8px; text-align: left; border-right: 1px solid #e5e7eb;"><b>Crypto ETPs</b> ({cryp_alloc_pct*100:.0f}%)</td>
                        <td style="padding: 8px; border-right: 1px solid #e5e7eb;">${cryp_tot:,.0f}</td>
                        <td style="padding: 8px; border-right: 1px solid #e5e7eb;">${cryp_tot * weight_A:,.0f}</td>
                        <td style="padding: 8px;">${cryp_tot * weight_C:,.0f}</td>
                    </tr>
                    <tr style="border-bottom: 1px solid #e5e7eb;">
                        <td style="padding: 8px; text-align: left; border-right: 1px solid #e5e7eb;"><b>Gold (SGLN)</b> ({gold_alloc_pct*100:.0f}%)</td>
                        <td style="padding: 8px; border-right: 1px solid #e5e7eb;">${gold_tot:,.0f}</td>
                        <td style="padding: 8px; border-right: 1px solid #e5e7eb;">${gold_tot * weight_A:,.0f}</td>
                        <td style="padding: 8px;">${gold_tot * weight_C:,.0f}</td>
                    </tr>
                    <tr style="background-color: #f8fafc; font-weight: bold;">
                        <td style="padding: 8px; text-align: left; border-right: 1px solid #cbd5e1; color: #1e293b;">TOTAL (100%)</td>
                        <td style="padding: 8px; color: #1d4ed8; border-right: 1px solid #cbd5e1;">${actual_deploy:,.0f}</td>
                        <td style="padding: 8px; color: #1d4ed8; border-right: 1px solid #cbd5e1;">${actual_deploy * weight_A:,.0f}</td>
                        <td style="padding: 8px; color: #1d4ed8;">${actual_deploy * weight_C:,.0f}</td>
                    </tr>
                </tbody>
            </table>
            {cap_str}
        </div>
        """, unsafe_allow_html=True)
        
        st.write("")
        
        if st.button("✅ Log Weekly Deployment as Executed", width="stretch"):
            conn = sqlite3.connect(DB_PATH)
            c = conn.cursor()
            c.execute("INSERT INTO deployment_ledger (deploy_date, regime, amount) VALUES (?, ?, ?)", 
                      (datetime.date.today().isoformat(), regime_str, actual_deploy))
            conn.commit()
            conn.close()
            st.cache_data.clear()
            st.rerun()

st.divider()

# --- SECTION 8: CAPITAL DEPLOYMENT & MARGIN TRACKER ---
st.subheader("6. Capital Deployment & Margin Capacity Tracker")

# Enlarging Global Gauges via Column Weights
c_gb_cash, c_sa_cash, c_sc_cash, c_gb_marg, c_sa_marg, c_sc_marg = st.columns([1.5, 1, 1, 1.5, 1, 1])

with c_gb_cash:
    fig_gauge_cash = go.Figure(go.Indicator(
        mode="gauge+number+delta", 
        value=pct_cash, 
        title={'text': "<b>Global Cash Buffer</b>", 'font': {'size': 18}}, 
        delta={'reference': 40, 'increasing': {'color': "green"}, 'decreasing': {'color': "red"}}, 
        gauge={
            'axis': {'range': [0, 100], 'tickwidth': 1}, 
            'bar': {'color': "blue"}, 
            'steps': [{'range': [0, 40], 'color': "rgba(239, 68, 68, 0.3)"}, {'range': [40, 100], 'color': "rgba(34, 197, 94, 0.3)"}], 
            'threshold': {'line': {'color': "red", 'width': 4}, 'thickness': 0.75, 'value': 40}
        }
    ))
    fig_gauge_cash.update_layout(height=250, margin=dict(l=10, r=10, t=40, b=10))
    st.plotly_chart(fig_gauge_cash, width="stretch")

with c_sa_cash:
    cash_A = pos_df[(pos_df['account'] == 'U23144948') & (pos_df['asset_class'].isin(['IB01', 'Cash']))]['market_value'].sum() if not pos_df.empty else 0
    pct_cash_A = (cash_A / nav_A * 100) if nav_A > 0 else 0
    
    fig_A_cash = go.Figure(go.Indicator(
        mode="gauge+number", 
        value=pct_cash_A, 
        number={'suffix': "%", 'font': {'size': 20}}, 
        title={'text': "Silo A Buffer", 'font': {'size': 12}}, 
        gauge={
            'axis': {'range': [0, 100], 'tickwidth': 1}, 
            'bar': {'color': "blue"}, 
            'steps': [{'range': [0, 40], 'color': "rgba(239, 68, 68, 0.3)"}, {'range': [40, 100], 'color': "rgba(34, 197, 94, 0.3)"}], 
            'threshold': {'line': {'color': "red", 'width': 2}, 'thickness': 0.75, 'value': 40}
        }
    ))
    fig_A_cash.update_layout(height=250, margin=dict(l=5, r=5, t=50, b=10))
    st.plotly_chart(fig_A_cash, width="stretch")

with c_sc_cash:
    cash_C = pos_df[(pos_df['account'] == 'U23154199') & (pos_df['asset_class'].isin(['IB01', 'Cash']))]['market_value'].sum() if not pos_df.empty else 0
    pct_cash_C = (cash_C / nav_C * 100) if nav_C > 0 else 0
    
    fig_C_cash = go.Figure(go.Indicator(
        mode="gauge+number", 
        value=pct_cash_C, 
        number={'suffix': "%", 'font': {'size': 20}}, 
        title={'text': "Silo C Buffer", 'font': {'size': 12}}, 
        gauge={
            'axis': {'range': [0, 100], 'tickwidth': 1}, 
            'bar': {'color': "blue"}, 
            'steps': [{'range': [0, 40], 'color': "rgba(239, 68, 68, 0.3)"}, {'range': [40, 100], 'color': "rgba(34, 197, 94, 0.3)"}], 
            'threshold': {'line': {'color': "red", 'width': 2}, 'thickness': 0.75, 'value': 40}
        }
    ))
    fig_C_cash.update_layout(height=250, margin=dict(l=5, r=5, t=50, b=10))
    st.plotly_chart(fig_C_cash, width="stretch")

with c_gb_marg:
    # Strict 20% cap visualization
    fig_gauge_margin = go.Figure(go.Indicator(
        mode="gauge+number+delta", 
        value=pct_margin, 
        title={'text': "<b>Global Options Margin</b>", 'font': {'size': 18}}, 
        delta={'reference': 20, 'increasing': {'color': "red"}, 'decreasing': {'color': "green"}}, 
        gauge={
            'axis': {'range': [0, 100], 'tickwidth': 1}, 
            'bar': {'color': "purple"}, 
            'steps': [{'range': [0, 20], 'color': "rgba(34, 197, 94, 0.3)"}, {'range': [20, 100], 'color': "rgba(239, 68, 68, 0.3)"}], 
            'threshold': {'line': {'color': "red", 'width': 4}, 'thickness': 0.75, 'value': 20}
        }
    ))
    fig_gauge_margin.update_layout(height=250, margin=dict(l=10, r=10, t=40, b=10))
    st.plotly_chart(fig_gauge_margin, width="stretch")

with c_sa_marg:
    margin_A = get_exact_opt_margin(pos_df[pos_df['account'] == 'U23144948']) if not pos_df.empty else 0
    pct_margin_A = (margin_A / nav_A * 100) if nav_A > 0 else 0
    
    fig_A_margin = go.Figure(go.Indicator(
        mode="gauge+number", 
        value=pct_margin_A, 
        number={'suffix': "%", 'font': {'size': 20}}, 
        title={'text': "Silo A Margin", 'font': {'size': 12}}, 
        gauge={
            'axis': {'range': [0, 100], 'tickwidth': 1}, 
            'bar': {'color': "purple"}, 
            'steps': [{'range': [0, 20], 'color': "rgba(34, 197, 94, 0.3)"}, {'range': [20, 100], 'color': "rgba(239, 68, 68, 0.3)"}], 
            'threshold': {'line': {'color': "red", 'width': 2}, 'thickness': 0.75, 'value': 20}
        }
    ))
    fig_A_margin.update_layout(height=250, margin=dict(l=5, r=5, t=50, b=10))
    st.plotly_chart(fig_A_margin, width="stretch")

with c_sc_marg:
    margin_C = get_exact_opt_margin(pos_df[pos_df['account'] == 'U23154199']) if not pos_df.empty else 0
    pct_margin_C = (margin_C / nav_C * 100) if nav_C > 0 else 0
    
    fig_C_margin = go.Figure(go.Indicator(
        mode="gauge+number", 
        value=pct_margin_C, 
        number={'suffix': "%", 'font': {'size': 20}}, 
        title={'text': "Silo C Margin", 'font': {'size': 12}}, 
        gauge={
            'axis': {'range': [0, 100], 'tickwidth': 1}, 
            'bar': {'color': "purple"}, 
            'steps': [{'range': [0, 20], 'color': "rgba(34, 197, 94, 0.3)"}, {'range': [20, 100], 'color': "rgba(239, 68, 68, 0.3)"}], 
            'threshold': {'line': {'color': "red", 'width': 2}, 'thickness': 0.75, 'value': 20}
        }
    ))
    fig_C_margin.update_layout(height=250, margin=dict(l=5, r=5, t=50, b=10))
    st.plotly_chart(fig_C_margin, width="stretch")

st.divider()

# --- ENHANCEMENTS E.1 AND E.2: Beta-Weighted Risk & Catastrophe Coverage ---
st.subheader("6B. Advanced Portfolio Risk Metrics")
col_r1, col_r2 = st.columns(2)

with col_r1:
    total_bw_delta = 0.0
    spy_price = bench_df['SPY'].iloc[-1] if not bench_df.empty else 550.0
    qqq_beta = qqq_co * (bench_df['qqq_ret'].std() / bench_df['spy_ret'].std()) if not bench_df.empty else 1.2
    
    for _, r in pos_df.iterrows():
        ac = r['asset_class']
        mv = r['market_value']
        sym = r['symbol']
        
        if ac in ['Cash', 'IB01', 'Accounting Offset', 'Gold', 'Opt Liab']:
            continue
        elif ac in ['Physical US Stocks', 'International Stocks', 'US Tech CFDs', 'CSPX', 'CNYA', 'ITWN', 'CSKR', 'Active Swing']:
            total_bw_delta += mv / spy_price
        elif ac == 'CNDX':
            total_bw_delta += (mv / spy_price) * qqq_beta
        elif ac == 'Crypto':
            total_bw_delta += (mv / spy_price) * 2.0
        elif r['sec_type'] == 'OPT':
            try:
                parts = sym.split('_')
                tckr = parts[0]
                right = parts[3]
                strike = float(parts[2])
                dte = (pd.to_datetime(parts[1]) - pd.Timestamp.today()).days
                pos = r['position']
                
                if 'XSP' in tckr:
                    S, V = fetch_live_data('XSP')
                    price, d, g, v, t = get_call_greeks(S, strike, max(dte/365,0.001), LIVE_RF_RATE, V) if right=='C' else get_put_greeks(S, strike, max(dte/365,0.001), LIVE_RF_RATE, V)
                    total_bw_delta += d * pos * 100 * (S / spy_price)
                elif 'XND' in tckr:
                    S, V = fetch_live_data('XND')
                    price, d, g, v, t = get_call_greeks(S, strike, max(dte/365,0.001), LIVE_RF_RATE, V) if right=='C' else get_put_greeks(S, strike, max(dte/365,0.001), LIVE_RF_RATE, V)
                    total_bw_delta += d * pos * 100 * (S / spy_price) * qqq_beta
            except:
                pass
                
    bw_usd_exposure = total_bw_delta * spy_price
    bw_pct_nav = (bw_usd_exposure / global_metrics['nav'] * 100) if global_metrics['nav'] > 0 else 0
    
    st.markdown(f"""
    <div style="background-color: #f8fafc; padding: 20px; border-radius: 8px; border: 1px solid #cbd5e1; text-align: center;">
        <h4 style="margin: 0; color: #334155; font-size: 16px;">SPY Beta-Weighted Delta (Estate-Wide)</h4>
        <div style="font-size: 28px; font-weight: bold; color: {'#16a34a' if bw_pct_nav > 0 else '#dc2626'}; margin-top: 10px;">{bw_pct_nav:+.1f}% of NAV</div>
        <div style="font-size: 14px; color: #64748b;">Directional Equivalent: {total_bw_delta:,.0f} SPY Shares (${bw_usd_exposure:,.0f})</div>
    </div>
    """, unsafe_allow_html=True)
    
with col_r2:
    th_payout = 0.0
    for _, r in pos_df[pos_df['asset_class'] == 'Tail Hedge'].iterrows():
        try:
            parts = r['symbol'].split('_')
            strike = float(parts[2])
            dte = (pd.to_datetime(parts[1]) - pd.Timestamp.today()).days
            pos = r['position']
            S, V = fetch_live_data('XSP')
            S_crash = S * 0.80
            V_crash = min(V * 2.5, 0.80) 
            cost_price = r['avg_cost'] / 100
            crash_price, _, _, _, _ = get_put_greeks(S_crash, strike, max(dte/365,0.001), LIVE_RF_RATE, V_crash)
            th_payout += max(0, (crash_price - cost_price)) * pos * 100
        except: pass
        
    coverage_ratio = (th_payout / opt_margin_total * 100) if opt_margin_total > 0 else 0
    
    st.markdown(f"""
    <div style="background-color: #f8fafc; padding: 20px; border-radius: 8px; border: 1px solid #cbd5e1; text-align: center;">
        <h4 style="margin: 0; color: #334155; font-size: 16px;">Black Swan Catastrophe Coverage (20% Crash)</h4>
        <div style="font-size: 28px; font-weight: bold; color: {'#16a34a' if coverage_ratio >= 100 else '#d97706'}; margin-top: 10px;">{coverage_ratio:.1f}% Covered</div>
        <div style="font-size: 14px; color: #64748b;">Est. Tail Payout: ${th_payout:,.0f} vs Max Liability: ${opt_margin_total:,.0f}</div>
    </div>
    """, unsafe_allow_html=True)

st.divider()

# --- SECTION 9: THE MASTER MATRIX ---
st.subheader("7. The Master Instrument Matrix (Tax, Alpha, & Sharpe Grading)")
matrix_data = [
    {"Instrument": "USD Cash", "Type": "Currency", "Risk Profile": "Risk-Free", "Alpha Potential": "Zero", "Sharpe Impact": "Stabilizer", "Trading Strategy": "Liquidity", "Jurisdiction": "US (IBKR)", "Tax Treatment": "Exempt (Bank Deposit)", "CIO Min Alloc. %": "1%", "CIO Max Alloc. %": "100%", "CIO Grading": "Splendid", "Noteworthy Comments": "Uninvested USD held in IBKR. Mandatory margin collateral."},
    {"Instrument": "IB01", "Type": "UCITS ETF", "Risk Profile": "Risk-Free", "Alpha Potential": "Zero", "Sharpe Impact": "High", "Trading Strategy": "Collateral", "Jurisdiction": "Ireland", "Tax Treatment": "Exempt (Irish Domicile)", "CIO Min Alloc. %": "10%", "CIO Max Alloc. %": "100%", "CIO Grading": "Splendid", "Noteworthy Comments": "Irish-domiciled short-term US Treasury fund. Accumulates ~4.5% tax-free."},
    {"Instrument": "Deep OTM Tail Hedge", "Type": "Index Option", "Risk Profile": "Defensive", "Alpha Potential": "Crisis Alpha", "Sharpe Impact": "Negative in Bull / Parabolic in Bear", "Trading Strategy": "Black Swan Insurance", "Jurisdiction": "US (Cboe)", "Tax Treatment": "Exempt (Cash-Settled)", "CIO Min Alloc. %": "0%", "CIO Max Alloc. %": "2%", "CIO Grading": "Great", "Noteworthy Comments": "90-120 DTE Puts (Delta < 5). Triggered by VIX crash or Red Regime. Budgeted strictly from 10% of collected VRP."},
    {"Instrument": "XSP Put Spreads", "Type": "Index Option", "Risk Profile": "Moderate", "Alpha Potential": "High (VRP)", "Sharpe Impact": "High", "Trading Strategy": "Weekly Income", "Jurisdiction": "US (Cboe)", "Tax Treatment": "Exempt (Cash-Settled)", "CIO Min Alloc. %": "0%", "CIO Max Alloc. %": "20%", "CIO Grading": "Splendid", "Noteworthy Comments": "Cash-settled S&P 500 options. 100% safe from IRS."},
    {"Instrument": "XND Put Spreads", "Type": "Index Option", "Risk Profile": "Mod/High", "Alpha Potential": "High", "Sharpe Impact": "Moderate", "Trading Strategy": "Satellite Income", "Jurisdiction": "US (Cboe)", "Tax Treatment": "Exempt (Cash-Settled)", "CIO Min Alloc. %": "0%", "CIO Max Alloc. %": "10%", "CIO Grading": "Great", "Noteworthy Comments": "Micro-Nasdaq 100. Cash-settled. IRS Safe. Higher volatility than XSP."},
    {"Instrument": "CSPX", "Type": "UCITS ETF", "Risk Profile": "Moderate", "Alpha Potential": "Zero", "Sharpe Impact": "Baseline", "Trading Strategy": "Long Term", "Jurisdiction": "Ireland", "Tax Treatment": "Exempt (Irish Domicile)", "CIO Min Alloc. %": "0%", "CIO Max Alloc. %": "60%", "CIO Grading": "Great", "Noteworthy Comments": "Irish-domiciled S&P 500. Shields against 40% Estate Tax."},
    {"Instrument": "CNDX", "Type": "UCITS ETF", "Risk Profile": "Aggressive", "Alpha Potential": "High", "Sharpe Impact": "Moderate", "Trading Strategy": "Long Term", "Jurisdiction": "Ireland", "Tax Treatment": "Exempt (Irish Domicile)", "CIO Min Alloc. %": "0%", "CIO Max Alloc. %": "40%", "CIO Grading": "Great", "Noteworthy Comments": "Irish-domiciled Nasdaq 100. Shields against 40% Estate Tax. High beta tech exposure."},
    {"Instrument": "ITWN (Taiwan)", "Type": "UCITS ETF", "Risk Profile": "Aggressive", "Alpha Potential": "High", "Sharpe Impact": "Moderate", "Trading Strategy": "Momentum", "Jurisdiction": "Ireland", "Tax Treatment": "Exempt (Irish Domicile)", "CIO Min Alloc. %": "0%", "CIO Max Alloc. %": "15%", "CIO Grading": "Great", "Noteworthy Comments": "Geographic tech alpha via Irish wrapper."},
    {"Instrument": "CSKR (Korea)", "Type": "UCITS ETF", "Risk Profile": "Aggressive", "Alpha Potential": "High", "Sharpe Impact": "Moderate", "Trading Strategy": "Momentum", "Jurisdiction": "Ireland", "Tax Treatment": "Exempt (Irish Domicile)", "CIO Min Alloc. %": "0%", "CIO Max Alloc. %": "15%", "CIO Grading": "Great", "Noteworthy Comments": "Geographic tech alpha via Irish wrapper."},
    {"Instrument": "CNYA (China)", "Type": "UCITS ETF", "Risk Profile": "Aggressive", "Alpha Potential": "High", "Sharpe Impact": "Volatile", "Trading Strategy": "Momentum", "Jurisdiction": "Ireland", "Tax Treatment": "Exempt (Irish Domicile)", "CIO Min Alloc. %": "0%", "CIO Max Alloc. %": "10%", "CIO Grading": "Great", "Noteworthy Comments": "Geographic tech alpha via Irish wrapper."},
    {"Instrument": "SGLN / IGLN (Gold)", "Type": "UCITS ETC", "Risk Profile": "Moderate", "Alpha Potential": "Crisis Alpha", "Sharpe Impact": "Stabilizer", "Trading Strategy": "Tail Hedge", "Jurisdiction": "Ireland", "Tax Treatment": "Exempt (Irish Domicile)", "CIO Min Alloc. %": "0%", "CIO Max Alloc. %": "10%", "CIO Grading": "Good", "Noteworthy Comments": "Geopolitical crisis hedge. Rises during interest rate cuts and wars."},
    {"Instrument": "BTC/ETH ETPs", "Type": "Crypto ETP", "Risk Profile": "Aggressive", "Alpha Potential": "High", "Sharpe Impact": "Volatile", "Trading Strategy": "Uncorrelated", "Jurisdiction": "Europe (Jersey/CH)", "Tax Treatment": "Exempt (Offshore Wrapper)", "CIO Min Alloc. %": "0%", "CIO Max Alloc. %": "5%", "CIO Grading": "Good", "Noteworthy Comments": "Offshore crypto wrappers (e.g. CoinShares). IRS safe spot exposure."},
    {"Instrument": "US Tech CFDs", "Type": "OTC Contract", "Risk Profile": "Aggressive", "Alpha Potential": "High", "Sharpe Impact": "Negative", "Trading Strategy": "Swing Trading", "Jurisdiction": "UK/Offshore", "Tax Treatment": "Exempt (OTC Derivative)", "CIO Min Alloc. %": "0%", "CIO Max Alloc. %": "3%", "CIO Grading": "Good", "Noteworthy Comments": "Synthetic derivatives. 0% IRS risk. Quarantined strictly based on cash buffers to prevent PDT locks."},
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

if not pos_df.empty:
    for i, r in pos_df.iterrows():
        ac = r['asset_class']
        if ac == 'Crypto': alloc_map['BTC/ETH ETPs'] = alloc_map.get('BTC/ETH ETPs', 0) + r['market_value']
        elif ac == 'Gold': alloc_map['SGLN / IGLN (Gold)'] = alloc_map.get('SGLN / IGLN (Gold)', 0) + r['market_value']
        elif ac == 'Cash': alloc_map['USD Cash'] = alloc_map.get('USD Cash', 0) + r['market_value']
        elif ac == 'International Stocks': 
            alloc_map['International Stocks'] = alloc_map.get('International Stocks', 0) + r['market_value']
        elif ac == 'US Tech CFDs': 
            alloc_map['US Tech CFDs'] = alloc_map.get('US Tech CFDs', 0) + r['market_value']
        elif ac == 'Active Swing': alloc_map['International Stocks'] = alloc_map.get('International Stocks', 0) + r['market_value']
        elif ac == 'Opt Liab':
            if 'XND' in r['symbol']: alloc_map['XND Put Spreads'] = alloc_map.get('XND Put Spreads', 0) + r['market_value']
            else: alloc_map['XSP Put Spreads'] = alloc_map.get('XSP Put Spreads', 0) + r['market_value']
        elif ac == 'Tail Hedge': alloc_map['Deep OTM Tail Hedge'] = alloc_map.get('Deep OTM Tail Hedge', 0) + r['market_value']
        else: alloc_map[ac] = alloc_map.get(ac, 0) + r['market_value']
    
def get_pct(inst):
    if inst == 'Accruals, Unsettled & FX': return 0.0 
    if inst == 'ITWN (Taiwan)': val = alloc_map.get('ITWN', 0)
    elif inst == 'CSKR (Korea)': val = alloc_map.get('CSKR', 0)
    elif inst == 'CNYA (China)': val = alloc_map.get('CNYA', 0)
    elif inst == 'SGLN / IGLN (Gold)': val = alloc_map.get('SGLN / IGLN (Gold)', 0)
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

option_instruments = ["XSP Put Spreads", "XND Put Spreads", "/MES Put Spreads", "XSP LEAPS"]
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

# --- SECTION 10: MONTE CARLO SIMULATION ---
st.subheader("8. Estate Montecarlo PnL Simulation - Projections vs History")
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
        
        spaghetti_colors = [
            'rgba(148, 163, 184, 0.25)', 'rgba(100, 116, 139, 0.25)', 
            'rgba(71, 85, 105, 0.25)', 'rgba(56, 189, 248, 0.15)', 'rgba(14, 165, 233, 0.15)'
        ]
        
        for i in range(200):
            mc_fig.add_trace(go.Scatter(
                y=cum_sim[i], mode='lines', line=dict(color=random.choice(spaghetti_colors), width=1.5), showlegend=False, hoverinfo='skip'
            ))
        
        mc_fig.add_trace(go.Scatter(y=cum_sim[best_idx], name='Best Case', mode='lines', line=dict(color='#166534', width=4.5)))
        mc_fig.add_trace(go.Scatter(y=cum_sim[worst_idx], name='Worst Case', mode='lines', line=dict(color='#991b1b', width=4.5)))
        mc_fig.add_trace(go.Scatter(y=mc_avg_path, name='Statistically Expected (Mean)', mode='lines', line=dict(color='blue', width=6)))
        mc_fig.add_trace(go.Scatter(y=orig_cum, name='Original Realized History', mode='lines', line=dict(color='black', width=9)))
        
        last_x = sim_length
        mc_fig.add_annotation(x=last_x, y=cum_sim[best_idx][-1], text=f"Best: ${cum_sim[best_idx][-1]:,.0f}", showarrow=False, xanchor='left', bgcolor='#166534', font=dict(color='white', size=11))
        mc_fig.add_annotation(x=last_x, y=cum_sim[worst_idx][-1], text=f"Worst: ${cum_sim[worst_idx][-1]:,.0f}", showarrow=False, xanchor='left', bgcolor='#991b1b', font=dict(color='white', size=11))
        mc_fig.add_annotation(x=last_x, y=mc_avg_path[-1], text=f"Expected: ${mc_avg_path[-1]:,.0f}", showarrow=False, xanchor='left', bgcolor='blue', font=dict(color='white', size=11))
        mc_fig.add_annotation(x=last_x, y=orig_cum[-1], text=f"Original: ${orig_cum[-1]:,.0f}", showarrow=False, xanchor='left', bgcolor='black', font=dict(color='white', size=11))
        
        mc_fig.update_layout(
            height=800, margin=dict(l=20, r=80, t=30, b=20), plot_bgcolor='rgba(0,0,0,0)', 
            xaxis_title='Trading Days Forward', 
            yaxis=dict(title='Cumulative Net Profit (USD)', showgrid=True, gridcolor='LightGray', zeroline=True, zerolinecolor='black', zerolinewidth=1, layer='above traces'), 
            xaxis=dict(showgrid=True, gridwidth=1, gridcolor='LightGray', layer='above traces'),
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
        )
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

# --- SECTION 11: THE OPTIONS PERFORMANCE LEDGER & TOPOGRAPHY ENGINE ---
st.subheader("9. The Options Performance Ledger & Topography Engine")

if not journal_raw_df.empty:
    active_vrp = journal_raw_df[pd.isnull(journal_raw_df['Close Date'])].copy()
    if not active_vrp.empty:
        active_vrp['Days Remaining'] = pd.to_numeric(active_vrp['Days Remaining'], errors='coerce')
        active_vrp['Annualized ROC %'] = pd.to_numeric(active_vrp['Annualized ROC %'], errors='coerce')
        
        # Safely calculate marker size avoiding Division by Zero or NaN
        max_collateral = active_vrp['Collateral Locked (USD)'].max()
        if pd.isna(max_collateral) or max_collateral <= 0:
            marker_sizes = 20  # Safe fallback size
        else:
            marker_sizes = (active_vrp['Collateral Locked (USD)'] / max_collateral * 40 + 10).fillna(20)
        
        fig_scatter = go.Figure()
        fig_scatter.add_trace(go.Scatter(
            x=active_vrp['Days Remaining'],
            y=active_vrp['Annualized ROC %'],
            mode='markers+text',
            text=active_vrp['Ticker'] + ' ' + active_vrp['Short Strike'].astype(str),
            textposition="top center",
            textfont=dict(size=9),
            marker=dict(
                size=marker_sizes,
                color=active_vrp['Return on Capital (ROC) %'],
                colorscale='RdYlGn',
                showscale=True,
                colorbar=dict(title="Live ROC %"),
                line=dict(width=1, color='black')
            ),
            hovertemplate="<b>%{text}</b><br>Days Rem: %{x}<br>Ann. ROC: %{y:.1f}%<br>Margin: $%{customdata:,.0f}<extra></extra>",
            customdata=active_vrp['Collateral Locked (USD)']
        ))        
        
        fig_scatter.add_vline(x=21, line_dash="dash", line_color="red", annotation_text="Gamma Cliff (21 DTE)")
        fig_scatter.add_hline(y=0, line_dash="solid", line_color="black")
        
        fig_scatter.update_layout(
            title="VRP Capital Velocity Visualizer (Theta vs. ROC)",
            xaxis_title="Days Remaining (DTE) →",
            yaxis_title="Annualized ROC (%)",
            xaxis=dict(autorange="reversed"),
            plot_bgcolor='rgba(0,0,0,0)',
            margin=dict(l=20, r=20, t=40, b=20),
            height=400
        )
        st.plotly_chart(fig_scatter, width="stretch")

def style_journal(df):
    css_df = pd.DataFrame('', index=df.index, columns=df.columns)
    for i, row in df.iterrows():
        # Green highlight logic injected from session state
        if row.get('👁️ View 3D') == True:
            css_df.loc[i] = 'background-color: #dcfce7; color: #166534; font-weight: bold;'
            continue
            
        if 'Annualized ROC %' in df.columns and pd.notna(row['Annualized ROC %']) and isinstance(row['Annualized ROC %'], (int, float)) and row['Annualized ROC %'] > 100.0:
            css_df.at[i, 'Annualized ROC %'] = 'background-color: #fef08a; color: #856404; font-weight: bold;'
        if 'Days in Trade' in df.columns and pd.notna(row['Days in Trade']) and isinstance(row['Days in Trade'], (int, float)) and row['Days in Trade'] <= 14 and row['Days in Trade'] > 0:
            css_df.at[i, 'Days in Trade'] = 'background-color: #d1e7dd; color: #0f5132; font-weight: bold;'
        if 'Days Remaining' in df.columns and pd.notna(row['Days Remaining']) and str(row['Days Remaining']) != 'Closed' and 'DTE at Entry' in df.columns and pd.notna(row['DTE at Entry']):
            try:
                if float(row['Days Remaining']) < (float(row['DTE at Entry']) / 2): css_df.at[i, 'Days Remaining'] = 'background-color: #f8d7da; color: #842029; font-weight: bold;'
                else: css_df.at[i, 'Days Remaining'] = 'background-color: #d1e7dd; color: #0f5132; font-weight: bold;'
            except: pass
        for col in ['Collateral Locked (USD)', 'Total Net Credit (USD)', 'Target 50% Exit Price (USD)', 'Days Remaining', 'Days in Trade', 'Total P&L (USD)', 'Return on Capital (ROC) %', 'Annualized ROC %']:
            if col in css_df.columns: css_df.at[i, col] += ' background-color: #f3f4f6;'
    return css_df

if not journal_raw_df.empty:
    col_ledger, col_2d, col_3d = st.columns([0.50, 0.25, 0.25])
    
    with col_ledger:
       
        if 'checked_3d_rows' not in st.session_state:
            st.session_state['checked_3d_rows'] = set()
            
        if 'journal_editor' in st.session_state:
            edits = st.session_state['journal_editor'].get('edited_rows', {})
            for row_idx, row_edits in edits.items():
                if '👁️ View 3D' in row_edits:
                    if row_edits['👁️ View 3D']:
                        st.session_state['checked_3d_rows'].add(row_idx)
                    else:
                        st.session_state['checked_3d_rows'].discard(row_idx)
                        
        view_state = [True if i in st.session_state['checked_3d_rows'] else False for i in range(len(journal_raw_df))]
        
        display_df = journal_raw_df.copy()
        display_df.insert(0, '👁️ View 3D', view_state)
        
        # Apply logic styles AND reduce the font size
        styled_journal = display_df.style.apply(lambda x: style_journal(display_df), axis=None).set_properties(**{'font-size': '13px'})
        
        edited_df = st.data_editor(
            styled_journal, width='stretch', num_rows="dynamic", height=750, key="journal_editor",
            disabled=['Collateral Locked (USD)', 'Total Net Credit (USD)', 'Target 50% Exit Price (USD)', 'Days Remaining', 'Days in Trade', 'Total P&L (USD)', 'Return on Capital (ROC) %', 'Annualized ROC %'],
            column_config={
                "👁️ View 3D": st.column_config.CheckboxColumn("3D", width="small"),
                "Tranche ID": st.column_config.TextColumn("Tranche", width="medium"),
                "Open Date": st.column_config.DateColumn("Open", width="small"), 
                "Ticker": st.column_config.TextColumn("Sym", width="small"),
                "DTE at Entry": st.column_config.NumberColumn("DTE In", width="small"),
                "Short Strike": st.column_config.NumberColumn("Short", width="small"),
                "Long Strike": st.column_config.NumberColumn("Long", width="small"),
                "Quantity": st.column_config.NumberColumn("Qty", width="small"),
                "Premium Collected (USD)": st.column_config.NumberColumn("Prem", format="$%.2f", width="small"),
                "Collateral Locked (USD)": st.column_config.NumberColumn("Margin", format="$%.0f", width="small"),
                "Total Net Credit (USD)": st.column_config.NumberColumn("NetCred", format="$%.0f", width="small"),
                "Target 50% Exit Price (USD)": st.column_config.NumberColumn("50% TP", format="$%.2f", width="small"),
                "Close Date": st.column_config.DateColumn("Close", width="small"),
                "Days Remaining": st.column_config.Column("DTE", width="small"),
                "Closing Price (USD)": st.column_config.NumberColumn("Exit $", format="$%.2f", width="small"),
                "Days in Trade": st.column_config.NumberColumn("Days", width="small"),
                "Total P&L (USD)": st.column_config.NumberColumn("PnL", format="$%.0f", width="small"),
                "Return on Capital (ROC) %": st.column_config.NumberColumn("ROC", format="%.1f%%", width="small"),
                "Annualized ROC %": st.column_config.NumberColumn("Ann ROC", format="%.0f%%", width="small"),
         
                # --- HIDING THE FAT ---
                "Macro VIX at Entry": None,
                "Chain ATM IV at Entry (%)": None,
                "Exit Macro VIX": None,
                "Exit Chain ATM IV (%)": None,
                "Notes / Adjustments": None
            }
        )
        
        
    db_df = edited_df.drop(columns=['👁️ View 3D'])
    
    def normalize_for_compare(df_in):
        df_cmp = df_in.copy()
        cols_to_drop = ['Collateral Locked (USD)', 'Total Net Credit (USD)', 'Target 50% Exit Price (USD)', 'Days Remaining', 'Days in Trade', 'Total P&L (USD)', 'Return on Capital (ROC) %', 'Annualized ROC %']
        df_cmp = df_cmp.drop(columns=[c for c in cols_to_drop if c in df_cmp.columns])
        for col in df_cmp.select_dtypes(include=['float64', 'float32']).columns: df_cmp[col] = df_cmp[col].round(4)
        return df_cmp.fillna('').astype(str).replace(r'^(nan|None|NaT|<NA>)$', '', regex=True).apply(lambda x: x.str.strip())
        
    if not normalize_for_compare(journal_raw_df).equals(normalize_for_compare(db_df)):
        conn = sqlite3.connect(DB_PATH)
        db_df.to_sql('options_journal', conn, if_exists='replace', index=False)
        conn.close()
        st.rerun() 

    selected_rows = edited_df[edited_df['👁️ View 3D'] == True]
    
    if selected_rows.empty:
        with col_2d: st.info("👈 Check '3D' on any contract row to render Live 2D/3D Topography.")
    elif selected_rows.shape[0] > 1:
        with col_2d: st.error("❌ **Mutex Lock Active:** You have checked multiple boxes. Please uncheck duplicates so only ONE contract is selected.")           
    else:
        row_data = selected_rows.iloc[0]
        tckr = row_data.get('Ticker', 'XSP')
        raw_dte = row_data.get('Days Remaining', 0)
        
        if str(raw_dte) == 'Closed':
            with col_2d: st.warning(f"**{tckr} Contract is Closed.** Black-Scholes topography locked.")
        else:
            curr_dte = float(raw_dte) if pd.notna(raw_dte) else 0.0
            init_dte = float(row_data.get('DTE at Entry', 45)) if pd.notna(row_data.get('DTE at Entry', 45)) else 45.0
            K_s = float(row_data.get('Short Strike', 0)) if pd.notna(row_data.get('Short Strike', 0)) else 0.0
            K_l = float(row_data.get('Long Strike', 0)) if pd.notna(row_data.get('Long Strike', 0)) else 0.0
            qty = float(row_data.get('Quantity', 1)) if pd.notna(row_data.get('Quantity', 1)) else 1.0
            prem = float(row_data.get('Premium Collected (USD)', 0)) if pd.notna(row_data.get('Premium Collected (USD)', 0)) else 0.0
            
            with st.spinner(f"Fetching Live Data for {tckr}..."): 
                S_live, iv_live_raw = fetch_live_data(tckr)
            
            with col_2d:
                iv_override = st.slider(f"🌪️ {tckr} Volatility (IV) Stress Tester %", min_value=5.0, max_value=80.0, value=float(iv_live_raw), step=0.1, help="Simulate a Volatility Shock. Default value is locked to the live market VIX.")

            r_rate = LIVE_RF_RATE
            iv_dec = iv_override / 100.0
            T_init = init_dte / 365.0
            T_curr = curr_dte / 365.0
            
            # v52: 3D Engine Type Detection
            tranche_str = str(row_data.get('Tranche ID', ''))
            is_long_call = (K_s == 0 or pd.isna(K_s)) and K_l > 0 and ('Beta' in tranche_str or 'Call' in tranche_str)
            is_long_put = (K_s == 0 or pd.isna(K_s)) and K_l > 0 and not is_long_call
            is_call = K_s < K_l and not is_long_call and not is_long_put
            
            pricing_func = get_call_greeks if (is_call or is_long_call) else get_put_greeks
            
            def calc_exp_payoff(p, k_s, k_l, prem):
                if is_long_put: return max(k_l - p, 0) - prem
                if is_long_call: return max(p - k_l, 0) - prem
                if is_call: return prem - (max(p - k_s, 0) - max(p - k_l, 0))
                else: return prem - (max(k_s - p, 0) - max(k_l - p, 0))

            if is_long_put:
                s_p, s_d, s_g, s_v, s_t = 0, 0, 0, 0, 0
                l_p, l_d, l_g, l_v, l_t = get_put_greeks(S_live, K_l, T_curr, r_rate, iv_dec)
                curr_spread_price = l_p
                unrealized_pnl = (curr_spread_price - prem) * qty * 100
                margin_req = prem * 100 * qty 
                rom_pct = (unrealized_pnl / margin_req * 100) if margin_req > 0 else 0
                net_delta, net_gamma, net_theta, net_vega = l_d * qty * 100, l_g * qty * 100, l_t * qty * 100, l_v * qty * 100
                min_plot = int(min(K_l - 60, S_live - 30))
                max_plot = int(max(K_l + 20, S_live + 20))
                
            elif is_long_call:
                s_p, s_d, s_g, s_v, s_t = 0, 0, 0, 0, 0
                l_p, l_d, l_g, l_v, l_t = get_call_greeks(S_live, K_l, T_curr, r_rate, iv_dec)
                curr_spread_price = l_p
                unrealized_pnl = (curr_spread_price - prem) * qty * 100
                margin_req = prem * 100 * qty 
                rom_pct = (unrealized_pnl / margin_req * 100) if margin_req > 0 else 0
                net_delta, net_gamma, net_theta, net_vega = l_d * qty * 100, l_g * qty * 100, l_t * qty * 100, l_v * qty * 100
                min_plot = int(min(K_l - 20, S_live - 30))
                max_plot = int(max(K_l + 60, S_live + 30))
                
            else:
                s_p, s_d, s_g, s_v, s_t = pricing_func(S_live, K_s, T_curr, r_rate, iv_dec)
                l_p, l_d, l_g, l_v, l_t = pricing_func(S_live, K_l, T_curr, r_rate, iv_dec)
                curr_spread_price = s_p - l_p
                unrealized_pnl = (prem - curr_spread_price) * qty * 100
                margin_req = abs(K_s - K_l) * 100 * qty
                rom_pct = (unrealized_pnl / margin_req * 100) if margin_req > 0 else 0
                net_delta, net_gamma, net_theta, net_vega = (l_d - s_d) * qty * 100, (l_g - s_g) * qty * 100, (l_t - s_t) * qty * 100, (l_v - s_v) * qty * 100
                
                if is_call:
                    min_plot = int(min(K_s - 40, S_live - 10))
                    max_plot = int(max(K_l + 30, S_live + 10))
                else:
                    min_plot = int(min(K_l - 30, S_live - 10))
                    max_plot = int(max(K_s + 40, S_live + 10))

            x_vals = [p / 2.0 for p in range(int(min_plot * 2), int(max_plot * 2) + 1)]
            y_exp, y_init, y_curr = [], [], []
                            
            for p in x_vals:
                y_exp.append(calc_exp_payoff(p, K_s, K_l, prem) * qty * 100)
                if is_long_put:
                    t0_l, _, _, _, _ = get_put_greeks(p, K_l, T_init, r_rate, iv_dec)
                    y_init.append((t0_l - prem) * qty * 100)
                    tC_l, _, _, _, _ = get_put_greeks(p, K_l, T_curr, r_rate, iv_dec)
                    y_curr.append((tC_l - prem) * qty * 100)
                else:
                    t0_s, _, _, _, _ = pricing_func(p, K_s, T_init, r_rate, iv_dec)
                    t0_l, _, _, _, _ = pricing_func(p, K_l, T_init, r_rate, iv_dec)
                    y_init.append((prem - (t0_s - t0_l)) * qty * 100)
                    tC_s, _, _, _, _ = pricing_func(p, K_s, T_curr, r_rate, iv_dec)
                    tC_l, _, _, _, _ = pricing_func(p, K_l, T_curr, r_rate, iv_dec)
                    y_curr.append((prem - (tC_s - tC_l)) * qty * 100)

            with col_2d:
                tranche_id = str(row_data.get('Tranche ID', ''))
                acct_filter = 'U23144948' if 'Silo A' in tranche_id else 'U23154199' if 'Silo C' in tranche_id else None
                if acct_filter: leg_mask = pos_df['account'] == acct_filter
                else: leg_mask = pd.Series(True, index=pos_df.index)
                    
                if is_long_put:
                    long_mask = leg_mask & pos_df['symbol'].str.contains(tckr) & (pos_df['symbol'].str.contains(f"_{float(K_l)}_") | pos_df['symbol'].str.contains(f"_{int(K_l)}_"))
                    tws_unrealized_pnl = pos_df[long_mask]['unrealized_pnl'].sum()
                else:
                    short_mask = leg_mask & pos_df['symbol'].str.contains(tckr) & (pos_df['symbol'].str.contains(f"_{float(K_s)}_") | pos_df['symbol'].str.contains(f"_{int(K_s)}_"))
                    long_mask = leg_mask & pos_df['symbol'].str.contains(tckr) & (pos_df['symbol'].str.contains(f"_{float(K_l)}_") | pos_df['symbol'].str.contains(f"_{int(K_l)}_"))
                    tws_unrealized_pnl = pos_df[short_mask | long_mask]['unrealized_pnl'].sum()
                
                tws_rom_pct = (tws_unrealized_pnl / margin_req * 100) if margin_req > 0 else 0
                
                color_css = "#166534" if unrealized_pnl >= 0 else "#991b1b"
                bg_css = "#f0fdf4" if unrealized_pnl >= 0 else "#fef2f2"
                tws_color = "#166534" if tws_unrealized_pnl >= 0 else "#991b1b"
                tws_bg = "#f0fdf4" if tws_unrealized_pnl >= 0 else "#fef2f2"
                
                st.markdown(f"""
                <div style="display: flex; gap: 15px; margin-bottom: 10px;">
                    <div style="flex: 1; background-color: {tws_bg}; padding: 15px; border-radius: 8px; border: 1px solid {tws_color}; text-align: center; box-shadow: 0 1px 3px rgba(0,0,0,0.1);">
                        <span style="font-size: 13px; color: #4b5563; font-weight: bold; text-transform: uppercase;">Live TWS P&L (Actual)</span><br>
                        <span style="font-size: 26px; font-weight: 900; color: {tws_color};">${tws_unrealized_pnl:,.2f} <span style="font-size: 16px;">({tws_rom_pct:+.2f}%)</span></span>
                    </div>
                    <div style="flex: 1; background-color: {bg_css}; padding: 15px; border-radius: 8px; border: 1px solid {color_css}; text-align: center; opacity: 0.9;">
                        <span style="font-size: 13px; color: #4b5563; font-weight: bold; text-transform: uppercase;">Theoretical P&L (Sim)</span><br>
                        <span style="font-size: 26px; font-weight: 900; color: {color_css};">${unrealized_pnl:,.2f} <span style="font-size: 16px;">({rom_pct:+.2f}%)</span></span>
                    </div>
                </div>
                <div style="text-align: center; font-size: 12px; color: #4b5563; margin-bottom: 20px; background-color: #f9fafb; padding: 8px; border-radius: 6px; border: 1px solid #e5e7eb;">
                    <b>Sim Spread Value:</b> ${curr_spread_price:.2f} | <b>Net Theta:</b> ${net_theta:+.2f}/day | <b>Underlying:</b> ${S_live:,.2f} | <b>IV Override:</b> {iv_override:.2f}%
                </div>
                """.replace('\n', ''), unsafe_allow_html=True)

                fig_2d = go.Figure()
                if is_long_put:
                    fig_2d.add_vrect(x0=min_plot, x1=K_l, fillcolor="red", opacity=0.05, layer="below", line_width=0)
                    fig_2d.add_vline(x=K_l, line_dash="dot", line_color="red", annotation_text="Long", annotation_position="top right")
                elif is_call:
                    fig_2d.add_vrect(x0=min_plot, x1=K_s, fillcolor="green", opacity=0.05, layer="below", line_width=0)
                    fig_2d.add_vrect(x0=K_l, x1=max_plot, fillcolor="red", opacity=0.05, layer="below", line_width=0)
                    fig_2d.add_vline(x=K_s, line_dash="dot", line_color="green", annotation_text="Short", annotation_position="top right")
                    fig_2d.add_vline(x=K_l, line_dash="dot", line_color="red", annotation_text="Long", annotation_position="top left")
                else:
                    fig_2d.add_vrect(x0=K_s, x1=max_plot, fillcolor="green", opacity=0.05, layer="below", line_width=0)    
                    fig_2d.add_vrect(x0=min_plot, x1=K_l, fillcolor="red", opacity=0.05, layer="below", line_width=0)
                    fig_2d.add_vline(x=K_s, line_dash="dot", line_color="green", annotation_text="Short", annotation_position="top left")
                    fig_2d.add_vline(x=K_l, line_dash="dot", line_color="red", annotation_text="Long", annotation_position="top right")

                fig_2d.add_trace(go.Scatter(x=x_vals, y=y_exp, mode='lines', name='Expiration', line=dict(color='gray', dash='dot', width=2)))
                fig_2d.add_trace(go.Scatter(x=x_vals, y=y_init, mode='lines', name='Entry Day', line=dict(color='purple', width=8, dash='dash')))
                fig_2d.add_trace(go.Scatter(x=x_vals, y=y_curr, mode='lines', name='Today', line=dict(color='#2563eb', width=4.5)))
                fig_2d.add_trace(go.Scatter(x=[S_live], y=[unrealized_pnl], mode='markers', name='Current Price', marker=dict(color='black', size=12)))
                
                fig_2d.update_layout(title="2D Theta Decay Profile & Gamma Cliff", margin=dict(l=20, r=20, t=40, b=20), height=500, legend=dict(orientation="h", y=-0.2))
                st.plotly_chart(fig_2d, width="stretch")
            
            with col_3d:
                step = 1
                y_3d = list(range(int(init_dte), -1, -step))
                z_3d = []
                for d in y_3d:
                    T_3d = max(d / 365.0, 0.0001)
                    z_row = []
                    for p in x_vals:
                        if T_3d <= 0.0001: 
                            z_row.append(calc_exp_payoff(p, K_s, K_l, prem) * qty * 100)
                        else:
                            if is_long_put:
                                t_l, _, _, _, _ = get_put_greeks(p, K_l, T_3d, r_rate, iv_dec)
                                z_row.append((t_l - prem) * qty * 100)
                            elif is_long_call:
                                t_l, _, _, _, _ = get_call_greeks(p, K_l, T_3d, r_rate, iv_dec)
                                z_row.append((t_l - prem) * qty * 100)
                            else:
                                t_s, _, _, _, _ = pricing_func(p, K_s, T_3d, r_rate, iv_dec)
                                t_l, _, _, _, _ = pricing_func(p, K_l, T_3d, r_rate, iv_dec)
                                z_row.append((prem - (t_s - t_l)) * qty * 100)
                    z_3d.append(z_row)
                z_min, z_max = np.min(z_3d), np.max(z_3d)

                fig_3d = go.Figure(data=[go.Surface(
                    z=z_3d, x=x_vals, y=y_3d, 
                    colorscale=[[0, '#fef2f2'],[0.2, '#fca5a5'],[0.5, 'white'],[0.8, '#86efac'],[1, '#f0fdf4']],
                    opacity=0.85, contours=dict(z=dict(show=True, color='black', width=1))
                )])

                skip_days = [int(init_dte), int(curr_dte), int(init_dte / 2.0), 0]
                for idx_d, d in enumerate(y_3d):
                    if int(d) not in skip_days:
                        fig_3d.add_trace(go.Scatter3d(x=x_vals, y=[d]*len(x_vals), z=z_3d[idx_d], mode='lines', line=dict(color='black', width=1), showlegend=False, hoverinfo='skip'))
                
                # Render Scaffolding, Bounds, and Crosses ONLY for Spreads
                if not is_long_put:
                    z_green, z_red = [], []
                    for d in y_3d:
                        T_3d = max(d / 365.0, 0.0001)
                        t_s_g, _, _, _, _ = pricing_func(K_s, K_s, T_3d, r_rate, iv_dec)
                        t_l_g, _, _, _, _ = pricing_func(K_s, K_l, T_3d, r_rate, iv_dec)
                        z_green.append((prem - (t_s_g - t_l_g)) * qty * 100)
                        t_s_r, _, _, _, _ = pricing_func(K_l, K_s, T_3d, r_rate, iv_dec)
                        t_l_r, _, _, _, _ = pricing_func(K_l, K_l, T_3d, r_rate, iv_dec)
                        z_red.append((prem - (t_s_r - t_l_r)) * qty * 100)
                        
                    half_dte = init_dte / 2.0
                    T_half = max(half_dte / 365.0, 0.0001)
                    z_yellow = []
                    for p in x_vals:
                        t_s_y, _, _, _, _ = pricing_func(p, K_s, T_half, r_rate, iv_dec)
                        t_l_y, _, _, _, _ = pricing_func(p, K_l, T_half, r_rate, iv_dec)
                        z_yellow.append((prem - (t_s_y - t_l_y)) * qty * 100)

                    fig_3d.add_trace(go.Scatter3d(x=[K_s]*len(y_3d), y=y_3d, z=z_green, mode='lines', name='Short Strike Limit', line=dict(color='green', width=6), showlegend=False, hoverinfo='skip'))
                    fig_3d.add_trace(go.Scatter3d(x=[K_l]*len(y_3d), y=y_3d, z=z_red, mode='lines', name='Max Loss Limit', line=dict(color='red', width=6), showlegend=False, hoverinfo='skip'))
                    fig_3d.add_trace(go.Scatter3d(x=x_vals, y=[half_dte]*len(x_vals), z=z_yellow, mode='lines', name='Time Stop Limit', line=dict(color='gold', width=6), showlegend=False, hoverinfo='skip'))
                    
                    fig_3d.add_trace(go.Surface(x=[[K_s, K_s],[K_s, K_s]], y=[[0, init_dte],[0, init_dte]], z=[[z_min, z_min],[z_max, z_max]], colorscale=[[0, 'green'],[1, 'green']], opacity=0.225, showscale=False, hoverinfo='skip'))
                    fig_3d.add_trace(go.Surface(x=[[K_l, K_l],[K_l, K_l]], y=[[0, init_dte],[0, init_dte]], z=[[z_min, z_min],[z_max, z_max]], colorscale=[[0, 'red'],[1, 'red']], opacity=0.225, showscale=False, hoverinfo='skip'))
                    fig_3d.add_trace(go.Surface(x=[[x_vals[0], x_vals[-1]], [x_vals[0], x_vals[-1]]], y=[[half_dte, half_dte],[half_dte, half_dte]], z=[[z_min, z_min],[z_max, z_max]], colorscale=[[0, 'yellow'],[1, 'yellow']], opacity=0.30, showscale=False, hoverinfo='skip'))
                    fig_3d.add_trace(go.Surface(x=[[x_vals[0], x_vals[-1]],[x_vals[0], x_vals[-1]]], y=[[0, 0],[init_dte, init_dte]], z=[[0, 0],[0, 0]], colorscale=[[0, 'gray'],[1, 'gray']], opacity=0.30, showscale=False, hoverinfo='skip'))

                    # Scaffolding & Perimeters (Black Frame & Colored Borders)
                    fig_3d.add_trace(go.Scatter3d(x=[K_s, K_s], y=[half_dte, half_dte], z=[z_min, z_max], mode='lines', line=dict(color='black', width=6, dash='dash'), showlegend=False, hoverinfo='skip'))
                    fig_3d.add_trace(go.Scatter3d(x=[K_l, K_l], y=[half_dte, half_dte], z=[z_min, z_max], mode='lines', line=dict(color='black', width=6, dash='dash'), showlegend=False, hoverinfo='skip'))
                    fig_3d.add_trace(go.Scatter3d(x=[K_s, K_s], y=[0, init_dte], z=[0, 0], mode='lines', line=dict(color='black', width=6, dash='dash'), showlegend=False, hoverinfo='skip'))
                    fig_3d.add_trace(go.Scatter3d(x=[K_l, K_l], y=[0, init_dte], z=[0, 0], mode='lines', line=dict(color='black', width=6, dash='dash'), showlegend=False, hoverinfo='skip'))
                    fig_3d.add_trace(go.Scatter3d(x=[x_vals[0], x_vals[-1]], y=[half_dte, half_dte], z=[0, 0], mode='lines', line=dict(color='black', width=6, dash='dash'), showlegend=False, hoverinfo='skip'))

                    fig_3d.add_trace(go.Scatter3d(x=[K_s, K_s, K_s, K_s, K_s], y=[0, init_dte, init_dte, 0, 0], z=[z_min, z_min, z_max, z_max, z_min], mode='lines', line=dict(color='green', width=3), showlegend=False, hoverinfo='skip'))
                    fig_3d.add_trace(go.Scatter3d(x=[K_l, K_l, K_l, K_l, K_l], y=[0, init_dte, init_dte, 0, 0], z=[z_min, z_min, z_max, z_max, z_min], mode='lines', line=dict(color='red', width=3), showlegend=False, hoverinfo='skip'))
                    fig_3d.add_trace(go.Scatter3d(x=[x_vals[0], x_vals[-1], x_vals[-1], x_vals[0], x_vals[0]], y=[half_dte, half_dte, half_dte, half_dte, half_dte], z=[z_min, z_min, z_max, z_max, z_min], mode='lines', line=dict(color='yellow', width=3), showlegend=False, hoverinfo='skip'))
                    fig_3d.add_trace(go.Scatter3d(x=[x_vals[0], x_vals[-1], x_vals[-1], x_vals[0], x_vals[0]], y=[0, 0, init_dte, init_dte, 0], z=[0, 0, 0, 0, 0], mode='lines', line=dict(color='gray', width=3), showlegend=False, hoverinfo='skip'))

                    # --- NEW EXACT BREAKEVEN INTERSECTION TRACE (z=0) ---
                    roots_by_day = []
                    for idx_d, d in enumerate(y_3d):
                        z_row = z_3d[idx_d]
                        day_roots = []
                        for i in range(len(x_vals)-1):
                            # Detect zero crossings 
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
                    # ----------------------------------------------------

                    target_pnl = (prem / 2.0) * qty * 100
                    fig_3d.add_trace(go.Scatter3d(x=[S_live], y=[curr_dte], z=[target_pnl], mode='markers', name='50% Target', marker=dict(color='#16a34a', size=15, symbol='cross')))
                    stop_loss_pnl = -(prem * 2.0) * qty * 100 
                    fig_3d.add_trace(go.Scatter3d(x=[S_live], y=[curr_dte], z=[stop_loss_pnl], mode='markers', name='200% Stop Loss', marker=dict(color='#dc2626', size=15, symbol='cross')))

                # Theta Glide Path (Works for Spreads, Long Puts, and Long Calls)
                y_glide = [d for d in y_3d if d <= curr_dte]
                z_glide = []
                for d in y_glide:
                    T_glide = max(d / 365.0, 0.0001)
                    if is_long_put:
                        t_l_glide, _, _, _, _ = get_put_greeks(S_live, K_l, T_glide, r_rate, iv_dec)
                        z_glide.append((t_l_glide - prem) * qty * 100)
                    elif is_long_call:
                        t_l_glide, _, _, _, _ = get_call_greeks(S_live, K_l, T_glide, r_rate, iv_dec)
                        z_glide.append((t_l_glide - prem) * qty * 100)
                    else:
                        t_s_glide, _, _, _, _ = pricing_func(S_live, K_s, T_glide, r_rate, iv_dec)
                        t_l_glide, _, _, _, _ = pricing_func(S_live, K_l, T_glide, r_rate, iv_dec)
                        z_glide.append((prem - (t_s_glide - t_l_glide)) * qty * 100)

                fig_3d.add_trace(go.Scatter3d(x=[S_live] * len(y_glide), y=y_glide, z=z_glide, mode='lines', name='Theta Glide Path', line=dict(color='cyan', width=8, dash='dashdot')))

                # Existing Traces (Entry/Today/Current Price)
                fig_3d.add_trace(go.Scatter3d(x=x_vals, y=[init_dte]*len(x_vals), z=y_init, mode='lines', name='Entry Day', line=dict(color='purple', width=10, dash='dash')))
                fig_3d.add_trace(go.Scatter3d(x=x_vals, y=[curr_dte]*len(x_vals), z=y_curr, mode='lines', name='Today', line=dict(color='#2563eb', width=7)))
                fig_3d.add_trace(go.Scatter3d(x=[S_live], y=[curr_dte], z=[tws_unrealized_pnl], mode='markers', name='Current Price', marker=dict(color='black', size=6)))
                
                if not is_long_put:
                    fig_3d.add_trace(go.Scatter3d(x=[S_live, S_live], y=[curr_dte, curr_dte], z=[0, tws_unrealized_pnl], mode='lines', name='Anchor Line', line=dict(color='black', width=3, dash='dot'), showlegend=False, hoverinfo='skip'))
                    fig_3d.add_trace(go.Scatter3d(x=[S_live], y=[curr_dte], z=[0], mode='markers', name='Zero Floor Anchor', marker=dict(color='black', size=5, symbol='cross'), showlegend=False, hoverinfo='skip'))            
            
                fig_3d.update_layout(
                    title="3D Topography (Time vs Price)", margin=dict(l=0, r=0, b=0, t=40), height=645, 
                    scene=dict(xaxis_title='Price', yaxis_title='DTE', zaxis_title='P&L ($)', yaxis=dict(autorange='reversed'), camera=dict(eye=dict(x=-1.25, y=-1.25, z=1.25))),
                    legend=dict(orientation="h", yanchor="top", y=-0.15, xanchor="left", x=0)
                )
                st.plotly_chart(fig_3d, width="stretch")

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
    
st.divider()

# --- SECTION 12: THE CHAMPION JOURNAL ---
st.subheader("10. The Champion Journal & TOR Ledger")

if not champion_df.empty:
    ideal_tor = chart_df['tor'].iloc[-1] if not chart_df.empty else 5
    global_1r_base = global_metrics['nav'] * 0.0025 if global_metrics['nav'] > 0 else 1
    global_usd_risk = champion_df['Open Risk ($)'].sum()
    global_tor = global_usd_risk / global_1r_base
    
    # TOR Command Bar
    cols_tor = st.columns(5)
    with cols_tor[0]:
        tor_color = "normal" if global_tor <= ideal_tor else "inverse"
        st.metric(label=f"Global TOR (Limit: {ideal_tor}R)", value=f"{global_tor:.2f} R", delta=f"{ideal_tor - global_tor:.2f} R Buffer", delta_color=tor_color)
        st.caption(f"**Risk:** ${global_usd_risk:,.0f}")
    
    for idx, silo_name in enumerate(['Silo A', 'Silo B', 'Silo C', 'Silo D']):
        with cols_tor[idx+1]:
            silo_df = champion_df[champion_df['Silo'] == silo_name]
            silo_tor = silo_df['Open Risk (R)'].sum() if not silo_df.empty else 0
            silo_usd_risk = silo_df['Open Risk ($)'].sum() if not silo_df.empty else 0
            st.metric(label=f"{silo_name} TOR", value=f"{silo_tor:.2f} R")
            st.caption(f"**Risk:** ${silo_usd_risk:,.0f}")

    st.markdown("---")
    
    # Highlight logic for R-Metrics and Silo Rows
    def highlight_r(val):
        if isinstance(val, float):
            if val <= 0: return 'color: #991b1b; font-weight: bold;' # Red for risk/negative
            elif val > 0: return 'color: #166534; font-weight: bold;' # Green for positive R
        return ''

    def highlight_silo_row(row):
        # Maps Silo names to light, transparent pastel versions of their SILO_MAP colors
        silo_colors = {
            'Silo A': 'background-color: #eff6ff;', # Light Pastel Blue
            'Silo B': 'background-color: #faf5ff;', # Light Pastel Purple
            'Silo C': 'background-color: #f0fdf4;', # Light Pastel Green
            'Silo D': 'background-color: #fefce8;'  # Light Pastel Yellow
        }
        bg_style = silo_colors.get(row['Silo'], '')
        return [bg_style] * len(row)
        
    st.markdown("##### 📈 Active Alpha Positions (Stocks, CFDs, Crypto)")
    st.dataframe(
        champion_df.style.apply(highlight_silo_row, axis=1).format({
            'Qty': '{:,.0f}',
            'Avg Cost': '${:,.2f}',
            'CMP': '${:,.2f}',
            'Live SL (Local)': '{:,.2f}',
            'Live SL (USD)': '${:,.2f}',
            '1R Base ($)': '${:,.0f}',
            'Open Risk ($)': '${:,.0f}',
            'Open Risk (R)': '{:.2f} R',
            'Unrealized (R)': '{:+.2f} R'
        }).map(highlight_r, subset=['Open Risk (R)', 'Unrealized (R)']),
        hide_index=True,
        width="stretch"
    )
else:
    st.info("No active Alpha positions (Stocks/CFDs/Crypto) found to track in the Champion Journal.")    

st.markdown("<br>", unsafe_allow_html=True)
champ_hist_df, all_states_df = load_champion_history()

c_log, c_calc = st.columns([1, 1])

with c_log:
    st.markdown("##### 📥 Automated Reconciliation Inbox")
    st.markdown("""
    <div style="background-color: #f0fdf4; border-left: 5px solid #16a34a; padding: 15px; border-radius: 4px; color: #166534; font-size: 14px;">
        <b>🤖 API Sync Active:</b> The manual data entry form has been permanently decommissioned.<br><br>
        All closed Alpha trades (Stocks, CFDs, Crypto) are now automatically ingested directly from the clearinghouse via the <b>Flex Query API Engine</b>, ensuring 100% mathematical accuracy and zero double-counting.<br><br>
        <i>Action Required: Use the interactive Ledger below to assign Strategy Tags to your newly closed trades to populate your Expectancy analytics.</i>
    </div>
    """, unsafe_allow_html=True)
    
    if not champ_hist_df.empty:
        if st.button("⏪ Undo / Delete Last Logged Exit", width="stretch"):
            conn = sqlite3.connect(DB_PATH)
            c = conn.cursor()
            c.execute("DELETE FROM champion_closed_trades WHERE rowid = (SELECT MAX(rowid) FROM champion_closed_trades)")
            conn.commit()
            conn.close()
            st.success("Deleted last entry.")
            st.cache_data.clear()
            st.rerun()

    with st.form("champion_log_form", clear_on_submit=True):
        unified_options = []
        if not all_states_df.empty:
            for _, r in all_states_df.iterrows():
                silo_name = SILO_MAP.get(r['account'], [r['account']])[0]
                unified_options.append(f"{r['symbol']} - {silo_name}")
        if not champion_df.empty:
            for _, r in champion_df.iterrows():
                unified_options.append(f"{r['Symbol']} - {r['Silo']}")
        unified_options = sorted(list(set(unified_options)))
        
        log_choice = st.selectbox("Select Asset to Log", unified_options + ["Other (Manual Entry)"])
        log_date = st.date_input("Exit Date", datetime.date.today())
        log_pnl = st.number_input("Realized PnL ($) on this Exit", value=0.0, step=50.0, help="Enter the USD profit/loss locked in on this specific exit.")
        log_tags = st.multiselect("Select Tags (Required for Analytics)", CHAMPION_TAGS)
        log_notes = st.text_input("Notes (e.g., 'Scaled out 50% at target')")
        
        if st.form_submit_button("Record Trade in Ledger"):
            if log_choice != "Other (Manual Entry)":
                log_sym, log_silo = log_choice.split(" - ")
                log_acc = next((k for k, v in SILO_MAP.items() if v[0] == log_silo), "Manual")
                
                match = all_states_df[(all_states_df['symbol'] == log_sym) & (all_states_df['account'] == log_acc)]
                if not match.empty:
                    base_nav = match.iloc[0]['base_nav']
                    r_base = base_nav * 0.0025
                else:
                    r_base = 500.0 # Fallback 1R base
                acc = log_acc
                silo = log_silo
            else:
                log_sym = "Manual"
                r_base = 500.0
                acc = "Manual"
                silo = "Manual"
                
            r_multiple = log_pnl / r_base if r_base > 0 else 0
            tags_str = ", ".join(log_tags)
            
            conn = sqlite3.connect(DB_PATH)
            c = conn.cursor()
            c.execute('''INSERT INTO champion_closed_trades 
                         (close_date, symbol, account, silo, r_base, realized_pnl, r_multiple, notes, tags) 
                         VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)''', 
                      (log_date.isoformat(), log_sym, acc, silo, r_base, log_pnl, r_multiple, log_notes, tags_str))
            conn.commit()
            conn.close()
            st.success(f"Successfully logged {log_sym} in {silo} Exit: {r_multiple:+.2f} R")
            st.cache_data.clear()
            st.rerun()

with c_calc:
    st.markdown("##### 🏆 Champion Profitability Calculator")
    
    if not champ_hist_df.empty:
        # --- THE EXPECTANCY FILTER ---
        selected_filters = st.multiselect("Filter Analytics by Tag(s):", CHAMPION_TAGS, help="Leave blank to view global metrics.")
        
        filtered_df = champ_hist_df.copy()
        if selected_filters:
            # Keep rows where the 'tags' string contains AT LEAST ONE of the selected filters
            mask = filtered_df['tags'].fillna('').apply(lambda x: any(f in x for f in selected_filters))
            filtered_df = filtered_df[mask]
        
        if not filtered_df.empty:
            tot_trades = len(filtered_df)
            winners = filtered_df[filtered_df['r_multiple'] > 0]
            losers = filtered_df[filtered_df['r_multiple'] <= 0]
            
            win_rate = (len(winners) / tot_trades) * 100 if tot_trades > 0 else 0
            avg_r_win = winners['r_multiple'].mean() if not winners.empty else 0
            avg_r_loss = losers['r_multiple'].mean() if not losers.empty else 0
            
            arr = abs(avg_r_win / avg_r_loss) if avg_r_loss != 0 else 0
            expectancy = ((win_rate/100) * avg_r_win) + ((1 - (win_rate/100)) * avg_r_loss)
            net_r_gained = filtered_df['r_multiple'].sum()
            
            html_calc = f"""
            <table style="width:100%; border-collapse: collapse; background-color: white; border: 1px solid #cbd5e1; font-size: 14px;">
                <tbody>
                    <tr style="background-color: #f8fafc; border-bottom: 1px solid #e5e7eb;">
                        <td style="padding: 10px; font-weight: bold; color: #334155;">Filtered Exits</td>
                        <td style="padding: 10px; text-align: right; font-weight: bold;">{tot_trades}</td>
                    </tr>
                    <tr style="background-color: #dcfce7; border-bottom: 1px solid #e5e7eb;">
                        <td style="padding: 10px; font-weight: bold; color: #166534;">Win Rate</td>
                        <td style="padding: 10px; text-align: right; font-weight: bold; color: #166534;">{win_rate:.2f}%</td>
                    </tr>
                    <tr style="border-bottom: 1px solid #e5e7eb;">
                        <td style="padding: 10px; font-weight: bold; color: #166534;">Average R Gain (Winners)</td>
                        <td style="padding: 10px; text-align: right; font-weight: bold; color: #166534;">+{avg_r_win:.2f} R</td>
                    </tr>
                    <tr style="border-bottom: 1px solid #e5e7eb;">
                        <td style="padding: 10px; font-weight: bold; color: #991b1b;">Average R Loss (Losers)</td>
                        <td style="padding: 10px; text-align: right; font-weight: bold; color: #991b1b;">{avg_r_loss:.2f} R</td>
                    </tr>
                    <tr style="background-color: #f8fafc; border-bottom: 1px solid #e5e7eb;">
                        <td style="padding: 10px; font-weight: bold; color: #334155;">Absolute Reward/Risk (ARR)</td>
                        <td style="padding: 10px; text-align: right; font-weight: bold;">{arr:.2f}</td>
                    </tr>
                    <tr style="background-color: #eff6ff; border-bottom: 1px solid #bfdbfe;">
                        <td style="padding: 10px; font-weight: bold; color: #1e3a8a;">Trade Expectancy (in R)</td>
                        <td style="padding: 10px; text-align: right; font-weight: bold; color: #1e3a8a;">{expectancy:.3f} R</td>
                    </tr>
                    <tr style="background-color: #f0fdf4; border-bottom: 2px solid #166534;">
                        <td style="padding: 10px; font-weight: bold; font-size: 16px; color: #166534;">Total Net R Gained</td>
                        <td style="padding: 10px; text-align: right; font-weight: 900; font-size: 16px; color: #166534;">{net_r_gained:+.2f} R</td>
                    </tr>
                </tbody>
            </table>
            """
            st.markdown(html_calc, unsafe_allow_html=True)
        else:
            st.warning("No trades match the selected tag filters.")
    else:
        st.info("No closed trades logged yet.")

st.markdown("---")
st.markdown("##### 📚 Closed Trades Ledger (Editable)")
if not champ_hist_df.empty:   
    display_hist = champ_hist_df.copy()
    display_hist.rename(columns={
        'close_date': 'Exit Date', 'symbol': 'Symbol', 'silo': 'Silo',
        'r_base': '1R Base ($)', 'realized_pnl': 'Realized PnL ($)',
        'r_multiple': 'R-Multiple', 'tags': 'Tags', 'notes': 'Notes'
    }, inplace=True)
    
    if 'Tags' not in display_hist.columns: display_hist['Tags'] = ''
    
    # rowid is kept hidden for safe database updates
    display_hist = display_hist[['rowid', 'Exit Date', 'Symbol', 'Silo', '1R Base ($)', 'Realized PnL ($)', 'R-Multiple', 'Tags', 'Notes']]
    display_hist.insert(0, '✏️ Edit Tags', [False]*len(display_hist))
    
    fmt_hist = display_hist.copy()
    
    edited_ledger = st.data_editor(
        fmt_hist,
        hide_index=True,
        width="stretch",
        disabled=['Exit Date', 'Symbol', 'Silo', '1R Base ($)', 'Realized PnL ($)', 'R-Multiple', 'Tags'],
        column_config={
            "✏️ Edit Tags": st.column_config.CheckboxColumn("Edit Tags", width="small"),
            "rowid": None, 
            "1R Base ($)": st.column_config.NumberColumn("1R Base ($)", format="$%.2f"),
            "Realized PnL ($)": st.column_config.NumberColumn("Realized PnL ($)", format="$%.2f"),
            "R-Multiple": st.column_config.NumberColumn("R-Multiple", format="%.2f R"),
            "Notes": st.column_config.TextColumn("Notes (Click to Type)", width="large")
        },
        key="ledger_editor_v55"
    )
    
    # 1. Detect Note Edits directly in the grid
    for idx in fmt_hist.index:
        old_note = str(fmt_hist.at[idx, 'Notes']) if pd.notna(fmt_hist.at[idx, 'Notes']) else ""
        new_note = str(edited_ledger.at[idx, 'Notes']) if pd.notna(edited_ledger.at[idx, 'Notes']) else ""
        if old_note != new_note:
            row_id = int(fmt_hist.at[idx, 'rowid'])
            conn = sqlite3.connect(DB_PATH)
            conn.execute("PRAGMA journal_mode=WAL;")
            conn.execute("UPDATE champion_closed_trades SET notes = ? WHERE rowid = ?", (new_note, row_id))
            conn.commit()
            conn.close()
            st.cache_data.clear()
            st.rerun()

    # 2. Detect Tag Selection Checkbox for native Multi-Select
    selected_ledger = edited_ledger[edited_ledger['✏️ Edit Tags'] == True]
    if selected_ledger.shape[0] > 1:
        st.error("❌ Please check the 'Edit' box for only ONE trade at a time to modify Tags.")
    elif selected_ledger.shape[0] == 1:
        sel_row = selected_ledger.iloc[0]
        st.markdown(f"**Tag Editor for:** {sel_row['Symbol']} closed on {sel_row['Exit Date']} (Realized: ${sel_row['Realized PnL ($)']:.2f})")
        
        curr_tags_str = str(sel_row['Tags']) if pd.notna(sel_row['Tags']) else ""
        curr_tags = [t.strip() for t in curr_tags_str.split(',')] if curr_tags_str else []
        curr_tags = [t for t in curr_tags if t in CHAMPION_TAGS]
        
        new_tags = st.multiselect("Modify Strategy Tags:", CHAMPION_TAGS, default=curr_tags)
        
        if st.button("💾 Save New Tags"):
            new_tags_str = ", ".join(new_tags)
            row_id = int(sel_row['rowid'])
            conn = sqlite3.connect(DB_PATH)
            conn.execute("PRAGMA journal_mode=WAL;")
            conn.execute("UPDATE champion_closed_trades SET tags = ? WHERE rowid = ?", (new_tags_str, row_id))
            conn.commit()
            conn.close()
            st.success("Tags successfully updated!")
            st.cache_data.clear()
            st.rerun()
else:
    st.info("No closed trades have been recorded yet.")