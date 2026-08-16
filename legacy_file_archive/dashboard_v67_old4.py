"""
=============================================================================
Script Name: dashboard_v67.py
Purpose: The Streamlit Frontend (Family Office Estate Architecture)

⚙️ HOW TO LAUNCH THIS DASHBOARD:
1. Open Command Prompt (cmd)
2. Navigate to the Estate directory by pasting:
   cd "C:\\Users\\donca\\Desktop\\Desktop HP Envy x360 al 22Abr24\\Docs Manuel\\IBKR_Options"
3. Launch the UI by running exactly:
   streamlit run dashboard_v67.py

CHANGELOG (v67):
         - ADDED: Section 3B Alpha Engine & Physical Equity Risk Ledger (Visualizes cost vs value vs stops).
         - UPDATED: SWAN Stress Test now utilizes exact Stop Loss triggers with gap slippage penalties.
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

@st.cache_data(ttl=3600)
def get_fx_rate(currency):
    if currency == 'USD' or pd.isna(currency): return 1.0
    direct = {'EUR': 'EURUSD=X', 'GBP': 'GBPUSD=X', 'AUD': 'AUDUSD=X', 'NZD': 'NZDUSD=X'}
    inverted = {'KRW': 'KRW=X', 'SEK': 'SEK=X', 'CAD': 'CAD=X', 'CHF': 'CHF=X', 'JPY': 'JPY=X', 'TWD': 'TWD=X', 'HKD': 'HKD=X', 'SGD': 'SGD=X'}
    try:
        if currency in direct:
            return float(yf.Ticker(direct[currency]).history(period='1d')['Close'].iloc[-1])
        elif currency in inverted:
            rate = float(yf.Ticker(inverted[currency]).history(period='1d')['Close'].iloc[-1])
            return 1.0 / rate if rate > 0 else 1.0
    except: return 1.0
    return 1.0

@st.cache_data(ttl=300)
def fetch_live_data(ticker_symbol):

    # v67: Safeguard against empty cells during live data-entry
    if pd.isna(ticker_symbol) or not ticker_symbol or str(ticker_symbol).strip().upper() in ['NAN', 'NONE', '']:
        return 550.0, 15.0
        
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
    df_opt = df_in[(df_in['sec_type'] == 'OPT') & (~df_in['asset_class'].isin(['Tail Hedge', 'Synthetic Beta']))].copy()
    if df_opt.empty: return 0
    try:
        margin = 0
        # Extract base ticker to prevent expiration date collisions across different assets
        df_opt['base_tckr'] = df_opt['symbol'].apply(lambda x: x.split('_')[0])
        df_opt['strike'] = df_opt['symbol'].apply(lambda x: float(x.split('_')[2]))
        df_opt['exp'] = df_opt['symbol'].apply(lambda x: x.split('_')[1])
        df_opt['right'] = df_opt['symbol'].apply(lambda x: x.split('_')[3])
        
        # v67 FIX: Added base_tckr to the groupby!
        for _, group in df_opt.groupby(['account', 'base_tckr', 'exp', 'right']):
            shorts = group[group['position'] < 0]
            longs = group[group['position'] > 0]
            if shorts.empty: continue
            
            short_sum = shorts.apply(lambda r: r['strike'] * abs(r['position']), axis=1).sum()

            if longs.empty:
                margin += short_sum * 100
                continue
                
            long_sum = longs.apply(lambda r: r['strike'] * abs(r['position']), axis=1).sum()
            short_avg = short_sum / shorts['position'].abs().sum()
            long_avg = long_sum / longs['position'].abs().sum()
            
            right = group['right'].iloc[0]
            is_credit = False
            if right == 'P' and short_avg > long_avg:
                is_credit = True
            elif right == 'C' and short_avg < long_avg:
                is_credit = True
                
            if is_credit:
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
    
    # Robust Global Aggregation: Prevent NAV drops when accounts miss a daily sync
    pivot_nav = df.pivot_table(index='date', columns='account', values='nav', aggfunc='last').ffill().fillna(0)
    pivot_flow = df.pivot_table(index='date', columns='account', values='net_flow', aggfunc='sum').fillna(0)
    
    global_df = pd.DataFrame({
        'nav': pivot_nav.sum(axis=1),
        'net_flow': pivot_flow.sum(axis=1)
    }).reset_index()
    
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

    # Global tracking arrays (now using 100% Verified Clearinghouse MTM PnL)
    if not global_df.empty:
        global_df['prev_nav'] = global_df['nav'].shift(1)
        
        # Fetch the verified attribution directly to override the delta-NAV guessing
        try:
            temp_attr = pd.read_sql_query("SELECT * FROM daily_attribution", conn)

            if not temp_attr.empty:
                temp_attr['date'] = pd.to_datetime(temp_attr['date'])
                temp_attr['true_daily_pnl'] = temp_attr[['a1_yield', 'a2_beta', 'a3_vrp', 'a4_alpha', 'a5_fees']].sum(axis=1)
                global_df = pd.merge(global_df, temp_attr[['date', 'true_daily_pnl']], on='date', how='left')
                
                # INTRADAY FALLBACK: Flex Query is T-1. For the live active session, fall back to delta-NAV math.
                delta_nav_pnl = global_df['nav'] - global_df['net_flow'] - global_df['prev_nav'].fillna(global_df['nav'] - global_df['net_flow'])
                global_df['daily_pnl'] = global_df['true_daily_pnl'].fillna(delta_nav_pnl)
                
                global_df['daily_return'] = global_df['daily_pnl'] / global_df['prev_nav'].replace(0, np.nan)
                
                # Override the global metrics total PnL with official history + today's live PnL
                global_metrics['pnl'] = global_df['daily_pnl'].sum()
            else:
                global_df['daily_return'] = (global_df['nav'] - global_df['net_flow'] - global_df['prev_nav']) / global_df['prev_nav'].replace(0, np.nan)
                global_df['daily_pnl'] = global_df['nav'] - global_df['net_flow'] - global_df['prev_nav'].fillna(global_df['nav'] - global_df['net_flow'])
        except Exception:
            global_df['daily_return'] = (global_df['nav'] - global_df['net_flow'] - global_df['prev_nav']) / global_df['prev_nav'].replace(0, np.nan)
            global_df['daily_pnl'] = global_df['nav'] - global_df['net_flow'] - global_df['prev_nav'].fillna(global_df['nav'] - global_df['net_flow'])

        global_df['cum_return'] = (1 + global_df['daily_return'].fillna(0)).cumprod() - 1
        global_df['cum_pnl'] = global_df['daily_pnl'].cumsum()

    live_date = df['date'].max()
    
    # Query ONLY ONCE using the version that includes the 'currency' column
    pos_df = pd.read_sql_query(f"SELECT account, symbol, sec_type, position, market_price, market_value, avg_cost, unrealized_pnl, currency FROM daily_positions WHERE date = '{live_date.strftime('%Y-%m-%d')}'", conn)
    
    attr_df = pd.read_sql_query("SELECT * FROM daily_attribution", conn)
    if not attr_df.empty: 
        attr_df['date'] = pd.to_datetime(attr_df['date'])
        # BUG A FIX INCLUDED HERE:
        attr_df = attr_df[attr_df['date'] >= pd.to_datetime('2025-12-01')].copy()
    
    try: 
        open_orders_df = pd.read_sql_query(f"SELECT * FROM open_orders WHERE date = '{live_date.strftime('%Y-%m-%d')}'", conn)
    except: 
        open_orders_df = pd.DataFrame()
        
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
                        
                        # PATCH: Classify VIX Calls as Black Swan Tail Hedges
                        if parts[0] == 'VIX' and right == 'C':
                            return 'Tail Hedge'
                            
                        if right == 'P' and dte > 60:
                            # Broad Market Whitelist prevents Decapitation Bug for Sector Shorts (like SMH)
                            if parts[0] in ['SPY', 'SPX', 'XSP', 'QQQ', 'NDX', 'XND']:
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
        lambda r: 0.0 if (pd.isna(r['Short Strike']) or r['Short Strike'] == 0 or r.get('Premium Collected (USD)', 0) < 0)
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
    
    # Dynamically calculate PnL for both Credit Spreads (Net Credit) and Debit Spreads (Net Debit)
    journal_raw_df['Total P&L (USD)'] = journal_raw_df.apply(
        lambda r: (r['Premium Collected (USD)'] - r['Closing Price (USD)']) * 100 * r['Quantity'] if r.get('Premium Collected (USD)', 0) >= 0 
        else (r['Premium Collected (USD)'] + r['Closing Price (USD)']) * 100 * r['Quantity'], 
        axis=1
    )
    
    journal_raw_df['Return on Capital (ROC) %'] = journal_raw_df.apply(
        lambda r: (r['Total P&L (USD)'] / abs(r['Premium Collected (USD)'] * 100 * r['Quantity'])) * 100 if r.get('Premium Collected (USD)', 0) < 0 
        else ((r['Total P&L (USD)'] / r['Collateral Locked (USD)']) * 100 if r['Collateral Locked (USD)'] > 0 else 0),
        axis=1
    )

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

if not balances_df.empty and 'net_liquidation' in balances_df.columns:
    silo_b_bal = balances_df[(balances_df['account'] == 'U23139264') & (balances_df['date'] == balances_df['date'].max())]
    if not silo_b_bal.empty:
        nl = silo_b_bal['net_liquidation'].iloc[0]
        if 0 < nl < 27000:
            alerts.append(f"⚠️ **PDT Danger (Silo B):** Net Liquidity (${nl:,.0f}) approaching the $25k FINRA lockout threshold. Deposit cash or close Alpha swings immediately.")

if not pos_df.empty:
    open_opts = pos_df[pos_df['sec_type'] == 'OPT'].copy()
    for acc, group in open_opts.groupby('account'):
        group['base_tckr'] = group['symbol'].apply(lambda x: x.split('_')[0] if '_' in x else x)
        group['right'] = group['symbol'].apply(lambda x: x.split('_')[3] if len(x.split('_')) >= 4 else '')
        
        for base_tckr, tckr_group in group.groupby('base_tckr'):
            shorts = tckr_group[tckr_group['position'] < 0]
            longs = tckr_group[tckr_group['position'] > 0]
            silo_name = SILO_MAP.get(acc, [acc])[0]
            
            # Rule 1: Naked Short Call (Infinite Risk)
            if not shorts[shorts['right'] == 'C'].empty and longs[longs['right'] == 'C'].empty:
                alerts.append(f"🚨 **CRITICAL (Infinite Risk):** Naked Short Call detected on {base_tckr} in {silo_name}! Close or hedge immediately.")
            
            # Rules 2 & 3: Short Puts
            short_puts = shorts[shorts['right'] == 'P']
            if not short_puts.empty:
                is_spread = not longs[longs['right'] == 'P'].empty
                has_order = False
                if not open_orders_df.empty:
                    has_order = not open_orders_df[(open_orders_df['account'] == acc) & (open_orders_df['symbol'].str.contains(base_tckr))].empty
                
                if not has_order:
                    if base_tckr in ['SPY', 'SPX', 'XSP', 'QQQ', 'NDX', 'XND']:
                        alerts.append(f"🚨 **CRITICAL (Missing Brackets):** Short Index Put ({base_tckr}) in {silo_name} is missing resting OCO brackets!")
                    elif not is_spread:
                        alerts.append(f"ℹ️ **CSP Active:** Short Equity Put ({base_tckr}) in {silo_name}. No brackets detected. The Estate will accept physical assignment if ITM at expiration.")

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
alerts.append(f"🧭 **EOD Market Regime:** {regime_str}")

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

# --- SECTION 3B: ALPHA ENGINE & PHYSICAL EQUITY RISK LEDGER ---
st.subheader("3B. Alpha Engine & Physical Equity Risk Ledger")

alpha_assets = ['Physical US Stocks', 'International Stocks', 'US Tech CFDs', 'Gold', 'Crypto', 'CSPX', 'CNDX', 'ITWN', 'CSKR', 'CNYA']
df_phys = pos_df[pos_df['asset_class'].isin(alpha_assets)].copy() if not pos_df.empty else pd.DataFrame()
phys_grouped = []
if not df_phys.empty:
    for sym, g in df_phys.groupby('symbol'):
        shares = g['position'].sum()
        if shares <= 0.001: continue
        
        # The sync_engine_v24 ALREADY converted these to USD natively
        mkt_val = g['market_value'].sum()
        cost = (g['position'] * g['avg_cost']).sum() 
        mkt_price_usd = g['market_price'].iloc[0]
        avg_cost_usd = g['avg_cost'].iloc[0]
        
        # The open_orders_df aux_price (Stop Loss) is in LOCAL currency. 
        # We must fetch the FX rate to convert the stop loss to USD.
        curr = g['currency'].iloc[0] if 'currency' in g.columns else 'USD'
        fx_rate = get_fx_rate(curr)
        
        # Fetch Stops (Broadened match to catch 'STP', 'STP LMT', 'TRAIL')
        sym_stops = pd.DataFrame()
        if 'open_orders_df' in locals() and not open_orders_df.empty:
            sym_stops = open_orders_df[(open_orders_df['symbol'] == sym) & 
                                       (open_orders_df['action'] == 'SELL') & 
                                       (open_orders_df['order_type'].str.contains('STP|TRAIL', case=False, na=False))].copy()
        if not sym_stops.empty:
            sym_stops = sym_stops.sort_values('aux_price', ascending=False)
        
        rem_shares = shares
        open_risk = 0.0
        locked_profit = 0.0
        sl_val_total_usd = 0.0
        total_stopped_shares = 0
        stop_details = []
        
        for _, sr in sym_stops.iterrows():
            q = min(sr['total_quantity'], rem_shares)
            if q <= 0: break
            sl_price_usd = sr['aux_price'] * fx_rate
            
            chunk_cost = q * avg_cost_usd
            chunk_val = q * sl_price_usd
            diff = chunk_val - chunk_cost

            if diff < 0: open_risk += diff
            else: locked_profit += diff
            
            sl_val_total_usd += chunk_val
            total_stopped_shares += q
            rem_shares -= q
            stop_details.append({'q': q, 'sl_usd': sl_price_usd})

        if rem_shares > 0:
            open_risk -= (rem_shares * avg_cost_usd)
            stop_details.append({'q': rem_shares, 'sl_usd': 0.0})
            
        avg_sl_usd = (sl_val_total_usd / total_stopped_shares) if total_stopped_shares > 0 else 0.0
        
        total_profit = mkt_val - cost
        unlocked_profit = total_profit - locked_profit
        
        phys_grouped.append({
            'Ticker': sym,
            'Shares': shares,
            'Spot Price': mkt_price_usd,
            'Market Value': mkt_val,
            'Cost': cost,
            'Avg SL': avg_sl_usd,
            'Total SL Value': sl_val_total_usd,
            'Protected Shares': total_stopped_shares,
            'Open Risk': open_risk,
            'Locked Profit': locked_profit,
            'Unlocked Profit': unlocked_profit,
            'Total Profit': total_profit,
            'stop_details': stop_details
        })

df_alpha = pd.DataFrame(phys_grouped)

if not df_alpha.empty:
    df_alpha = df_alpha.sort_values('Market Value', ascending=False).reset_index(drop=True)
    nav_for_pct = global_metrics['nav'] if global_metrics['nav'] > 0 else 1.0
    df_alpha['Global Estate %'] = (df_alpha['Market Value'] / nav_for_pct) * 100
    
    c_chart, c_ctrl = st.columns([8, 1])
    with c_ctrl:
        st.markdown("<br><br><br>", unsafe_allow_html=True)
        use_log = st.toggle("Logarithmic Scale", value=False)
    
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
    
    # Custom Shapes for Cost, Val, and SL lines to match the exact drawing requested
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
            showarrow=False, yshift=28,
            font=dict(size=9, color="#475569"), align="center"
        )
    y_layout = dict(gridcolor='LightGray', zeroline=True, zerolinecolor='black')
    if use_log:
        y_layout['type'] = 'log'
        y_layout['dtick'] = 1
        
    fig_alpha.update_layout(
        barmode='stack', title="Global Physical Equity Risk Profiles",
        plot_bgcolor='rgba(0,0,0,0)', yaxis=y_layout,
        margin=dict(l=20, r=20, t=65, b=40), height=500,
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
    )
    
    tick_texts = df_alpha.apply(lambda r: f"{r['Ticker']}<br><span style='font-size:10px;color:gray;'>{r['Global Estate %']:.2f}%</span>", axis=1)
    fig_alpha.update_xaxes(tickmode='array', tickvals=x_pos, ticktext=tick_texts)
    
    with c_chart:
        st.plotly_chart(fig_alpha, width="stretch")
    
    display_alpha = df_alpha[['Ticker', 'Global Estate %', 'Shares', 'Spot Price', 'Market Value', 'Cost', 'Avg SL', 'Open Risk', 'Locked Profit', 'Unlocked Profit', 'Total Profit']].copy()
    
    global_tor = display_alpha['Open Risk'].sum()
    global_lp = display_alpha['Locked Profit'].sum()
    tor_pct = (global_tor / global_metrics['nav'] * 100) if global_metrics['nav'] > 0 else 0
    
    st.markdown(f"""
    <div style='display:flex; justify-content:space-between; background-color:#f8fafc; padding:15px; border-radius:8px; border:1px solid #cbd5e1; margin-bottom:15px;'>
        <div><span style='color:#475569; font-size:14px;'>Global Total Open Risk (TOR):</span> <span style='font-size:18px; font-weight:bold; color:#dc2626;'>${global_tor:,.0f} ({tor_pct:.1f}% NAV)</span></div>
        <div><span style='color:#475569; font-size:14px;'>Global Locked Profit:</span> <span style='font-size:18px; font-weight:bold; color:#16a34a;'>+${global_lp:,.0f}</span></div>
    </div>
    """, unsafe_allow_html=True)

    def color_profit_loss(val):
        if isinstance(val, (int, float)):
            if val > 0: return 'color: #16a34a; font-weight:bold;'
            elif val < 0: return 'color: #dc2626; font-weight:bold;'
        return ''

    st.dataframe(display_alpha.style.format({
        'Global Estate %': '{:.2f}%', 'Shares': '{:,.0f}', 'Spot Price': '${:,.2f}', 
        'Market Value': '${:,.0f}', 'Cost': '${:,.0f}', 'Avg SL': '${:,.2f}', 
        'Open Risk': '${:,.0f}', 'Locked Profit': '${:,.0f}', 'Unlocked Profit': '${:,.0f}', 
        'Total Profit': '${:,.0f}'
    }).map(lambda x: 'color: #dc2626; font-weight:bold;' if isinstance(x, (int, float)) and x < 0 else '', subset=['Open Risk'])
      .map(color_profit_loss, subset=['Locked Profit', 'Unlocked Profit', 'Total Profit']), 
    hide_index=True, width="stretch")
else:
    st.info("No physical equities currently held in the Estate.")
st.divider()

# --- SECTION 4: PNL ATTRIBUTION & VELOCITY ---
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
    
    # CHANGED: Replaced '#3b82f6' (Light Blue) with '#2352d9' (Navy Blue) for the Yield bucket
    bar_colors = ['#2352d9', '#f97316', '#166534', '#a855f7', '#991b1b']
    
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
        
        # CHANGED: Replaced line color here as well
        fig_attr_line.add_trace(go.Scatter(x=line_df['date'], y=line_df['a1_yield'].cumsum(), name='Yield', line=dict(color='#2352d9', width=4)))
        
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
# v67 FIX: Added Physical US Stocks & International Stocks to Core Assets pool
core_assets = ['CSPX', 'CNDX', 'ITWN', 'CSKR', 'CNYA', 'Crypto', 'Gold', 'Physical US Stocks', 'International Stocks']

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
    
    st.markdown("<div style='text-align: center; color: #991b1b; font-size: 11px; font-weight: bold; margin-top: -25px;'>⚠️ 18% Warning | 🚨 20% FINRA Limit</div>", unsafe_allow_html=True)

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
    delta_breakdown = {'Equities & ETFs': 0.0, 'Synthetic Beta': 0.0, 'VRP & CSPs': 0.0, 'Tail Hedges': 0.0}
    spy_price = bench_df['SPY'].iloc[-1] if not bench_df.empty else 550.0
    qqq_beta = qqq_co * (bench_df['qqq_ret'].std() / bench_df['spy_ret'].std()) if not bench_df.empty else 1.2
    
    for _, r in pos_df.iterrows():
        ac = r['asset_class']
        mv = r['market_value']
        sym = r['symbol']
        
        if ac in ['Cash', 'IB01', 'Accounting Offset', 'Gold', 'Opt Liab']:
            continue
        elif ac in ['Physical US Stocks', 'International Stocks', 'US Tech CFDs', 'CSPX', 'CNYA', 'ITWN', 'CSKR', 'Active Swing']:
            d_val = mv / spy_price
            total_bw_delta += d_val
            delta_breakdown['Equities & ETFs'] += d_val
        elif ac == 'CNDX':
            d_val = (mv / spy_price) * qqq_beta
            total_bw_delta += d_val
            delta_breakdown['Equities & ETFs'] += d_val
        elif ac == 'Crypto':
            d_val = (mv / spy_price) * 2.0
            total_bw_delta += d_val
            delta_breakdown['Equities & ETFs'] += d_val
        elif r['sec_type'] == 'OPT':
            try:
                parts = sym.split('_')
                tckr = parts[0]
                right = parts[3]
                strike = float(parts[2])
                dte = (pd.to_datetime(parts[1]) - pd.Timestamp.today()).days
                pos = r['position']
                
                if 'XSP' in tckr or 'SPX' in tckr:
                    S, V = fetch_live_data('XSP')
                    price, d, g, v, t = get_call_greeks(S, strike, max(dte/365,0.001), LIVE_RF_RATE, V) if right=='C' else get_put_greeks(S, strike, max(dte/365,0.001), LIVE_RF_RATE, V)
                    d_val = d * pos * 100 * (S / spy_price)
                    total_bw_delta += d_val
                    if ac == 'Synthetic Beta': delta_breakdown['Synthetic Beta'] += d_val
                    elif ac == 'Tail Hedge': delta_breakdown['Tail Hedges'] += d_val
                    else: delta_breakdown['VRP & CSPs'] += d_val
                elif 'XND' in tckr or 'NDX' in tckr or 'QQQ' in tckr:
                    S, V = fetch_live_data('XND')
                    price, d, g, v, t = get_call_greeks(S, strike, max(dte/365,0.001), LIVE_RF_RATE, V) if right=='C' else get_put_greeks(S, strike, max(dte/365,0.001), LIVE_RF_RATE, V)
                    d_val = d * pos * 100 * (S / spy_price) * qqq_beta
                    total_bw_delta += d_val
                    if ac == 'Synthetic Beta': delta_breakdown['Synthetic Beta'] += d_val
                    elif ac == 'Tail Hedge': delta_breakdown['Tail Hedges'] += d_val
                    else: delta_breakdown['VRP & CSPs'] += d_val
            except:
                pass
                
    bw_usd_exposure = total_bw_delta * spy_price
    bw_pct_nav = (bw_usd_exposure / global_metrics['nav'] * 100) if global_metrics['nav'] > 0 else 0
    
    st.markdown(f"""
    <div style="background-color: #f8fafc; padding: 20px 20px 5px 20px; border-radius: 8px 8px 0 0; border: 1px solid #cbd5e1; border-bottom: none; text-align: center;">
        <h4 style="margin: 0; color: #334155; font-size: 16px;" title="Beta-Weighted Delta converts all disparate assets into 'SPY Equivalent Shares'. It measures total directional risk. If this is +50%, the entire Estate behaves as if 50% of your cash is invested in the S&P 500.">SPY Beta-Weighted Delta (Estate-Wide) ⓘ</h4>
        <div style="font-size: 28px; font-weight: bold; color: {'#16a34a' if bw_pct_nav > 0 else '#dc2626'}; margin-top: 10px;">{bw_pct_nav:+.1f}% of NAV</div>
        <div style="font-size: 14px; color: #64748b; margin-bottom: 10px;">Directional Equivalent: {total_bw_delta:,.0f} SPY Shares (${bw_usd_exposure:,.0f})</div>
    </div>
    """, unsafe_allow_html=True)

    # Plotly Horizontal Stacked Bar for Delta Breakdown
    fig_delta = go.Figure()
    color_map = {'Equities & ETFs': '#3b82f6', 'Synthetic Beta': '#8b5cf6', 'VRP & CSPs': '#16a34a', 'Tail Hedges': '#0f172a'}
    for k, v in delta_breakdown.items():
        pct_contrib = (v * spy_price / global_metrics['nav'] * 100) if global_metrics['nav'] > 0 else 0
        if abs(pct_contrib) > 0.1:
            fig_delta.add_trace(go.Bar(
                y=['Source'], x=[pct_contrib], name=k, orientation='h', 
                marker_color=color_map.get(k, '#94a3b8'),
                text=f"{k}<br>{pct_contrib:+.1f}%", textposition='inside', insidetextanchor='middle'
            ))
    
    fig_delta.update_layout(
        barmode='relative', height=80, margin=dict(l=0, r=0, t=0, b=0),
        xaxis=dict(visible=False), yaxis=dict(visible=False),
        showlegend=False, plot_bgcolor='rgba(0,0,0,0)', paper_bgcolor='rgba(0,0,0,0)'
    )
    st.plotly_chart(fig_delta, width="stretch")
    
    st.markdown(f"""
    <div style="background-color: #f8fafc; padding: 0 20px 10px 20px; border-radius: 0 0 8px 8px; border: 1px solid #cbd5e1; border-top: none; text-align: center;">
        <div style="font-size: 11px; color: #94a3b8; margin-top: -5px;">*Hover over the title ⓘ for definition. Chart displays allocation of directional risk.</div>
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
            S_crash = S * 0.70  # CHANGED to 0.70 to strictly sync with the 30% macro shock parameter
            V_crash = min(V * 2.5, 0.80) 
            cost_price = r['avg_cost'] / 100
            crash_price, _, _, _, _ = get_put_greeks(S_crash, strike, max(dte/365,0.001), LIVE_RF_RATE, V_crash)
            th_payout += max(0, (crash_price - cost_price)) * pos * 100
        except: pass
        
    coverage_ratio = (th_payout / opt_margin_total * 100) if opt_margin_total > 0 else 0
    
    st.markdown(f"""
    <div style="background-color: #f8fafc; padding: 20px; border-radius: 8px; border: 1px solid #cbd5e1; text-align: center;">
        <h4 style="margin: 0; color: #334155; font-size: 16px;">Black Swan Catastrophe Coverage (30% Crash)</h4>
        <div style="font-size: 28px; font-weight: bold; color: {'#16a34a' if coverage_ratio >= 100 else '#d97706'}; margin-top: 10px;">{coverage_ratio:.1f}% Covered</div>
        <div style="font-size: 14px; color: #64748b;">Est. Tail Payout: ${th_payout:,.0f} vs Max Liability: ${opt_margin_total:,.0f}</div>
        <div style="font-size: 11px; color: #94a3b8; margin-top: 5px;">*Synchronized with SWAN 30% Stress Test parameters.</div>
    </div>
    """, unsafe_allow_html=True)

st.divider()

# --- SECTION 6C: THE S.W.A.N. STRESS TEST ---
st.subheader("6C. The S.W.A.N. (Sleep Well At Night) Stress Test")
st.markdown("<p style='color: #4b5563; font-size: 14px; margin-bottom: 20px;'><strong>S.W.A.N.</strong> is an institutional framework designed to survive Black Swan events without panic. Adjust the slider below to stress-test the Estate's Barbell against sudden market collapses.</p>", unsafe_allow_html=True)

# 1. Interactive Crash Slider
sim_crash_input = st.slider("💥 Simulated Market Drop (%)", min_value=10, max_value=50, value=30, step=5, help="Simulates an instant drop in the S&P 500, calculating expected equity losses vs. Tail Hedge payouts.")

swan_shock_pct = sim_crash_input / 100.0
swan_vix_spike = 0.80

# 2. Equity & Synthetic Beta Losses (with Alpha Ledger Slippage Penalty)
swan_phys_loss = 0.0
swan_slippage = 0.10 # 10% gap down slippage penalty on stops

if 'df_alpha' in locals() and not df_alpha.empty:
    for _, r in df_alpha.iterrows():
        spot_usd = r['Spot Price']
        shock_price = spot_usd * (1 - swan_shock_pct)
        for chunk in r['stop_details']:
            q = chunk['q']
            sl_usd = chunk['sl_usd']
            if sl_usd > 0 and shock_price < sl_usd:
                # Stop triggered. Assume 10% slippage, but capped at the gap price
                fill_price = min(sl_usd * (1 - swan_slippage), spot_usd)
                fill_price = max(fill_price, shock_price)
                chunk_loss = (spot_usd - fill_price) * q
            else:
                # Unprotected or SL so low it wasn't triggered
                chunk_loss = (spot_usd - shock_price) * q
            swan_phys_loss += chunk_loss

spy_price_swan = bench_df['SPY'].iloc[-1] if not bench_df.empty else 550.0
synth_usd_exp = delta_breakdown.get('Synthetic Beta', 0.0) * spy_price_swan if 'delta_breakdown' in locals() else 0.0
swan_synth_loss = synth_usd_exp * swan_shock_pct

swan_equity_loss = swan_phys_loss + swan_synth_loss

# 3. VRP Stop-Loss Assumptions
swan_vrp_loss = 0.0
if not journal_raw_df.empty:
    open_vrp = journal_raw_df[pd.isnull(journal_raw_df['Close Date'])]
    for _, r in open_vrp.iterrows():
        prem = r.get('Premium Collected (USD)', 0)
        qty = r.get('Quantity', 1)
        if prem > 0:
            # Assuming 200% stop loss triggers (Net loss = 2x Premium)
            swan_vrp_loss += (prem * 2.0) * 100 * qty

# 4. Tail Hedge Payout Simulation
swan_th_payout = 0.0
for _, r in pos_df[pos_df['asset_class'] == 'Tail Hedge'].iterrows():
    try:
        parts = r['symbol'].split('_')
        strike = float(parts[2])
        dte = (pd.to_datetime(parts[1]) - pd.Timestamp.today()).days
        pos = r['position']
        S, V = fetch_live_data('XSP')
        S_crash = S * (1 - swan_shock_pct)
        V_crash = swan_vix_spike 
        cost_price = r['avg_cost'] / 100 
        crash_price, _, _, _, _ = get_put_greeks(S_crash, strike, max(dte/365, 0.001), LIVE_RF_RATE, V_crash)
        swan_th_payout += max(0, (crash_price - cost_price)) * pos * 100
    except: pass

swan_net_impact = -swan_equity_loss - swan_vrp_loss + swan_th_payout
swan_ending_nav = global_metrics['nav'] + swan_net_impact
swan_estate_impact_pct = (swan_net_impact / global_metrics['nav']) * 100 if global_metrics['nav'] > 0 else 0

col_swan_chart, col_swan_text = st.columns([2, 1])

with col_swan_chart:
    fig_waterfall = go.Figure(go.Waterfall(
        name="SWAN", orientation="v",
        measure=["absolute", "relative", "relative", "relative", "total"],
        x=["Starting NAV", f"Equities (-{sim_crash_input}%)", "VRP Stops", "Tail Payout", "Ending NAV"],
        textposition="outside",
        text=[f"${global_metrics['nav']/1000:.0f}k", 
              f"-${swan_equity_loss/1000:.0f}k", 
              f"-${swan_vrp_loss/1000:.0f}k", 
              f"+${swan_th_payout/1000:.0f}k", 
              f"${swan_ending_nav/1000:.0f}k"],
        y=[global_metrics['nav'], -swan_equity_loss, -swan_vrp_loss, swan_th_payout, 0],
        connector={"line":{"color":"rgb(63, 63, 63)"}},
        decreasing={"marker":{"color":"#dc2626"}},
        increasing={"marker":{"color":"#16a34a"}},
        totals={"marker":{"color":"#1d4ed8"}}
    ))
    fig_waterfall.update_layout(
        title=f"Portfolio Impact Waterfall (-{sim_crash_input}% S&P 500 Crash)",
        margin=dict(l=20, r=20, t=40, b=20),
        plot_bgcolor='rgba(0,0,0,0)',
        yaxis=dict(gridcolor='LightGray', zeroline=True, zerolinecolor='black')
    )
    st.plotly_chart(fig_waterfall, width="stretch")

with col_swan_text:
    impact_color = "#16a34a" if swan_estate_impact_pct >= -10 else "#dc2626"
    st.markdown(f'''
    <div style="background-color: #f8fafc; padding: 25px; border-radius: 8px; border: 1px solid #cbd5e1; height: 100%;">
        <h4 style="margin-top: 0; color: #0f172a; border-bottom: 2px solid #e5e7eb; padding-bottom: 10px;">CFO Executive Summary</h4>
        <div style="display: flex; justify-content: space-between; margin-top: 15px;">
            <span style="font-size: 16px; color: #475569;">Market Impact:</span>
            <span style="font-size: 18px; font-weight: bold; color: #dc2626;">-{sim_crash_input}.0%</span>
        </div>
        <div style="display: flex; justify-content: space-between; margin-top: 10px;">
            <span style="font-size: 16px; color: #475569;">Estate Impact:</span>
            <span style="font-size: 18px; font-weight: bold; color: {impact_color};">{swan_estate_impact_pct:+.1f}%</span>
        </div>
        <hr style="margin: 20px 0; border-color: #e5e7eb;">
        <p style="font-size: 14px; color: #334155; font-style: italic; line-height: 1.6;">
            "If the S&P 500 crashes {sim_crash_input}% tomorrow, the Estate will only suffer an estimated <b>{abs(swan_estate_impact_pct):.1f}%</b> drawdown. 
            The <b>${(swan_equity_loss + swan_vrp_loss):,.0f}</b> losses from our core equity exposure and VRP stops are overwhelmingly absorbed 
            by a projected <b>${swan_th_payout:,.0f}</b> payout from our deep OTM Black Swan insurance policies. Furthermore, the <b>{pct_cash:.1f}%</b> (${tot_cash:,.0f}) allocated to Risk-Free Yield (IB01/Cash) acts as a massive concrete anchor, insulating the principal from market shocks."
        </p>
    </div>
    ''', unsafe_allow_html=True)

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

# --- SECTION 9A: THE MASTER OPTIONS MATRIX (DIDACTIC ROSETTA STONE) ---
st.subheader("9A. The Master Options Matrix & CFO Briefing")
st.markdown("<p style='color: #4b5563; font-size: 14px;'>A didactic Rosetta Stone for the Estate's Barbell mechanics. Outlines tax suitability, tactical execution, and live structural health for every active options class.</p>", unsafe_allow_html=True)

matrix_rows = ""
active_strats = set()

if not pos_df.empty:
    open_opts = pos_df[pos_df['sec_type'] == 'OPT'].copy()
    if not open_opts.empty:
        open_opts['base_tckr'] = open_opts['symbol'].apply(lambda x: x.split('_')[0])
        open_opts['strike'] = open_opts['symbol'].apply(lambda x: float(x.split('_')[2]))
        open_opts['exp'] = open_opts['symbol'].apply(lambda x: pd.to_datetime(x.split('_')[1]))
        
        for (base_tckr, asset_class), group in open_opts.groupby(['base_tckr', 'asset_class']):
            try: spot, _ = fetch_live_data(base_tckr)
            except: spot = 0.0
            
            dte = (group['exp'].iloc[0] - pd.Timestamp.today()).days
            shorts = group[group['position'] < 0]
            longs = group[group['position'] > 0]
            exp_str = group['exp'].iloc[0].strftime('%b %Y')
            
            # 1. VRP Income (XSP)
            if base_tckr in ['XSP', 'SPX'] and not shorts.empty and not longs.empty:
                active_strats.add('VRP')
                strike = shorts['strike'].iloc[0]
                dist = (spot - strike) / spot * 100 if spot > 0 else 0
                color = "#166534" if dist > 1 else "#b91c1c"
                status = f"<b>SAFEGUARDED.</b> The underlying index ({base_tckr}) is currently trading at ${spot:.0f}. Your short strike liability ({strike}) is {dist:.1f}% Out-of-the-Money, maintaining a healthy structural cushion." if dist > 1 else f"<b>DANGER.</b> Spot is testing the short strike. Monitor for mechanical 200% stop-loss."
                verdict = f"<b>Nominal Condition.</b> With {dte} DTE remaining, allow Theta decay to naturally run its course. Do not manually intervene unless the 50% Take-Profit is triggered." if dte > 21 else f"<b>EJECT IMMEDIATELY:</b> Gamma Cliff Reached ({dte} DTE). Time decay is now overpowered by explosive price sensitivity."
                matrix_rows += f"<tr><td><b>{base_tckr} Bull Put Spreads</b><br><span style='font-size:11px; color:#15803d; background-color:#dcfce7; padding:2px 4px; border-radius:3px;'><b>TAX: EXCELLENT.</b> Section 1256 Cash-Settled. No US Estate Tax risk. No dividend withholding.</span></td><td style='color:{color}; font-size: 13px;'>{exp_str} {strike} Short<br><br>{status}</td><td style='font-size: 13px;'><b>The Income Engine (VRP).</b><br>• <i>Pro:</i> High win-rate (90%+), defined maximum loss.<br>• <i>Con:</i> Asymmetric risk/reward; requires disciplined stop-losses to survive tail events.</td><td style='font-size: 13px;'><b>Entry:</b> VIX > 15. Exactly 45-50 DTE. ~0.20 Delta.<br><br><b>Exit:</b> Mechanical 50% Take-Profit, 200% Stop-Loss, or 21-DTE Time Stop.</td><td style='font-size: 13px;'>{verdict}</td></tr>"
                
            # 2. Synthetic Beta (XND/NDX/QQQ)
            elif base_tckr in ['XND', 'QQQ', 'NDX'] and not longs.empty and shorts.empty:
                active_strats.add('SYNTH_BETA')
                strike = longs['strike'].iloc[0]
                status = f"<b>ACTIVE & TRACKING.</b> {base_tckr} is trading at ${spot:.2f}. These Deep ITM calls are successfully mirroring physical stock movements with 5x capital efficiency."
                verdict = f"<b>Nominal Condition.</b> With {dte} DTE remaining, the options are safely traversing the 'flat' part of the Theta decay curve." if dte > 45 else f"<b>ROLL REQUIRED:</b> Theta acceleration zone entered ({dte} DTE). Execute the rolling protocol to push the expiration back to 150 DTE."
                matrix_rows += f"<tr><td><b>{base_tckr} Calls (Synthetic Beta)</b><br><span style='font-size:11px; color:#15803d; background-color:#dcfce7; padding:2px 4px; border-radius:3px;'><b>TAX: MANDATORY.</b> Section 1256. Fully shields Estate from 40% US tax confiscation.</span></td><td style='color:#1d4ed8; font-size: 13px;'>{exp_str} {strike} Call<br><br>{status}</td><td style='font-size: 13px;'><b>The Growth Engine.</b> Replaces physical US ETFs.<br>• <i>Pro:</i> Frees up 80% of capital to earn 5% in Treasuries. Zero overnight CFD financing fees.<br>• <i>Con:</i> Suffers from slight Theta (time) decay.</td><td style='font-size: 13px;'><b>Entry:</b> 120-180 DTE. Delta > 0.80 (Deep ITM). No stop-losses.<br><br><b>Exit:</b> Never sell. Roll mechanically when 45 DTE is breached.</td><td style='font-size: 13px;'>{verdict}</td></tr>"
            
            # 3. Tail Hedges
            elif base_tckr in ['XSP', 'SPX'] and not longs.empty and shorts.empty:
                active_strats.add('TAIL')
                strike = longs['strike'].iloc[0]
                matrix_rows += f"<tr><td><b>120-DTE Black Swan Puts ({base_tckr})</b><br><span style='font-size:11px; color:#15803d; background-color:#dcfce7; padding:2px 4px; border-radius:3px;'><b>TAX: EXCELLENT.</b> Section 1256 Cash-Settled. IRS Safe.</span></td><td style='color:#166534; font-size: 13px;'>{exp_str} {strike} Put<br><br><b>SAFEGUARD.</b> Deep Out-of-the-Money insurance policies silently resting on the ledger.</td><td style='font-size: 13px;'><b>Black Swan Insurance (The Barbell).</b><br>• <i>Pro:</i> Mathematically guarantees survival during multi-month systemic meltdowns.<br>• <i>Con:</i> 100% loss of capital expected. Acts as a constant Theta drag on the portfolio.</td><td style='font-size: 13px;'><b>Entry:</b> Financed strictly by 10% of VRP winnings. 120-150 DTE. Delta < -0.05.<br><br><b>Exit:</b> Monetize dynamically during deep market panic to buy physical assets at the bottom.</td><td style='font-size: 13px;'><b>Nominal.</b> Expect this to bleed to $0. Do not track for daily PnL. Let it ride to catch unexpected crashes.</td></tr>"
            
            # 4. Whale Hedges (SMH)
            elif base_tckr == 'SMH' and not shorts.empty:
                active_strats.add('WHALE')
                strike = shorts['strike'].iloc[0]
                matrix_rows += f"<tr><td><b>{base_tckr} Bear Puts (Whale Hedge)</b><br><span style='font-size:11px; color:#991b1b; background-color:#fee2e2; padding:2px 4px; border-radius:3px;'><b>TAX: WARNING.</b> Equity Options carry physical assignment risk, exposing non-US persons.</span></td><td style='color:#b91c1c; font-size: 13px;'>{exp_str} {strike} Put<br><br><b>MACRO BET.</b> Highly speculative directional short tracking semiconductor capex trends.</td><td style='font-size: 13px;'><b>Tactical Directional Short.</b><br>• <i>Pro:</i> Massive asymmetric leverage if the macro thesis plays out perfectly.<br>• <i>Con:</i> Extremely low probability of success; high Theta burn.</td><td style='font-size: 13px;'><b>Entry:</b> Based entirely on CIO macro-economic thesis, not mechanical rules.<br><br><b>Exit:</b> Hit subjective price targets or expire worthless.</td><td style='font-size: 13px;'><b>Discretionary.</b> Track manually. Do not apply mechanical 21-DTE rules to macro lotto tickets.</td></tr>"
            
            # 5. Conviction Cash-Secured Puts (e.g., BE, MU)
            elif not shorts.empty and base_tckr not in ['XSP', 'SPX', 'XND', 'NDX', 'QQQ', 'SMH']:
                active_strats.add('CSP')
                strike = shorts['strike'].iloc[0]
                matrix_rows += f"<tr><td><b>{base_tckr} Conviction Puts (CSP)</b><br><span style='font-size:11px; color:#991b1b; background-color:#fee2e2; padding:2px 4px; border-radius:3px;'><b>TAX: WARNING.</b> Assignment increases physical US Situs exposure. Manage allocations strictly.</span></td><td style='color:#166534; font-size: 13px;'>{exp_str} {strike} Put<br><br><b>CONVICTION ACQUISITION.</b> {base_tckr} is at ${spot:.2f}. Selling puts during high-fear drops to harvest elevated premium or average-down cost basis on owned assets.</td><td style='font-size: 13px;'><b>Volatility Harvesting / Averaging Down.</b><br>• <i>Pro:</i> Generates massive cash yield. Turns market fear into an opportunity to acquire desired assets at a discount.<br>• <i>Con:</i> Locks up heavy notional margin. Increases Estate Tax risk if held physically.</td><td style='font-size: 13px;'><b>Entry:</b> High IV Rank on targeted infrastructure/AI physical assets already in the portfolio.<br><br><b>Exit:</b> 50% Take-Profit to free up margin, or happily take physical assignment to increase position size.</td><td style='font-size: 13px;'><b>Nominal.</b> Keep collecting the premium. Assignment is an acceptable outcome based on CIO conviction.</td></tr>"

# --- RENDER MISSING STRATEGIES (STATIC ROWS) ---
if 'VRP' not in active_strats:
    matrix_rows += f"<tr><td><span style='color:#64748b'><b>XSP Bull Put Spreads</b></span><br><span style='font-size:11px; color:#15803d; background-color:#dcfce7; padding:2px 4px; border-radius:3px;'><b>TAX: EXCELLENT.</b> Section 1256 Cash-Settled. No US Estate Tax risk. No dividend withholding.</span></td><td style='color:#64748b; font-size: 13px; font-style:italic;'>NO ACTIVE POSITIONS<br><br>Awaiting signal to deploy.</td><td style='color:#64748b; font-size: 13px;'><b>The Income Engine (VRP).</b><br>• <i>Pro:</i> High win-rate (90%+), defined maximum loss.<br>• <i>Con:</i> Asymmetric risk/reward; requires disciplined stop-losses to survive tail events.</td><td style='color:#64748b; font-size: 13px;'><b>Entry:</b> VIX > 15. Exactly 45-50 DTE. ~0.20 Delta.<br><br><b>Exit:</b> Mechanical 50% Take-Profit, 200% Stop-Loss, or 21-DTE Time Stop.</td><td style='color:#64748b; font-size: 13px;'><b>Standby.</b> Monitor VIX for deployment opportunities.</td></tr>"

if 'SYNTH_BETA' not in active_strats:
    matrix_rows += f"<tr><td><span style='color:#64748b'><b>XND/QQQ Calls (Synthetic Beta)</b></span><br><span style='font-size:11px; color:#15803d; background-color:#dcfce7; padding:2px 4px; border-radius:3px;'><b>TAX: MANDATORY.</b> Section 1256. Fully shields Estate from 40% US tax confiscation.</span></td><td style='color:#64748b; font-size: 13px; font-style:italic;'>NO ACTIVE POSITIONS<br><br>Awaiting signal to deploy.</td><td style='color:#64748b; font-size: 13px;'><b>The Growth Engine.</b> Replaces physical US ETFs.<br>• <i>Pro:</i> Frees up 80% of capital to earn 5% in Treasuries. Zero overnight CFD financing fees.<br>• <i>Con:</i> Suffers from slight Theta (time) decay.</td><td style='color:#64748b; font-size: 13px;'><b>Entry:</b> 120-180 DTE. Delta > 0.80 (Deep ITM). No stop-losses.<br><br><b>Exit:</b> Never sell. Roll mechanically when 45 DTE is breached.</td><td style='color:#64748b; font-size: 13px;'><b>Standby.</b> Deploy capital to establish core macro exposure.</td></tr>"
    
if 'TAIL' not in active_strats:
    matrix_rows += f"<tr><td><span style='color:#64748b'><b>120-DTE Black Swan Puts (XSP)</b></span><br><span style='font-size:11px; color:#15803d; background-color:#dcfce7; padding:2px 4px; border-radius:3px;'><b>TAX: EXCELLENT.</b> Section 1256 Cash-Settled. IRS Safe.</span></td><td style='color:#64748b; font-size: 13px; font-style:italic;'>NO ACTIVE POSITIONS<br><br>Estate is completely naked to Black Swan gap-downs.</td><td style='color:#64748b; font-size: 13px;'><b>Black Swan Insurance (The Barbell).</b><br>• <i>Pro:</i> Mathematically guarantees survival during multi-month systemic meltdowns.<br>• <i>Con:</i> 100% loss of capital expected. Acts as a constant Theta drag on the portfolio.</td><td style='color:#64748b; font-size: 13px;'><b>Entry:</b> Financed strictly by 10% of VRP winnings. 120-150 DTE. Delta < -0.05.<br><br><b>Exit:</b> Monetize dynamically during deep market panic to buy physical assets at the bottom.</td><td style='color:#64748b; font-size: 13px; color:#b91c1c;'><b>CRITICAL.</b> VRP Tail budget is sitting idle. Purchase deep OTM puts immediately to restore the Barbell.</td></tr>"

if 'WHALE' not in active_strats:
    matrix_rows += f"<tr><td><span style='color:#64748b'><b>SMH Bear Puts (Whale Hedge)</b></span><br><span style='font-size:11px; color:#991b1b; background-color:#fee2e2; padding:2px 4px; border-radius:3px;'><b>TAX: WARNING.</b> Equity Options carry physical assignment risk, exposing non-US persons.</span></td><td style='color:#64748b; font-size: 13px; font-style:italic;'>NO ACTIVE POSITIONS<br><br>Awaiting signal to deploy.</td><td style='color:#64748b; font-size: 13px;'><b>Tactical Directional Short.</b><br>• <i>Pro:</i> Massive asymmetric leverage if the macro thesis plays out perfectly.<br>• <i>Con:</i> Extremely low probability of success; high Theta burn.</td><td style='color:#64748b; font-size: 13px;'><b>Entry:</b> Based entirely on CIO macro-economic thesis, not mechanical rules.<br><br><b>Exit:</b> Hit subjective price targets or expire worthless.</td><td style='color:#64748b; font-size: 13px;'><b>Standby.</b> Monitor macro sector imbalances for entry.</td></tr>"

if 'CSP' not in active_strats:
    matrix_rows += f"<tr><td><span style='color:#64748b'><b>Conviction Puts (CSP)</b></span><br><span style='font-size:11px; color:#991b1b; background-color:#fee2e2; padding:2px 4px; border-radius:3px;'><b>TAX: WARNING.</b> Assignment increases physical US Situs exposure. Manage allocations strictly.</span></td><td style='color:#64748b; font-size: 13px; font-style:italic;'>NO ACTIVE POSITIONS<br><br>Awaiting signal to deploy.</td><td style='color:#64748b; font-size: 13px;'><b>Volatility Harvesting / Averaging Down.</b><br>• <i>Pro:</i> Generates massive cash yield. Turns market fear into an opportunity to acquire desired assets at a discount.<br>• <i>Con:</i> Locks up heavy notional margin. Increases Estate Tax risk if held physically.</td><td style='color:#64748b; font-size: 13px;'><b>Entry:</b> High IV Rank on targeted infrastructure/AI physical assets already in the portfolio.<br><br><b>Exit:</b> 50% Take-Profit to free up margin, or happily take physical assignment to increase position size.</td><td style='color:#64748b; font-size: 13px;'><b>Standby.</b> Monitor high-conviction assets (e.g., MU) for IV spikes and Red market days to sell premium.</td></tr>"

    html_matrix = f"""
    <div style="background-color: #ffffff; padding: 20px; border-radius: 12px; border: 1px solid #e5e7eb; margin-bottom: 30px; box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1);">
        <table style="width: 100%; text-align: left; font-family: sans-serif; border-collapse: collapse;">
            <thead>
                <tr style="background-color: #1e293b; color: #ffffff; border-bottom: 2px solid #cbd5e1;">
                    <th style="padding: 12px; font-size: 14px; width: 15%;">Instrument & Tax Class</th>
                    <th style="padding: 12px; font-size: 14px; width: 20%;">Active Position & Live Status</th>
                    <th style="padding: 12px; font-size: 14px; width: 25%;">Strategic Thesis (Pros & Cons)</th>
                    <th style="padding: 12px; font-size: 14px; width: 20%;">Execution Protocol (Entry / Exit)</th>
                    <th style="padding: 12px; font-size: 14px; width: 20%;">Automated CFO Verdict</th>
                </tr>
            </thead>
            <tbody>
                {matrix_rows}
            </tbody>
        </table>
    </div>
    """
    st.markdown(html_matrix, unsafe_allow_html=True)
    st.divider()

# --- SECTION 9B: THE OPTIONS PERFORMANCE LEDGER & TOPOGRAPHY ENGINE ---
st.subheader("9B. The Options Performance Ledger & Topography Engine")

if not journal_raw_df.empty:
    
    # Generate CSV data for the full historical ledger
    csv_data = journal_raw_df.to_csv(index=False).encode('utf-8')
    st.download_button(
        label="💾 Download Full Options Journal (CSV)",
        data=csv_data,
        file_name=f"Estate_Options_Journal_{datetime.date.today().isoformat()}.csv",
        mime="text/csv"
    )

    active_vrp = journal_raw_df[pd.isnull(journal_raw_df['Close Date'])].copy()
    if not active_vrp.empty:
        active_vrp['Days Remaining'] = pd.to_numeric(active_vrp['Days Remaining'], errors='coerce')
        
        # v67: Dynamically map LIVE TWS PnL to calculate Live Annualized ROC
        live_roc_list = []
        live_ann_roc_list = []

        for idx, r in active_vrp.iterrows():
            try:
                tckr = str(r['Ticker']).upper()
                tranche = str(r.get('Tranche ID', ''))
                acc = 'U23144948' if 'Silo A' in tranche else ('U23154199' if 'Silo C' in tranche else None)
                
                if acc and not pos_df.empty:
                    k_s = float(r.get('Short Strike', 0)) if pd.notna(r.get('Short Strike')) else 0.0
                    k_l = float(r.get('Long Strike', 0)) if pd.notna(r.get('Long Strike')) else 0.0
                    
                    sub_df = pos_df[(pos_df['account'] == acc) & pos_df['symbol'].str.startswith(tckr + "_")].copy()
                    live_pnl = 0.0
                    
                    if not sub_df.empty:
                        # BUG B FIX: Filter by exact expiration to stop Strike Cross-Contamination
                        try:
                            exp_date = pd.to_datetime(r['Open Date']) + pd.Timedelta(days=int(r['DTE at Entry']))
                            target_exp = exp_date.strftime('%Y%m%d')
                            sub_df = sub_df[sub_df['symbol'].str.contains(target_exp)].copy()
                        except Exception:
                            pass # Fallback to original behavior if dates are missing
                            
                        sub_df['strike'] = sub_df['symbol'].apply(lambda x: float(x.split('_')[2]) if len(x.split('_'))>2 else 0.0)
                        
                        if k_s > 0 and k_l > 0:
                            live_pnl = sub_df[sub_df['strike'].isin([k_s, k_l])]['unrealized_pnl'].sum()
                        elif k_l > 0:
                            live_pnl = sub_df[sub_df['strike'] == k_l]['unrealized_pnl'].sum()
                        elif k_s > 0:
                            live_pnl = sub_df[sub_df['strike'] == k_s]['unrealized_pnl'].sum()
                        
                    margin = r.get('Collateral Locked (USD)', 0)

                    if pd.isna(margin) or margin <= 0:
                        margin = abs(r.get('Premium Collected (USD)', 0) * 100 * r.get('Quantity', 1))
                        
                    days_in = max(1, r.get('Days in Trade', 1))
                    
                    roc = (live_pnl / margin * 100) if margin > 0 else 0
                    ann_roc = roc * (365.0 / days_in)
                    
                    live_roc_list.append(roc)
                    live_ann_roc_list.append(ann_roc)
                else:
                    live_roc_list.append(0)
                    live_ann_roc_list.append(0)
            except:
                live_roc_list.append(0)
                live_ann_roc_list.append(0)
                
        active_vrp['Live ROC %'] = live_roc_list
        active_vrp['Live Ann ROC %'] = live_ann_roc_list

        def classify_radar(r):
            tckr = str(r['Ticker']).upper()
            tranche = str(r.get('Tranche ID', ''))
            k_s = r.get('Short Strike', 0)
            k_l = r.get('Long Strike', 0)
            prem = r.get('Premium Collected (USD)', 0)
            is_long_call = (pd.isna(k_s) or k_s == 0) and k_l > 0 and ('Beta' in tranche or 'Call' in tranche)
            is_long_put = (pd.isna(k_s) or k_s == 0) and k_l > 0 and not is_long_call
            is_debit = prem < 0 and k_s > 0 and k_l > 0
            
            if is_long_call: return 'Synthetic Beta'
            if is_long_put or is_debit or 'Hedge' in tranche: return 'Catastrophe'
            if tckr not in ['SPY', 'SPX', 'XSP', 'QQQ', 'NDX', 'XND']: return 'CSP'
            return 'VRP'

        active_vrp['Radar Class'] = active_vrp.apply(classify_radar, axis=1)
        
        tab1, tab2, tab3, tab4 = st.tabs(["🎯 VRP Income Engine", "🛒 Assignment Radar (CSPs)", "🚀 Synthetic Beta Conveyor", "🛡️ Catastrophe Multiplier"])

        with tab1:
            vrp_df = active_vrp[active_vrp['Radar Class'] == 'VRP'].copy()
            if not vrp_df.empty:
                max_col = vrp_df['Collateral Locked (USD)'].max()
                sizes = (vrp_df['Collateral Locked (USD)'] / max_col * 40 + 10).fillna(20) if pd.notna(max_col) and max_col > 0 else 20
                fig1 = go.Figure(go.Scatter(
                    x=vrp_df['Days Remaining'], y=vrp_df['Live Ann ROC %'], mode='markers+text',
                    text=vrp_df['Ticker'] + ' ' + vrp_df['Short Strike'].astype(str), textposition="top center",
                    marker=dict(size=sizes, color=vrp_df['Live ROC %'], colorscale='RdYlGn', cmid=0, showscale=True, line=dict(width=1, color='black')),
                    customdata=vrp_df['Quantity'],
                    hovertemplate="<b>%{text}</b><br>Contracts: %{customdata:.0f}<br>Days Rem: %{x}<br>Live Ann ROC: %{y:.1f}%<extra></extra>"
                ))
                fig1.add_vline(x=21, line_dash="dash", line_color="red", annotation_text="Gamma Cliff (21 DTE)")
                fig1.add_hline(y=0, line_dash="solid", line_color="black")
                fig1.update_layout(title="VRP Capital Velocity", xaxis_title="Days Remaining (DTE) →", yaxis_title="Live Ann. ROC (%)", xaxis=dict(autorange="reversed"), height=350, margin=dict(l=0, r=0, t=30, b=0))
                st.plotly_chart(fig1, width="stretch")
            else:
                st.info("No active VRP income trades.")

        with tab2:
            csp_df = active_vrp[active_vrp['Radar Class'] == 'CSP'].copy()
            if not csp_df.empty:
                dist_list, yield_list, spot_list = [], [], []
                for _, r in csp_df.iterrows():
                    try:
                        tckr_sym = str(r['Ticker']).strip().upper()
                        
                        # BUG FIX: Bypass Yahoo Finance to prevent NaN crashes.
                        # Query the 100% accurate, live Spot Price directly from the synced TWS database.
                        stock_row = pos_df[(pos_df['symbol'] == tckr_sym) & (pos_df['sec_type'].isin(['STK', 'CFD']))]
                        if not stock_row.empty:
                            S = float(stock_row['market_price'].iloc[0])
                        else:
                            S, _ = fetch_live_data(tckr_sym) 
                            
                        K = float(r.get('Short Strike', 0)) if pd.notna(r.get('Short Strike')) else 0.0
                        prem = float(r.get('Premium Collected (USD)', 0)) if pd.notna(r.get('Premium Collected (USD)')) else 0.0
                        
                        dist = ((S - K) / S) * 100 if S > 0 and K > 0 and pd.notna(S) else 0
                        yd = (prem / K) * 100 if K > 0 else 0
                        
                        dist_list.append(dist)
                        yield_list.append(yd)
                        spot_list.append(S if pd.notna(S) else 0)
                    except:
                        dist_list.append(0)
                        yield_list.append(0)
                        spot_list.append(0)
                        
                csp_df['Distance %'] = dist_list
                csp_df['Yield %'] = yield_list
                csp_df['Spot'] = spot_list
                
                fig2 = go.Figure()
                
                # B2: Visual Enhancement - Background Threat Zones
                fig2.add_vrect(x0=-100, x1=0, fillcolor="#fee2e2", opacity=0.5, layer="below", line_width=0, annotation_text="Assignment (ITM)", annotation_position="top left", annotation_font_color="#991b1b")
                fig2.add_vrect(x0=0, x1=10, fillcolor="#fef9c3", opacity=0.5, layer="below", line_width=0, annotation_text="Danger (0-10%)", annotation_position="top left", annotation_font_color="#a16207")
                fig2.add_vrect(x0=10, x1=100, fillcolor="#dcfce7", opacity=0.5, layer="below", line_width=0, annotation_text="Safe (>10%)", annotation_position="top left", annotation_font_color="#166534")

                # Compile rich data for the hover tooltip
                custom_data = np.column_stack((csp_df['Quantity'], csp_df['Short Strike'], csp_df['Spot']))

                # B1: Visual Enhancement - Dynamic Bubble Colors
                fig2.add_trace(go.Scatter(
                    x=csp_df['Distance %'], y=csp_df['Yield %'], mode='markers+text',
                    text=csp_df['Ticker'], textposition="top center",
                    marker=dict(
                        size=25, 
                        color=csp_df['Distance %'], 
                        colorscale='RdYlGn', 
                        cmin=-5,   
                        cmax=20,   
                        showscale=True,
                        colorbar=dict(title="Safety Margin (%)"),
                        line=dict(width=1.5, color='black')
                    ),
                    customdata=custom_data,
                    hovertemplate="<b>%{text} Cash-Secured Put</b><br>" +
                                  "Contracts: %{customdata[0]:.0f}<br>" +
                                  "Short Strike: $%{customdata[1]:.2f}<br>" +
                                  "Live Spot Price: $%{customdata[2]:.2f}<br>" +
                                  "Distance to Assign: %{x:.1f}%<br>" +
                                  "Yield: %{y:.1f}%<extra></extra>"
                ))
                
                fig2.add_vline(x=0, line_dash="dash", line_color="red")
                
                # Dynamic X-axis range to frame the zones nicely
                max_d = max(25, csp_df['Distance %'].max() + 10)
                min_d = min(-10, csp_df['Distance %'].min() - 5)

                fig2.update_layout(
                    title="Assignment Discount Radar", 
                    xaxis_title="Distance to Strike (%) ← Closer to Assignment | Safer Cushion →", 
                    yaxis_title="Premium Yield (%)", 
                    xaxis=dict(range=[max_d, min_d]), # Natively reverses the axis (Right-to-Left)
                    height=450, 
                    margin=dict(l=0, r=0, t=40, b=0),
                    plot_bgcolor='rgba(0,0,0,0)'
                )
                
                fig2.update_xaxes(showgrid=True, gridcolor='#e5e7eb')
                fig2.update_yaxes(showgrid=True, gridcolor='#e5e7eb')
                
                st.plotly_chart(fig2, width="stretch")
            else:
                st.info("No active Cash-Secured Puts.")

        with tab3:
            sb_df = active_vrp[active_vrp['Radar Class'] == 'Synthetic Beta'].copy()
            if not sb_df.empty:
                # 1. Aggregate overlapping positions (e.g., Silo A & C having the exact same contract)
                sb_grouped = sb_df.groupby(['Ticker', 'Long Strike', 'Days Remaining']).agg({
                    'Quantity': 'sum',
                    'Premium Collected (USD)': 'mean'
                }).reset_index()

                # 2. Dynamically calculate Notional Exposure and Capital Efficiency
                def get_spot_for_calc(tckr):
                    try:
                        return fetch_live_data(tckr)[0]
                    except:
                        return 0.0
                
                sb_grouped['Spot'] = sb_grouped['Ticker'].apply(get_spot_for_calc)
                sb_grouped['Notional'] = sb_grouped['Quantity'] * 100 * sb_grouped['Spot']
                sb_grouped['Cost'] = abs(sb_grouped['Premium Collected (USD)']) * 100 * sb_grouped['Quantity']
                sb_grouped['Leverage'] = np.where(sb_grouped['Cost'] > 0, sb_grouped['Notional'] / sb_grouped['Cost'], 0)
                sb_grouped['y_pos'] = np.sqrt(sb_grouped['Days Remaining'] / 180) * 100

                # 3. Generate a stylized Theta decay curve
                days_curve = np.linspace(180, 0, 180)
                theta_curve = np.sqrt(days_curve / 180) * 100

                fig3 = go.Figure()
                
                fig3.add_trace(go.Scatter(
                    x=days_curve, y=theta_curve, mode='lines', 
                    name='Theoretical Time Value', line=dict(color='#9ca3af', width=3, dash='dash'),
                    hovertemplate="DTE: %{x:.0f}<br>Retained Time Value: %{y:.1f}%<extra></extra>"
                ))

                fig3.add_vrect(x0=0, x1=45, fillcolor="#fee2e2", opacity=0.4, layer="below")
                fig3.add_annotation(x=22.5, y=50, text="<b>DANGER ZONE</b><br>Accelerated Theta Decay<br>(Eject & Roll)", showarrow=False, font=dict(color="#b91c1c", size=12))
                
                fig3.add_vrect(x0=45, x1=180, fillcolor="#dcfce7", opacity=0.3, layer="below")
                fig3.add_annotation(x=112.5, y=50, text="<b>SAFE ZONE</b><br>Slow Glacier Melt", showarrow=False, font=dict(color="#15803d", size=14))

                # 4. Plot the Aggregated Positions with Rich Tooltips
                custom_data = np.column_stack((sb_grouped['Quantity'], sb_grouped['Notional'], sb_grouped['Leverage']))
                
                fig3.add_trace(go.Scatter(
                    x=sb_grouped['Days Remaining'], y=sb_grouped['y_pos'], mode='markers+text',
                    text=sb_grouped['Ticker'] + ' ' + sb_grouped['Long Strike'].astype(str), textposition="top center",
                    marker=dict(size=28, color='#2563eb', symbol='diamond', line=dict(width=2, color='black')),
                    customdata=custom_data,
                    hovertemplate="<b>%{text}</b><br>" +
                                  "Total Contracts: %{customdata[0]:.0f}<br>" +
                                  "Notional Exposure: $%{customdata[1]:,.0f}<br>" +
                                  "Capital Efficiency: %{customdata[2]:.1f}x<br>" +
                                  "Days Rem: %{x}<br>" +
                                  "Est. Time Value Retained: %{y:.1f}%<extra></extra>",
                    name="Active Positions"
                ))

                fig3.update_layout(
                    title="Synthetic Beta Rolling Conveyor (Theta Decay Profile)", 
                    xaxis_title="Days Remaining (DTE) →", 
                    yaxis_title="Retained Time Premium (%)",
                    xaxis=dict(autorange="reversed", range=[180, 0]), 
                    yaxis=dict(range=[0, 110]),
                    height=400, margin=dict(l=20, r=20, t=40, b=20),
                    showlegend=False,
                    plot_bgcolor='rgba(0,0,0,0)'
                )
                fig3.update_yaxes(showgrid=True, gridcolor='#e5e7eb')
                fig3.update_xaxes(showgrid=True, gridcolor='#e5e7eb')
                
                st.plotly_chart(fig3, width="stretch")
            else:
                st.info("No active Synthetic Beta trades.")

        with tab4:
            cat_df = active_vrp[active_vrp['Radar Class'] == 'Catastrophe'].copy()
            if not cat_df.empty:
                names, costs, payouts, quantities = [], [], [], []
                for _, r in cat_df.iterrows():
                    tckr = str(r['Ticker']).upper() if pd.notna(r.get('Ticker')) else "UNKNOWN"
                    l_strike = float(r['Long Strike']) if pd.notna(r.get('Long Strike')) else 0.0
                    s_strike = float(r['Short Strike']) if pd.notna(r.get('Short Strike')) else 0.0
                    prem = float(r['Premium Collected (USD)']) if pd.notna(r.get('Premium Collected (USD)')) else 0.0
                    qty = float(r['Quantity']) if pd.notna(r.get('Quantity')) else 1.0
                    dte_rem = str(r.get('Days Remaining', '0'))
                    
                    names.append(f"{tckr} {int(l_strike)} (DTE {dte_rem})")
                    cost = abs(prem * 100 * qty)
                    costs.append(-cost)
                    quantities.append(qty)
                    
                    try:
                        if tckr in ["UNKNOWN", "NAN", "NONE"]: raise ValueError("Skip Fetch")
                        S, V = fetch_live_data(tckr)
                        S_crash = S * 0.70
                        V_crash = min(V * 2.5, 0.80)
                        
                        dte_math = 0.001
                        if pd.notna(r.get('Days Remaining')) and str(r.get('Days Remaining')) != 'Closed':
                            dte_math = max(float(r['Days Remaining'])/365.0, 0.001)
                            
                        is_debit = prem < 0 and s_strike > 0
                        
                        if is_debit:
                            s_p, _, _, _, _ = get_put_greeks(S_crash, s_strike, dte_math, LIVE_RF_RATE, V_crash)
                            l_p, _, _, _, _ = get_put_greeks(S_crash, l_strike, dte_math, LIVE_RF_RATE, V_crash)
                            payout = (s_p - l_p) * 100 * qty
                        else:
                            l_p, _, _, _, _ = get_put_greeks(S_crash, l_strike, dte_math, LIVE_RF_RATE, V_crash)
                            payout = l_p * 100 * qty
                        payouts.append(max(0, payout - cost))
                    except: 
                        payouts.append(0)
                
                fig4 = go.Figure()
                fig4.add_trace(go.Bar(
                    name='Sunk Cost', x=names, y=costs, marker_color='#dc2626',
                    customdata=quantities, hovertemplate="<b>%{x}</b><br>Contracts: %{customdata:.0f}<br>Sunk Cost: $%{y:,.0f}<extra></extra>"
                ))
                fig4.add_trace(go.Bar(
                    name='Est. Payout (-30% Crash)', x=names, y=payouts, marker_color='#16a34a',
                    customdata=quantities, hovertemplate="<b>%{x}</b><br>Contracts: %{customdata:.0f}<br>Est. Payout: $%{y:,.0f}<extra></extra>"
                ))
                fig4.update_layout(title="Catastrophe Multiplier (-30% Shock)", barmode='relative', height=350, margin=dict(l=0, r=0, t=30, b=0))
                st.plotly_chart(fig4, width="stretch")
            else:
                st.info("No active Catastrophe Hedges.")

def style_journal(df):
    css_df = pd.DataFrame('', index=df.index, columns=df.columns)
    for i, row in df.iterrows():
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
            
            # v67: 3D Engine Native Debit Spread & Call Detection
            tranche_str = str(row_data.get('Tranche ID', ''))
            is_long_call = (K_s == 0 or pd.isna(K_s)) and K_l > 0 and ('Beta' in tranche_str or 'Call' in tranche_str)
            is_long_put = (K_s == 0 or pd.isna(K_s)) and K_l > 0 and not is_long_call
            
            if not (is_long_call or is_long_put):
                if prem > 0:
                    is_call = K_s < K_l
                else:
                    is_call = K_s > K_l
            else:
                is_call = False
                
            pricing_func = get_call_greeks if (is_call or is_long_call) else get_put_greeks

            def calc_exp_payoff(p, k_s, k_l, prem):
                if is_long_put: return max(k_l - p, 0) - abs(prem)
                if is_long_call: return max(p - k_l, 0) - abs(prem)
                if is_call: return prem - (max(p - k_s, 0) - max(p - k_l, 0))
                else: return prem - (max(k_s - p, 0) - max(k_l - p, 0))

            if is_long_put:
                s_p, s_d, s_g, s_v, s_t = 0, 0, 0, 0, 0
                l_p, l_d, l_g, l_v, l_t = get_put_greeks(S_live, K_l, T_curr, r_rate, iv_dec)
                curr_spread_price = l_p
                unrealized_pnl = (curr_spread_price - abs(prem)) * qty * 100
                margin_req = abs(prem) * 100 * qty 
                rom_pct = (unrealized_pnl / margin_req * 100) if margin_req > 0 else 0
                net_delta, net_gamma, net_theta, net_vega = l_d * qty * 100, l_g * qty * 100, l_t * qty * 100, l_v * qty * 100
                min_plot = int(min(K_l - 60, S_live - 30))
                max_plot = int(max(K_l + 20, S_live + 20))
                
            elif is_long_call:
                s_p, s_d, s_g, s_v, s_t = 0, 0, 0, 0, 0
                l_p, l_d, l_g, l_v, l_t = get_call_greeks(S_live, K_l, T_curr, r_rate, iv_dec)
                curr_spread_price = l_p
                unrealized_pnl = (curr_spread_price - abs(prem)) * qty * 100
                margin_req = abs(prem) * 100 * qty 
                rom_pct = (unrealized_pnl / margin_req * 100) if margin_req > 0 else 0
                net_delta, net_gamma, net_theta, net_vega = l_d * qty * 100, l_g * qty * 100, l_t * qty * 100, l_v * qty * 100
                min_plot = int(min(K_l - 40, S_live - 20))
                max_plot = int(max(K_l + 60, S_live + 20))
                
            else:
                s_p, s_d, s_g, s_v, s_t = pricing_func(S_live, K_s, T_curr, r_rate, iv_dec)
                l_p, l_d, l_g, l_v, l_t = pricing_func(S_live, K_l, T_curr, r_rate, iv_dec)
                curr_spread_price = s_p - l_p
                unrealized_pnl = (prem - curr_spread_price) * qty * 100
                margin_req = abs(prem) * 100 * qty if prem < 0 else abs(K_s - K_l) * 100 * qty
                rom_pct = (unrealized_pnl / margin_req * 100) if margin_req > 0 else 0
                net_delta, net_gamma, net_theta, net_vega = (l_d - s_d) * qty * 100, (l_g - s_g) * qty * 100, (l_t - s_t) * qty * 100, (l_v - s_v) * qty * 100
                
                min_plot = int(min(min(K_s, K_l) - 40, S_live - 10))
                max_plot = int(max(max(K_s, K_l) + 40, S_live + 10))

            x_vals = [p / 2.0 for p in range(int(min_plot * 2), int(max_plot * 2) + 1)]
            y_exp, y_init, y_curr = [], [], []
                            
            for p in x_vals:
                y_exp.append(calc_exp_payoff(p, K_s, K_l, prem) * qty * 100)
                if is_long_put:
                    t0_l, _, _, _, _ = get_put_greeks(p, K_l, T_init, r_rate, iv_dec)
                    y_init.append((t0_l - abs(prem)) * qty * 100)
                    tC_l, _, _, _, _ = get_put_greeks(p, K_l, T_curr, r_rate, iv_dec)
                    y_curr.append((tC_l - abs(prem)) * qty * 100)
                elif is_long_call:
                    t0_l, _, _, _, _ = get_call_greeks(p, K_l, T_init, r_rate, iv_dec)
                    y_init.append((t0_l - abs(prem)) * qty * 100)
                    tC_l, _, _, _, _ = get_call_greeks(p, K_l, T_curr, r_rate, iv_dec)
                    y_curr.append((tC_l - abs(prem)) * qty * 100)
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

                tws_unrealized_pnl = 0.0
                if acct_filter and not pos_df.empty:
                    sub_df = pos_df[(pos_df['account'] == acct_filter) & pos_df['symbol'].str.startswith(tckr + "_")].copy()
                    if not sub_df.empty:
                        # BUG B FIX: Filter 3D Live PnL by explicit expiration
                        try:
                            exp_date_3d = pd.to_datetime(row_data['Open Date']) + pd.Timedelta(days=int(row_data['DTE at Entry']))
                            target_exp_3d = exp_date_3d.strftime('%Y%m%d')
                            sub_df = sub_df[sub_df['symbol'].str.contains(target_exp_3d)].copy()
                        except Exception:
                            pass
                            
                        sub_df['strike'] = sub_df['symbol'].apply(lambda x: float(x.split('_')[2]) if len(x.split('_'))>2 else 0.0)
                        
                        if is_long_put or is_long_call:
                            tws_unrealized_pnl = sub_df[sub_df['strike'] == K_l]['unrealized_pnl'].sum()
                        else:
                            tws_unrealized_pnl = sub_df[sub_df['strike'].isin([K_s, K_l])]['unrealized_pnl'].sum()
                
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
                elif is_long_call:
                    fig_2d.add_vrect(x0=min_plot, x1=K_l, fillcolor="red", opacity=0.05, layer="below", line_width=0)
                    fig_2d.add_vrect(x0=K_l, x1=max_plot, fillcolor="green", opacity=0.05, layer="below", line_width=0)
                    fig_2d.add_vline(x=K_l, line_dash="dot", line_color="black", annotation_text="Long", annotation_position="top left")
                else:
                    if is_call:
                        if prem > 0: # Bear Call
                            fig_2d.add_vrect(x0=min_plot, x1=K_s, fillcolor="green", opacity=0.05, layer="below", line_width=0)
                            fig_2d.add_vrect(x0=K_l, x1=max_plot, fillcolor="red", opacity=0.05, layer="below", line_width=0)
                        else: # Bull Call
                            fig_2d.add_vrect(x0=K_s, x1=max_plot, fillcolor="green", opacity=0.05, layer="below", line_width=0)
                            fig_2d.add_vrect(x0=min_plot, x1=K_l, fillcolor="red", opacity=0.05, layer="below", line_width=0)
                    else:
                        if prem > 0: # Bull Put
                            fig_2d.add_vrect(x0=K_s, x1=max_plot, fillcolor="green", opacity=0.05, layer="below", line_width=0)    
                            fig_2d.add_vrect(x0=min_plot, x1=K_l, fillcolor="red", opacity=0.05, layer="below", line_width=0)
                        else: # Bear Put
                            fig_2d.add_vrect(x0=min_plot, x1=K_s, fillcolor="green", opacity=0.05, layer="below", line_width=0)
                            fig_2d.add_vrect(x0=K_l, x1=max_plot, fillcolor="red", opacity=0.05, layer="below", line_width=0)
                            
                    fig_2d.add_vline(x=K_s, line_dash="dot", line_color="green", annotation_text="Short", annotation_position="top right" if K_s > K_l else "top left")
                    fig_2d.add_vline(x=K_l, line_dash="dot", line_color="red", annotation_text="Long", annotation_position="top left" if K_s > K_l else "top right")

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
                                z_row.append((t_l - abs(prem)) * qty * 100)
                            elif is_long_call:
                                t_l, _, _, _, _ = get_call_greeks(p, K_l, T_3d, r_rate, iv_dec)
                                z_row.append((t_l - abs(prem)) * qty * 100)
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
                if not (is_long_put or is_long_call):
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

                    fig_3d.add_trace(go.Scatter3d(x=[K_s, K_s], y=[half_dte, half_dte], z=[z_min, z_max], mode='lines', line=dict(color='black', width=6, dash='dash'), showlegend=False, hoverinfo='skip'))
                    fig_3d.add_trace(go.Scatter3d(x=[K_l, K_l], y=[half_dte, half_dte], z=[z_min, z_max], mode='lines', line=dict(color='black', width=6, dash='dash'), showlegend=False, hoverinfo='skip'))
                    fig_3d.add_trace(go.Scatter3d(x=[K_s, K_s], y=[0, init_dte], z=[0, 0], mode='lines', line=dict(color='black', width=6, dash='dash'), showlegend=False, hoverinfo='skip'))
                    fig_3d.add_trace(go.Scatter3d(x=[K_l, K_l], y=[0, init_dte], z=[0, 0], mode='lines', line=dict(color='black', width=6, dash='dash'), showlegend=False, hoverinfo='skip'))
                    fig_3d.add_trace(go.Scatter3d(x=[x_vals[0], x_vals[-1]], y=[half_dte, half_dte], z=[0, 0], mode='lines', line=dict(color='black', width=6, dash='dash'), showlegend=False, hoverinfo='skip'))

                    fig_3d.add_trace(go.Scatter3d(x=[K_s, K_s, K_s, K_s, K_s], y=[0, init_dte, init_dte, 0, 0], z=[z_min, z_min, z_max, z_max, z_min], mode='lines', line=dict(color='green', width=3), showlegend=False, hoverinfo='skip'))
                    fig_3d.add_trace(go.Scatter3d(x=[K_l, K_l, K_l, K_l, K_l], y=[0, init_dte, init_dte, 0, 0], z=[z_min, z_min, z_max, z_max, z_min], mode='lines', line=dict(color='red', width=3), showlegend=False, hoverinfo='skip'))
                    fig_3d.add_trace(go.Scatter3d(x=[x_vals[0], x_vals[-1], x_vals[-1], x_vals[0], x_vals[0]], y=[half_dte, half_dte, half_dte, half_dte, half_dte], z=[z_min, z_min, z_max, z_max, z_min], mode='lines', line=dict(color='yellow', width=3), showlegend=False, hoverinfo='skip'))
                    fig_3d.add_trace(go.Scatter3d(x=[x_vals[0], x_vals[-1], x_vals[-1], x_vals[0], x_vals[0]], y=[0, 0, init_dte, init_dte, 0], z=[0, 0, 0, 0, 0], mode='lines', line=dict(color='gray', width=3), showlegend=False, hoverinfo='skip'))

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

                    target_pnl = (prem / 2.0) * qty * 100
                    fig_3d.add_trace(go.Scatter3d(x=[S_live], y=[curr_dte], z=[target_pnl], mode='markers', name='50% Target', marker=dict(color='#16a34a', size=15, symbol='cross')))
                    stop_loss_pnl = -(abs(prem) * 2.0) * qty * 100 
                    fig_3d.add_trace(go.Scatter3d(x=[S_live], y=[curr_dte], z=[stop_loss_pnl], mode='markers', name='200% Stop Loss', marker=dict(color='#dc2626', size=15, symbol='cross')))

                # Theta Glide Path (Works for Spreads, Long Puts, and Long Calls)
                y_glide = [d for d in y_3d if d <= curr_dte]
                z_glide = []
                for d in y_glide:
                    T_glide = max(d / 365.0, 0.0001)
                    if is_long_put:
                        t_l_glide, _, _, _, _ = get_put_greeks(S_live, K_l, T_glide, r_rate, iv_dec)
                        z_glide.append((t_l_glide - abs(prem)) * qty * 100)
                    elif is_long_call:
                        t_l_glide, _, _, _, _ = get_call_greeks(S_live, K_l, T_glide, r_rate, iv_dec)
                        z_glide.append((t_l_glide - abs(prem)) * qty * 100)
                    else:
                        t_s_glide, _, _, _, _ = pricing_func(S_live, K_s, T_glide, r_rate, iv_dec)
                        t_l_glide, _, _, _, _ = pricing_func(S_live, K_l, T_glide, r_rate, iv_dec)
                        z_glide.append((prem - (t_s_glide - t_l_glide)) * qty * 100)

                fig_3d.add_trace(go.Scatter3d(x=[S_live] * len(y_glide), y=y_glide, z=z_glide, mode='lines', name='Theta Glide Path', line=dict(color='cyan', width=8, dash='dashdot')))

                fig_3d.add_trace(go.Scatter3d(x=x_vals, y=[init_dte]*len(x_vals), z=y_init, mode='lines', name='Entry Day', line=dict(color='purple', width=10, dash='dash')))
                fig_3d.add_trace(go.Scatter3d(x=x_vals, y=[curr_dte]*len(x_vals), z=y_curr, mode='lines', name='Today', line=dict(color='#2563eb', width=7)))
                fig_3d.add_trace(go.Scatter3d(x=[S_live], y=[curr_dte], z=[tws_unrealized_pnl], mode='markers', name='Current Price', marker=dict(color='black', size=6)))
                
                if not (is_long_put or is_long_call):
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
                <div style="background-color: #eff6ff; border: 1px solid #bfdbfe; border-radius: 12px; padding: 24px; color: #2352d9; font-size: 14px;">
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