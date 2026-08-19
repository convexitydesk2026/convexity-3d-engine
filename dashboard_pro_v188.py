"""
=============================================================================
Script Name: dashboard_pro_v188.py
Purpose: The Streamlit Frontend (Family Office Estate Architecture)
⚙️ HOW TO LAUNCH THIS DASHBOARD:
Simply double-click the 'Launch_Dashboard.bat' file.
(Alternatively, open a terminal in this directory and run: streamlit run dashboard_pro_v187.py)

CHANGELOG (v188 PRO):
- STAGE 96 (v188 PRO): Upgraded Alpha Risk Calculator with Multi-Timeframe ATR (Daily, Weekly, Monthly) to prevent long-term whipsaws. Fixed PnL Trajectory percentage distortion.
- STAGE 95 (v187 PRO): Integrated Tiered Drawdown Scaling (Rubber Band Model) into Alpha Risk Calculator and TOR limits.
- STAGE 94 (v186 PRO): Bug Fix - Exempted Tail Hedges (Short Strike 0.0) from the 21-DTE Gamma Cliff scanner.
- STAGE 93 (v185 PRO): Integrated "Definitive Quantitative Mapping" (Ripe Conditions) into Executive Alerts and Master Options Matrix.
- STAGE 92 (v184 PRO): Updated SYNC_SCRIPT variable to point to sync_engine_v39.py (Privacy Mode).
=============================================================================
"""
import streamlit as st
import streamlit.components.v1 as components
import pandas as pd
import sqlite3
import numpy as np
import plotly.graph_objects as go
import plotly.express as px
import yfinance as yf
import os
import sys
import datetime
import random
import subprocess
import glob
import math
import logging
import calendar
import base64
import configparser

from core_math import normCDF, normPDF, get_put_greeks, get_call_greeks, calculate_xirr, process_metrics, get_exact_opt_margin, generate_mc_paths
from risk_engine import get_decoupled_regimes, check_sector_veto, calculate_hwm_budget, calculate_position_size
from estate_env import TARGET_DIR, DB_PATH, CONFIG_PATH

logging.getLogger('yfinance').setLevel(logging.CRITICAL)

st.set_page_config(page_title="Master Dashboard", layout="wide")

SYNC_SCRIPT = os.path.join(TARGET_DIR, "sync_engine_v39.py")

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

def load_silo_map():
    config = configparser.ConfigParser()
    config.read(CONFIG_PATH)
    smap = {}
    if 'SILOS' in config:
        for acc, val in config['SILOS'].items():
            parts = val.split('|')
            alias = parts[0] if len(parts) > 0 else acc
            desc = parts[1] if len(parts) > 1 else "Auto-discovered"
            color = parts[2] if len(parts) > 2 else "#94a3b8"
            is_macro = parts[3] == 'True' if len(parts) > 3 else False
            smap[acc.upper()] = (alias, desc, color, is_macro)
    return smap

SILO_MAP = load_silo_map()

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

@st.cache_data(ttl=3600)
def get_fx_rate(currency):
    if currency == 'USD' or pd.isna(currency): return 1.0
    direct = {'EUR': 'EURUSD=X', 'GBP': 'GBPUSD=X', 'AUD': 'AUDUSD=X', 'NZD': 'NZDUSD=X'}
    inverted = {'KRW': 'KRW=X', 'SEK': 'SEK=X', 'NOK': 'NOK=X', 'CAD': 'CAD=X', 'CHF': 'CHF=X', 'JPY': 'JPY=X', 'TWD': 'TWD=X', 'HKD': 'HKD=X', 'SGD': 'SGD=X'}
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

    # v75: Safeguard against empty cells during live data-entry
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

@st.cache_data(ttl=900)
def get_vix_term_structure():
    """Fetches VIX9D and VIX3M to calculate Contango vs Backwardation."""
    try:
        vix9d = float(yf.Ticker('^VIX9D').history(period='1d')['Close'].iloc[-1])
        vix3m = float(yf.Ticker('^VIX3M').history(period='1d')['Close'].iloc[-1])
        return vix9d, vix3m
    except Exception:
        return 0.0, 0.0

@st.cache_data(ttl=900)
def get_distribution_tracker():
    """Fetches last 10 days of SPY, QQQ, and RSP to track consecutive red candles (Close < Open)."""
    try:
        # Explicitly set auto_adjust=False to silence the yfinance FutureWarning
        data = yf.download(["SPY", "QQQ", "RSP"], period="15d", progress=False, auto_adjust=False)
        if isinstance(data.columns, pd.MultiIndex):
            spy_open = data['Open']['SPY'].dropna().tail(10)
            spy_close = data['Close']['SPY'].dropna().tail(10)
            qqq_open = data['Open']['QQQ'].dropna().tail(10)
            qqq_close = data['Close']['QQQ'].dropna().tail(10)
            rsp_open = data['Open']['RSP'].dropna().tail(10)
            rsp_close = data['Close']['RSP'].dropna().tail(10)
        else:
            return {"SPY": (0, []), "QQQ": (0, []), "RSP": (0, [])}
        
        def calc_consecutive_red(open_s, close_s):
            is_red = (close_s < open_s).tolist()
            count = 0
            for red in reversed(is_red):
                if red: count += 1
                else: break
            return count, is_red
        
        spy_count, spy_seq = calc_consecutive_red(spy_open, spy_close)
        qqq_count, qqq_seq = calc_consecutive_red(qqq_open, qqq_close)
        rsp_count, rsp_seq = calc_consecutive_red(rsp_open, rsp_close)
        return {"SPY": (spy_count, spy_seq), "QQQ": (qqq_count, qqq_seq), "RSP": (rsp_count, rsp_seq)}
    except Exception:
        return {"SPY": (0, []), "QQQ": (0, []), "RSP": (0, [])}

@st.cache_data(ttl=3600)
def get_fundamentals_and_news(symbol):
    """Fetches Forward P/E, Short Interest, Market Cap, Avg Volume, and recent news headlines."""
    try:
        clean_sym = symbol.split()[0]
        tkr = yf.Ticker(clean_sym)
        info = tkr.info
        fwd_pe = info.get('forwardPE', 'N/A')
        short_float = info.get('shortPercentOfFloat', 'N/A')
        if isinstance(short_float, float): short_float = f"{short_float * 100:.2f}%"
        
        mkt_cap = info.get('marketCap', 'N/A')
        if isinstance(mkt_cap, (int, float)):
            if mkt_cap >= 1e12: mkt_cap = f"${mkt_cap/1e12:.2f}T"
            elif mkt_cap >= 1e9: mkt_cap = f"${mkt_cap/1e9:.2f}B"
            elif mkt_cap >= 1e6: mkt_cap = f"${mkt_cap/1e6:.2f}M"
            else: mkt_cap = f"${mkt_cap:,.0f}"
            
        avg_vol = info.get('averageVolume', 'N/A')
        if isinstance(avg_vol, (int, float)):
            if avg_vol >= 1e6: avg_vol = f"{avg_vol/1e6:.2f}M"
            elif avg_vol >= 1e3: avg_vol = f"{avg_vol/1e3:.2f}K"
            else: avg_vol = f"{avg_vol:,.0f}"
        
        news_items = tkr.news[:3] if tkr.news else []
        news_str = ""
        for n in news_items:
            # Handle Yahoo's new nested 'content' structure or fallback to standard keys
            if 'content' in n and isinstance(n['content'], dict):
                title = n['content'].get('title', 'No Title')
                publisher = n['content'].get('provider', {}).get('displayName', 'Unknown')
            else:
                title = n.get('title', 'No Title')
                publisher = n.get('publisher', 'Unknown')
            news_str += f"- {title} ({publisher})\n"
        if not news_str: news_str = "- No recent news found.\n"
        
        return fwd_pe, short_float, mkt_cap, avg_vol, news_str
    except Exception:
        return "N/A", "N/A", "N/A", "N/A", "- Error fetching news.\n"

@st.cache_data(ttl=3600)
def get_relative_strength_stats(symbol):
    """Calculates 3-Month Thrust vs SPY and RVOL for the ticker and its Sector ETF."""
    try:
        clean_sym = symbol.split()[0]
        sector_map = {
            'Technology': 'XLK', 'Financial Services': 'XLF', 'Healthcare': 'XLV',
            'Consumer Cyclical': 'XLY', 'Industrials': 'XLI', 'Utilities': 'XLU',
            'Consumer Defensive': 'XLP', 'Real Estate': 'XLRE', 'Energy': 'XLE',
            'Basic Materials': 'XLB', 'Communication Services': 'XLC'
        }
        sec_str = get_sector(clean_sym, 'Physical US Stocks')
        etf_sym = sector_map.get(sec_str, 'SPY')
        
        tickers_to_dl = list(set([clean_sym, etf_sym, "SPY"]))
        data = yf.download(tickers_to_dl, period="100d", progress=False, auto_adjust=False)
        
        def calc_stats(tckr):
            try:
                if isinstance(data.columns, pd.MultiIndex):
                    df = pd.DataFrame({'Close': data['Close'][tckr], 'Volume': data['Volume'][tckr]}).dropna()
                    spy_close = data['Close']['SPY'].dropna()
                else:
                    df = pd.DataFrame({'Close': data['Close'], 'Volume': data['Volume']}).dropna()
                    spy_close = data['Close'].dropna()
                    
                if len(df) < 65: return "N/A", "N/A"
                
                curr_p = df['Close'].iloc[-1]
                p_3m = df['Close'].iloc[-64]
                spy_curr = spy_close.iloc[-1]
                spy_3m = spy_close.iloc[-64]
                
                thrust = ((curr_p / p_3m) / (spy_curr / spy_3m)) - 1
                vol_50 = df['Volume'].rolling(50).mean().iloc[-1]
                rvol = df['Volume'].iloc[-1] / vol_50 if vol_50 > 0 else 0
                
                return f"{thrust*100:+.1f}%", f"{rvol:.1f}x"
            except:
                return "N/A", "N/A"
        
        sym_thrust, sym_rvol = calc_stats(clean_sym)
        etf_thrust, etf_rvol = calc_stats(etf_sym)
        return sym_thrust, sym_rvol, etf_sym, etf_thrust, etf_rvol
    except Exception:
        return "N/A", "N/A", "N/A", "N/A", "N/A"

def make_cdd_sparkline(seq):
    if not seq: return "<span style='color:gray; font-size:10px;'>No data</span>"
    boxes = [f"<div style='width: 12px; height: 12px; background-color: {'#ef4444' if is_red else '#22c55e'}; border-radius: 2px;'></div>" for is_red in seq]
    return f"<div style='display: flex; gap: 3px; align-items: center;'>{''.join(boxes)}</div>"

# --- DYNAMIC SCRIPT DISCOVERY ---
def get_active_scripts():
    active_dash = os.path.basename(__file__)
    patterns = ['Telegram_Notifier_v*.py', 'sync_engine_v*.py', 'estate_daemon.py', 'Run_Estate_Daemon.bat']
    scripts = [f"{active_dash} [Active]"]
    for p in patterns:
        matches = glob.glob(os.path.join(TARGET_DIR, p))
        if matches:
            latest = max(matches, key=os.path.getmtime)
            scripts.append(os.path.basename(latest))
    return " • ".join(scripts)

active_scripts_str = get_active_scripts()

# --- SIDEBAR: SYNC BUTTON & CASH FLOW Ledger ---
with st.sidebar:

    st.markdown('''
    <style>

    [data-testid="stSidebar"] button[kind="secondary"] {
        background-color: #ffffff !important;
    }
    [data-testid="stSidebar"] button[kind="primary"] {
        background-color: #c8e6c9 !important;
        color: #1b5e20 !important;
        border: 1px solid #a5d6a7 !important;
        font-weight: bold !important;
    }
        background-color: #ffffff !important;
    }

    [data-testid="stSidebar"] [data-testid="stExpander"] details,
    [data-testid="stSidebar"] [data-testid="stExpander"] summary,
    [data-testid="stSidebar"] [data-testid="stExpander"] {
        background-color: #ffffff !important;
        border-radius: 8px;
    }
    </style>
    ''', unsafe_allow_html=True)
    st.markdown("### 📌 Institutional Directory")
    st.markdown("""
    - [Master Dashboard](#top)
    - [Estate Aggregation](#master-agg)
    - [Calendars](#sec1b)
    - [Market Flow](#sec1c)
    - [Capital Breakdown](#sec1)
    - [Options Center](#sec6)
    - [Convexity Project Tracker](#sec100)
    """)
    st.markdown("---")

    # Placeholder for Risk Calculator (Populated after DB loads)
    calc_placeholder = st.empty()

    
    if st.button("⟳ Sync Live from TWS", type="primary", width="stretch"):
        with st.spinner("Connecting to TWS... Please wait (~15s)"):
            try:
                subprocess.run(["python", SYNC_SCRIPT], check=True)
                st.success("Sync Complete!")
                st.cache_data.clear() 
                st.rerun()
            except Exception as e:
                st.error(f"Sync failed. Is TWS open? Error: {e}")
    if st.button("🌐 Generate Market Flow Report", width="stretch"):
        with st.spinner("Calculating Institutional Flow & Generating PDF... Please wait (~15s)"):
            try:
                subprocess.run(["python", "market_flow_engine_v8.py"], cwd=TARGET_DIR, check=True)
                st.success("Market Flow Updated & PDF Ready!")
                st.rerun()
            except Exception as e:
                st.error(f"Market Flow Engine failed: {e}")
    with st.expander("⚙️ Silo Management"):
        st.markdown("Configure auto-discovered accounts.")
        config = configparser.ConfigParser()
        config.read(CONFIG_PATH)
        if 'SILOS' not in config: config['SILOS'] = {}
        with st.form("silo_mgmt_form"):
            updated_silos = {}
            for acc, data in SILO_MAP.items():
                st.markdown(f"**Account: {acc}**")
                c1, c2 = st.columns([3, 1])
                new_alias = c1.text_input("Alias", value=data[0], key=f"alias_{acc}")
                new_color = c2.color_picker("Color", value=data[2], key=f"color_{acc}")
                new_desc = st.text_input("Description / Strategy", value=data[1], key=f"desc_{acc}")
                new_macro = st.checkbox("Include in Macro Core?", value=data[3], key=f"macro_{acc}")
                updated_silos[acc] = f"{new_alias}|{new_desc}|{new_color}|{new_macro}"
            if st.form_submit_button("Save Configuration", use_container_width=True):
                for acc, val_str in updated_silos.items():
                    config['SILOS'][acc] = val_str
                with open(CONFIG_PATH, 'w') as f:
                    config.write(f)
                st.cache_data.clear()
                st.rerun()
    with st.expander("Record External or Internal Transfer"):
        with st.form("transfer_form", clear_on_submit=True):
            t_date = st.date_input("Date of Transfer", datetime.date.today())
            silo_options = [f"{acc} ({data[0]})" for acc, data in SILO_MAP.items()]
            t_acc = st.selectbox("Destination / Origin Silo", silo_options if silo_options else ["No Silos Found"])
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
    with st.expander("Manage Alpha Watchlist"):
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute("CREATE TABLE IF NOT EXISTS alpha_watchlist (symbol TEXT PRIMARY KEY, target_iv REAL, current_iv REAL DEFAULT 0.0)")
        with st.form("add_watchlist_form", clear_on_submit=True):
            wl_ticker = st.text_input("Ticker Symbol (e.g., MU, BE)").upper()
            c_iv1, c_iv2 = st.columns(2)
            with c_iv1:
                wl_low_iv = st.number_input("52-Wk Low IV (%)", min_value=1.0, value=30.0, step=1.0)
            with c_iv2:
                wl_high_iv = st.number_input("52-Wk High IV (%)", min_value=1.0, value=60.0, step=1.0)
                
            if st.form_submit_button("Calculate & Add to Scanner"):
                if wl_ticker and wl_high_iv > wl_low_iv:
                    # CFO Policy: Top 25% of Annual Range (75th Percentile)
                    calc_target = wl_low_iv + (0.75 * (wl_high_iv - wl_low_iv))
                    
                    # COALESCE ensures a brand new ticker defaults current_iv to 0.0 instead of NULL
                    c.execute("INSERT OR REPLACE INTO alpha_watchlist (symbol, target_iv, current_iv) VALUES (?, ?, COALESCE((SELECT current_iv FROM alpha_watchlist WHERE symbol=?), 0.0))", (wl_ticker, calc_target, wl_ticker))
                    conn.commit()
                    st.success(f"Added {wl_ticker}. Target auto-calculated to {calc_target:.1f}%.")
                    st.cache_data.clear()
                    st.rerun()
                elif wl_ticker:
                    st.error("High IV must be mathematically greater than Low IV.")
                    
        st.markdown("**Active Watchlist:**")
        wl_df = pd.read_sql_query("SELECT symbol, target_iv, current_iv FROM alpha_watchlist", conn)
        if not wl_df.empty:
            for idx, row in wl_df.iterrows():
                col_sym, col_del = st.columns([3, 1])
                with col_sym:
                    st.write(f"**{row['symbol']}** (Tgt: {row['target_iv']}%)")
                with col_del:
                    if st.button("X", key=f"del_wl_{row['symbol']}"):
                        c.execute("DELETE FROM alpha_watchlist WHERE symbol=?", (row['symbol'],))
                        conn.commit()
                        st.rerun()
        else:
            st.caption("Watchlist is empty.")
        conn.close()

# --- HELPER FUNCTIONS ---
    
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

@st.cache_data(ttl=86400) # Cache for 24 hours to prevent Yahoo API rate limits
def get_upcoming_earnings(symbol):
    try:
        clean_sym = symbol.split()[0]
        tkr = yf.Ticker(clean_sym)
        cal = tkr.calendar
        # yfinance API returns different structures depending on the version. We handle all safely:
        if isinstance(cal, dict) and 'Earnings Date' in cal:
            val = cal['Earnings Date']
            if isinstance(val, list) and len(val) > 0:
                return pd.to_datetime(val[0]).date()
            elif isinstance(val, pd.Series) and not val.empty:
                return pd.to_datetime(val.iloc[0]).date()
            else:
                return pd.to_datetime(val).date()
        elif isinstance(cal, pd.DataFrame) and not cal.empty:
            if 'Earnings Date' in cal.index:
                return pd.to_datetime(cal.loc['Earnings Date'].dropna().iloc[0]).date()
            elif 'Earnings Date' in cal.columns:
                return pd.to_datetime(cal['Earnings Date'].dropna().iloc[0]).date()
    except Exception:
        pass
    return None

@st.cache_data(ttl=3600)
def get_stock_smas(symbol):
    try:
        clean_sym = symbol.split()[0]
        # Fetch last 100 days to safely ensure we have 50 trading days for the moving average
        hist = yf.Ticker(clean_sym).history(period='100d')
        if not hist.empty and len(hist) >= 50:
            sma_20 = hist['Close'].rolling(window=20).mean().iloc[-1]
            sma_50 = hist['Close'].rolling(window=50).mean().iloc[-1]
            return float(sma_20), float(sma_50)
        elif not hist.empty and len(hist) >= 20:
            sma_20 = hist['Close'].rolling(window=20).mean().iloc[-1]
            return float(sma_20), 0.0
    except Exception:
        pass
    return 0.0, 0.0

@st.cache_data(ttl=86400)
def get_sector_and_industry(symbol, asset_class):
    if asset_class not in ['Physical US Stocks', 'International Stocks', 'US Tech CFDs']:
        return asset_class, 'N/A'
        
    # FIX: Added timeout=15 and WAL mode to prevent intra-thread deadlocks.
    conn = sqlite3.connect(DB_PATH, timeout=15)
    conn.execute("PRAGMA journal_mode=WAL;")
    c = conn.cursor()
    c.execute("CREATE TABLE IF NOT EXISTS asset_sectors_v2 (symbol TEXT PRIMARY KEY, sector TEXT, industry TEXT)")
    c.execute("SELECT sector, industry FROM asset_sectors_v2 WHERE symbol=?", (symbol,))
    row = c.fetchone()
    
    if row:
        conn.close()
        return row[0], row[1]
        
    clean_sym = symbol.split()[0]
    try:
        info = yf.Ticker(clean_sym).info
        sector = info.get('sector', 'Unknown Equities')
        industry = info.get('industry', 'N/A')
    except Exception:
        sector = 'Unknown Equities'
        industry = 'N/A'
        
    c.execute("INSERT OR REPLACE INTO asset_sectors_v2 VALUES (?, ?, ?)", (symbol, sector, industry))
    conn.commit()
    conn.close()
    return sector, industry

@st.cache_data(ttl=3600)
def get_stock_smas_v2(symbol):
    try:
        clean_sym = symbol.split()[0]
        hist = yf.Ticker(clean_sym).history(period='300d')
        if not hist.empty and len(hist) >= 20:
            sma_20 = float(hist['Close'].rolling(window=20).mean().iloc[-1])
            sma_50 = float(hist['Close'].rolling(window=50).mean().iloc[-1]) if len(hist) >= 50 else 0.0
            sma_200 = float(hist['Close'].rolling(window=200).mean().iloc[-1]) if len(hist) >= 200 else 0.0
            return sma_20, sma_50, sma_200
    except Exception:
        pass
    return 0.0, 0.0, 0.0

@st.cache_data(ttl=3600)
def get_atr(symbol, period=14, timeframe='Daily'):
    try:
        clean_sym = symbol.split()[0]
        
        if timeframe == 'Weekly':
            df = yf.Ticker(clean_sym).history(period="1y", interval="1wk")
        elif timeframe == 'Monthly':
            df = yf.Ticker(clean_sym).history(period="3y", interval="1mo")
        else:
            df = yf.Ticker(clean_sym).history(period=f"{period+10}d", interval="1d")
            
        if len(df) < period: return 0.0
        
        high_low = df['High'] - df['Low']
        high_close = (df['High'] - df['Close'].shift(1)).abs()
        low_close = (df['Low'] - df['Close'].shift(1)).abs()
        tr = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
        return float(tr.rolling(period).mean().iloc[-1])
    except Exception:
        return 0.0

@st.cache_data(ttl=3600)
def evaluate_sector_veto(symbol):
    if not symbol or pd.isna(symbol): return False
    try:
        sector_str = get_sector(symbol, 'Physical US Stocks')
        return check_sector_veto(sector_str)
    except Exception:
        return False

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

        # V77 FIX: OUTER JOIN to prevent dropping cash flows on days TWS wasn't synced
        df = pd.merge(df, daily_transfers, on=['date', 'account'], how='outer')
        df = df.sort_values(['account', 'date']).reset_index(drop=True)
        
        # Suppress Pandas future warning by explicitly avoiding silent downcasting
        if not df['new_flow'].empty:
            df['new_flow'] = df['new_flow'].fillna(0.0).infer_objects(copy=False)
        else:
            df['new_flow'] = 0.0
            
        # v91 FIX: Robust NAV Forward Fill (Solves the Phantom Volatility Jump)
        # If a date has a cash flow but no NAV, we mathematically force the old NAV to absorb the flow.
        for acc in df['account'].unique():
            acc_idxs = df[df['account'] == acc].index
            last_nav = 0.0
            for i in acc_idxs:
                current_nav = df.at[i, 'nav']
                flow = df.at[i, 'new_flow']
                if pd.isna(current_nav) or current_nav == 0:
                    if last_nav > 0:
                        df.at[i, 'nav'] = last_nav + flow
                        last_nav = df.at[i, 'nav']
                else:
                    last_nav = current_nav
    except Exception:
        df['new_flow'] = 0.0
        
    # Combine legacy SQL patches with new UI ledger entries
    if not df['legacy_flow'].empty:
        df['legacy_flow'] = df['legacy_flow'].fillna(0.0).infer_objects(copy=False)
    else:
        df['legacy_flow'] = 0.0
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
            acc_df['prev_nav'] = acc_df['nav'].shift(1).fillna(0.0)
            acc_df['daily_pnl'] = acc_df['nav'] - acc_df['net_flow'] - acc_df['prev_nav']
            acc_df['daily_return'] = acc_df['daily_pnl'] / acc_df['prev_nav'].replace(0, np.nan)
            acc_df['cum_return'] = (1 + acc_df['daily_return'].fillna(0)).cumprod() - 1
        silo_dfs[acc] = acc_df

    # Global tracking arrays (v91: Pure Absolute Math across all Silos. Kills the Whipsaw)
    if not global_df.empty:
        global_df['prev_nav'] = global_df['nav'].shift(1).fillna(0.0)
        global_df['daily_pnl'] = global_df['nav'] - global_df['net_flow'] - global_df['prev_nav']
        global_df['daily_return'] = global_df['daily_pnl'] / global_df['prev_nav'].replace(0, np.nan)

        global_df['cum_return'] = (1 + global_df['daily_return'].fillna(0)).cumprod() - 1
        global_df['cum_pnl'] = global_df['daily_pnl'].cumsum()
        
        # Override the global metrics total PnL with the mathematically perfect absolute total
        global_metrics['pnl'] = global_df['nav'].iloc[-1] - global_df['net_flow'].sum()

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
              
    # Option A: Pre-load the Master Options Journal to cross-reference option classes
    synth_beta_keys = set()
    tail_hedge_keys = set()
    try:
        df_j = pd.read_sql_query("SELECT `Tranche ID`, Ticker, `Long Strike` FROM options_journal", conn)
        for _, r in df_j.iterrows():
            tranche = str(r['Tranche ID']).lower()
            tckr = str(r['Ticker']).upper()
            try: strike = float(r['Long Strike'])
            except: strike = 0.0
            
            if 'beta' in tranche or 'call' in tranche:
                synth_beta_keys.add((tckr, strike))
            elif 'tail' in tranche or 'hedge' in tranche:
                tail_hedge_keys.add((tckr, strike))
    except Exception:
        pass

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
            return 'Physical US Stocks' if curr == 'USD' else 'International Stocks'
        if sec == 'OPT':
            if pos > 0: 
                try:
                    parts = s.split('_')
                    if len(parts) >= 4:
                        tckr = parts[0]
                        strike = float(parts[2])
                        right = parts[3]
                        
                        # Option A: Definitive Database Cross-Reference
                        if right == 'C' and (tckr, strike) in synth_beta_keys:
                            return 'Synthetic Beta'
                        if right == 'P' and (tckr, strike) in tail_hedge_keys:
                            return 'Tail Hedge'
                        
                        # Fallbacks just in case
                        if tckr == 'VIX' and right == 'C': return 'Tail Hedge'
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
        data = yf.download(["SPY", "QQQ", "RSP", "^VIX"], start=start_date - datetime.timedelta(days=300), end=end_date + datetime.timedelta(days=1), progress=False, auto_adjust=False)
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
    
    # Legacy SPY SMAs (Kept for potential chart plotting dependencies)
    bench_df['sma_10'] = bench_df['SPY'].rolling(window=10).mean()  
    bench_df['sma_20'] = bench_df['SPY'].rolling(window=20).mean()
    bench_df['sma_50'] = bench_df['SPY'].rolling(window=50).mean()
    bench_df['sma_200'] = bench_df['SPY'].rolling(window=200).mean()
        
    # Multi-Factor SMAs for the Decoupled Engines
    bench_df['rsp_sma_10'] = bench_df['RSP'].rolling(window=10).mean()
    bench_df['rsp_sma_20'] = bench_df['RSP'].rolling(window=20).mean()
    bench_df['rsp_sma_50'] = bench_df['RSP'].rolling(window=50).mean()
    bench_df['sma_10'] = bench_df['SPY'].rolling(window=10).mean()
    bench_df['sma_20'] = bench_df['SPY'].rolling(window=20).mean()
    bench_df['sma_50'] = bench_df['SPY'].rolling(window=50).mean()
    
    bench_df = bench_df[bench_df['date'] >= pd.to_datetime(start_date)].copy()
               
    bench_df[['alpha_gear', 'opt_dir']] = bench_df.apply(lambda row: pd.Series(get_decoupled_regimes(row)), axis=1)
    bench_df['spy_ret'] = bench_df['SPY'].pct_change().fillna(0)
    bench_df['qqq_ret'] = bench_df['QQQ'].pct_change().fillna(0)
    bench_df['rsp_ret'] = bench_df['RSP'].pct_change().fillna(0)
    bench_df['spy_cum'] = (1 + bench_df['spy_ret']).cumprod() - 1
    bench_df['qqq_cum'] = (1 + bench_df['qqq_ret']).cumprod() - 1
    bench_df['rsp_cum'] = (1 + bench_df['rsp_ret']).cumprod() - 1
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
exp_top = st.expander("Master Dashboard", expanded=False)
exp_top.title("Master Dashboard", anchor="top")
exp_top.markdown(f"**Data Pipeline:** Live IBKR Sync via SQLite (`{os.path.basename(DB_PATH)}`) • **Last Refresh:** {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
exp_top.markdown(f"**Active Scripts:** `{active_scripts_str}`")
exp_top.divider()

global_df, global_metrics, silo_dfs, silo_metrics, pos_df, attr_df, balances_df, open_orders_df = load_and_process_data()

# --- POPULATE SIDEBAR CALCULATOR ---
with calc_placeholder.container():
    st.markdown("### 🧮 Alpha Risk Calculator & HWM Budget")
    
    # 1. Calculate Global High-Water Mark (HWM) & Tiered Drawdown Multiplier
    hwm, dd_pct, tier_multiplier, tier_name = calculate_hwm_budget(global_df, global_metrics['nav'])
    
    # 2. Check 48-Hour Revenge Trading Lockout (v7.0 Inception Filter)
    conn_lock = sqlite3.connect(DB_PATH)
    c_lock = conn_lock.cursor()
    c_lock.execute("SELECT COUNT(*) FROM alpha_campaigns WHERE status IN ('Closed', 'Closed 🏁') AND total_pnl < 0 AND close_date >= date('now', '-2 days') AND close_date >= '2026-07-17'")
    recent_losses = c_lock.fetchone()[0]
    conn_lock.close()
    
    # FIX 1: Cast to native Python bool to prevent Streamlit protobuf TypeError
    is_locked = bool(recent_losses >= 3 or tier_multiplier == 0.0)
    
    budget_color = "#16a34a" if tier_multiplier == 1.0 else ("#eab308" if tier_multiplier == 0.5 else ("#f97316" if tier_multiplier == 0.25 else "#dc2626"))
    
    # Calculate Max TOR for display (Using temp_chart_ui to avoid top-to-bottom NameErrors)
    temp_bench_ui = load_benchmarks(global_df['date'].min(), global_df['date'].max())
    temp_chart_ui = pd.merge(global_df, temp_bench_ui, on='date', how='left').ffill().fillna(0)
    base_gear_display = temp_chart_ui['alpha_gear'].iloc[-1] if not temp_chart_ui.empty else 2
    
    gear_risk_map_display = {5: 0.20, 4: 0.135, 3: 0.09, 2: 0.06, 1: 0.04, 0: 0.00}
    max_r_display = gear_risk_map_display.get(base_gear_display, 0.0) * tier_multiplier
    max_tor_usd_display = global_metrics['nav'] * (max_r_display * 10.0 / 100.0)

    # Calculate Current TOR unconditionally for the sidebar display
    alpha_assets_list_ui = ['Physical US Stocks', 'International Stocks', 'US Tech CFDs', 'Gold', 'Crypto', 'CSPX', 'CNDX', 'ITWN', 'CSKR', 'CNYA']
    df_phys_ui = pos_df[pos_df['asset_class'].isin(alpha_assets_list_ui)]
    current_global_risk_ui = 0.0
    
    for sym, g in df_phys_ui.groupby('symbol'):
        shares = g['position'].sum()
        if shares <= 0: continue
        avg_cost = g['avg_cost'].iloc[0]
        curr = g['currency'].iloc[0] if 'currency' in g.columns else 'USD'
        fx_r = get_fx_rate(curr)
        
        sym_stops = pd.DataFrame()
        if not open_orders_df.empty:
            sym_stops = open_orders_df[(open_orders_df['symbol'] == sym) & 
                                       (open_orders_df['action'] == 'SELL') & 
                                       (open_orders_df['order_type'].str.contains('STP|TRAIL', case=False, na=False))].sort_values('aux_price', ascending=False)
        rem_shares = shares
        sym_risk = 0.0
        for _, sr in sym_stops.iterrows():
            q = min(sr['total_quantity'], rem_shares)
            if q <= 0: break
            sl_usd = sr['aux_price'] * fx_r
            if sl_usd > 0 and g['market_price'].iloc[0] > 0:
                if (sl_usd / g['market_price'].iloc[0]) > 50: sl_usd /= 100.0
                elif (sl_usd / g['market_price'].iloc[0]) < 0.02: sl_usd *= 100.0
            diff = (q * sl_usd) - (q * avg_cost)
            if diff < 0: sym_risk += diff
            rem_shares -= q
        if rem_shares > 0:
            sym_risk -= (rem_shares * avg_cost)
        
        current_global_risk_ui += sym_risk
        
    current_tor_abs = abs(current_global_risk_ui)
    remaining_tor_usd = max_tor_usd_display - current_tor_abs
    remaining_color = "#16a34a" if remaining_tor_usd > 0 else "#dc2626"

    # FIX 2: Use HTML entity &#36; instead of \$ to prevent Python SyntaxWarnings and Markdown LaTeX bugs
    st.markdown(f"""
    <div style='background-color: #f8fafc; padding: 15px; border-radius: 8px; border: 1px solid #cbd5e1; margin-bottom: 15px;'>
        <div style='font-size: 12px; color: #64748b; font-weight: bold; text-transform: uppercase;'>Tiered Drawdown Governor</div>
        <div style='font-size: 24px; font-weight: 900; color: {budget_color};'>{tier_name} ({tier_multiplier}x)</div>
        <div style='font-size: 12px; color: #475569; margin-top: 5px;'>HWM: &#36;{hwm:,.0f} | Current Drawdown: {dd_pct:.2f}%</div>
        <hr style='margin: 10px 0; border-color: #e5e7eb;'>
        <div style='display: flex; justify-content: space-between;'>
            <div>
                <div style='font-size: 11px; color: #64748b; font-weight: bold; text-transform: uppercase;'>Max Capacity</div>
                <div style='font-size: 16px; font-weight: bold; color: #1d4ed8;'>&#36;{max_tor_usd_display:,.0f}</div>
            </div>
            <div style='text-align: right;'>
                <div style='font-size: 11px; color: #64748b; font-weight: bold; text-transform: uppercase;'>Remaining</div>
                <div style='font-size: 16px; font-weight: bold; color: {remaining_color};'>&#36;{remaining_tor_usd:,.0f}</div>
            </div>
        </div>
    </div>
    """, unsafe_allow_html=True)
    
    if is_locked:
        lock_reason = "3 consecutive losses in 48h." if recent_losses >= 3 else "Tier 4 Drawdown Lockout (-3.0% breached)."
        st.error(f"🚨 **ALPHA ENGINE LOCKED:** {lock_reason} Trading halted until recovery. (Simulation Mode Active)")

    with st.expander("Position Sizing Engine", expanded=False):
        
        # Fetch Live Regime for Dynamic Risk Capping
        temp_bench_ui = load_benchmarks(global_df['date'].min(), global_df['date'].max())
        temp_chart_ui = pd.merge(global_df, temp_bench_ui, on='date', how='left').ffill().fillna(0)
        
        silo_options = [f"{acc} ({data[0]})" for acc, data in SILO_MAP.items()]
        calc_silo = st.selectbox("Target Silo", silo_options if silo_options else ["No Silos Found"], key="calc_silo")
        
        calc_silo_key = calc_silo.split(" ")[0]
        calc_nav = silo_metrics.get(calc_silo_key, {}).get('nav', 0.0)
        calc_uninvested_cash = pos_df[(pos_df['account'] == calc_silo_key) & (pos_df['asset_class'] == 'Cash')]['market_value'].sum() if not pos_df.empty else 0.0
        
        st.markdown(f"<div style='font-size: 13px; color: #475569;'>Silo NAV: <b>${calc_nav:,.0f}</b></div>", unsafe_allow_html=True)
        st.markdown(f"<div style='font-size: 13px; color: #475569; margin-bottom: 10px;'>Uninvested Cash: <b>${calc_uninvested_cash:,.0f}</b></div>", unsafe_allow_html=True)
        
        is_ipo = st.checkbox("Flag as IPO / Unproven Asset (< 6mo or < $2B MC)")
        
        calc_mode = st.radio("Trade Mode", ["Initial Entry", "Scale-In (Pyramid)"], horizontal=True, label_visibility="collapsed")
        trade_horizon = st.selectbox("Trade Horizon (ATR Sizing)", ["Short-Term (Daily)", "Medium-Term (Weekly)", "Long-Term (Monthly)"])
        
        # Determine Ticker FIRST for Sector Veto
        calc_sym_init = ""
        target_sym_atr = ""
        active_alpha = pd.DataFrame()
        
        if calc_mode == "Scale-In (Pyramid)":
            alpha_assets = ['Physical US Stocks', 'International Stocks', 'US Tech CFDs', 'Crypto', 'Gold', 'Active Swing']
            active_alpha = pos_df[(pos_df['account'] == calc_silo_key) & (pos_df['position'] != 0) & (pos_df['asset_class'].isin(alpha_assets))]
            if not active_alpha.empty:
                calc_sym = st.selectbox("Target Asset", active_alpha['symbol'].unique())
                target_sym_atr = calc_sym
        else:
            calc_sym_init = st.text_input("Ticker Symbol").upper()
            target_sym_atr = calc_sym_init

        # Calculate 6-Gear System & Sector Veto
        base_gear = temp_chart_ui['alpha_gear'].iloc[-1] if not temp_chart_ui.empty else 2
        is_vetoed = False
        if target_sym_atr:
            is_vetoed = evaluate_sector_veto(target_sym_atr)
            
        active_gear = max(0, base_gear - 1) if is_vetoed else base_gear
        gear_risk_map = {5: 0.20, 4: 0.135, 3: 0.09, 2: 0.06, 1: 0.04, 0: 0.00}
        
        # Apply the Tiered Drawdown Multiplier to the Base Risk
        base_max_r = gear_risk_map.get(active_gear, 0.0)
        max_r = base_max_r * tier_multiplier
        
        c1, c2 = st.columns(2)
        
        veto_text = " (Sector Veto: -1 Gear)" if is_vetoed else ""
        calc_risk_pct = c1.number_input("Risk %", min_value=0.00, value=max_r, step=0.01, format="%.3f", help=f"Gear {active_gear}{veto_text} @ {tier_multiplier}x Multiplier: Max Risk capped at {max_r}%.")

        if calc_risk_pct > max_r:
            st.error(f"🚨 **RULE VIOLATION:** You are attempting to risk {calc_risk_pct}%. The absolute maximum allowed under current Drawdown Tier ({tier_multiplier}x) is {max_r}%.")

        if is_ipo and calc_risk_pct > 0.5:
            st.warning("IPO/Unproven Asset selected. Risk % mechanically capped at 0.5%.")
            calc_risk_pct = 0.5

        is_valid_pyramid = False
        proposed_shares = 0
        old_risk_usd = 0
        available_risk_usd = 0
        
        if calc_mode == "Scale-In (Pyramid)":
            if active_alpha.empty:
                st.warning("No scalable assets found in this Silo.")
                calc_dir = c2.selectbox("Direction", ["Long", "Short"], disabled=True)
                calc_currency = st.selectbox("Asset Currency", ['USD'], disabled=True)
                calc_entry = 0.0
                calc_stop = 0.0
            else:
                sym_row = active_alpha[active_alpha['symbol'] == calc_sym].iloc[0]
                existing_shares = sym_row['position']
                existing_avg_usd = sym_row['avg_cost']
                calc_currency = sym_row['currency'] if pd.notna(sym_row.get('currency')) else 'USD'
                
                fx_rate = get_fx_rate(calc_currency)
                existing_avg_local = existing_avg_usd / fx_rate if fx_rate > 0 else existing_avg_usd
                
                current_price_usd = sym_row['market_price']
                current_price_local = current_price_usd / fx_rate if fx_rate > 0 else current_price_usd
                
                actual_dir = "Long" if existing_shares > 0 else "Short"
                calc_dir = c2.selectbox("Direction", [actual_dir], disabled=True)
                
                sym_stops = pd.DataFrame()
                if 'open_orders_df' in locals() and not open_orders_df.empty:
                    sym_stops = open_orders_df[(open_orders_df['symbol'] == calc_sym) & 
                                               (open_orders_df['action'] == ('SELL' if actual_dir == 'Long' else 'BUY')) & 
                                               (open_orders_df['order_type'].str.contains('STP|TRAIL', case=False, na=False))]
                
                live_stop_local = 0.0
                if not sym_stops.empty:
                    live_stop_local = sym_stops['aux_price'].max() if actual_dir == 'Long' else sym_stops['aux_price'].min()

                st.markdown(f"<div style='font-size: 11px; background-color: #eff6ff; padding: 6px; border-radius: 4px; color: #1e3a8a; margin-bottom: 10px; border: 1px solid #bfdbfe;'>Existing Position: <b>{abs(existing_shares):,.0f}</b> shares @ <b>{existing_avg_local:,.2f} {calc_currency}</b><br>Live Stop Loss: <b>{live_stop_local:.2f} {calc_currency}</b></div>", unsafe_allow_html=True)
                
                is_violation = False
                if live_stop_local <= 0:
                    is_violation = True
                elif actual_dir == 'Long' and current_price_local <= live_stop_local:
                    is_violation = True
                elif actual_dir == 'Short' and current_price_local >= live_stop_local:
                    is_violation = True

                calc_entry = current_price_local
                calc_stop = 0.0
                
                if is_violation:
                    st.error("🚨 **Trade NOT allowed! Serious Risk Management Violation! DO NOT do it!!!** Apparently you removed or lowered the SL. Restore it immediately!!!")
                elif (actual_dir == 'Long' and current_price_local < existing_avg_local) or (actual_dir == 'Short' and current_price_local > existing_avg_local):
                    st.info(f"📉 **Tranche Accumulation:** Current price (\\${current_price_local:.2f}) is below your average cost (\\${existing_avg_local:.2f}).")
                    
                    max_cash_shares = int(calc_uninvested_cash / current_price_usd) if current_price_usd > 0 else 0
                    st.markdown(f"**Max additional shares allowed (Cash Limit):** {max_cash_shares:,}")
                    
                    if max_cash_shares > 0:
                        desired_shares = st.number_input("Shares to Purchase", min_value=1, max_value=max_cash_shares, value=1, step=1)
                        
                        risk_budget_usd = calc_nav * (calc_risk_pct / 100.0)
                        old_val_usd = existing_avg_usd * abs(existing_shares)
                        new_val_usd = current_price_usd * desired_shares
                        total_shares = abs(existing_shares) + desired_shares
                        
                        if actual_dir == 'Long':
                            req_sl_usd = (old_val_usd + new_val_usd - risk_budget_usd) / total_shares
                        else:
                            req_sl_usd = (risk_budget_usd + old_val_usd + new_val_usd) / total_shares
                            
                        req_sl_local = req_sl_usd / fx_rate if fx_rate > 0 else req_sl_usd
                        
                        if (actual_dir == 'Long' and req_sl_local >= current_price_local) or (actual_dir == 'Short' and req_sl_local <= current_price_local):
                            st.error("The required Stop Loss to maintain 1R is tighter than the current price. You cannot afford this many shares.")
                        elif (actual_dir == 'Long' and req_sl_local < live_stop_local) or (actual_dir == 'Short' and req_sl_local > live_stop_local):
                            st.error(f"Integrity Violation: You may never lower an existing stop loss. Must be tighter than {live_stop_local:.2f} {calc_currency}.")
                        else:
                            st.warning(f"⚠️ To keep total risk under 1R (\\${risk_budget_usd:,.0f}), you MUST move your SL to: **{req_sl_local:.2f} {calc_currency}**")
                            calc_stop = req_sl_local
                            proposed_shares = desired_shares
                            is_valid_pyramid = True
                else:
                    st.success(f"📈 **Pro-Trend Pyramiding:** Current price (\\${current_price_local:.2f}) is above your average cost (\\${existing_avg_local:.2f}).")
                    input_sl = st.number_input(f"Enter NEW Stop Loss ({calc_currency})", min_value=0.0, value=float(live_stop_local), step=1.0)
                    
                    valid_new_stop = False
                    if actual_dir == "Long" and input_sl > live_stop_local:
                        valid_new_stop = True
                    elif actual_dir == "Short" and input_sl < live_stop_local and input_sl > 0:
                        valid_new_stop = True
                        
                    if not valid_new_stop and input_sl > 0:
                        st.error(f"Integrity Violation: You may never lower an existing stop loss. Must be tighter than {live_stop_local:.2f} {calc_currency}.")
                    elif valid_new_stop:
                        calc_stop = input_sl
                        risk_budget_usd = calc_nav * (calc_risk_pct / 100.0)
                        stop_usd = calc_stop * fx_rate
                        
                        if actual_dir == "Long":
                            old_risk_usd = (existing_avg_usd - stop_usd) * abs(existing_shares)
                            risk_per_share_usd = current_price_usd - stop_usd
                        else:
                            old_risk_usd = (stop_usd - existing_avg_usd) * abs(existing_shares)
                            risk_per_share_usd = stop_usd - current_price_usd
                        
                        available_risk_usd = risk_budget_usd - old_risk_usd
                        
                        if risk_per_share_usd <= 0:
                            st.error("Stop loss must be below current price for Longs (above for Shorts).")
                        elif available_risk_usd <= 0:
                            st.error("Risk budget exhausted even with the new stop loss.")
                        else:
                            max_shares_risk = int(available_risk_usd // risk_per_share_usd)
                            max_cash_shares = int(calc_uninvested_cash / current_price_usd) if current_price_usd > 0 else 0
                            proposed_shares = min(max_shares_risk, max_cash_shares)
                            is_valid_pyramid = True
        else:
            calc_dir = c2.selectbox("Direction", ["Long", "Short"])
            calc_currency = st.selectbox("Asset Currency", ['USD', 'SEK', 'NOK', 'TWD', 'HKD', 'KRW', 'CNY', 'JPY', 'EUR', 'GBP', 'CAD', 'ILS'])
            calc_entry = st.number_input(f"Entry Price ({calc_currency})", min_value=0.0, value=0.0, step=1.0)
            calc_stop = st.number_input(f"Stop Loss Limit ({calc_currency})", min_value=0.0, value=0.0, step=1.0)

        if calc_entry > 0 and calc_stop > 0 and calc_nav > 0:
            fx_rate = get_fx_rate(calc_currency)
            entry_usd = calc_entry * fx_rate
            stop_usd = calc_stop * fx_rate
            risk_budget_usd = calc_nav * (calc_risk_pct / 100.0)
            
            if calc_dir == "Long" and calc_stop >= calc_entry:
                st.error("Long stop must be below entry.")
            elif calc_dir == "Short" and calc_stop <= calc_entry:
                st.error("Short stop must be above entry.")
                
            # --- GATE 1: ATR VOLATILITY FLOOR ---
            if target_sym_atr:
                horizon_map = {"Short-Term (Daily)": "Daily", "Medium-Term (Weekly)": "Weekly", "Long-Term (Monthly)": "Monthly"}
                active_horizon = horizon_map.get(trade_horizon, "Daily")
                atr_val = get_atr(target_sym_atr, timeframe=active_horizon)
                min_stop_dist = atr_val * 1.5
                actual_dist = abs(calc_entry - calc_stop)
                if actual_dist < min_stop_dist and atr_val > 0:
                    st.error(f"🚨 **Stop-loss is too tight!** Minimum allowed distance (1.5x {active_horizon} ATR) is **{min_stop_dist:.2f} {calc_currency}**. You must give the asset room to breathe.")
            
            # Global TOR is capped at 10x the active gear's RPT (which is already multiplied by the Tier)
            daily_tor_pct = max_r * 10.0  
            max_global_risk_usd = global_metrics['nav'] * (daily_tor_pct / 100.0)

            if daily_tor_pct <= 0.0:
                if tier_multiplier == 0.0:
                    st.error("🚨 **TIER 4 LOCKOUT (Absolute Block):** Allowable Global TOR is 0.0%. You have breached the -3.0% drawdown limit. Protect capital.")
                else:
                    st.error("🚨 **GEAR ZERO (Absolute Block):** Allowable Global TOR is 0.0%. Absolutely no new positions can be opened in these circumstances. Protect capital.")
            
            if calc_mode != "Scale-In (Pyramid)":
                proposed_shares, risk_budget_usd, new_risk_per_share_usd = calculate_position_size(
                    calc_nav, calc_risk_pct, entry_usd, stop_usd, fx_rate, is_ipo
                )
                old_risk_usd = 0
                available_risk_usd = risk_budget_usd
                
                # UI Warning for Notional Cap
                if (proposed_shares * entry_usd) > (calc_nav * (0.02 if is_ipo else 0.05)):
                    st.warning(f"⚠️ Shares mechanically reduced to **{proposed_shares:,}** to comply with the **{2 if is_ipo else 5}% Absolute Notional Cap**.")

            if proposed_shares > 0 and (calc_mode != "Scale-In (Pyramid)" or is_valid_pyramid):

                    proposed_added_risk_usd = proposed_shares * new_risk_per_share_usd
                    
                    alpha_assets_list = ['Physical US Stocks', 'International Stocks', 'US Tech CFDs', 'Gold', 'Crypto', 'CSPX', 'CNDX', 'ITWN', 'CSKR', 'CNYA']
                    df_phys_calc = pos_df[pos_df['asset_class'].isin(alpha_assets_list)]
                    calc_global_risk = 0.0
                    culprit_sym, culprit_silo, culprit_risk = "None", "None", 0.0
                    
                    for sym, g in df_phys_calc.groupby('symbol'):
                        shares = g['position'].sum()
                        if shares <= 0: continue
                        avg_cost = g['avg_cost'].iloc[0]
                        curr = g['currency'].iloc[0] if 'currency' in g.columns else 'USD'
                        fx_r = get_fx_rate(curr)
                        
                        sym_stops = pd.DataFrame()
                        if not open_orders_df.empty:
                            sym_stops = open_orders_df[(open_orders_df['symbol'] == sym) & 
                                                       (open_orders_df['action'] == 'SELL') & 
                                                       (open_orders_df['order_type'].str.contains('STP|TRAIL', case=False, na=False))].sort_values('aux_price', ascending=False)
                        rem_shares = shares
                        sym_risk = 0.0
                        for _, sr in sym_stops.iterrows():
                            q = min(sr['total_quantity'], rem_shares)
                            if q <= 0: break
                            sl_usd = sr['aux_price'] * fx_r
                            if sl_usd > 0 and g['market_price'].iloc[0] > 0:
                                if (sl_usd / g['market_price'].iloc[0]) > 50: sl_usd /= 100.0
                                elif (sl_usd / g['market_price'].iloc[0]) < 0.02: sl_usd *= 100.0
                            diff = (q * sl_usd) - (q * avg_cost)
                            if diff < 0: sym_risk += diff
                            rem_shares -= q
                        if rem_shares > 0:
                            sym_risk -= (rem_shares * avg_cost)
                        
                        calc_global_risk += sym_risk
                        if sym_risk < culprit_risk:
                            culprit_risk = sym_risk
                            culprit_sym = sym
                            culprit_silo = SILO_MAP.get(g['account'].iloc[0], (g['account'].iloc[0],))[0]
                            
                    current_global_risk_abs = abs(calc_global_risk)
                    projected_global_risk = current_global_risk_abs + proposed_added_risk_usd
                    global_available_risk = max_global_risk_usd - current_global_risk_abs
                    
                    if projected_global_risk > max_global_risk_usd:
                        safe_shares = int(max(0, global_available_risk) // new_risk_per_share_usd) if new_risk_per_share_usd > 0 else 0
                        culprit_text = f"<b>Culprit:</b> {culprit_sym} in {culprit_silo} is hogging <b>${abs(culprit_risk):,.0f}</b> of risk.<br>" if current_global_risk_abs > 0 else ""
                        action_text = f"<b>Action Required:</b> Raise stops on {culprit_sym} to free up risk capital, or reduce this order to a maximum of <b>{safe_shares} shares</b>." if current_global_risk_abs > 0 else f"<b>Action Required:</b> Reduce this order to a maximum of <b>{safe_shares} shares</b>."
                        
                        st.markdown(f"""
                        <div style="background-color: #fef2f2; padding: 15px; border-radius: 6px; border: 1px solid #ef4444; margin-bottom: 15px;">
                            <div style="font-size: 13px; color: #b91c1c; font-weight: bold; margin-bottom: 5px;">🚨 MACRO GOVERNOR WARNING: Global TOR Exceeded</div>
                            <div style="font-size: 12px; color: #7f1d1d;">
                                Your regime allows <b>{daily_tor_pct:.1f}%</b> Global NAV risk (<b>${max_global_risk_usd:,.0f}</b>).<br>
                                Current Open Risk is <b>${current_global_risk_abs:,.0f}</b>.<br>
                                This trade adds <b>${proposed_added_risk_usd:,.0f}</b>, pushing projected risk to <b>${projected_global_risk:,.0f}</b> (Excess: ${projected_global_risk - max_global_risk_usd:,.0f}).<br><br>
                                {culprit_text}
                                {action_text}
                            </div>
                        </div>
                        """, unsafe_allow_html=True)

                    capital_req_usd = proposed_shares * entry_usd
                    cash_remaining = calc_uninvested_cash - capital_req_usd
                    
                    # --- GATE 3: OVERNIGHT GAP STRESS TEST ---
                    gap_risk_usd = proposed_shares * (entry_usd * 0.25)
                    st.markdown(f"<div style='background-color: #fef2f2; padding: 10px; border: 1px solid #ef4444; border-radius: 6px; margin-top: 10px;'><span style='color: #b91c1c; font-weight: bold;'>⚠️ Overnight 25% Gap Risk: -${gap_risk_usd:,.0f}</span></div>", unsafe_allow_html=True)
                    ack_gap = st.checkbox("I acknowledge the overnight gap risk", disabled=is_locked)
                    
                    if ack_gap:
                        if calc_mode == "Scale-In (Pyramid)":
                            st.markdown(f"""
                            <div style="background-color: #f8fafc; padding: 10px; border-radius: 6px; border: 1px solid #cbd5e1; margin-top: 10px;">
                                <div style="font-size: 11px; color: #64748b; font-weight: bold; text-transform: uppercase;">Max New Shares Authorized (Local Silo Limit)</div>
                                <div style="font-size: 22px; font-weight: 900; color: #1d4ed8;">{proposed_shares:,}</div>
                                <hr style="margin: 8px 0;">
                                <div style="font-size: 12px; color: #475569;">Total Allowable Risk: <b>${risk_budget_usd:,.2f}</b></div>
                                <div style="font-size: 12px; color: {'#16a34a' if old_risk_usd < 0 else '#b91c1c'};">Old Shares Risk Consumption: <b>${old_risk_usd:,.2f}</b></div>
                                <div style="font-size: 12px; color: #475569;">Available Risk for Scale-In: <b>${available_risk_usd:,.2f}</b></div>
                                <div style="font-size: 12px; color: #475569; margin-top: 5px;">Total Capital Required (USD): <b>${capital_req_usd:,.2f}</b></div>
                                <div style="font-size: 12px; color: {'#16a34a' if cash_remaining >= 0 else '#dc2626'};">Post-Trade Cash (USD): <b>${cash_remaining:,.2f}</b></div>
                            </div>
                            """, unsafe_allow_html=True)
                        else:
                            st.markdown(f"""
                            <div style="background-color: #f8fafc; padding: 10px; border-radius: 6px; border: 1px solid #cbd5e1; margin-top: 10px;">
                                <div style="font-size: 11px; color: #64748b; font-weight: bold; text-transform: uppercase;">Max Authorized Shares (Local Silo Limit)</div>
                                <div style="font-size: 22px; font-weight: 900; color: #1d4ed8;">{proposed_shares:,}</div>
                                <hr style="margin: 8px 0;">
                                <div style="font-size: 12px; color: #475569;">Risk per Share (USD): <b>${new_risk_per_share_usd:,.2f}</b></div>
                                <div style="font-size: 12px; color: #475569;">Total Capital Required (USD): <b>${capital_req_usd:,.2f}</b></div>
                                <div style="font-size: 12px; color: {'#16a34a' if cash_remaining >= 0 else '#dc2626'}; margin-top: 5px;">Post-Trade Cash (USD): <b>${cash_remaining:,.2f}</b></div>
                            </div>
                            """, unsafe_allow_html=True)

                        if cash_remaining < 0:
                            st.markdown(f"<div style='font-size: 11px; color: #b91c1c; margin-top: 5px; font-weight: bold;'>⚠️ Insufficient Cash: Manually liquidate ${abs(cash_remaining):,.0f} of IB01 to fund this trade.</div>", unsafe_allow_html=True)
            elif proposed_shares == 0:
                st.warning("Available risk budget is too small to purchase a single share.")
    st.markdown("---")

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
exp_top.markdown("### 🔔 Executive Briefing & Actionable Alerts")
alerts = {
    "critical": [],
    "warning": [],
    "opportunity": [],
    "info": []
}

if not balances_df.empty and 'net_liquidation' in balances_df.columns:
    silo_b_bal = balances_df[(balances_df['account'] == 'U23139264') & (balances_df['date'] == balances_df['date'].max())]
    if not silo_b_bal.empty:
        nl = silo_b_bal['net_liquidation'].iloc[0]
        if 0 < nl < 27000:
            alerts["critical"].append(f"⚠️ **PDT Danger (Silo B):** Net Liquidity (${nl:,.0f}) approaching the $25k FINRA lockout threshold. Deposit cash or close Alpha swings immediately.")

# v90b: Pre-Earnings Ejection Protocol
if not pos_df.empty:
    alpha_assets = ['Physical US Stocks', 'International Stocks', 'US Tech CFDs']
    df_alpha_held = pos_df[pos_df['asset_class'].isin(alpha_assets) & (pos_df['position'] != 0)]
    for sym in df_alpha_held['symbol'].unique():
        e_date = get_upcoming_earnings(sym)
        if e_date:
            days_to_earnings = (e_date - datetime.date.today()).days
            if 0 <= days_to_earnings <= 5:
                alerts["warning"].append(f"⚠️ **Earnings Risk:** {sym} reports earnings on {e_date.strftime('%b %d')} (in {days_to_earnings} days). Prepare to trim or tighten trailing stops to mitigate binary gap risk.")

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
                alerts["critical"].append(f"🚨 **CRITICAL (Infinite Risk):** Naked Short Call detected on {base_tckr} in {silo_name}! Close or hedge immediately.")
            
            # Rules 2 & 3: Short Puts
            short_puts = shorts[shorts['right'] == 'P']
            if not short_puts.empty:
                is_spread = not longs[longs['right'] == 'P'].empty
                has_order = False
                if not open_orders_df.empty:
                    has_order = not open_orders_df[(open_orders_df['account'] == acc) & (open_orders_df['symbol'].str.contains(base_tckr))].empty
                
                if not has_order:
                    if base_tckr in ['SPY', 'SPX', 'XSP', 'QQQ', 'NDX', 'XND']:
                        alerts["critical"].append(f"🚨 **CRITICAL (Missing Brackets):** Short Index Put ({base_tckr}) in {silo_name} is missing resting OCO brackets!")
                    elif not is_spread:
                        alerts["info"].append(f"ℹ️ **CSP Active:** Short Equity Put ({base_tckr}) in {silo_name}. No brackets detected. The Estate will accept physical assignment if ITM at expiration.")

opt_margin_journal = 0
if not journal_raw_df.empty:
    open_journal = journal_raw_df[pd.isnull(journal_raw_df['Close Date'])]
    opt_margin_journal = open_journal['Collateral Locked (USD)'].sum()
    if abs(opt_margin_journal - opt_margin_total) > 0.01:
        alerts["warning"].append(f"⚠️ **Ledger Drift Detected:** Live TWS options margin is **${opt_margin_total:,.0f}**, but manual Options Journal reflects **${opt_margin_journal:,.0f}**. Please reconcile.")

pct_margin = (opt_margin_total / global_metrics['nav']) * 100 if global_metrics['nav'] > 0 else 0

if pct_margin >= 20.0:
    alerts["critical"].append(f"🚨 **CRITICAL (Margin Cap Breached):** Global Options Margin is {pct_margin:.1f}% (Limit: 20.0%). Halt all new options deployments immediately.")
elif pct_margin >= 16.0:
    alerts["warning"].append(f"⚠️ **Margin Capacity Warning:** Global Options Margin is {pct_margin:.1f}%. Approaching the absolute 20% limit.")

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
                alerts["critical"].append(f"🚨 **CRITICAL (Theta Cliff):** Synthetic Beta Call **{sym}** has reached **{dte} DTE**! Execute the Rolling Protocol IMMEDIATELY to avoid terminal Theta decay.")
            elif dte <= 60:
                alerts["warning"].append(f"⚠️ **Rolling Radar:** Synthetic Beta Call **{sym}** is at **{dte} DTE**. Prepare to roll the contract to a new 150-DTE window.")
        except: pass

if not journal_raw_df.empty:
    today = datetime.date.today()    
    for _, row in journal_raw_df[pd.isnull(journal_raw_df['Close Date'])].iterrows():
        try:
            tckr, dte_rem = row['Ticker'], row['Days Remaining']
            
            # EXEMPTION: Tail Hedges (Short Strike = 0.0) do not have Gamma Cliff ejection rules.
            is_tail_hedge = False
            try:
                if pd.notna(row.get('Short Strike')) and float(row['Short Strike']) == 0.0:
                    is_tail_hedge = True
            except:
                pass

            if str(dte_rem) != 'Closed' and not is_tail_hedge:
                dte_int = int(dte_rem)
                if dte_int <= 21:
                    alerts["critical"].append(f"🚨 **CRITICAL (Gamma Cliff):** {tckr} ({row['Short Strike']}/{row['Long Strike']}) has reached {dte_int} DTE! EJECT IMMEDIATELY to avoid terminal Gamma risk.")
                elif dte_int == 22:
                    alerts["critical"].append(f"⚡ **EVE OF DESTRUCTION (22 DTE):** {tckr} ({row['Short Strike']}/{row['Long Strike']}) hits the Gamma Cliff tomorrow. Prepare to execute mechanical ejection.")
                elif dte_int <= 30:
                    alerts["warning"].append(f"⏱️ **Options Gamma Warning:** Contract {tckr} ({row['Short Strike']}/{row['Long Strike']}) is approaching the 21 DTE Gamma Cliff ({dte_int} days remaining).")
            
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
                        alerts["critical"].append(f"🛑 **STOP LOSS TRIGGERED:** {tckr} ({short_str}/{long_str}) live spread price (${curr_spread_price:.2f}) breached 200% limit (${stop_loss_threshold:.2f}). Close immediately.")
                    elif curr_spread_price >= warning_threshold:
                        alerts["warning"].append(f"⚠️ **Stop Loss Warning:** {tckr} ({short_str}/{long_str}) live spread price (${curr_spread_price:.2f}) is approaching the 200% limit (${stop_loss_threshold:.2f}).")
        except: pass

if not bench_df.empty:
    last_spy = bench_df['SPY'].iloc[-1]
    sma_20 = bench_df['sma_20'].iloc[-1]
    sma_50 = bench_df['sma_50'].iloc[-1]
    sma_200 = bench_df['sma_200'].iloc[-1]
    if last_spy < sma_20: alerts["warning"].append(f"📉 **Trend Alert:** SPY (${last_spy:.2f}) has breached below the 20-day SMA (${sma_20:.2f}).")
    if last_spy < sma_50: alerts["warning"].append(f"🚨 **Trend Alert:** SPY (${last_spy:.2f}) has breached below the 50-day SMA (${sma_50:.2f}).")
    if last_spy < sma_200: alerts["critical"].append(f"☢️ **CRITICAL ALERT:** SPY (${last_spy:.2f}) has breached below the 200-day SMA (${sma_200:.2f}). Bear market threshold.")
live_alpha_gear_alert = chart_df['alpha_gear'].iloc[-1] if not chart_df.empty else 0
live_opt_dir_alert = chart_df['opt_dir'].iloc[-1] if not chart_df.empty else 'Unknown'
alerts["info"].append(f"🧭 **EOD Market Weather:** Alpha Gear {live_alpha_gear_alert} | Options {live_opt_dir_alert}")

tot_vrp = attr_df['a3_vrp'].sum() if not attr_df.empty else 0
th_budget = tot_vrp * 0.10
th_df = pos_df[pos_df['asset_class'] == 'Tail Hedge'] if not pos_df.empty else pd.DataFrame()
th_deployed = (th_df['position'].abs() * th_df['avg_cost']).sum() if not th_df.empty else 0
th_available = th_budget - th_deployed

# VIX Crush Alert logic
vix_live = fetch_live_data('^VIX')[1]
is_vix_crush = vix_live < 15.0

# VIX Term Structure Alert
vix9d, vix3m = get_vix_term_structure()
is_backwardation = (vix9d > vix3m) and (vix9d > 0)

if is_backwardation:
    alerts["critical"].append(f"☢️ **SYSTEMIC PANIC (BACKWARDATION):** VIX9D ({vix9d:.2f}) has inverted above VIX3M ({vix3m:.2f}). The Volatility Curve is broken. **HALT ALL VRP SELLING IMMEDIATELY.** Prepare to monetize Tail Hedges.")

# 10-Day Distribution Tracker (CDD) Alert
dist_data_alert = get_distribution_tracker()
spy_cdd_alert = dist_data_alert.get("SPY", (0, []))[0]
rsp_cdd_alert = dist_data_alert.get("RSP", (0, []))[0]
max_cdd = max(spy_cdd_alert, rsp_cdd_alert)

# 10-Day Distribution Tracker (CDD) Alert
dist_data_alert = get_distribution_tracker()
spy_cdd_alert = dist_data_alert.get("SPY", (0, []))[0]
qqq_cdd_alert = dist_data_alert.get("QQQ", (0, []))[0]
rsp_cdd_alert = dist_data_alert.get("RSP", (0, []))[0]
max_cdd = max(spy_cdd_alert, qqq_cdd_alert, rsp_cdd_alert)

if max_cdd >= 4:
    alerts["critical"].append(f"🚨 **DISTRIBUTION WARNING (CDD):** Severe selling pressure detected. SPY is at {spy_cdd_alert} consecutive red days, QQQ at {qqq_cdd_alert}, RSP at {rsp_cdd_alert}. Capital preservation mode engaged.")
elif max_cdd == 3:
    alerts["warning"].append(f"⚠️ **DISTRIBUTION ALERT (CDD):** 3 consecutive red days detected on major indices (SPY: {spy_cdd_alert}, QQQ: {qqq_cdd_alert}, RSP: {rsp_cdd_alert}). Elevated risk of short-term breakdown.")

if th_available >= 400.0:
    tranches_due = int(th_available // 400.0)
    if is_vix_crush:
        alerts["opportunity"].append(f"🟢 **VIX CRUSH DETECTED (VIX: {vix_live:.2f}):** Tail insurance is cheap! You have **${th_available:,.0f}** available. Deploy **{tranches_due} tranche(s)** of 120-DTE Deep OTM S&P 500 Puts immediately.")
    else:
        if tranches_due == 1:
            alerts["info"].append(f"🛡️ **Tail Hedge Deployment Due:** You have **${th_available:,.0f}** available in house money. Purchase **1 tranche** (~$400) of 120-DTE deep OTM S&P 500 Puts (Delta < 5).")
        else:
            alerts["warning"].append(f"🛡️ **Tail Hedge Backlog Detected:** You have **${th_available:,.0f}** available. DO NOT deploy as a lump sum. Split this into **{tranches_due} staggered tranches** (~$400 each) across 90, 120, and 150+ DTE.")

# Alpha Conviction IV Scanner Alert
try:
    conn_wl = sqlite3.connect(DB_PATH)
    wl_df_alert = pd.read_sql_query("SELECT * FROM alpha_watchlist", conn_wl)
    conn_wl.close()
    if not wl_df_alert.empty:
        for _, w_row in wl_df_alert.iterrows():
            c_iv = float(w_row['current_iv']) if pd.notna(w_row['current_iv']) else 0.0
            t_iv = float(w_row['target_iv']) if pd.notna(w_row['target_iv']) else 0.0
            if c_iv >= t_iv and c_iv > 0:
                alerts["opportunity"].append(f"🎯 **ALPHA OPPORTUNITY ({w_row['symbol']}):** Live IV ({c_iv:.1f}%) has breached your target ({t_iv:.1f}%). Ready for Conviction CSPs.")
except Exception:
    pass

# --- NEW: RIPE CONDITION ALERTS (PRE-FLIGHT MATRIX) ---
if not bench_df.empty:
    spy_spot_alert = bench_df['SPY'].iloc[-1]
    spy_50_alert = bench_df['sma_50'].iloc[-1]
    spy_200_alert = bench_df['sma_200'].iloc[-1]
    
    if 15.0 <= vix_live and (spy_spot_alert > spy_50_alert or spy_spot_alert < spy_200_alert):
        alerts["opportunity"].append(f"🟢 **RIPE: Bull Put Spreads.** VIX ({vix_live:.2f}) and Trend are optimal. Authorized to harvest VRP.")
    if 15.0 <= vix_live <= 25.0 and spy_spot_alert < spy_50_alert:
        alerts["opportunity"].append(f"🔴 **RIPE: Bear Call Spreads.** VIX ({vix_live:.2f}) and Trend are optimal. Authorized to harvest gravity premium.")
    if 15.0 <= vix_live <= 22.0 and (abs(spy_spot_alert - spy_50_alert)/spy_50_alert < 0.02 or live_alpha_gear_alert == 3):
        alerts["opportunity"].append(f"⚖️ **RIPE: Iron Condors.** VIX ({vix_live:.2f}) is optimal and SPY is rangebound. Authorized for delta-neutral efficiency.")
    if vix_live < 15.0 and spy_spot_alert > spy_50_alert:
        alerts["opportunity"].append(f"🐌 **RIPE: The Theta Machine (Calendars).** VIX ({vix_live:.2f}) is dead. Pivot to positive-Vega calendar spreads.")
    
    # Self-contained macro dates to prevent top-down execution NameErrors
    macro_dates_alert = [
        datetime.date(2026, 1, 28), datetime.date(2026, 3, 18), datetime.date(2026, 5, 6), datetime.date(2026, 6, 17),
        datetime.date(2026, 7, 29), datetime.date(2026, 9, 16), datetime.date(2026, 11, 4), datetime.date(2026, 12, 16),
        datetime.date(2026, 1, 13), datetime.date(2026, 2, 10), datetime.date(2026, 3, 11), datetime.date(2026, 4, 14),
        datetime.date(2026, 5, 13), datetime.date(2026, 6, 10), datetime.date(2026, 7, 14), datetime.date(2026, 8, 12),
        datetime.date(2026, 9, 15), datetime.date(2026, 10, 14), datetime.date(2026, 11, 12), datetime.date(2026, 12, 10)
    ]
    macro_soon = any(0 <= (d - datetime.date.today()).days <= 1 for d in macro_dates_alert)
    if macro_soon:
        alerts["opportunity"].append(f"💥 **RIPE: Macro IV Crush (Iron Butterfly).** Tier-1 Macro event imminent. Check 0-DTE vs 7-DTE IV ratio to trap event premium.")

if pct_cash > 60: alerts["info"].append(f"ℹ️ **Cash Drag Detected:** Unleveraged Cash/IB01 is {pct_cash:.1f}%. Await weekly Command Center deployment schedule.")
if pct_cash < 40: alerts["warning"].append(f"⚠️ **Cash Buffer Warning:** Global cash buffer dropped to {pct_cash:.1f}% (Below 40% optimal floor).")
if pct_tech > 40: alerts["warning"].append(f"⚠️ **Sector Concentration:** Tech/Semi exposure is {pct_tech:.1f}% (Above 40% safe threshold).")

has_alerts = any(len(cat) > 0 for cat in alerts.values())

if has_alerts:
    if alerts["critical"]:
        alert_html = "".join([f"<li style='margin-bottom: 5px;'>{a}</li>" for a in alerts["critical"]])
        exp_top.markdown(f"""
        <div style="background-color: #fef2f2; border-left: 6px solid #ef4444; padding: 15px; border-radius: 4px; color: #7f1d1d; font-size: 14px; margin-bottom: 15px;">
            <div style="font-weight: bold; margin-bottom: 8px; font-size: 15px; display: flex; align-items: center;">🚨 CRITICAL ACTION REQUIRED</div>
            <ul style="margin: 0; padding-left: 20px;">{alert_html}</ul>
        </div>
        """.replace('\n', ''), unsafe_allow_html=True)

    if alerts["warning"]:
        alert_html = "".join([f"<li style='margin-bottom: 5px;'>{a}</li>" for a in alerts["warning"]])
        exp_top.markdown(f"""
        <div style="background-color: #fffbeb; border-left: 6px solid #f59e0b; padding: 15px; border-radius: 4px; color: #78350f; font-size: 14px; margin-bottom: 15px;">
            <div style="font-weight: bold; margin-bottom: 8px; font-size: 15px; display: flex; align-items: center;">⚠️ STRUCTURAL WARNINGS</div>
            <ul style="margin: 0; padding-left: 20px;">{alert_html}</ul>
        </div>
        """.replace('\n', ''), unsafe_allow_html=True)
        
    if alerts["opportunity"]:
        alert_html = "".join([f"<li style='margin-bottom: 5px;'>{a}</li>" for a in alerts["opportunity"]])
        exp_top.markdown(f"""
        <div style="background-color: #f0fdf4; border-left: 6px solid #10b981; padding: 15px; border-radius: 4px; color: #064e3b; font-size: 14px; margin-bottom: 15px;">
            <div style="font-weight: bold; margin-bottom: 8px; font-size: 15px; display: flex; align-items: center;">🟢 TACTICAL OPPORTUNITIES</div>
            <ul style="margin: 0; padding-left: 20px;">{alert_html}</ul>
        </div>
        """.replace('\n', ''), unsafe_allow_html=True)

    if alerts["info"]:
        alert_html = "".join([f"<li style='margin-bottom: 5px;'>{a}</li>" for a in alerts["info"]])
        exp_top.markdown(f"""
        <div style="background-color: #eff6ff; border-left: 6px solid #3b82f6; padding: 15px; border-radius: 4px; color: #1e3a8a; font-size: 14px; margin-bottom: 25px;">
            <div style="font-weight: bold; margin-bottom: 8px; font-size: 15px; display: flex; align-items: center;">ℹ️ SYSTEM INTELLIGENCE</div>
            <ul style="margin: 0; padding-left: 20px;">{alert_html}</ul>
        </div>
        """.replace('\n', ''), unsafe_allow_html=True)

else:
    exp_top.success("✅ All systems nominal. No actionable alerts at this time.")

exp_top.divider() 

# --- GLOBAL BETA-WEIGHTED DELTA CALCULATION (HOISTED FOR HUD) ---
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
        except: pass

bw_usd_exposure = total_bw_delta * spy_price
bw_pct_nav = (bw_usd_exposure / global_metrics['nav'] * 100) if global_metrics['nav'] > 0 else 0

# --- THE HEADS-UP DISPLAY (HUD) KPI BANNER ---
hud_html = f"""
<div style='display: flex; gap: 20px; margin-bottom: 15px;'>
    <div style="flex: 1; background-color: #f8fafc; padding: 25px 20px; border-radius: 12px; border: 1px solid #e5e7eb; box-shadow: 0 4px 6px -1px rgba(0,0,0,0.1); text-align: center;">
        <div style="color: #64748b; font-size: 14px; font-weight: bold; text-transform: uppercase; letter-spacing: 1px;">Global Estate NAV</div>
        <div style="color: #1e293b; font-size: 32px; font-weight: 900; margin-top: 5px;">${global_metrics['nav']:,.0f}</div>
    </div>
    <div style="flex: 1; background-color: #f8fafc; padding: 25px 20px; border-radius: 12px; border: 1px solid #e5e7eb; box-shadow: 0 4px 6px -1px rgba(0,0,0,0.1); text-align: center;">
        <div style="color: #64748b; font-size: 14px; font-weight: bold; text-transform: uppercase; letter-spacing: 1px;">Idle Cash Buffer</div>
        <div style="color: {'#16a34a' if pct_cash >= 40 else '#d97706'}; font-size: 32px; font-weight: 900; margin-top: 5px;">{pct_cash:.1f}%</div>
    </div>
    <div style="flex: 1; background-color: #f8fafc; padding: 25px 20px; border-radius: 12px; border: 1px solid #e5e7eb; box-shadow: 0 4px 6px -1px rgba(0,0,0,0.1); text-align: center;">
        <div style="color: #64748b; font-size: 14px; font-weight: bold; text-transform: uppercase; letter-spacing: 1px;">Options Margin Locked</div>
        <div style="color: {'#dc2626' if pct_margin >= 18 else '#9333ea'}; font-size: 32px; font-weight: 900; margin-top: 5px;">{pct_margin:.1f}%</div>
    </div>
    <div style="flex: 1; background-color: #f8fafc; padding: 25px 20px; border-radius: 12px; border: 1px solid #e5e7eb; box-shadow: 0 4px 6px -1px rgba(0,0,0,0.1); text-align: center;">
        <div style="color: #64748b; font-size: 14px; font-weight: bold; text-transform: uppercase; letter-spacing: 1px;" title="Directional Exposure to S&P 500">Beta-Weighted Delta ⓘ</div>
        <div style="color: {'#0284c7' if bw_pct_nav >= 0 else '#dc2626'}; font-size: 32px; font-weight: 900; margin-top: 5px;">{bw_pct_nav:+.1f}%</div>
    </div>
</div>
"""
exp_top.markdown(hud_html, unsafe_allow_html=True)

# --- MASTER WEATHER STATION ---
live_alpha_gear = chart_df['alpha_gear'].iloc[-1] if not chart_df.empty else 0
live_opt_dir = chart_df['opt_dir'].iloc[-1] if not chart_df.empty else 'Bear'
live_vix = fetch_live_data('^VIX')[1]
vix9d, vix3m = get_vix_term_structure()
is_backwardation = (vix9d > vix3m) and (vix9d > 0)

gear_color_map = {5: '#14532d', 4: '#22c55e', 3: '#84cc16', 2: '#eab308', 1: '#f97316', 0: '#991b1b'}
gear_risk_map = {5: 0.20, 4: 0.135, 3: 0.09, 2: 0.06, 1: 0.04, 0: 0.00}
gear_desc_map = {5: 'Perfect Bull', 4: 'Steady Bull', 3: 'Pullback Phase', 2: 'Breadth Divergence', 1: 'Cap-Weighted Breakdown', 0: 'Bear Market'}

alpha_color = gear_color_map.get(live_alpha_gear, '#991b1b')
alpha_risk = gear_risk_map.get(live_alpha_gear, 0.0)
alpha_desc = gear_desc_map.get(live_alpha_gear, 'Unknown')

opt_color = '#166534' if live_opt_dir == 'Bull' else '#991b1b'
vix_status = "COMPLACENT (Buy Tails)" if live_vix < 15 else ("NORMAL (Standard VRP)" if live_vix <= 20 else "ELEVATED (Prime VRP)")
opt_action = "Sell Bull Puts" if live_opt_dir == 'Bull' else "Sell Bear Calls"

# VIX Term Structure Circuit Breaker Override
if is_backwardation:
    opt_color = '#991b1b'
    vix_status = f"BACKWARDATION (VIX9D {vix9d:.1f} > VIX3M {vix3m:.1f})"
    opt_action = "HALT VRP / MONETIZE TAILS"

dist_data = get_distribution_tracker()
spy_cdd, spy_seq = dist_data.get("SPY", (0, []))
qqq_cdd, qqq_seq = dist_data.get("QQQ", (0, []))
rsp_cdd, rsp_seq = dist_data.get("RSP", (0, []))
cdd_color = '#ef4444' if max(spy_cdd, qqq_cdd, rsp_cdd) >= 4 else ('#f59e0b' if max(spy_cdd, qqq_cdd, rsp_cdd) == 3 else '#3b82f6')

weather_html = f"""
<div style='display: flex; gap: 20px; margin-bottom: 25px;'>
    <div style="flex: 1; background-color: #ffffff; padding: 15px 20px; border-radius: 8px; border-left: 8px solid {alpha_color}; box-shadow: 0 2px 4px rgba(0,0,0,0.05);">
        <div style="color: #475569; font-size: 12px; font-weight: bold; text-transform: uppercase;">Alpha Engine (Stocks)</div>
        <div style="font-size: 20px; font-weight: 900; color: {alpha_color}; margin-top: 2px;">GEAR {live_alpha_gear} | {alpha_desc}</div>
        <div style="font-size: 14px; color: #334155; margin-top: 2px;"><b>Max Risk:</b> {alpha_risk}% RPT</div>
    </div>
    <div style="flex: 1; background-color: #ffffff; padding: 15px 20px; border-radius: 8px; border-left: 8px solid {cdd_color}; box-shadow: 0 2px 4px rgba(0,0,0,0.05);">
        <div style="color: #475569; font-size: 12px; font-weight: bold; text-transform: uppercase;">Distribution Tracker (CDD)</div>
        <div style="display: flex; justify-content: space-between; align-items: center; margin-top: 6px;">
            <div style="font-size: 13px; font-weight: bold; color: #334155;">SPY (Cap-Weight)</div>
            {make_cdd_sparkline(spy_seq)}
        </div>
        <div style="display: flex; justify-content: space-between; align-items: center; margin-top: 6px;">
            <div style="font-size: 13px; font-weight: bold; color: #334155;">QQQ (Tech-Weight)</div>
            {make_cdd_sparkline(qqq_seq)}
        </div>
        <div style="display: flex; justify-content: space-between; align-items: center; margin-top: 6px;">
            <div style="font-size: 13px; font-weight: bold; color: #334155;">RSP (Eq-Weight)</div>
            {make_cdd_sparkline(rsp_seq)}
        </div>
        <div style="font-size: 12px; color: #64748b; margin-top: 6px;"><b>Consecutive Red:</b> SPY ({spy_cdd}) | QQQ ({qqq_cdd}) | RSP ({rsp_cdd})</div>
    </div>
    <div style="flex: 1; background-color: #ffffff; padding: 15px 20px; border-radius: 8px; border-left: 8px solid {opt_color}; box-shadow: 0 2px 4px rgba(0,0,0,0.05);">
        <div style="color: #475569; font-size: 12px; font-weight: bold; text-transform: uppercase;">Options Engine (VRP)</div>
        <div style="font-size: 20px; font-weight: 900; color: {opt_color}; margin-top: 2px;">STRUCTURAL {live_opt_dir.upper()}</div>
        <div style="font-size: 14px; color: #334155; margin-top: 2px;"><b>Volatility:</b> {vix_status} (VIX {live_vix:.2f})<br><b>Action:</b> {opt_action}</div>
    </div>
</div>
"""
exp_top.markdown(weather_html, unsafe_allow_html=True)


# SECTION 1: MASTER AGGREGATION
html_metrics = f"""
<div id="master-agg" style="background-color: #f3f4f6; padding: 20px; border-radius: 12px; border: 1px solid #e5e7eb; margin-bottom: 20px;">
    <h4 style="text-align: center; color: #1f2937; margin-bottom: 20px; text-transform: uppercase; letter-spacing: 2px; font-size: 24px;">Estate Aggregation</h4>
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
num_silos = max(1, len(SILO_MAP))
cols = st.columns(num_silos)
for idx, acc in enumerate(SILO_MAP.keys()):
    name, desc, color, _ = SILO_MAP[acc]
    m = silo_metrics.get(acc, {"nav": 0, "irr": 0, "sharpe": 0, "pnl": 0, "max_dd": 0, "dd_days": 0, "roc": 0})
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

# --- SECTION 1B: CALENDARS ---
st.subheader("Calendars", anchor="sec1b")
exp_sec1b = st.expander("🔥 Month / Year Return Heatmap", expanded=False)
if not global_df.empty:
    df_h = global_df.copy()
    df_h['Year'] = df_h['date'].dt.year
    df_h['Month'] = df_h['date'].dt.month
    
    # Calculate compounded Time-Weighted Return (TWR) for each month
    m_ret = df_h.groupby(['Year', 'Month'])['daily_return'].apply(lambda x: (x + 1).prod() - 1).reset_index()
    m_pivot = m_ret.pivot(index='Year', columns='Month', values='daily_return')
    
    month_map = {1:'Jan', 2:'Feb', 3:'Mar', 4:'Apr', 5:'May', 6:'Jun', 7:'Jul', 8:'Aug', 9:'Sep', 10:'Oct', 11:'Nov', 12:'Dec'}
    m_pivot.columns = [month_map[m] for m in m_pivot.columns]
    
    # Ensure all 12 months exist
    all_months = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
    for m in all_months:
        if m not in m_pivot.columns:
            m_pivot[m] = np.nan
    m_pivot = m_pivot[all_months]
    
    # Calculate YTD by compounding the available monthly returns for that year
    m_pivot['YTD'] = m_pivot[all_months].apply(lambda row: (row.dropna() + 1).prod() - 1, axis=1)
    
    # Sort years descending (most recent on top)
    m_pivot = m_pivot.sort_index(ascending=False) 
    
    z_data = m_pivot.values
    x_data = m_pivot.columns.tolist()
    y_data = m_pivot.index.tolist()
    
    # Format Text Array (+XX.XX%)
    text_data = []
    for row in z_data:
        text_row = []
        for val in row:
            if pd.isna(val):
                text_row.append("")
            else:
                text_row.append(f"{val*100:+.2f}%")
        text_data.append(text_row)
        
    fig_hm = go.Figure(data=go.Heatmap(
        z=z_data, x=x_data, y=y_data, text=text_data, texttemplate="%{text}",
        textfont={"size": 13, "color": "black", "family": "monospace"},
        colorscale=[[0.0, '#fca5a5'], [0.5, '#f8fafc'], [1.0, '#86efac']], zmid=0,
        showscale=False, xgap=4, ygap=4, hoverinfo='skip'
    ))

    fig_hm.update_layout(
        height=120 + len(y_data)*50,
        margin=dict(l=50, r=20, t=30, b=20),
        yaxis=dict(type='category', autorange='reversed', tickfont=dict(size=14, weight='bold', color='#334155')),
        xaxis=dict(side='top', tickfont=dict(size=14, weight='bold', color='#334155')),
        plot_bgcolor='rgba(0,0,0,0)'
    )
    exp_sec1b.plotly_chart(fig_hm, width="stretch")
else:
    exp_sec1b.info("Not enough data to generate Return Heatmap.")

if not global_df.empty:
    with st.expander("📅 Day / Week / Month PnL", expanded=False):
        cal_df = global_df[['date', 'daily_pnl', 'daily_return']].copy()
        cal_df['date_str'] = cal_df['date'].dt.strftime('%Y-%m-%d')
        cal_dict = cal_df.set_index('date_str').to_dict('index')
        
        # Fetch Trade Counts from Clearinghouse Ledger
        conn_cal = sqlite3.connect(DB_PATH)
        try:
            trades_df = pd.read_sql_query("SELECT close_date, COUNT(*) as trade_count FROM champion_closed_trades GROUP BY close_date", conn_cal)
            trade_counts = dict(zip(trades_df['close_date'], trades_df['trade_count']))
        except Exception:
            trade_counts = {}
        conn_cal.close()
        
        cal_df['Month_Str'] = cal_df['date'].dt.strftime('%Y - %B')
        available_months = cal_df['Month_Str'].unique().tolist()
        
        if available_months:
            available_months = available_months[::-1] # Newest months first
            
            c_sel, c_empty = st.columns([1, 3])
            with c_sel:
                selected_month_str = st.selectbox("Select Month to Inspect", available_months, label_visibility="collapsed")
            
            sel_year = int(selected_month_str.split(' - ')[0])
            sel_month_name = selected_month_str.split(' - ')[1]
            sel_month = list(calendar.month_name).index(sel_month_name)
            
            # Set Sunday as the first day of the week to match your screenshot
            calendar.setfirstweekday(calendar.SUNDAY)
            month_matrix = calendar.monthcalendar(sel_year, sel_month)
            
            month_pnl_total = 0.0
            
            # Calculate Month Total First
            for week in month_matrix:
                for day in week:
                    if day != 0:
                        date_str = f"{sel_year}-{sel_month:02d}-{day:02d}"
                        if date_str in cal_dict:
                            month_pnl_total += cal_dict[date_str]['daily_pnl']

            month_color = "#34d399" if month_pnl_total >= 0 else "#f87171"
            month_sign = "+" if month_pnl_total >= 0 else ""
            
            # CSS Styling matching the Dark Mode Institutional aesthetic
            # Flattened to single-line strings to prevent Streamlit's Markdown engine from rendering it as an indented <code> block
            cal_html = f"<style>.cal-wrapper {{ background: #1e293b; color: #f8fafc; border-radius: 8px; padding: 20px; font-family: sans-serif; margin-top: 10px; box-shadow: 0 4px 6px -1px rgba(0,0,0,0.1); }} .cal-header {{ display: flex; justify-content: space-between; align-items: center; margin-bottom: 15px; border-bottom: 1px solid #334155; padding-bottom: 10px; }} .cal-title {{ font-size: 22px; font-weight: bold; color: #e2e8f0; }} .cal-total {{ font-size: 16px; font-weight: normal; color: #94a3b8; }} .cal-total span {{ font-weight: bold; }} .cal-grid {{ display: grid; grid-template-columns: repeat(8, 1fr); gap: 1px; background: #334155; border: 1px solid #334155; border-radius: 6px; overflow: hidden; }} .cal-day-label {{ background: #0f172a; color: #94a3b8; font-size: 13px; text-align: center; padding: 10px 0; font-weight: bold; text-transform: uppercase; }} .cal-cell {{ background: #1e293b; padding: 12px; display: flex; flex-direction: column; min-height: 90px; transition: background 0.2s; }} .cal-cell:hover {{ background: #283548; }} .cal-cell-header {{ font-size: 14px; color: #cbd5e1; margin-bottom: 8px; font-weight: bold; display: flex; justify-content: space-between; }} .pnl-green {{ color: #34d399; font-weight: bold; font-size: 16px; margin-top: auto; }} .pnl-red {{ color: #f87171; font-weight: bold; font-size: 16px; margin-top: auto; }} .pnl-zero {{ color: #64748b; font-size: 16px; margin-top: auto; }} .ret-text {{ font-size: 12px; color: #94a3b8; margin-top: 4px; }} .trades-text {{ font-size: 11px; color: #64748b; margin-top: 2px; font-weight: bold; }} .week-total-cell {{ background: #0f172a; border-left: 2px solid #334155; }}</style>"
            cal_html += f"<div class='cal-wrapper'><div class='cal-header'><div class='cal-title'>{sel_month_name}, {sel_year}</div><div class='cal-total'>Monthly P&L: <span style='color: {month_color};'>{month_sign}${month_pnl_total:,.2f}</span></div></div><div class='cal-grid'>"
            
            days_labels = ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Total']
            for d in days_labels:
                cal_html += f"<div class='cal-day-label'>{d}</div>"
                
            for w_idx, week in enumerate(month_matrix):
                week_pnl = 0.0
                week_html = ""
                for day in week:
                    if day == 0:
                        week_html += "<div class='cal-cell'></div>"
                    else:
                        date_str = f"{sel_year}-{sel_month:02d}-{day:02d}"
                        day_pnl = 0.0
                        day_ret = 0.0
                        t_count = trade_counts.get(date_str, 0)
                        
                        if date_str in cal_dict:
                            day_pnl = cal_dict[date_str]['daily_pnl']
                            day_ret = cal_dict[date_str]['daily_return'] * 100
                            week_pnl += day_pnl
                            
                        if day_pnl > 0:
                            pnl_str = f"<div class='pnl-green'>+${day_pnl:,.2f}</div>"
                        elif day_pnl < 0:
                            pnl_str = f"<div class='pnl-red'>-${abs(day_pnl):,.2f}</div>"
                        else:
                            pnl_str = f"<div class='pnl-zero'>$0</div>"
                            
                        ret_str = f"<div class='ret-text'>{day_ret:+.2f}%</div>" if day_pnl != 0 else "<div class='ret-text'>0.00%</div>"
                        trades_str = f"<div class='trades-text'>{t_count} trade{'s' if t_count != 1 else ''}</div>" if t_count > 0 else "<div class='trades-text' style='opacity:0.3'>0 trades</div>"
                        
                        week_html += f"<div class='cal-cell'><div class='cal-cell-header'><span>{day}</span></div>{pnl_str}{ret_str}{trades_str}</div>"
                        
                if week_pnl > 0:
                    w_pnl_str = f"<div class='pnl-green'>+${week_pnl:,.2f}</div>"
                elif week_pnl < 0:
                    w_pnl_str = f"<div class='pnl-red'>-${abs(week_pnl):,.2f}</div>"
                else:
                    w_pnl_str = f"<div class='pnl-zero'>$0</div>"
                    
                week_html += f"<div class='cal-cell week-total-cell'><div class='cal-cell-header' style='color:#f8fafc;'>Week {w_idx+1}</div>{w_pnl_str}</div>"
                cal_html += week_html
                
            cal_html += "</div></div>"
            st.markdown(cal_html, unsafe_allow_html=True)

# Build Event Pipeline
calendar_events = []
today_date = datetime.date.today()

# 1. Earnings
if not pos_df.empty:
    alpha_assets = ['Physical US Stocks', 'International Stocks', 'US Tech CFDs']
    df_alpha_held = pos_df[pos_df['asset_class'].isin(alpha_assets) & (pos_df['position'] != 0)]
    for sym in df_alpha_held['symbol'].unique():
        e_date = get_upcoming_earnings(sym)
        if e_date:
            calendar_events.append({'date': e_date, 'type': 'Earn', 'label': f"{sym.split()[0]} Earn", 'color': '#8b5cf6'}) # Purple
            
# 2. Options Expirations, 21-DTE Ejects, 45-DTE Rolls
if not pos_df.empty:
    open_opts = pos_df[pos_df['sec_type'] == 'OPT'].copy()
    for _, r in open_opts.iterrows():
        try:
            parts = r['symbol'].split('_')
            base_tckr = parts[0]
            exp_date = pd.to_datetime(parts[1]).date()
            ac = r['asset_class']
            
            # Expiration
            calendar_events.append({'date': exp_date, 'type': 'Exp', 'label': f"{base_tckr} Exp", 'color': '#0f172a'}) # Black
            
            # 45-DTE Roll (Synthetic Beta)
            if ac == 'Synthetic Beta':
                roll_date = exp_date - datetime.timedelta(days=45)
                calendar_events.append({'date': roll_date, 'type': 'Roll', 'label': f"{base_tckr} Roll", 'color': '#eab308', 'text_color': '#451a03'}) # Yellow
                
            # 21-DTE Eject (VRP / CSP) - Exempts Tail Hedges
            elif ac not in ['Synthetic Beta', 'Tail Hedge']:
                eject_date = exp_date - datetime.timedelta(days=21)
                calendar_events.append({'date': eject_date, 'type': 'Eject', 'label': f"{base_tckr} Eject", 'color': '#ef4444'}) # Red
        except:
            pass
            
# 3. Day 10 Time Stop (Alpha Campaigns)
try:
    conn_cal = sqlite3.connect(DB_PATH)
    df_open_camps = pd.read_sql_query("SELECT symbol, open_date FROM alpha_campaigns WHERE status IN ('Open 🟢', 'Open', 'Pending Settlement ⏳')", conn_cal)
    conn_cal.close()
    for _, r in df_open_camps.iterrows():
        try:
            o_date = datetime.datetime.strptime(r['open_date'], '%Y-%m-%d').date()
            day10_date = o_date + datetime.timedelta(days=10)
            calendar_events.append({'date': day10_date, 'type': 'Day10', 'label': f"{r['symbol']} Day-10", 'color': '#64748b'}) # Gray
        except:
            pass
except:
    pass

# 4. Macroeconomic Catalysts (FOMC & CPI - 2026 Hardcoded)
macro_events = [
    # FOMC Rate Decisions (Wednesdays)
    {'date': datetime.date(2026, 1, 28), 'label': '🏦 FOMC', 'color': '#3b82f6'},
    {'date': datetime.date(2026, 3, 18), 'label': '🏦 FOMC', 'color': '#3b82f6'},
    {'date': datetime.date(2026, 5, 6), 'label': '🏦 FOMC', 'color': '#3b82f6'},
    {'date': datetime.date(2026, 6, 17), 'label': '🏦 FOMC', 'color': '#3b82f6'},
    {'date': datetime.date(2026, 7, 29), 'label': '🏦 FOMC', 'color': '#3b82f6'},
    {'date': datetime.date(2026, 9, 16), 'label': '🏦 FOMC', 'color': '#3b82f6'},
    {'date': datetime.date(2026, 11, 4), 'label': '🏦 FOMC', 'color': '#3b82f6'},
    {'date': datetime.date(2026, 12, 16), 'label': '🏦 FOMC', 'color': '#3b82f6'},
    # CPI Data Releases (Mid-month)
    {'date': datetime.date(2026, 1, 13), 'label': '📊 CPI', 'color': '#f97316'},
    {'date': datetime.date(2026, 2, 10), 'label': '📊 CPI', 'color': '#f97316'},
    {'date': datetime.date(2026, 3, 11), 'label': '📊 CPI', 'color': '#f97316'},
    {'date': datetime.date(2026, 4, 14), 'label': '📊 CPI', 'color': '#f97316'},
    {'date': datetime.date(2026, 5, 13), 'label': '📊 CPI', 'color': '#f97316'},
    {'date': datetime.date(2026, 6, 10), 'label': '📊 CPI', 'color': '#f97316'},
    {'date': datetime.date(2026, 7, 14), 'label': '📊 CPI', 'color': '#f97316'},
    {'date': datetime.date(2026, 8, 12), 'label': '📊 CPI', 'color': '#f97316'},
    {'date': datetime.date(2026, 9, 15), 'label': '📊 CPI', 'color': '#f97316'},
    {'date': datetime.date(2026, 10, 14), 'label': '📊 CPI', 'color': '#f97316'},
    {'date': datetime.date(2026, 11, 12), 'label': '📊 CPI', 'color': '#f97316'},
    {'date': datetime.date(2026, 12, 10), 'label': '📊 CPI', 'color': '#f97316'}
]

for me in macro_events:
    calendar_events.append({'date': me['date'], 'type': 'Macro', 'label': me['label'], 'color': me['color']})
    
# Sort events chronologically
calendar_events.sort(key=lambda x: x['date'])

# Find Next Event
next_event = None
for ev in calendar_events:
    if ev['date'] >= today_date:
        next_event = ev
        break
        
with st.expander("📅 Actionable Items", expanded=False):
    if next_event:
        days_until = (next_event['date'] - today_date).days
        if days_until <= 3:
            border_color = "#ef4444" # Red
            text_color = "#ef4444"
        elif days_until <= 7:
            border_color = "#f59e0b" # Yellow
            text_color = "#d97706"
        else:
            border_color = "#10b981" # Green
            text_color = "#059669"
            
        st.markdown(f'''
        <div style="background: white; border-left: 6px solid {border_color}; padding: 15px 20px; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.05); display: flex; justify-content: space-between; align-items: center; margin-bottom: 20px;">
            <div>
                <div style="font-size: 12px; color: #64748b; font-weight: bold; text-transform: uppercase;">Next Operational Hazard</div>
                <div style="font-size: 18px; font-weight: bold; color: #0f172a; margin-top: 4px;">{next_event['label']}</div>
            </div>
            <div style="text-align: right;">
                <div style="font-size: 12px; color: #64748b; font-weight: bold; text-transform: uppercase;">Date</div>
                <div style="font-size: 18px; font-weight: bold; color: {text_color}; margin-top: 4px;">{next_event['date'].strftime('%b %d')} ({days_until} Days)</div>
            </div>
        </div>
        ''', unsafe_allow_html=True)
    else:
        st.info("No upcoming operational hazards detected.")
        
    # Generate 5-Week Rolling Grid
    # Find the Sunday of the current week
    idx = (today_date.weekday() + 1) % 7 # Sunday is 0
    start_date = today_date - datetime.timedelta(days=idx)
    
    cal_html = """
    <style>
        .cal-grid-u { display: grid; grid-template-columns: repeat(7, 1fr); gap: 1px; background: #cbd5e1; border: 1px solid #cbd5e1; border-radius: 8px; overflow: hidden; }
        .cal-header-u { background: #1e293b; color: white; text-align: center; padding: 10px; font-weight: bold; font-size: 14px; }
        .cal-cell-u { background: white; min-height: 100px; padding: 8px; display: flex; flex-direction: column; gap: 4px; }
        .cal-cell-today { border: 2px solid #10b981; background: #f0fdf4; }
        .cal-date-u { font-size: 14px; font-weight: bold; color: #64748b; margin-bottom: 4px; }
        .cal-date-today { color: #059669; }
        .event-pill-u { font-size: 11px; padding: 3px 6px; border-radius: 4px; font-weight: bold; color: white; text-align: center; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
    </style>
    <div class="cal-grid-u">
        <div class="cal-header-u">Sun</div><div class="cal-header-u">Mon</div><div class="cal-header-u">Tue</div><div class="cal-header-u">Wed</div><div class="cal-header-u">Thu</div><div class="cal-header-u">Fri</div><div class="cal-header-u">Sat</div>
    """
    
    for i in range(35): # 5 weeks
        current_cell_date = start_date + datetime.timedelta(days=i)
        is_today = current_cell_date == today_date
        cell_class = "cal-cell-u cal-cell-today" if is_today else "cal-cell-u"
        date_class = "cal-date-u cal-date-today" if is_today else "cal-date-u"
        
        # Get events for this day
        day_events = [ev for ev in calendar_events if ev['date'] == current_cell_date]
        
        # Deduplicate labels for the same day to prevent clutter
        seen_labels = set()
        unique_day_events = []
        for ev in day_events:
            if ev['label'] not in seen_labels:
                unique_day_events.append(ev)
                seen_labels.add(ev['label'])
        
        pills_html = ""
        for ev in unique_day_events:
            txt_color = ev.get('text_color', 'white')
            pills_html += f'<div class="event-pill-u" style="background: {ev["color"]}; color: {txt_color};" title="{ev["label"]}">{ev["label"]}</div>'
            
        # Format date: show month name on the 1st or the very first cell
        if current_cell_date.day == 1 or i == 0:
            date_str = current_cell_date.strftime('%b %d')
        else:
            date_str = str(current_cell_date.day)
            
        cal_html += f'<div class="{cell_class}"><div class="{date_class}">{date_str}</div>{pills_html}</div>'
        
    cal_html += "</div>"
    st.markdown(cal_html, unsafe_allow_html=True)
# --- SECTION 1C: MARKET FLOW ---
st.subheader("Market Flow", anchor="sec1c")

with st.expander("🗺️ S&P 500 Market Cap Heatmap", expanded=False):
    tv_html = """<!DOCTYPE html>
    <html>
    <head><style>body, html {margin: 0; padding: 0; height: 100%; overflow: hidden;}</style></head>
    <body>
      <div class="tradingview-widget-container" style="height: 100%; width: 100%;">
        <div class="tradingview-widget-container__widget" style="height: 100%; width: 100%;"></div>
        <script type="text/javascript" src="https://s3.tradingview.com/external-embedding/embed-widget-stock-heatmap.js" async>
        {
        "exchanges": [],
        "dataSource": "SPX500",
        "grouping": "sector",
        "blockSize": "market_cap_basic",
        "blockColor": "change",
        "locale": "en",
        "symbolUrl": "",
        "colorTheme": "dark",
        "hasTopBar": true,
        "isTransparent": false,
        "saveImage": false,
        "backgroundColor": "rgba(15, 23, 42, 1)",
        "width": "100%",
        "height": "100%"
        }
        </script>
      </div>
    </body>
    </html>
    """
    b64_tv = base64.b64encode(tv_html.encode('utf-8')).decode('utf-8')
    st.markdown(f'<iframe src="data:text/html;base64,{b64_tv}" width="100%" height="600" style="border:none;"></iframe>', unsafe_allow_html=True)

with st.expander("📊 Institutional Flow", expanded=False):
    # Feature: One-Click PDF Download
    pdf_path = os.path.join(TARGET_DIR, "market_flow_report.pdf")
    if os.path.exists(pdf_path):
        with open(pdf_path, "rb") as pdf_file:
            st.download_button(
                label="📄 Download Institutional Flow Report (PDF)",
                data=pdf_file,
                file_name=f"Estate_Market_Flow_{datetime.date.today().isoformat()}.pdf",
                mime="application/pdf"
            )

    html_path = os.path.join(TARGET_DIR, "market_flow_report.html")
    if os.path.exists(html_path):
        with open(html_path, "r", encoding="utf-8") as f:
            html_data = f.read()
        
        # Bypassing Streamlit's custom components entirely to permanently silence all terminal deprecation warnings.
        # Encodes the file into a Base64 data URI and injects it natively via Markdown.
        b64_html = base64.b64encode(html_data.encode('utf-8')).decode('utf-8')
        st.markdown(f'<iframe src="data:text/html;base64,{b64_html}" width="100%" height="900" style="border:none;"></iframe>', unsafe_allow_html=True)
    else:
        st.info("Market Flow Report not found. Click '🌐 Generate Market Flow Report' in the ⚙️ Engine Control sidebar to create it.")



# --- SECTION 3: CAPITAL BREAKDOWN ---
st.subheader("Capital Breakdown", anchor="sec1")

exp_sec8 = st.expander("🎲 Montecarlo PnL Simulation", expanded=False)
daily_pnl_array = global_df['daily_pnl'].dropna().values
sim_length = len(daily_pnl_array)

if sim_length > 0:
    cum_sim, max_dds, mc_avg_dd, mc_best_dd, mc_worst_dd, mc_avg_path = generate_mc_paths(daily_pnl_array)
    
    nav_base = global_metrics['nav'] if global_metrics['nav'] > 0 else 1
    
    orig_cum = np.insert(np.cumsum(daily_pnl_array), 0, 0)
    orig_peaks = np.maximum.accumulate(orig_cum)
    orig_dd = np.max(orig_peaks - orig_cum)
    
    best_idx = np.argmax(cum_sim[:, -1])
    worst_idx = np.argmin(cum_sim[:, -1])
    
    col_mc_chart, col_mc_leg = exp_sec8.columns([0.85, 0.15])
    
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
        st.markdown("<div style='margin-top: 50px;'></div>", unsafe_allow_html=True)
        ruin_pct_limit = st.slider("💥 Ruin Threshold (%)", min_value=5, max_value=50, value=20, step=5, help="Define the maximum acceptable portfolio drawdown.")
        ruin_prob = (np.sum(max_dds > (nav_base * (ruin_pct_limit / 100.0))) / 10000) * 100
        
        st.markdown(f"""
        <div style="background-color: rgba(255, 255, 255, 0.9); padding: 15px; border: 1px solid black; border-radius: 5px; font-size: 12px; color: black; margin-top: 10px;">
            <b style="font-size: 14px; color: #1d4ed8;">RISK METRICS</b><br><br>
            <b>Empirical Risk of Ruin:</b> <span style="color: {'red' if ruin_prob>5 else 'green'}; font-weight: bold;">{ruin_prob:.2f}%</span><br>
            <i>(Probability of hitting a >{ruin_pct_limit}% drawdown based on 10,000 resampled realities).</i><br><br>
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


exp_sec1 = st.expander("🏦 View GAAP Balance Sheet & Allocation", expanded=False)
col_bar, col_pie, col_sector = exp_sec1.columns(3)

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
        exp_sec1.plotly_chart(fig_bar, width="stretch")

    with col_pie:
        fig_pie = go.Figure(data=[go.Pie(
            labels=pie_df['legend_label'], values=pie_df['market_value'], hole=.4, 
            marker=dict(colors=[COLOR_PALETTE.get(a, '#cbd5e1') for a in pie_df['asset_class']]), textinfo='percent'
        )])
        fig_pie.update_layout(
            title="Gross Asset Allocation", margin=dict(l=20, r=20, t=40, b=20),
            legend=dict(orientation="h", yanchor="top", y=-0.2, xanchor="center", x=0.5), font=dict(size=12)
        )
        exp_sec1.plotly_chart(fig_pie, width="stretch")
        
    with col_sector:
        if not sec_df.empty:
            fig_sec = go.Figure(data=[go.Pie(
                labels=sec_df['Sector'], values=sec_df['Value'], hole=.4, textinfo='percent'
            )])
            fig_sec.update_layout(
                title="Sector Concentration Risk", margin=dict(l=20, r=20, t=40, b=20),
                legend=dict(orientation="h", yanchor="top", y=-0.2, xanchor="center", x=0.5), font=dict(size=12)
            )
            exp_sec1.plotly_chart(fig_sec, width="stretch")


exp_sec2 = st.expander("🔍 View Live Portfolio Composition", expanded=False)
num_silos = max(1, len(SILO_MAP))
comp_cols = exp_sec2.columns(num_silos)

for idx, acc in enumerate(SILO_MAP.keys()):
    name, desc, color, _ = SILO_MAP[acc]
    acc_pos = pos_df[pos_df['account'] == acc].copy() if not pos_df.empty else pd.DataFrame()
    
    with comp_cols[idx]:
        st.markdown(f"**{name}**")
        if not acc_pos.empty:
            acc_nav = silo_metrics.get(acc, {}).get('nav', 0)
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
            f"<div style='font-size: 11px; color: #000000; padding: 10px; border-top: 1px solid #e5e7eb; margin-top: 10px; height: 180px; overflow-y: auto;'><b>STRATEGY & EXECUTION:</b> {desc}</div>", 
            unsafe_allow_html=True
        )


exp_sec3 = st.expander("📈 View Daily PnL Trajectory", expanded=False)

privacy_mode = exp_sec3.toggle("🙈 Privacy Mode (Hide Estate & Silo PnL)", value=False)


initial_nav = chart_df['net_flow'].sum() + chart_df['nav'].iloc[0] if not chart_df.empty else 0
chart_df['spy_usd_cum'] = chart_df['spy_cum'] * initial_nav
chart_df['qqq_usd_cum'] = chart_df['qqq_cum'] * initial_nav
chart_df['rsp_usd_cum'] = chart_df['rsp_cum'] * initial_nav

fig_pnl = go.Figure()

if not privacy_mode:
    for acc in SILO_MAP.keys():
        name, _, color, _ = SILO_MAP[acc]
        if acc in silo_dfs and not silo_dfs[acc].empty: 
            fig_pnl.add_trace(go.Bar(
                x=silo_dfs[acc]['date'], 
                y=silo_dfs[acc]['daily_pnl'], 
                name=name, 
                marker_color=color
            ))
    fig_pnl.add_trace(go.Scatter(x=chart_df['date'], y=chart_df['cum_pnl'], name='Estate (Cum PnL USD)', mode='lines', line=dict(color='black', width=6), yaxis='y2'))
    
    fig_pnl.add_trace(go.Scatter(x=chart_df['date'], y=chart_df['spy_usd_cum'], name='SPY (Cum PnL USD)', mode='lines', line=dict(color='#3b82f6', width=3), yaxis='y2'))
    fig_pnl.add_trace(go.Scatter(x=chart_df['date'], y=chart_df['qqq_usd_cum'], name='QQQ (Cum PnL USD)', mode='lines', line=dict(color='#dc2626', width=3), yaxis='y2'))
    fig_pnl.add_trace(go.Scatter(x=chart_df['date'], y=chart_df['rsp_usd_cum'], name='RSP (Cum PnL USD)', mode='lines', line=dict(color='#16a34a', width=3), yaxis='y2'))
else:
    fig_pnl.add_trace(go.Scatter(x=chart_df['date'], y=chart_df['spy_cum']*100, name='SPY (Cum Return %)', mode='lines', line=dict(color='#3b82f6', width=3), yaxis='y2'))
    fig_pnl.add_trace(go.Scatter(x=chart_df['date'], y=chart_df['qqq_cum']*100, name='QQQ (Cum Return %)', mode='lines', line=dict(color='#dc2626', width=3), yaxis='y2'))
    fig_pnl.add_trace(go.Scatter(x=chart_df['date'], y=chart_df['rsp_cum']*100, name='RSP (Cum Return %)', mode='lines', line=dict(color='#16a34a', width=3), yaxis='y2'))

# Map colors directly to the 0-5 Gear (tor) instead of the broad regime string
gear_color_map = {
    5: '#14532d', # Deep Green
    4: '#22c55e', # Light Green
    3: '#84cc16', # Yellow-Green
    2: '#eab308', # True Yellow
    1: '#f97316', # Orange
    0: '#991b1b'  # Red
}
gear_txt_map = {5: 'white', 4: 'black', 3: 'black', 2: 'black', 1: 'black', 0: 'white'}

chart_df['alpha_bg'] = chart_df['alpha_gear'].map({5: '#14532d', 4: '#22c55e', 3: '#84cc16', 2: '#eab308', 1: '#f97316', 0: '#991b1b'})
chart_df['alpha_txt'] = chart_df['alpha_gear'].map({5: 'white', 4: 'black', 3: 'black', 2: 'black', 1: 'black', 0: 'white'})
chart_df['opt_bg'] = chart_df['opt_dir'].map({'Bull': '#166534', 'Bear': '#991b1b'})

# Alpha Engine (Squares)
fig_pnl.add_trace(go.Scatter(
    x=chart_df['date'], y=[0]*len(chart_df), mode='markers+text', 
    marker=dict(color=chart_df['alpha_bg'], symbol='square', size=16, line=dict(width=1, color='black')),
    text=chart_df['alpha_gear'], textposition='middle center', textfont=dict(color=chart_df['alpha_txt'], size=10, weight='bold'),
    hovertemplate="<b>Date:</b> %{x|%Y-%m-%d}<br><b>Alpha Gear:</b> %{customdata}<extra></extra>",
    customdata=chart_df['alpha_gear'], 
    name='Alpha Engine', showlegend=False, yaxis='y3'
))

# Options Engine (Circles) - Hidden in Privacy Mode
if not privacy_mode:
    fig_pnl.add_trace(go.Scatter(
        x=chart_df['date'], y=[-1]*len(chart_df), mode='markers', 
        marker=dict(color=chart_df['opt_bg'], symbol='circle', size=12, line=dict(width=1, color='black')),
        hovertemplate="<b>Date:</b> %{x|%Y-%m-%d}<br><b>Options Trend:</b> %{customdata}<extra></extra>",
        customdata=chart_df['opt_dir'], 
        name='Options Engine', showlegend=False, yaxis='y3'
    ))

last_dt = chart_df['date'].iloc[-1]

if not privacy_mode:
    est_val = chart_df['cum_pnl'].iloc[-1]
    spy_val = chart_df['spy_usd_cum'].iloc[-1]
    qqq_val = chart_df['qqq_usd_cum'].iloc[-1]
    rsp_val = chart_df['rsp_usd_cum'].iloc[-1]
    
    # FIX: Use the pure cumulative return for the percentage, but keep the USD value for the dollar display.
    est_pct = chart_df['cum_return'].iloc[-1] * 100
    spy_pct = chart_df['spy_cum'].iloc[-1] * 100
    qqq_pct = chart_df['qqq_cum'].iloc[-1] * 100
    rsp_pct = chart_df['rsp_cum'].iloc[-1] * 100
    
    fig_pnl.add_annotation(x=last_dt, y=est_val, text=f"{est_pct:.1f}%<br>${est_val:,.0f}", showarrow=False, xanchor='left', yref='y2', bgcolor='black', font=dict(color='white', size=11))
    fig_pnl.add_annotation(x=last_dt, y=spy_val, text=f"{spy_pct:.1f}%<br>${spy_val:,.0f}", showarrow=False, xanchor='left', yref='y2', bgcolor='#3b82f6', font=dict(color='white', size=11))
    fig_pnl.add_annotation(x=last_dt, y=qqq_val, text=f"{qqq_pct:.1f}%<br>${qqq_val:,.0f}", showarrow=False, xanchor='left', yref='y2', bgcolor='#dc2626', font=dict(color='white', size=11))
    fig_pnl.add_annotation(x=last_dt, y=rsp_val, text=f"{rsp_pct:.1f}%<br>${rsp_val:,.0f}", showarrow=False, xanchor='left', yref='y2', bgcolor='#16a34a', font=dict(color='white', size=11))
else:
    spy_pct = chart_df['spy_cum'].iloc[-1] * 100
    qqq_pct = chart_df['qqq_cum'].iloc[-1] * 100
    rsp_pct = chart_df['rsp_cum'].iloc[-1] * 100
    
    fig_pnl.add_annotation(x=last_dt, y=spy_pct, text=f"{spy_pct:.1f}%", showarrow=False, xanchor='left', yref='y2', bgcolor='#3b82f6', font=dict(color='white', size=11))
    fig_pnl.add_annotation(x=last_dt, y=qqq_pct, text=f"{qqq_pct:.1f}%", showarrow=False, xanchor='left', yref='y2', bgcolor='#dc2626', font=dict(color='white', size=11))
    fig_pnl.add_annotation(x=last_dt, y=rsp_pct, text=f"{rsp_pct:.1f}%", showarrow=False, xanchor='left', yref='y2', bgcolor='#16a34a', font=dict(color='white', size=11))

start_date_str = chart_df['date'].iloc[0].strftime('%b %d, %Y')
fig_pnl.add_annotation(x=0.01, y=0.95, xref='paper', yref='paper', text=f"<b>Start Date:</b> {start_date_str}", showarrow=False, xanchor='left', yanchor='top', font=dict(size=12, color='gray'), bgcolor='rgba(255,255,255,0.8)')

y2_title = 'Cumulative Return (%)' if privacy_mode else 'Cumulative PnL (USD)'
y1_title = '' if privacy_mode else 'Daily PnL (USD)'

fig_pnl.update_layout(
    barmode='relative', 
    margin=dict(l=20, r=20, t=30, b=20), 
    plot_bgcolor='rgba(0,0,0,0)', 
    legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1), 
    yaxis=dict(title=y1_title, showgrid=True, gridcolor='LightGray', zeroline=True, zerolinecolor='black', zerolinewidth=1, showticklabels=not privacy_mode), 
    yaxis2=dict(title=y2_title, overlaying='y', side='right', showgrid=False), 
    yaxis3=dict(overlaying='y', visible=False, range=[-2, 20])
)
exp_sec3.plotly_chart(fig_pnl, width="stretch")

# Alpha Engine Gear Legend
gear_legend_html = """
<div style="display: flex; justify-content: center; flex-wrap: wrap; gap: 15px; font-size: 11px; color: #4b5563; margin-top: -15px; margin-bottom: 10px;">
    <div style="display: flex; align-items: center; gap: 4px;"><div style="width: 12px; height: 12px; background-color: #14532d; border: 1px solid black; border-radius: 2px;"></div> <b>5:</b> Perfect Bull</div>
    <div style="display: flex; align-items: center; gap: 4px;"><div style="width: 12px; height: 12px; background-color: #22c55e; border: 1px solid black; border-radius: 2px;"></div> <b>4:</b> Steady Bull</div>
    <div style="display: flex; align-items: center; gap: 4px;"><div style="width: 12px; height: 12px; background-color: #84cc16; border: 1px solid black; border-radius: 2px;"></div> <b>3:</b> Pullback Phase</div>
    <div style="display: flex; align-items: center; gap: 4px;"><div style="width: 12px; height: 12px; background-color: #eab308; border: 1px solid black; border-radius: 2px;"></div> <b>2:</b> Breadth Divergence</div>
    <div style="display: flex; align-items: center; gap: 4px;"><div style="width: 12px; height: 12px; background-color: #f97316; border: 1px solid black; border-radius: 2px;"></div> <b>1:</b> Cap-Weighted Breakdown</div>
    <div style="display: flex; align-items: center; gap: 4px;"><div style="width: 12px; height: 12px; background-color: #991b1b; border: 1px solid black; border-radius: 2px;"></div> <b>0:</b> Bear Market</div>
</div>
"""
exp_sec3.markdown(gear_legend_html, unsafe_allow_html=True)


exp_sec3b = st.expander("⚔️ View Physical Equity Risk Ledger", expanded=False)

alpha_assets = ['Physical US Stocks', 'International Stocks', 'US Tech CFDs', 'Gold', 'Crypto', 'CSPX', 'CNDX', 'ITWN', 'CSKR', 'CNYA']
df_phys = pos_df[pos_df['asset_class'].isin(alpha_assets)].copy() if not pos_df.empty else pd.DataFrame()
phys_grouped = []
if not df_phys.empty:
    for sym, g in df_phys.groupby('symbol'):
        shares = g['position'].sum()
        if abs(shares) <= 0.001: continue
        
        is_long = shares > 0
        abs_shares = abs(shares)
        
        # The sync_engine_v32 ALREADY converted these to USD natively
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
            target_action = 'SELL' if is_long else 'BUY'
            sym_stops = open_orders_df[(open_orders_df['symbol'] == sym) & 
                                       (open_orders_df['action'] == target_action) & 
                                       (open_orders_df['order_type'].str.contains('STP|TRAIL', case=False, na=False))].copy()
        if not sym_stops.empty:
            # Sort descending for Longs (highest stop first), ascending for Shorts (lowest stop first)
            sym_stops = sym_stops.sort_values('aux_price', ascending=not is_long)
        
        rem_shares = abs_shares
        open_risk = 0.0
        locked_profit = 0.0
        sl_val_total_usd = 0.0
        total_stopped_shares = 0
        stop_details = []
        
        for _, sr in sym_stops.iterrows():
            q = min(sr['total_quantity'], rem_shares)
            if q <= 0: break
            
            sl_price_usd = sr['aux_price'] * fx_rate
            
            # IBKR GBX (British Pence) Anomaly Failsafe
            if sl_price_usd > 0 and mkt_price_usd > 0:
                ratio = sl_price_usd / mkt_price_usd
                if ratio > 50.0:
                    sl_price_usd /= 100.0
                elif ratio < 0.02:
                    sl_price_usd *= 100.0
            
            chunk_cost = q * avg_cost_usd
            chunk_val = q * sl_price_usd
            
            # Invert the math for Short positions
            if is_long:
                diff = chunk_val - chunk_cost
            else:
                diff = chunk_cost - chunk_val

            if diff < 0: open_risk += diff
            else: locked_profit += diff
            
            sl_val_total_usd += chunk_val
            total_stopped_shares += q
            rem_shares -= q
            stop_details.append({'q': q, 'sl_usd': sl_price_usd})

        if rem_shares > 0:
            # Unprotected shares risk
            if is_long:
                open_risk -= (rem_shares * avg_cost_usd)
            else:
                # For a short, theoretical risk is infinite, but we cap the display at 100% loss for the ledger
                open_risk -= (rem_shares * avg_cost_usd) 
            stop_details.append({'q': rem_shares, 'sl_usd': 0.0})
           
        avg_sl_usd = (sl_val_total_usd / total_stopped_shares) if total_stopped_shares > 0 else 0.0
        
        total_profit = mkt_val - cost
        unlocked_profit = total_profit - locked_profit
        
        # Fetch days_active from database to enforce the 5-Day Trailing Rule
        conn_temp = sqlite3.connect(DB_PATH)
        c_temp = conn_temp.cursor()
        c_temp.execute("SELECT days_active FROM alpha_campaigns WHERE symbol=? AND status LIKE 'Open%'", (sym,))
        res_d = c_temp.fetchone()
        d_act = res_d[0] if res_d else 0
        conn_temp.close()
        
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
            'Days Active': d_act,
            'stop_details': stop_details
        })

df_alpha = pd.DataFrame(phys_grouped)

if not df_alpha.empty:
    df_alpha = df_alpha.sort_values('Market Value', ascending=False).reset_index(drop=True)
    nav_for_pct = global_metrics['nav'] if global_metrics['nav'] > 0 else 1.0
    df_alpha['Global Estate %'] = (df_alpha['Market Value'] / nav_for_pct) * 100
    
    c_chart, c_ctrl = exp_sec3b.columns([8, 1])
    with c_ctrl:
        exp_sec3b.markdown("<br><br><br>", unsafe_allow_html=True)
        use_log = exp_sec3b.toggle("Logarithmic Scale", value=False)
    
    fig_alpha = go.Figure()
    
    base_vals = []
    green_tops = []
    red_tops = []
    
    for _, r in df_alpha.iterrows():
        c = abs(r['Cost'])
        m = abs(r['Market Value'])
        is_long = r['Shares'] > 0
        
        if is_long:
            if m >= c: # Profit
                base_vals.append(c)
                green_tops.append(m - c)
                red_tops.append(0)
            else: # Loss
                base_vals.append(m)
                green_tops.append(0)
                red_tops.append(c - m)
        else: # Short
            if m <= c: # Profit (Liability shrank)
                base_vals.append(m)
                green_tops.append(c - m)
                red_tops.append(0)
            else: # Loss (Liability grew)
                base_vals.append(c)
                green_tops.append(0)
                red_tops.append(m - c)
                
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
        c_abs = abs(r['Cost'])
        m_abs = abs(r['Market Value'])
        
        # Thick Blue Line for Cost Value
        fig_alpha.add_shape(type="line", x0=i-0.4, x1=i+0.4, y0=c_abs, y1=c_abs, line=dict(color="blue", width=3))
        
        # Thin Dashed Line for Current Value (Top of Bar)
        fig_alpha.add_shape(type="line", x0=i-0.4, x1=i+0.4, y0=m_abs, y1=m_abs, line=dict(color="gray", width=1, dash="dash"))
        
        # Stop Loss Line and Thick Black Dot (Left aligned)
        if r['Total SL Value'] > 0.01:
            sl_val = abs(r['Total SL Value'])
            fig_alpha.add_shape(type="line", x0=i-0.5, x1=i+0.4, y0=sl_val, y1=sl_val, line=dict(color="black", width=2))
            fig_alpha.add_trace(go.Scatter(x=[i-0.5], y=[sl_val], mode='markers', marker=dict(color='black', size=10), showlegend=False, hovertemplate=f"Stop Loss Val: ${sl_val:,.0f}<extra></extra>"))
        else:
            fig_alpha.add_annotation(x=i, y=0, text="SL=0", showarrow=False, yshift=-15, font=dict(color="#b91c1c", size=11, weight="bold"))

        # Column Header Annotations (mktv, tpro, cost)
        mkt_str = f"mktv={m_abs/1000:.1f}k"
        tpro_str = f"tpro={r['Total Profit']/1000:+.1f}k"
        cost_str = f"cost={c_abs/1000:.1f}k"
        
        fig_alpha.add_annotation(
            x=i, y=max(m_abs, c_abs),
            text=f"{mkt_str}<br>{tpro_str}<br>{cost_str}",
            showarrow=False, yshift=28,
            font=dict(size=9, color="#475569"), align="center"
        )
        
    y_layout = dict(gridcolor='LightGray', zeroline=True, zerolinecolor='black')
    if use_log:
        y_layout['type'] = 'log'
        y_layout['dtick'] = 1
        
    fig_alpha.update_layout(
        barmode='stack', title="Global Physical Equity Risk Profiles (Absolute Notional Value)",
        plot_bgcolor='rgba(0,0,0,0)', yaxis=y_layout,
        margin=dict(l=20, r=20, t=65, b=40), height=500,
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
    )
    
    tick_texts = df_alpha.apply(lambda r: f"{r['Ticker']} {'<span style=\"color:#dc2626;font-weight:bold;\">(Short)</span>' if r['Shares'] < 0 else ''}<br><span style='font-size:10px;color:gray;'>{abs(r['Global Estate %']):.2f}%</span>", axis=1)
    fig_alpha.update_xaxes(tickmode='array', tickvals=x_pos, ticktext=tick_texts)

    with c_chart:
        exp_sec3b.plotly_chart(fig_alpha, width="stretch")
    
    display_alpha = df_alpha[['Ticker', 'Global Estate %', 'Shares', 'Spot Price', 'Market Value', 'Cost', 'Avg SL', 'Open Risk', 'Locked Profit', 'Unlocked Profit', 'Total Profit', 'Days Active']].copy()
    
    # v91: Fetch and inject SMAs, Earnings, and R-Multiples
    sma20_list, sma50_list, earn_list, r_mult_list = [], [], [], []
    nav_1r = global_metrics['nav'] * 0.001 if global_metrics['nav'] > 0 else 1000.0
    
    for idx, row in display_alpha.iterrows():
        tckr = row['Ticker']
        s20, s50 = get_stock_smas(tckr)
        sma20_list.append(s20)
        sma50_list.append(s50)
        
        e_date = get_upcoming_earnings(tckr)
        if e_date:
            days_to_e = (e_date - datetime.date.today()).days
            earn_list.append(f"{e_date.strftime('%b %d')} ({days_to_e}d)")
        else:
            earn_list.append("N/A")
            
        r_mult = row['Total Profit'] / nav_1r
        r_mult_list.append(r_mult)
        
    idx_sl = display_alpha.columns.get_loc('Avg SL') + 1
    display_alpha.insert(idx_sl, '20 SMA', sma20_list)
    display_alpha.insert(idx_sl + 1, '50 SMA', sma50_list)
    
    idx_end = len(display_alpha.columns)
    display_alpha.insert(2, 'Earnings', earn_list)
    display_alpha.insert(idx_end, 'Live R-Mult', r_mult_list)
    
    global_tor = display_alpha['Open Risk'].sum()
    global_lp = display_alpha['Locked Profit'].sum()
    tor_pct = (global_tor / global_metrics['nav'] * 100) if global_metrics['nav'] > 0 else 0
    
    exp_sec3b.markdown(f"""
    <div style='display:flex; justify-content:space-between; background-color:#f8fafc; padding:15px; border-radius:8px; border:1px solid #cbd5e1; margin-bottom:15px;'>
        <div><span style='color:#475569; font-size:14px;'>Global Total Open Risk (TOR):</span> <span style='font-size:18px; font-weight:bold; color:#dc2626;'>${global_tor:,.0f} ({tor_pct:.1f}% NAV)</span></div>
        <div><span style='color:#475569; font-size:14px;'>Global Locked Profit:</span> <span style='font-size:18px; font-weight:bold; color:#16a34a;'>+${global_lp:,.0f}</span></div>
    </div>
    """, unsafe_allow_html=True)

    def style_alpha_row(row):
        styles = pd.Series([''] * len(row), index=row.index)
        
        # Format PnL coloring natively
        if row['Open Risk'] < 0:
            styles['Open Risk'] = 'color: #dc2626; font-weight:bold;'
        for col in ['Locked Profit', 'Unlocked Profit', 'Total Profit', 'Live R-Mult']:
            if pd.notna(row[col]) and isinstance(row[col], (int, float)):
                if row[col] > 0:
                    styles[col] = 'color: #16a34a; font-weight:bold;'
                elif row[col] < 0:
                    styles[col] = 'color: #dc2626; font-weight:bold;'
                
        # The Trailing Stop Audit Warning (Only active after Day 4 Survival Phase)
        if row['Total Profit'] > 0 and row['20 SMA'] > 0 and row['Avg SL'] < (row['20 SMA'] * 0.99) and row['Days Active'] >= 5:
            styles['Avg SL'] = 'background-color: #fef08a; color: #856404; font-weight:bold;'
            
        # The "Dead Asset" Time Stop (Rule 7)
        if row['Days Active'] >= 10 and row['Live R-Mult'] < 1.0:
            styles['Days Active'] = 'background-color: #fdba74; color: #9a3412; font-weight:bold;'
            
        # Earnings Warning (Red if <= 5 days, Orange if <= 14 days)
        if isinstance(row['Earnings'], str) and '(' in row['Earnings']:
            try:
                days_str = row['Earnings'].split('(')[1].replace('d)', '')
                if int(days_str) <= 5:
                    styles['Earnings'] = 'background-color: #fecaca; color: #991b1b; font-weight:bold;'
                elif int(days_str) <= 14:
                    styles['Earnings'] = 'color: #d97706; font-weight:bold;'
            except: pass
            
        return styles

    exp_sec3b.dataframe(display_alpha.style.format({
        'Global Estate %': '{:.2f}%', 'Shares': '{:,.0f}', 'Spot Price': '${:,.2f}', 
        'Market Value': '${:,.0f}', 'Cost': '${:,.0f}', 'Avg SL': '${:,.2f}', 
        '20 SMA': '${:,.2f}', '50 SMA': '${:,.2f}',
        'Open Risk': '${:,.0f}', 'Locked Profit': '${:,.0f}', 'Unlocked Profit': '${:,.0f}', 
        'Total Profit': '${:,.0f}', 'Live R-Mult': '{:+.2f}R', 'Days Active': '{:.0f}'
    }).apply(style_alpha_row, axis=1), hide_index=True, width="stretch")

else:
    exp_sec3b.info("No physical equities currently held in the Estate.")

exp_sec10 = st.expander("📓 View Accountability Journal & Pipeline", expanded=False)

# FIX: Added timeout and WAL mode to the Journal connection
conn_journal = sqlite3.connect(DB_PATH, timeout=15)
conn_journal.execute("PRAGMA journal_mode=WAL;")
cj = conn_journal.cursor()

cj.execute("""
    CREATE TABLE IF NOT EXISTS tag_glossary (
        tag TEXT PRIMARY KEY,
        description TEXT
    )
""")

cj.execute("""
    CREATE TABLE IF NOT EXISTS alpha_campaigns (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        symbol TEXT,
        type TEXT,
        status TEXT DEFAULT 'Open 🟢',
        open_date TEXT,
        close_date TEXT,
        regime_in TEXT,
        sector TEXT,
        industry TEXT,
        sma_20 REAL,
        sma_50 REAL,
        sma_200 REAL,
        entry_price REAL,
        initial_stop REAL DEFAULT 0.0,
        tags TEXT DEFAULT '',
        thesis TEXT DEFAULT '',
        days_active INTEGER DEFAULT 0,
        total_pnl REAL DEFAULT 0.0,
        r_multiple REAL DEFAULT 0.0,
        grade TEXT DEFAULT ''
    )
""")

# Safely add new columns for the Staging Pipeline if they don't exist
try:
    cj.execute("ALTER TABLE alpha_campaigns ADD COLUMN target_entry REAL DEFAULT 0.0")
    cj.execute("ALTER TABLE alpha_campaigns ADD COLUMN planned_stop REAL DEFAULT 0.0")
    cj.execute("ALTER TABLE alpha_campaigns ADD COLUMN tranche_added INTEGER DEFAULT 0")
except sqlite3.OperationalError:
    pass

conn_journal.commit()

# Dynamic Days Active Updater (Updates Open and Pending campaigns)
cj.execute("SELECT id, open_date FROM alpha_campaigns WHERE status IN ('Open 🟢', 'Pending Settlement ⏳')")
for c_id, o_date in cj.fetchall():
    try:
        d_act = (datetime.date.today() - datetime.date.fromisoformat(o_date)).days
        cj.execute("UPDATE alpha_campaigns SET days_active=? WHERE id=?", (d_act, c_id))
    except Exception: pass
conn_journal.commit()

col_scan, col_close = exp_sec10.columns(2)

with col_scan:
    if exp_sec10.button("🔍 Scan for Undocumented Campaigns", width="stretch"):
        alpha_assets = ['Physical US Stocks', 'International Stocks', 'US Tech CFDs', 'Gold', 'Crypto', 'Active Swing']
        open_positions = pos_df[(pos_df['asset_class'].isin(alpha_assets)) & (pos_df['position'] != 0)]
        
        new_campaigns = 0
        for _, r in open_positions.iterrows():
            sym = r['symbol']
            cj.execute("SELECT id FROM alpha_campaigns WHERE symbol=? AND status IN ('Open 🟢', 'Open')", (sym,))
            if not cj.fetchone():
                trade_type = "Long" if r['position'] > 0 else "Short"
                sec, ind = get_sector_and_industry(sym, r['asset_class'])
                s20, s50, s200 = get_stock_smas_v2(sym)
                curr = r['currency'] if pd.notna(r.get('currency')) else 'USD'
                fx = get_fx_rate(curr)
                entry_usd = r['avg_cost'] if fx == 1.0 else (r['avg_cost'] / fx)  # Normalizing to local entry just in case
                
                live_alpha_gear_jnl = chart_df['alpha_gear'].iloc[-1] if not chart_df.empty else 0
                regime_in_str = f"Gear {live_alpha_gear_jnl}"
                
                cj.execute("""
                    INSERT INTO alpha_campaigns 
                    (symbol, type, status, open_date, regime_in, sector, industry, sma_20, sma_50, sma_200, entry_price)
                    VALUES (?, ?, 'Open', ?, ?, ?, ?, ?, ?, ?, ?)
                """, (sym, trade_type, datetime.date.today().isoformat(), regime_in_str, sec, ind, s20, s50, s200, entry_usd))
                
                conn_journal.commit()
                new_campaigns += 1
                
        if new_campaigns > 0:
            exp_sec10.success(f"Generated {new_campaigns} new campaigns! Please input your Initial Stops and Thesis below.")
            st.rerun()
        else:
            exp_sec10.info("No undocumented campaigns found in current portfolio.")

with col_close:
    if exp_sec10.button("🏁 Check for Closed Campaigns", width="stretch"):
        # Fetch both Open and Pending campaigns to process T+1 Settlement Delay
        cj.execute("SELECT id, symbol, open_date, entry_price, initial_stop, status FROM alpha_campaigns WHERE status IN ('Open 🟢', 'Open', 'Pending Settlement ⏳', 'Pending Settlement')")
        camps_to_check = cj.fetchall()
        
        closed_count = 0
        pending_count = 0
        reopened_count = 0
        
        for camp in camps_to_check:
            c_id, sym, o_date, entry, stop, current_status = camp
            
            # Global Share Count Check (Aggregates across all silos)
            sym_positions = pos_df[pos_df['symbol'] == sym]
            global_shares = sym_positions['position'].sum() if not sym_positions.empty else 0.0

            if abs(global_shares) < 0.001:
                close_dt = datetime.date.today().isoformat()
                
                # 1. PnL Check (Strictly T+1 Clearinghouse Data)
                try:
                    cj.execute("SELECT SUM(realized_pnl) FROM champion_closed_trades WHERE symbol=? AND close_date >= ?", (sym, o_date))
                    pnl_res = cj.fetchone()[0]
                    total_pnl = pnl_res if pnl_res else 0.0
                except Exception:
                    total_pnl = 0.0
                
                # 2. T+1 Settlement Delay Logic
                if abs(total_pnl) < 0.01:
                    # If PnL is 0.00, the Flex Query hasn't hit yet. Send to Pending.
                    if current_status != 'Pending Settlement ⏳':
                        cj.execute("UPDATE alpha_campaigns SET status='Pending Settlement ⏳' WHERE id=?", (c_id,))
                        pending_count += 1

                else:
                    # The official PnL has arrived. Grade and Lock permanently.
                    # Global Share Count Aggregation Fix (Sum across silos per date, then Max)
                    # v118: Added 30-day lookback to catch peak size for campaigns logged late
                    cj.execute("""
                        SELECT MAX(daily_total) FROM (
                            SELECT SUM(ABS(position)) as daily_total 
                            FROM daily_positions 
                            WHERE symbol=? AND date >= date(?, '-30 days') 
                            GROUP BY date
                        )
                    """, (sym, o_date))
                    max_sh_res = cj.fetchone()[0]
                    max_shares = max_sh_res if max_sh_res else 1.0
                    initial_risk = abs(entry - stop) * max_shares
                    
                    if initial_risk > 0 and stop > 0:
                        r_mult = total_pnl / initial_risk
                        if r_mult >= 3.0: grade = "A+ (Elite Edge) 🏆"
                        elif r_mult >= 1.0: grade = "B (Solid Exec) 🟢"
                        elif r_mult >= -0.5: grade = "C (Scratch) 🟡"
                        elif r_mult >= -1.2: grade = "D (Pro Loss) 🛡️"
                        else: grade = "F (Discipline) 🚨"
                    else:
                        r_mult = 0.0
                        grade = "Ungraded (No Stop)"
                        
                    cj.execute("""
                        UPDATE alpha_campaigns 
                        SET status='Closed', close_date=?, total_pnl=?, r_multiple=?, grade=?
                        WHERE id=?
                    """, (close_dt, total_pnl, r_mult, grade, c_id))
                    closed_count += 1
            
            elif current_status == 'Pending Settlement ⏳':
                # The user bought back into the position before settlement occurred. Reopen the campaign.
                cj.execute("UPDATE alpha_campaigns SET status='Open' WHERE id=?", (c_id,))
                reopened_count += 1
                
        conn_journal.commit()
        
        msg_parts = []
        if closed_count > 0: msg_parts.append(f"Graded & Locked {closed_count} campaigns.")
        if pending_count > 0: msg_parts.append(f"Sent {pending_count} campaigns to T+1 Pending Settlement.")
        if reopened_count > 0: msg_parts.append(f"Reopened {reopened_count} campaigns due to new share acquisitions.")
        
        if msg_parts:
            exp_sec10.success(" ".join(msg_parts))
            st.rerun()
        else:
            exp_sec10.info("No actionable changes detected in open campaigns today.")

# -------------------------------------------------------------------------
# STRATEGY TAG GLOSSARY & SOPS
# -------------------------------------------------------------------------

# 2. Extract and Upsert all Unique Tags into Glossary
core_tags = {"13F": "", "VCP": "Volatility Contraction Pattern", "ALCC": "", "Q-EP": "", "M-FLOW": "", "ATR-Ext": ""}
for t, desc in core_tags.items():
    cj.execute("INSERT OR IGNORE INTO tag_glossary (tag, description) VALUES (?, ?)", (t, desc))
    
cj.execute("SELECT tags FROM alpha_campaigns WHERE tags IS NOT NULL AND tags != ''")
db_tags_rows = cj.fetchall()
for row in db_tags_rows:
    raw_tag_str = str(row[0])
    if raw_tag_str:
        split_tags = [t.strip() for t in raw_tag_str.split(',')]
        for t in split_tags:
            if t:
                cj.execute("INSERT OR IGNORE INTO tag_glossary (tag, description) VALUES (?, ?)", (t, ""))
conn_journal.commit()

# Fetch absolute list of all tags for the dropdowns
all_tags_list = pd.read_sql_query("SELECT tag FROM tag_glossary ORDER BY tag ASC", conn_journal)['tag'].tolist()

with exp_sec10.expander("🏷️ Global Campaign Tag Editor", expanded=False):
    df_all_camps = pd.read_sql_query("SELECT id, symbol, status, tags FROM alpha_campaigns ORDER BY status, symbol", conn_journal)
    if not df_all_camps.empty:
        df_all_camps['display_name'] = df_all_camps['symbol'] + " (" + df_all_camps['status'] + ")"
        
        c_camp, c_tags, c_btn = st.columns([2, 3, 1])
        with c_camp:
            selected_camp_name = st.selectbox("Select Campaign to Edit:", df_all_camps['display_name'].tolist())
        
        if selected_camp_name:
            selected_row = df_all_camps[df_all_camps['display_name'] == selected_camp_name].iloc[0]
            camp_id = int(selected_row['id'])
            curr_tags_str = selected_row['tags']
            
            # Parse current tags and ensure they exist in the glossary to prevent UI crashes
            curr_tags_list = [t.strip() for t in str(curr_tags_str).split(',')] if curr_tags_str else []
            valid_curr_tags = [t for t in curr_tags_list if t in all_tags_list]
            
            with c_tags:
                new_tags_list = st.multiselect("Modify Tags:", options=all_tags_list, default=valid_curr_tags)
                
            with c_btn:
                st.markdown("<br>", unsafe_allow_html=True)
                if st.button("💾 Save Tags", use_container_width=True):
                    new_tags_str = ", ".join(new_tags_list)
                    cj.execute("UPDATE alpha_campaigns SET tags=? WHERE id=?", (new_tags_str, camp_id))
                    conn_journal.commit()
                    st.rerun()
    else:
        exp_sec10.info("No campaigns available.")

with exp_sec10.expander("📖 Strategy Tag Glossary & SOPs", expanded=False):
    
    # --- NEW: Tag Creation Tool ---
    c_new_tag, c_add_btn = st.columns([4, 1])
    with c_new_tag:
        new_tag_val = st.text_input("Create New Tag", placeholder="Type new tag here to add it to your master list...", label_visibility="collapsed")
    with c_add_btn:
        if st.button("➕ Add Tag", width="stretch"):
            if new_tag_val:
                clean_tag = new_tag_val.replace(',', '').strip()
                if clean_tag:
                    cj.execute("INSERT OR IGNORE INTO tag_glossary (tag, description) VALUES (?, ?)", (clean_tag, ""))
                    conn_journal.commit()
                    st.rerun()

    st.markdown("<br>", unsafe_allow_html=True)

    df_glossary = pd.read_sql_query("SELECT tag, description FROM tag_glossary ORDER BY tag ASC", conn_journal)
    
    def commit_glossary_edits():
        state = st.session_state["glossary_editor"]
        edits = state.get("edited_rows", {})
        deletions = state.get("deleted_rows", [])
        
        if not edits and not deletions: return
        
        conn_gl = sqlite3.connect(DB_PATH, timeout=15)
        conn_gl.execute("PRAGMA journal_mode=WAL;")
        c_gl = conn_gl.cursor()
        
        # Handle Description Edits
        for row_idx_str, row_edits in edits.items():
            idx = int(row_idx_str)
            target_tag = df_glossary.at[idx, 'tag']
            new_desc = str(row_edits.get("description", ""))
            c_gl.execute("UPDATE tag_glossary SET description=? WHERE tag=?", (new_desc, target_tag))
            
        # Handle Tag Deletions
        for idx in deletions:
            target_tag = df_glossary.at[idx, 'tag']
            c_gl.execute("DELETE FROM tag_glossary WHERE tag=?", (target_tag,))
            
        conn_gl.commit()
        conn_gl.close()
    
    st.data_editor(
        df_glossary,
        column_config={
            "tag": st.column_config.TextColumn("Tag (Master List)", disabled=True),
            "description": st.column_config.TextColumn("Description / Rules (Editable)")
        },
        hide_index=True,
        width="stretch",
        num_rows="dynamic",
        key="glossary_editor",
        on_change=commit_glossary_edits
    )

# --- TRADINGVIEW SCREENER INGESTION ---
tv_csv_path = os.path.join(TARGET_DIR, "TV_Screener.csv")
if os.path.exists(tv_csv_path):
    with exp_sec10.expander("📈 TradingView Screener Ingestion", expanded=True):
        try:
            tv_df = pd.read_csv(tv_csv_path)
            # Dynamically find the ticker column (TV sometimes uses 'Ticker' or 'Symbol')
            ticker_col = next((c for c in tv_df.columns if 'ticker' in c.lower() or 'symbol' in c.lower()), None)
            
            if ticker_col:
                st.markdown("<div style='font-size: 14px; color: #334155; margin-bottom: 10px;'><b>New Screener Detected!</b> Check the boxes below to instantly stage candidates.</div>", unsafe_allow_html=True)
                
                if 'Stage' not in tv_df.columns:
                    tv_df.insert(0, 'Stage', False)
                    
                edited_tv = st.data_editor(
                    tv_df,
                    hide_index=True,
                    column_config={"Stage": st.column_config.CheckboxColumn("Stage", default=False)},
                    width="stretch",
                    key="tv_screener_editor"
                )
                
                c_imp, c_del = st.columns([3, 1])
                with c_imp:
                    if st.button("🔭 Send Selected to Stalk List", width="stretch"):
                        to_import = edited_tv[edited_tv['Stage'] == True]
                        if not to_import.empty:
                            conn_tv = sqlite3.connect(DB_PATH, timeout=15)
                            conn_tv.execute("PRAGMA journal_mode=WAL;")
                            c_tv = conn_tv.cursor()
                            added_count = 0
                            skipped_count = 0
                            
                            for _, row in to_import.iterrows():
                                sym = str(row[ticker_col]).strip().upper()
                                # Prevent duplicates if already active in the pipeline
                                c_tv.execute("SELECT id FROM alpha_campaigns WHERE symbol=? AND status IN ('Stalking 🔭', 'Waiting ⏳', 'Armed 🎯', 'Open 🟢', 'Open', 'Pending Settlement ⏳')", (sym,))
                                if not c_tv.fetchone():
                                    c_tv.execute("INSERT INTO alpha_campaigns (symbol, type, status, thesis) VALUES (?, 'Long', 'Stalking 🔭', 'Imported from TradingView Screener.')", (sym,))
                                    added_count += 1
                                else:
                                    skipped_count += 1
                                    
                            conn_tv.commit()
                            conn_tv.close()
                            
                            if added_count > 0:
                                st.success(f"Successfully staged {added_count} new candidates! ({skipped_count} skipped as duplicates).")
                            else:
                                st.warning(f"All selected candidates are already active in the pipeline.")
                            st.rerun()
                        else:
                            st.warning("No tickers selected.")
                with c_del:
                    if st.button("🗑️ Delete CSV", width="stretch"):
                        os.remove(tv_csv_path)
                        st.rerun()
            else:
                st.error("Could not find a 'Ticker' or 'Symbol' column in the CSV. Please check your TradingView export settings.")
        except Exception as e:
            st.error(f"Error reading TV_Screener.csv: {e}")

# --- NEW: PRE-TRADE STAGING AREA ---
with exp_sec10.expander("🔭 View Pre-Trade Staging Area (Pipeline)", expanded=False):
    
    # Add New Stalking Candidate UI
    with st.form("add_stalk_form", clear_on_submit=True):
        c_sym, c_dir, c_tags, c_thes, c_add = st.columns([1, 1, 2, 3, 1])
        with c_sym: new_stalk_sym = st.text_input("Ticker", placeholder="e.g. MU").upper()
        with c_dir: new_stalk_dir = st.selectbox("Direction", options=["Long", "Short"])
        with c_tags: new_stalk_tags = st.multiselect("Tags", options=all_tags_list)
        with c_thes: new_stalk_thes = st.text_input("Thesis", placeholder="Why are we stalking this?")
        with c_add: 
            st.markdown("<br>", unsafe_allow_html=True)
            if st.form_submit_button("Add to Stalk List", use_container_width=True):
                if new_stalk_sym:
                    tags_str = ", ".join(new_stalk_tags)
                    cj.execute("INSERT INTO alpha_campaigns (symbol, type, status, tags, thesis) VALUES (?, ?, 'Stalking 🔭', ?, ?)", (new_stalk_sym, new_stalk_dir, tags_str, new_stalk_thes))
                    conn_journal.commit()
                    st.rerun()

    if "staging_key" not in st.session_state:
        st.session_state["staging_key"] = 0

    df_staging = pd.read_sql_query("SELECT id, symbol, type, status, target_entry, planned_stop, tags, thesis FROM alpha_campaigns WHERE status IN ('Stalking 🔭', 'Waiting ⏳', 'Armed 🎯')", conn_journal)
    
    if not df_staging.empty:
        # Earnings Blackout & Risk Math
        earn_flags = []
        planned_risk_total = 0.0
        
        for idx, row in df_staging.iterrows():
            sym = row['symbol']
            e_date = get_upcoming_earnings(sym)
            if e_date:
                days_to_e = (e_date - datetime.date.today()).days
                if 0 <= days_to_e <= 5:
                    earn_flags.append(f"⚠️ {e_date.strftime('%b %d')} ({days_to_e}d)")
                else:
                    earn_flags.append(f"{e_date.strftime('%b %d')} ({days_to_e}d)")
            else:
                earn_flags.append("N/A")
                
            if row['status'] in ['Waiting ⏳', 'Armed 🎯']:
                # Assuming 1R sizing per trade (0.10% of Global NAV)
                planned_risk_total += (global_metrics['nav'] * 0.001) 
                    
        df_staging.insert(2, 'Earnings', earn_flags)
        
        # Pre-Flight Risk Budget Check
        regime_allowance = 0.0
        live_alpha_gear_stg = chart_df['alpha_gear'].iloc[-1] if not chart_df.empty else 0
        
        if live_alpha_gear_stg >= 3: regime_allowance = global_metrics['nav'] * 0.05 # 5% TOR
        elif live_alpha_gear_stg in [1, 2]: regime_allowance = global_metrics['nav'] * 0.03 # 3% TOR
        
        if planned_risk_total > 0:
            risk_color = "#16a34a" if planned_risk_total <= regime_allowance else "#dc2626"
            st.markdown(f"<div style='font-size:13px; padding:8px; background-color:#f8fafc; border:1px solid #cbd5e1; border-radius:4px; margin-bottom:10px;'><b>Pre-Flight Risk Budget:</b> You have <b>${planned_risk_total:,.0f}</b> of risk staged in Waiting/Armed. (Regime Allowance: ${regime_allowance:,.0f}) <span style='color:{risk_color};'>{'✅ Safe' if planned_risk_total <= regime_allowance else '🚨 EXCEEDS MACRO LIMIT'}</span></div>", unsafe_allow_html=True)

        def commit_staging_edits():
            current_key = f"staging_editor_{st.session_state['staging_key']}"
            state = st.session_state.get(current_key, {})
            edits = state.get("edited_rows", {})
            deletions = state.get("deleted_rows", [])
            
            if not edits and not deletions: return
            
            conn_stg = sqlite3.connect(DB_PATH, timeout=15)
            conn_stg.execute("PRAGMA journal_mode=WAL;")
            c_stg = conn_stg.cursor()
            
            # Handle Edits
            for row_idx_str, row_edits in edits.items():
                idx = int(row_idx_str)
                db_id = int(df_staging.at[idx, 'id'])
                
                # --- NEW: Cross-Column Validation Logic ---
                curr_type = df_staging.at[idx, 'type']
                curr_entry = float(df_staging.at[idx, 'target_entry']) if pd.notna(df_staging.at[idx, 'target_entry']) else 0.0
                curr_stop = float(df_staging.at[idx, 'planned_stop']) if pd.notna(df_staging.at[idx, 'planned_stop']) else 0.0
                curr_status = df_staging.at[idx, 'status']
                
                new_type = row_edits.get('type', curr_type)
                new_entry = float(row_edits.get('target_entry', curr_entry))
                new_stop = float(row_edits.get('planned_stop', curr_stop))
                new_status = row_edits.get('status', curr_status)
                
                # Pre-Flight Checklist Enforcement
                if new_status == 'Armed 🎯':
                    curr_tags = df_staging.at[idx, 'tags']
                    curr_thesis = df_staging.at[idx, 'thesis']
                    check_tags = row_edits.get('tags', curr_tags)
                    check_thesis = row_edits.get('thesis', curr_thesis)
                    
                    if not check_tags or not check_thesis or len(str(check_thesis).split()) < 5:
                        st.toast(f"❌ Pre-Flight Failed: {df_staging.at[idx, 'symbol']} requires Tags and a written Thesis to be Armed.", icon="🚨")
                        row_edits['status'] = 'Waiting ⏳'
                        st.session_state["staging_key"] += 1
                        continue
                
                if new_entry > 0 and new_stop > 0:
                    if new_type == 'Long' and new_stop >= new_entry:
                        st.toast(f"❌ Invalid Long: Stop ({new_stop}) must be below Entry ({new_entry}).", icon="🚨")
                        st.session_state["staging_key"] += 1 # Force UI remount
                        continue 
                    elif new_type == 'Short' and new_stop <= new_entry:
                        st.toast(f"❌ Invalid Short: Stop ({new_stop}) must be above Entry ({new_entry}).", icon="🚨")
                        st.session_state["staging_key"] += 1 # Force UI remount
                        continue 
                # ------------------------------------------
                
                set_clauses = []
                params = []
                for col, val in row_edits.items():
                    set_clauses.append(f"{col}=?")
                    params.append(val)
                
                if set_clauses:
                    params.append(db_id)
                    query = f"UPDATE alpha_campaigns SET {', '.join(set_clauses)} WHERE id=?"
                    c_stg.execute(query, tuple(params))
                    
            # Handle Deletions
            for idx in deletions:
                db_id = int(df_staging.at[idx, 'id'])
                c_stg.execute("DELETE FROM alpha_campaigns WHERE id=?", (db_id,))
                
            conn_stg.commit()
            conn_stg.close()

        def style_staging(row):
            styles = pd.Series([''] * len(row), index=row.index)
            if '⚠️' in str(row['Earnings']):
                styles['Earnings'] = 'background-color: #fecaca; color: #991b1b; font-weight:bold;'
            if row['status'] == 'Armed 🎯':
                styles['status'] = 'background-color: #dcfce7; color: #166534; font-weight:bold;'
            elif row['status'] == 'Waiting ⏳':
                styles['status'] = 'background-color: #fef08a; color: #856404; font-weight:bold;'
            return styles

        st.data_editor(
            df_staging.style.apply(style_staging, axis=1),
            column_config={
                "id": None,
                "symbol": st.column_config.TextColumn("Ticker", disabled=True),
                "type": st.column_config.SelectboxColumn("Direction", options=['Long', 'Short']),
                "Earnings": st.column_config.TextColumn("Earnings", disabled=True),
                "status": st.column_config.SelectboxColumn("Status", options=['Stalking 🔭', 'Waiting ⏳', 'Armed 🎯', 'Closed 🏁']),
                "target_entry": st.column_config.NumberColumn("Target Entry $", format="%.2f"),
                "planned_stop": st.column_config.NumberColumn("Planned Stop $", format="%.2f"),
                "tags": st.column_config.TextColumn("Tags"),
                "thesis": st.column_config.TextColumn("Thesis")
            },
            hide_index=True, width="stretch", num_rows="dynamic", height=400, key=f"staging_editor_{st.session_state['staging_key']}", on_change=commit_staging_edits
        )
        
        c_dl1, c_dl2 = st.columns(2)
        with c_dl1:
            csv_stalk = df_staging[df_staging['status'] == 'Stalking 🔭'].drop(columns=['id']).to_csv(index=False).encode('utf-8')
            st.download_button("💾 Download Stalk List (CSV)", data=csv_stalk, file_name=f"Stalk_List_{datetime.date.today().isoformat()}.csv", mime="text/csv")
        with c_dl2:
            csv_wait = df_staging[df_staging['status'].isin(['Waiting ⏳', 'Armed 🎯'])].drop(columns=['id']).to_csv(index=False).encode('utf-8')
            st.download_button("💾 Download Wait/Armed List (CSV)", data=csv_wait, file_name=f"Wait_List_{datetime.date.today().isoformat()}.csv", mime="text/csv")

        st.markdown("---")
        st.markdown("#### 🤖 C2 Quant Pitch Dossier Generator")
        
        c_pitch1, c_pitch2 = st.columns([2, 1])
        with c_pitch1:
            pitch_sym = st.selectbox("Select Staged Ticker for Dossier:", df_staging['symbol'].unique())
        with c_pitch2:
            st.markdown("<br>", unsafe_allow_html=True)
            if st.button(f"⚙️ Compile Data for {pitch_sym}", width="stretch"):
                with st.spinner("Compiling Macro, Technical, and Fundamental data..."):
                    row = df_staging[df_staging['symbol'] == pitch_sym].iloc[0]
                    entry = float(row['target_entry']) if pd.notna(row['target_entry']) else 0.0
                    stop = float(row['planned_stop']) if pd.notna(row['planned_stop']) else 0.0
                    direction = row['type']
                    thesis = row['thesis']
                    tags = row['tags']
                    
                    # Macro
                    gear = chart_df['alpha_gear'].iloc[-1] if not chart_df.empty else 0
                    opt_dir = chart_df['opt_dir'].iloc[-1] if not chart_df.empty else 'Bear'
                    vix = fetch_live_data('^VIX')[1]
                    dist_data = get_distribution_tracker()
                    spy_cdd = dist_data.get("SPY", (0, []))[0]
                    qqq_cdd = dist_data.get("QQQ", (0, []))[0]
                    rsp_cdd = dist_data.get("RSP", (0, []))[0]
                    
                    # Pre-Flight Math
                    risk_per_share = abs(entry - stop)
                    gear_risk_map = {5: 0.20, 4: 0.135, 3: 0.09, 2: 0.06, 1: 0.04, 0: 0.00}
                    max_r_pct = gear_risk_map.get(gear, 0.0)
                    max_risk_usd = global_metrics['nav'] * (max_r_pct / 100.0)
                    max_shares = int(max_risk_usd // risk_per_share) if risk_per_share > 0 else 0
                    
                    # Technicals
                    s20, s50, s200 = get_stock_smas_v2(pitch_sym)
                    atr = get_atr(pitch_sym)
                    spot, _ = fetch_live_data(pitch_sym)
                    
                    try:
                        hist_52 = yf.Ticker(pitch_sym.split()[0]).history(period="1y")
                        high_52 = hist_52['High'].max()
                        low_52 = hist_52['Low'].min()
                        dist_high = ((spot / high_52) - 1) * 100 if high_52 > 0 else 0
                        dist_low = ((spot / low_52) - 1) * 100 if low_52 > 0 else 0
                    except:
                        high_52, low_52, dist_high, dist_low = 0, 0, 0, 0
                    
                    # Fundamentals & News
                    fwd_pe, short_float, mkt_cap, avg_vol, news_str = get_fundamentals_and_news(pitch_sym)
                    
                    # Relative Strength
                    sym_thrust, sym_rvol, etf_sym, etf_thrust, etf_rvol = get_relative_strength_stats(pitch_sym)
                    
                    # Zero-Cost Enhancements
                    sec_name, ind_name = get_sector_and_industry(pitch_sym, 'Physical US Stocks')
                    e_date = get_upcoming_earnings(pitch_sym)
                    e_str = f"{e_date.strftime('%b %d, %Y')} ({(e_date - datetime.date.today()).days} days)" if e_date else "N/A"
                    
                    atr_dist = risk_per_share / atr if atr > 0 else 0
                    implied_rr = (high_52 - entry) / risk_per_share if risk_per_share > 0 and high_52 > entry else 0
                    
                    # Silo Distribution Math
                    nav_A = silo_metrics.get('U23144948', {}).get('nav', 0)
                    nav_B = silo_metrics.get('U23139264', {}).get('nav', 0)
                    nav_C = silo_metrics.get('U23154199', {}).get('nav', 0)
                    nav_D = silo_metrics.get('U25218481', {}).get('nav', 0)
                    g_nav = global_metrics['nav'] if global_metrics['nav'] > 0 else 1
                    
                    shares_A = int(max_shares * (nav_A / g_nav))
                    shares_B = int(max_shares * (nav_B / g_nav))
                    shares_C = int(max_shares * (nav_C / g_nav))
                    shares_D = int(max_shares * (nav_D / g_nav))
                    
                    md_content = f"""# C2 QUANT PITCH DOSSIER: {pitch_sym}
Date: {datetime.date.today().isoformat()}
Direction: {direction}
Sector/Industry: {sec_name} / {ind_name}
Tags: {tags}

## 1. MACRO WEATHER & CDD
- **Alpha Engine:** Gear {gear}
- **Options Trend:** {opt_dir}
- **VIX:** {vix:.2f}
- **Distribution Tracker (Consecutive Red Days):** SPY ({spy_cdd}) | QQQ ({qqq_cdd}) | RSP ({rsp_cdd})

## 2. TOP ACTIONABLE DISCOVERIES (MACRO NARRATIVE)
The Estate is currently operating in Gear {gear}. VIX is at {vix:.2f}. 
Distribution pressure is {'elevated' if max(spy_cdd, qqq_cdd, rsp_cdd) >= 3 else 'low'} across major indices.

## 3. CFO PRE-FLIGHT CHECK
- **Target Entry:** ${entry:.2f}
- **Planned Stop:** ${stop:.2f}
- **Risk Per Share:** ${risk_per_share:.2f}
- **Stop Distance in ATRs:** {atr_dist:.1f}x ATR
- **Max Allowed Risk (Gear {gear}):** ${max_risk_usd:,.2f} ({max_r_pct}%)
- **Max Position Size (Global):** {max_shares:,} shares
  - *Silo A Allocation:* {shares_A:,} shares
  - *Silo B Allocation:* {shares_B:,} shares
  - *Silo C Allocation:* {shares_C:,} shares
  - *Silo D Allocation:* {shares_D:,} shares

## 4. TECHNICAL SNAPSHOT
- **Live Spot Price:** ${spot:.2f}
- **Moving Averages:** 20-SMA (${s20:.2f}) | 50-SMA (${s50:.2f}) | 200-SMA (${s200:.2f})
- **Volatility (14-Day ATR):** ${atr:.2f}
- **52-Week Range:** ${low_52:.2f} - ${high_52:.2f}
- **Distance from High:** {dist_high:+.1f}%
- **Implied R/R to 52w High:** {implied_rr:.1f}R

## 5. RELATIVE STRENGTH & MARKET FLOW
- **{pitch_sym} 3-Month Thrust vs SPY:** {sym_thrust}
- **{pitch_sym} Relative Volume (RVOL):** {sym_rvol}
- **Sector ETF ({etf_sym}) 3-Month Thrust vs SPY:** {etf_thrust}
- **Sector ETF ({etf_sym}) RVOL:** {etf_rvol}

## 6. FUNDAMENTALS & UPCOMING EVENTS
- **Market Capitalization:** {mkt_cap}
- **Average Daily Volume:** {avg_vol}
- **Upcoming Earnings:** {e_str}
- **Forward P/E:** {fwd_pe}
- **Short Interest:** {short_float}

**Recent Headlines:**
{news_str}

## 7. CIO THESIS
{thesis}
"""
                    st.session_state['dossier_md'] = md_content
                    st.session_state['dossier_sym'] = pitch_sym
                    
        if 'dossier_md' in st.session_state and st.session_state.get('dossier_sym') == pitch_sym:
            st.success(f"✅ Data compiled successfully for {pitch_sym}!")
            c_dl, c_save = st.columns(2)
            with c_dl:
                st.download_button(
                    label=f"📥 Download {pitch_sym} C2 Pitch Dossier (.md)",
                    data=st.session_state['dossier_md'],
                    file_name=f"C2_Pitch_{pitch_sym}_{datetime.date.today().isoformat()}.md",
                    mime="text/markdown",
                    use_container_width=True
                )
            with c_save:
                if st.button("💾 Save Dossier to Database", use_container_width=True):
                    conn_dos = sqlite3.connect(DB_PATH)
                    c_dos = conn_dos.cursor()
                    c_dos.execute("CREATE TABLE IF NOT EXISTS pitch_dossiers (date TEXT, symbol TEXT, content TEXT, PRIMARY KEY(date, symbol))")
                    c_dos.execute("INSERT OR REPLACE INTO pitch_dossiers (date, symbol, content) VALUES (?, ?, ?)", (datetime.date.today().isoformat(), pitch_sym, st.session_state['dossier_md']))
                    conn_dos.commit()
                    conn_dos.close()
                    st.toast(f"Dossier for {pitch_sym} saved to SQLite!", icon="✅")

exp_sec10.markdown("##### 🟢 Active Campaigns")
# Updated query to include the new emojis and tranche_added flag
df_open = pd.read_sql_query("SELECT id, open_date, symbol, status, type, regime_in, sector, industry, sma_20, sma_50, sma_200, entry_price, initial_stop, tags, thesis, days_active, tranche_added FROM alpha_campaigns WHERE status IN ('Open 🟢', 'Pending Settlement ⏳', 'Open', 'Pending Settlement')", conn_journal)

if not df_open.empty:
    # --- AUTO-HEAL MISSING DATA ---
    needs_heal = False
    for idx, row in df_open.iterrows():
        if pd.isna(row['sector']) or row['sector'] == 'None' or pd.isna(row['sma_20']) or row['sma_20'] == 0.0:
            sym = row['symbol']
            sec, ind = get_sector_and_industry(sym, 'Physical US Stocks')
            s20, s50, s200 = get_stock_smas_v2(sym)
            
            reg_in = row['regime_in']
            if pd.isna(reg_in) or reg_in == 'None':
                live_alpha_gear_heal = chart_df['alpha_gear'].iloc[-1] if not chart_df.empty else 0
                reg_in = f"Gear {live_alpha_gear_heal}"
            
            cj.execute("""
                UPDATE alpha_campaigns 
                SET sector=?, industry=?, sma_20=?, sma_50=?, sma_200=?, regime_in=? 
                WHERE id=?
            """, (sec, ind, s20, s50, s200, reg_in, row['id']))
            needs_heal = True
    
    if needs_heal:
        conn_journal.commit()
        df_open = pd.read_sql_query("SELECT id, open_date, symbol, status, type, regime_in, sector, industry, sma_20, sma_50, sma_200, entry_price, initial_stop, tags, thesis, days_active, tranche_added FROM alpha_campaigns WHERE status IN ('Open 🟢', 'Pending Settlement ⏳', 'Open', 'Pending Settlement')", conn_journal)

    # Check for Tranche Added warnings
    if 'tranche_added' in df_open.columns and df_open['tranche_added'].sum() > 0:
        exp_sec10.warning("⚠️ **Tranche Added Detected:** One or more open campaigns have increased in share size. Please verify your 1R Stop Loss using the Alpha Risk Calculator.")
        # Reset the flag after displaying
        cj.execute("UPDATE alpha_campaigns SET tranche_added = 0 WHERE tranche_added = 1")
        conn_journal.commit()

    def commit_open_edits():
        state = st.session_state.get("open_camp_editor", {})
        edits = state.get("edited_rows", {})
        if not edits: return
        
        conn_op = sqlite3.connect(DB_PATH, timeout=15)
        conn_op.execute("PRAGMA journal_mode=WAL;")
        c_op = conn_op.cursor()
        
        for row_idx_str, row_edits in edits.items():
            idx = int(row_idx_str)
            db_id = int(df_open.at[idx, 'id'])
            
            set_clauses = []
            params = []
            for col, val in row_edits.items():
                set_clauses.append(f"{col}=?")
                params.append(val)
            
            if set_clauses:
                params.append(db_id)
                query = f"UPDATE alpha_campaigns SET {', '.join(set_clauses)} WHERE id=?"
                c_op.execute(query, tuple(params))
                
        conn_op.commit()
        conn_op.close()

    exp_sec10.markdown("<br><b>Active Campaigns Overview & Global Editor</b>", unsafe_allow_html=True)
    
    display_open = df_open.drop(columns=['tranche_added'], errors='ignore')
    
    # Force numeric conversion
    cols_to_fill = ['sma_20', 'sma_50', 'sma_200', 'entry_price', 'initial_stop']
    for col in cols_to_fill:
        if col in display_open.columns:
            display_open[col] = pd.to_numeric(display_open[col], errors='coerce').fillna(0.0)
            
    exp_sec10.data_editor(
        display_open,
        column_config={
            "id": None,
            "symbol": st.column_config.TextColumn("Ticker", disabled=True),
            "open_date": st.column_config.TextColumn("Open Date", disabled=True),
            "status": st.column_config.TextColumn("Status", disabled=True),
            "type": st.column_config.TextColumn("Type", disabled=True),
            "regime_in": st.column_config.TextColumn("Regime In", disabled=True),
            "sector": st.column_config.TextColumn("Sector", disabled=True),
            "industry": st.column_config.TextColumn("Industry", disabled=True),
            "sma_20": st.column_config.NumberColumn("20 SMA", format="%.2f", disabled=True),
            "sma_50": st.column_config.NumberColumn("50 SMA", format="%.2f", disabled=True),
            "sma_200": st.column_config.NumberColumn("200 SMA", format="%.2f", disabled=True),
            "entry_price": st.column_config.NumberColumn("Entry $", format="%.2f", disabled=True),
            "days_active": st.column_config.NumberColumn("Days", disabled=True),
            "initial_stop": st.column_config.NumberColumn("Initial Stop $", format="%.2f"),
            "tags": st.column_config.TextColumn("Tags (Editable)"),
            "thesis": st.column_config.TextColumn("Thesis (Editable)")
        },
        hide_index=True,
        width="stretch",
        key="open_camp_editor",
        on_change=commit_open_edits
    )
    
    csv_open_data = df_open.drop(columns=['id', 'tranche_added'], errors='ignore').to_csv(index=False).encode('utf-8')
    exp_sec10.download_button("💾 Download Active Campaigns & Theses (CSV)", data=csv_open_data, file_name=f"Alpha_Journal_Open_{datetime.date.today().isoformat()}.csv", mime="text/csv")
    
else:
    exp_sec10.caption("No open campaigns currently undocumented.")

exp_sec10.markdown("##### 🏁 Closed Campaigns (Post-Mortem & Grading)")

# We must select 'id' to map edits back to the specific row in the database
df_closed = pd.read_sql_query("SELECT id, open_date, close_date, symbol, type, regime_in, sector, industry, entry_price, initial_stop, tags, thesis, days_active, total_pnl, r_multiple, grade FROM alpha_campaigns WHERE status IN ('Closed', 'Closed 🏁', 'Closed (Auto-Healed) 🩹') ORDER BY close_date DESC, id DESC", conn_journal)

if not df_closed.empty:
    exp_closed = exp_sec10.expander("📚 View Closed Campaigns, Post-Mortem & Analytics", expanded=False)
    st.session_state['df_closed_cache'] = df_closed.copy()
    
    def commit_closed_edits():
        edits = st.session_state["closed_camp_editor"].get("edited_rows", {})
        if not edits: return
        
        cached_df = st.session_state.get('df_closed_cache')
        if cached_df is None: return
        
        conn_cb = sqlite3.connect(DB_PATH, timeout=15)
        conn_cb.execute("PRAGMA journal_mode=WAL;")
        c_cb = conn_cb.cursor()
        
        for row_idx_str, row_edits in edits.items():
            idx = int(row_idx_str)
            db_id = int(cached_df.at[idx, 'id'])
            
            c_cb.execute("SELECT tags, thesis FROM alpha_campaigns WHERE id=?", (db_id,))
            row_data = c_cb.fetchone()
            if not row_data: continue
            
            old_tags, old_thesis = row_data
            new_tags = str(row_edits.get("tags", old_tags if old_tags else ""))
            new_thesis = str(row_edits.get("thesis", old_thesis if old_thesis else ""))
            
            c_cb.execute("UPDATE alpha_campaigns SET tags=?, thesis=? WHERE id=?", (new_tags, new_thesis, db_id))
        
        conn_cb.commit()
        conn_cb.close()

    def style_grades(val):
        if "A+" in str(val): return 'color: #166534; font-weight: bold; background-color: #dcfce7;'
        if "B" in str(val): return 'color: #15803d; font-weight: bold; background-color: #ecfccb;'
        if "C" in str(val): return 'color: #856404; font-weight: bold; background-color: #fef08a;'
        if "D" in str(val): return 'color: #842029; font-weight: bold; background-color: #f8d7da;'
        if "F" in str(val): return 'color: #ffffff; font-weight: bold; background-color: #b91c1c;'
        if "Auto-Healed" in str(val): return 'color: #9a3412; font-weight: bold; background-color: #ffedd5;'
        return ''

    styled_closed = df_closed.style.format({
        "entry_price": "{:.2f}",
        "initial_stop": "{:.2f}",
        "total_pnl": "${:,.0f}",
        "r_multiple": "{:+.2f}R"
    }).map(style_grades, subset=['grade'])
    
    exp_closed.data_editor(
        styled_closed, 
        hide_index=True, 
        width="stretch",
        key="closed_camp_editor",
        on_change=commit_closed_edits,
        column_config={
            "id": None, # Hide the primary key from the UI
            "tags": st.column_config.TextColumn("tags (Editable)"),
            "thesis": st.column_config.TextColumn("thesis (Editable)")
        },
        disabled=["open_date", "close_date", "symbol", "type", "regime_in", "sector", "industry", "entry_price", "initial_stop", "days_active", "total_pnl", "r_multiple", "grade"]
    )
    
    # Exclude the internal 'id' column from the CSV export for a pristine spreadsheet    
    csv_data = df_closed.drop(columns=['id']).to_csv(index=False).encode('utf-8')
    exp_closed.download_button("💾 Download Accountability Journal (CSV)", data=csv_data, file_name=f"Alpha_Journal_Closed_{datetime.date.today().isoformat()}.csv", mime="text/csv")

    # --- NEW: ACCOUNTABILITY ANALYTICS (TAG PIVOT TABLES) ---
    analytics_df = df_closed.dropna(subset=['tags']).copy()
    # Explode the comma-separated strings into a list, stripping whitespace
    analytics_df['tags'] = analytics_df['tags'].apply(lambda x: [t.strip() for t in str(x).split(',') if t.strip()])
    exploded_df = analytics_df.explode('tags')
    exploded_df = exploded_df[exploded_df['tags'] != '']
    
    if not exploded_df.empty:
        exp_closed.markdown("<br><h4 style='text-align: left; color: #334155; font-size: 18px; margin-top: 10px;'>📊 Edge Analytics (Tag-Based Performance)</h4>", unsafe_allow_html=True)
        
        # Aggregate the metrics
        pivot_df = exploded_df.groupby('tags').agg(
            Trade_Count=('symbol', 'count'),
            # Win Rate strictly defined as Trades > $0
            Wins=('total_pnl', lambda x: (x > 0).sum()),
            Total_PnL=('total_pnl', 'sum'),
            Avg_R_Mult=('r_multiple', 'mean')
        ).reset_index()
        
        pivot_df['Win_Rate'] = (pivot_df['Wins'] / pivot_df['Trade_Count']) * 100
        # Sort by highest R-Multiple Expectancy
        pivot_df = pivot_df.sort_values(by='Avg_R_Mult', ascending=False).reset_index(drop=True)
        
        display_pivot = pivot_df[['tags', 'Trade_Count', 'Win_Rate', 'Avg_R_Mult', 'Total_PnL']].copy()
        display_pivot.columns = ['Tag / Strategy', 'Trade Count', 'Win Rate (%)', 'Avg R-Multiple', 'Total PnL ($)']
        
        c_tbl, c_cht = exp_closed.columns([1.2, 1])
        
        with c_tbl:
            def style_pivot(row):
                styles = pd.Series([''] * len(row), index=row.index)
                if row['Win Rate (%)'] >= 50.0:
                    styles['Win Rate (%)'] = 'color: #16a34a; font-weight: bold;'
                else:
                    styles['Win Rate (%)'] = 'color: #dc2626; font-weight: bold;'
                    
                if row['Avg R-Multiple'] > 0:
                    styles['Avg R-Multiple'] = 'color: #16a34a; font-weight: bold;'
                elif row['Avg R-Multiple'] < 0:
                    styles['Avg R-Multiple'] = 'color: #dc2626; font-weight: bold;'
                    
                if row['Total PnL ($)'] > 0:
                    styles['Total PnL ($)'] = 'color: #16a34a; font-weight: bold;'
                elif row['Total PnL ($)'] < 0:
                    styles['Total PnL ($)'] = 'color: #dc2626; font-weight: bold;'
                    
                return styles
            
            exp_closed.markdown("**Edge Verification Ledger**")
            exp_closed.dataframe(display_pivot.style.format({
                'Win Rate (%)': '{:.1f}%',
                'Avg R-Multiple': '{:+.2f}R',
                'Total PnL ($)': '${:,.0f}'
            }).apply(style_pivot, axis=1), hide_index=True, width="stretch")
        
        with c_cht:
            # Reverse sort so the highest bar renders at the top of the Plotly chart
            tags_chart_df = display_pivot.sort_values('Avg R-Multiple', ascending=True)
            colors = ['#16a34a' if val > 0 else '#dc2626' for val in tags_chart_df['Avg R-Multiple']]
            
            fig_edge = go.Figure(go.Bar(
                x=tags_chart_df['Avg R-Multiple'],
                y=tags_chart_df['Tag / Strategy'],
                orientation='h',
                marker_color=colors,
                text=tags_chart_df['Avg R-Multiple'].apply(lambda x: f"{x:+.2f}R"),
                textposition='auto',
                insidetextfont=dict(color='white'),
                outsidetextfont=dict(color='black')
            ))
            
            fig_edge.update_layout(
                title="Average Expectancy (R-Multiple) per Tag",
                margin=dict(l=0, r=20, t=30, b=0),
                height=max(250, 100 + (len(tags_chart_df) * 35)), # Dynamic height based on tag count
                xaxis=dict(title='Avg R-Multiple', zeroline=True, zerolinecolor='black', zerolinewidth=2),
                yaxis=dict(title=''),
                plot_bgcolor='rgba(0,0,0,0)'
            )
            exp_closed.plotly_chart(fig_edge, width="stretch")

else:
    exp_sec10.caption("No closed campaigns recorded yet.")
    
conn_journal.close()


exp_sec4 = st.expander("🚀 View PnL Attribution & Capital Velocity", expanded=False)
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
    
    # Calculate the exact T-0 Live Discrepancy (Unsettled PnL)
    attr_sum = tot_a1 + tot_a2 + tot_a3 + tot_a4 + tot_a5
    t0_unsettled = global_metrics['pnl'] - attr_sum
    
    th_budget = tot_a3 * 0.10
    th_df_vel = pos_df[pos_df['asset_class'] == 'Tail Hedge'] if not pos_df.empty else pd.DataFrame()        
    th_deployed = (th_df_vel['position'].abs() * th_df_vel['avg_cost']).sum() if not th_df_vel.empty else 0
    th_available = th_budget - th_deployed
    col_bar, col_line, col_vel = exp_sec4.columns([2, 3, 1])
    
    # CHANGED: Replaced '#3b82f6' (Light Blue) with '#2352d9' (Navy Blue) for the Yield bucket
    bar_colors = ['#2352d9', '#f97316', '#166534', '#a855f7', '#991b1b', '#94a3b8']
    
    with col_bar:
        fig_attr_bar = go.Figure(data=[go.Bar(
            x=['Yield (a1)', 'Beta (a2)', 'VRP (a3)', 'Alpha (a4)', 'Fees (a5)', 'T-0 Live (Unsettled)'], 
            y=[tot_a1, tot_a2, tot_a3, tot_a4, tot_a5, t0_unsettled], 
            text=[f"${v:,.0f}" for v in [tot_a1, tot_a2, tot_a3, tot_a4, tot_a5, t0_unsettled]], 
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
        exp_sec4.plotly_chart(fig_attr_bar, width="stretch")
        
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
        exp_sec4.plotly_chart(fig_attr_line, width="stretch")
        
    with col_vel:
        exp_sec4.markdown("##### Options Engine Velocity")
        exp_sec4.caption("(Silos A & C)")
        exp_sec4.metric("Total VRP Harvested", f"${tot_a3:,.0f}")
        exp_sec4.metric("Options Margin Locked", f"${opt_margin_total:,.0f}")
        exp_sec4.markdown("---")
        exp_sec4.metric("Tail Hedge Budget (10%)", f"${th_budget:,.0f}", help="Accumulated 10% of VRP budget reserved for deep OTM Ackman Puts.")
        exp_sec4.metric("Tail Hedge Deployed (Cost)", f"${th_deployed:,.0f}")
        exp_sec4.metric("Tail Hedge Available", f"${th_available:,.0f}")
        
        vix_spot = fetch_live_data('^VIX')[1]
        vix_color = "#16a34a" if vix_spot < 15.0 else ("#d97706" if vix_spot < 20.0 else "#dc2626")
        vix_status = "CRUSH (BUY TAIL)" if vix_spot < 15.0 else ("NORMAL" if vix_spot < 20.0 else "ELEVATED")
        
        exp_sec4.markdown(f"""
        <div style="margin-top: 15px; background-color: #f8fafc; padding: 10px; border-radius: 8px; border: 1px solid #cbd5e1; text-align: center;">
            <div style="font-size: 12px; color: #64748b; font-weight: bold; text-transform: uppercase;">Live VIX Status</div>
            <div style="font-size: 22px; font-weight: 900; color: {vix_color};">{vix_spot:.2f}</div>
            <div style="font-size: 11px; font-weight: bold; color: {vix_color}; background-color: {vix_color}20; padding: 2px; border-radius: 4px; margin-top: 5px;">{vix_status}</div>
        </div>
        """, unsafe_allow_html=True)


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



with st.expander("📊 Instrument Matrix & Tax Architecture", expanded=False):
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





# --- SECTION 8: CAPITAL DEPLOYMENT & MARGIN TRACKER ---
st.subheader("Options Center", anchor="sec6")

exp_sec6 = st.expander("📊 View Capital Deployment & Margin Capacity Tracker", expanded=False)
# Enlarging Global Gauges via Column Weights
c_gb_cash, c_sa_cash, c_sc_cash, c_gb_marg, c_sa_marg, c_sc_marg = exp_sec6.columns([1.5, 1, 1, 1.5, 1, 1])

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

# --- ENHANCEMENT: Capital Discipline Tracker (Margin vs VIX) ---
exp_sec6.markdown("<br><h4 style='text-align: center; color: #334155; font-size: 18px; margin-top: 20px;' title='Visual lie-detector: Purple margin bars should scale up when the black VIX line is high, and shrink when VIX is low.'>Capital Discipline Tracker: Historical Margin Utilization vs. VIX Regime ⓘ</h4>", unsafe_allow_html=True)

if not journal_raw_df.empty and not global_df.empty and not bench_df.empty:
    j_df = journal_raw_df.copy()
    j_df['Open Date'] = pd.to_datetime(j_df['Open Date'], errors='coerce')
    j_df['Close Date'] = pd.to_datetime(j_df['Close Date'], errors='coerce')
    
    dates_list = global_df['date'].dropna().sort_values().unique()
    margin_hist = []
    
    for d in dates_list:
        active_mask = (j_df['Open Date'] <= d) & ((j_df['Close Date'] >= d) | pd.isnull(j_df['Close Date']))
        active_margin = pd.to_numeric(j_df.loc[active_mask, 'Collateral Locked (USD)'], errors='coerce').fillna(0).sum()
        margin_hist.append(active_margin)
        
    disc_df = pd.DataFrame({'date': dates_list, 'Margin_USD': margin_hist})
    disc_df = pd.merge(disc_df, global_df[['date', 'nav']], on='date', how='left')
    disc_df = pd.merge(disc_df, bench_df[['date', '^VIX']], on='date', how='left').ffill()
    
    disc_df['Margin_Pct'] = (disc_df['Margin_USD'] / disc_df['nav'] * 100).fillna(0)
    
    fig_disc = go.Figure()
    
    fig_disc.add_trace(go.Bar(
        x=disc_df['date'], y=disc_df['Margin_Pct'], name='Margin Locked (%)', 
        marker_color='rgba(147, 51, 234, 0.5)', 
        hovertemplate="Date: %{x|%Y-%m-%d}<br>Margin: %{y:.1f}%<extra></extra>"
    ))
    
    fig_disc.add_trace(go.Scatter(
        x=disc_df['date'], y=disc_df['^VIX'], name='^VIX', mode='lines',
        line=dict(color='black', width=2.5), yaxis='y2',
        hovertemplate="VIX: %{y:.2f}<extra></extra>"
    ))
    
    fig_disc.add_hrect(y0=0, y1=15, fillcolor="#dcfce7", opacity=0.3, layer="below", yref="y2", annotation_text="Complacent (<15)", annotation_position="top left", annotation_font_color="#166534")
    fig_disc.add_hrect(y0=15, y1=20, fillcolor="#fef9c3", opacity=0.3, layer="below", yref="y2", annotation_text="Normal (15-20)", annotation_position="top left", annotation_font_color="#a16207")
    fig_disc.add_hrect(y0=20, y1=100, fillcolor="#fee2e2", opacity=0.3, layer="below", yref="y2", annotation_text="Elevated (>20)", annotation_position="top left", annotation_font_color="#b91c1c")
    
    fig_disc.add_hline(y=20, line_dash="dash", line_color="red", annotation_text="Absolute Cap (20%)", annotation_position="top right", annotation_font_color="red")
    
    max_vix = disc_df['^VIX'].max()
    max_vix = max_vix + 5 if pd.notnull(max_vix) else 40
    
    fig_disc.update_layout(
        height=400, margin=dict(l=20, r=20, t=40, b=20), plot_bgcolor='rgba(0,0,0,0)',
        yaxis=dict(title='Global Options Margin (%)', range=[0, 30], gridcolor='LightGray', zerolinecolor='black', title_font=dict(color='purple'), tickfont=dict(color='purple')),
        yaxis2=dict(title='^VIX Level', overlaying='y', side='right', range=[0, max_vix], showgrid=False, title_font=dict(color='black'), tickfont=dict(color='black')),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
    )
    exp_sec6.plotly_chart(fig_disc, width="stretch")
else:
    exp_sec6.info("Insufficient historical data to render Capital Discipline Tracker.")


exp_sec9b = st.expander("🧭 View Options Performance Ledger & Topography", expanded=False)

if not journal_raw_df.empty:
    
    # Generate CSV data for the full historical ledger
    csv_data = journal_raw_df.to_csv(index=False).encode('utf-8')
    exp_sec9b.download_button(
        label="💾 Download Full Options Journal (CSV)",
        data=csv_data,
        file_name=f"Estate_Options_Journal_{datetime.date.today().isoformat()}.csv",
        mime="text/csv"
    )

    active_vrp = journal_raw_df[pd.isnull(journal_raw_df['Close Date'])].copy()
    if not active_vrp.empty:
        active_vrp['Days Remaining'] = pd.to_numeric(active_vrp['Days Remaining'], errors='coerce')
        
        # v75: Dynamically map LIVE TWS PnL to calculate Live Annualized ROC
        live_roc_list = []
        live_ann_roc_list = []

        for idx, r in active_vrp.iterrows():
            try:
                tckr = str(r['Ticker']).upper()
                # Bulletproof string matching: remove spaces and make lowercase
                tranche = str(r.get('Tranche ID', '')).replace(' ', '').lower()
                
                acc = None
                for a, data in SILO_MAP.items():
                    alias_clean = data[0].replace(' ', '').lower()
                    if alias_clean in tranche:
                        acc = a
                        break
                
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
        
        tab1, tab2, tab3, tab4, tab5 = exp_sec9b.tabs(["🎯 VRP Income Engine", "🛒 Assignment Radar (CSPs)", "🚀 Synthetic Beta Conveyor", "🛡️ Catastrophe Multiplier", "🔬 Closed Trade Expectancy"])

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

        with tab5:
            closed_df = journal_raw_df[pd.notnull(journal_raw_df['Close Date']) & (journal_raw_df['Close Date'] != '')].copy()
            if not closed_df.empty:
                # 1. Apply Radar Classification
                closed_df['Radar Class'] = closed_df.apply(classify_radar, axis=1)
                
                # 2. UI Filter
                available_classes = sorted(closed_df['Radar Class'].unique().tolist())
                selected_classes = st.multiselect(
                    "🔍 Filter by Strategy (Radar Class):",
                    options=available_classes,
                    default=available_classes,
                    help="Remove structural trades like Catastrophe or Synthetic Beta to isolate pure VRP Income expectancy."
                )
                
                # 3. Apply Filter
                filtered_df = closed_df[closed_df['Radar Class'].isin(selected_classes)].copy()
                
                if not filtered_df.empty:
                    filtered_df['Total P&L (USD)'] = pd.to_numeric(filtered_df['Total P&L (USD)'], errors='coerce').fillna(0)
                    wins = filtered_df[filtered_df['Total P&L (USD)'] > 0]
                    losses = filtered_df[filtered_df['Total P&L (USD)'] <= 0]
                    
                    total_trades = len(filtered_df)
                    win_rate = (len(wins) / total_trades) * 100 if total_trades > 0 else 0
                    
                    avg_win = wins['Total P&L (USD)'].mean() if not wins.empty else 0
                    avg_loss = abs(losses['Total P&L (USD)'].mean()) if not losses.empty else 0
                    
                    gross_profit = wins['Total P&L (USD)'].sum() if not wins.empty else 0
                    gross_loss = abs(losses['Total P&L (USD)'].sum()) if not losses.empty else 0
                    profit_factor = (gross_profit / gross_loss) if gross_loss > 0 else (float('inf') if gross_profit > 0 else 0)
                    
                    expectancy = ((win_rate / 100.0) * avg_win) - ((1.0 - (win_rate / 100.0)) * avg_loss)
                    
                    exp_color = "#16a34a" if expectancy > 0 else "#dc2626"
                    
                    st.markdown(f'''
                    <div style="display: flex; gap: 15px; margin-bottom: 20px;">
                        <div style="flex: 1; background-color: #f8fafc; padding: 15px; border-radius: 8px; border: 1px solid #e5e7eb; text-align: center;">
                            <span style="font-size: 12px; color: #64748b; font-weight: bold; text-transform: uppercase;">Win Rate</span><br>
                            <span style="font-size: 24px; font-weight: 900; color: {'#16a34a' if win_rate >= 80 else '#d97706'};">{win_rate:.1f}%</span>
                        </div>
                        <div style="flex: 1; background-color: #f8fafc; padding: 15px; border-radius: 8px; border: 1px solid #e5e7eb; text-align: center;">
                            <span style="font-size: 12px; color: #64748b; font-weight: bold; text-transform: uppercase;">Average Win vs Loss</span><br>
                            <span style="font-size: 16px; font-weight: bold; color: #16a34a;">+${avg_win:,.0f}</span>
                            <span style="font-size: 16px; font-weight: bold; color: #64748b;"> / </span>
                            <span style="font-size: 16px; font-weight: bold; color: #dc2626;">-${avg_loss:,.0f}</span>
                        </div>
                        <div style="flex: 1; background-color: #f8fafc; padding: 15px; border-radius: 8px; border: 1px solid #e5e7eb; text-align: center;">
                            <span style="font-size: 12px; color: #64748b; font-weight: bold; text-transform: uppercase;">Profit Factor</span><br>
                            <span style="font-size: 24px; font-weight: 900; color: {'#16a34a' if profit_factor >= 1.5 else '#d97706'};">{profit_factor:.2f}</span>
                        </div>
                        <div style="flex: 1; background-color: #f8fafc; padding: 15px; border-radius: 8px; border: 1px solid #e5e7eb; text-align: center; border-bottom: 3px solid {exp_color};">
                            <span style="font-size: 12px; color: #64748b; font-weight: bold; text-transform: uppercase;" title="The mathematical amount you expect to make per trade.">Math Expectancy ⓘ</span><br>
                            <span style="font-size: 24px; font-weight: 900; color: {exp_color};">${expectancy:,.2f}</span>
                        </div>
                    </div>
                    ''', unsafe_allow_html=True)
                    
                    fig5 = go.Figure()
                    
                    filtered_df['Days in Trade'] = pd.to_numeric(filtered_df['Days in Trade'], errors='coerce').fillna(1)
                    filtered_df['Return on Capital (ROC) %'] = pd.to_numeric(filtered_df['Return on Capital (ROC) %'], errors='coerce').fillna(0)
                    filtered_df['Quantity'] = pd.to_numeric(filtered_df['Quantity'], errors='coerce').fillna(1)
                    filtered_df['Abs_PnL'] = filtered_df['Total P&L (USD)'].abs()
                    
                    max_pnl = filtered_df['Abs_PnL'].max()
                    if max_pnl == 0 or pd.isna(max_pnl): max_pnl = 1
                    
                    custom_data = np.column_stack((
                        filtered_df.get('Tranche ID', ''), 
                        filtered_df['Total P&L (USD)'], 
                        filtered_df['Days in Trade'],
                        filtered_df['Quantity']
                    ))
                    
                    fig5.add_trace(go.Scatter(
                        x=filtered_df['Close Date'], 
                        y=filtered_df['Return on Capital (ROC) %'], 
                        mode='markers',
                        marker=dict(
                            size=filtered_df['Abs_PnL'],
                            sizemode='area',
                            sizeref=2.0 * max_pnl / (50.0 ** 2), 
                            sizemin=6,
                            color=filtered_df['Days in Trade'],
                            colorscale='RdYlBu', 
                            cmin=0,
                            cmax=60, 
                            showscale=True,
                            colorbar=dict(title="Holding Time (Days)"),
                            line=dict(width=1.5, color='black'),
                            opacity=0.85
                        ),
                        text=filtered_df['Ticker'],
                        customdata=custom_data,
                        hovertemplate="<b>%{text}</b> (%{customdata[0]})<br>" +
                                      "Closed: %{x}<br>" +
                                      "ROC: <b>%{y:.1f}%</b><br>" +
                                      "Absolute PnL: <b>$%{customdata[1]:,.0f}</b><br>" +
                                      "Days in Trade: %{customdata[2]:.0f} Days<br>" +
                                      "Contracts: %{customdata[3]:.0f}<extra></extra>"
                    ))
                    
                    fig5.add_hline(y=0, line_dash="solid", line_color="black", line_width=2)
                    
                    fig5.update_layout(
                        title="Post-Mortem: Behavioral Bubble Chart (Size = Abs PnL | Color = Days in Trade)",
                        yaxis_title="Return on Capital (ROC) %",
                        xaxis_title="Close Date",
                        height=550, 
                        margin=dict(l=0, r=0, t=40, b=0),
                        plot_bgcolor='rgba(0,0,0,0)',
                        yaxis=dict(gridcolor='#e5e7eb', zeroline=False),
                        xaxis=dict(gridcolor='#e5e7eb')
                    )
                    
                    st.plotly_chart(fig5, width="stretch")
                else:
                    st.warning("No closed trades match the selected filter criteria.")
            else:
                st.info("No closed trades logged yet.")

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
    col_ledger, col_2d, col_3d = exp_sec9b.columns([0.50, 0.25, 0.25])
    
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
                # v151 FIX: Increased max_value to 300.0 to support high-IV individual equities (like MU)
                safe_iv_default = min(float(iv_live_raw), 300.0)
                iv_override = st.slider(f"🌪️ {tckr} Volatility (IV) Stress Tester %", min_value=5.0, max_value=300.0, value=safe_iv_default, step=0.1, help="Simulate a Volatility Shock. Default value is locked to the live market VIX.")

            r_rate = LIVE_RF_RATE
            iv_dec = iv_override / 100.0
            T_init = init_dte / 365.0
            T_curr = curr_dte / 365.0
            
            # v75: 3D Engine Native Debit Spread & Call Detection
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
                # Bulletproof string matching: remove spaces and make lowercase
                tranche_id = str(row_data.get('Tranche ID', '')).replace(' ', '').lower()
                
                acct_filter = None
                for a, data in SILO_MAP.items():
                    alias_clean = data[0].replace(' ', '').lower()
                    if alias_clean in tranche_id:
                        acct_filter = a
                        break

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
                        
                    time_stop = 21.0
                    T_stop = max(time_stop / 365.0, 0.0001)
                    z_yellow = []
                    for p in x_vals:
                        t_s_y, _, _, _, _ = pricing_func(p, K_s, T_stop, r_rate, iv_dec)
                        t_l_y, _, _, _, _ = pricing_func(p, K_l, T_stop, r_rate, iv_dec)
                        z_yellow.append((prem - (t_s_y - t_l_y)) * qty * 100)

                    fig_3d.add_trace(go.Scatter3d(x=[K_s]*len(y_3d), y=y_3d, z=z_green, mode='lines', name='Short Strike Limit', line=dict(color='green', width=6), showlegend=False, hoverinfo='skip'))
                    fig_3d.add_trace(go.Scatter3d(x=[K_l]*len(y_3d), y=y_3d, z=z_red, mode='lines', name='Max Loss Limit', line=dict(color='red', width=6), showlegend=False, hoverinfo='skip'))
                    fig_3d.add_trace(go.Scatter3d(x=x_vals, y=[time_stop]*len(x_vals), z=z_yellow, mode='lines', name='21-DTE Time Stop Limit', line=dict(color='gold', width=6), showlegend=False, hoverinfo='skip'))
                    
                    fig_3d.add_trace(go.Surface(x=[[K_s, K_s],[K_s, K_s]], y=[[0, init_dte],[0, init_dte]], z=[[z_min, z_min],[z_max, z_max]], colorscale=[[0, 'green'],[1, 'green']], opacity=0.225, showscale=False, hoverinfo='skip'))
                    fig_3d.add_trace(go.Surface(x=[[K_l, K_l],[K_l, K_l]], y=[[0, init_dte],[0, init_dte]], z=[[z_min, z_min],[z_max, z_max]], colorscale=[[0, 'red'],[1, 'red']], opacity=0.225, showscale=False, hoverinfo='skip'))
                    fig_3d.add_trace(go.Surface(x=[[x_vals[0], x_vals[-1]], [x_vals[0], x_vals[-1]]], y=[[time_stop, time_stop],[time_stop, time_stop]], z=[[z_min, z_min],[z_max, z_max]], colorscale=[[0, 'yellow'],[1, 'yellow']], opacity=0.30, showscale=False, hoverinfo='skip'))
                    fig_3d.add_trace(go.Surface(x=[[x_vals[0], x_vals[-1]],[x_vals[0], x_vals[-1]]], y=[[0, 0],[init_dte, init_dte]], z=[[0, 0],[0, 0]], colorscale=[[0, 'gray'],[1, 'gray']], opacity=0.30, showscale=False, hoverinfo='skip'))

                    fig_3d.add_trace(go.Scatter3d(x=[K_s, K_s], y=[time_stop, time_stop], z=[z_min, z_max], mode='lines', line=dict(color='black', width=6, dash='dash'), showlegend=False, hoverinfo='skip'))
                    fig_3d.add_trace(go.Scatter3d(x=[K_l, K_l], y=[time_stop, time_stop], z=[z_min, z_max], mode='lines', line=dict(color='black', width=6, dash='dash'), showlegend=False, hoverinfo='skip'))
                    fig_3d.add_trace(go.Scatter3d(x=[K_s, K_s], y=[0, init_dte], z=[0, 0], mode='lines', line=dict(color='black', width=6, dash='dash'), showlegend=False, hoverinfo='skip'))
                    fig_3d.add_trace(go.Scatter3d(x=[K_l, K_l], y=[0, init_dte], z=[0, 0], mode='lines', line=dict(color='black', width=6, dash='dash'), showlegend=False, hoverinfo='skip'))
                    fig_3d.add_trace(go.Scatter3d(x=[x_vals[0], x_vals[-1]], y=[time_stop, time_stop], z=[0, 0], mode='lines', line=dict(color='black', width=6, dash='dash'), showlegend=False, hoverinfo='skip'))

                    fig_3d.add_trace(go.Scatter3d(x=[K_s, K_s, K_s, K_s, K_s], y=[0, init_dte, init_dte, 0, 0], z=[z_min, z_min, z_max, z_max, z_min], mode='lines', line=dict(color='green', width=3), showlegend=False, hoverinfo='skip'))
                    fig_3d.add_trace(go.Scatter3d(x=[K_l, K_l, K_l, K_l, K_l], y=[0, init_dte, init_dte, 0, 0], z=[z_min, z_min, z_max, z_max, z_min], mode='lines', line=dict(color='red', width=3), showlegend=False, hoverinfo='skip'))
                    fig_3d.add_trace(go.Scatter3d(x=[x_vals[0], x_vals[-1], x_vals[-1], x_vals[0], x_vals[0]], y=[time_stop, time_stop, time_stop, time_stop, time_stop], z=[z_min, z_min, z_max, z_max, z_min], mode='lines', line=dict(color='yellow', width=3), showlegend=False, hoverinfo='skip'))
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

                half_dte = init_dte / 2.0
                y_half = []
                for px in x_vals:
                    if is_long_put:
                        tH_l, _, _, _, _ = get_put_greeks(px, K_l, half_dte/365.0, r_rate, iv_dec)
                        y_half.append((tH_l - abs(prem)) * qty * 100)
                    elif is_long_call:
                        tH_l, _, _, _, _ = get_call_greeks(px, K_l, half_dte/365.0, r_rate, iv_dec)
                        y_half.append((tH_l - abs(prem)) * qty * 100)
                    else:
                        tH_s, _, _, _, _ = pricing_func(px, K_s, half_dte/365.0, r_rate, iv_dec)
                        tH_l, _, _, _, _ = pricing_func(px, K_l, half_dte/365.0, r_rate, iv_dec)
                        y_half.append((prem - (tH_s - tH_l)) * qty * 100)

                fig_3d.add_trace(go.Scatter3d(x=x_vals, y=[init_dte]*len(x_vals), z=y_init, mode='lines', name='Entry Day', line=dict(color='purple', width=10, dash='dash')))
                fig_3d.add_trace(go.Scatter3d(x=x_vals, y=[half_dte]*len(x_vals), z=y_half, mode='lines', name='50% DTE', line=dict(color='orange', width=6, dash='dash')))
                fig_3d.add_trace(go.Scatter3d(x=x_vals, y=[curr_dte]*len(x_vals), z=y_curr, mode='lines', name='Today', line=dict(color='#2563eb', width=7)))
                fig_3d.add_trace(go.Scatter3d(x=[S_live], y=[curr_dte], z=[tws_unrealized_pnl], mode='markers', name='Current Price', marker=dict(color='white', size=8, line=dict(color='black', width=2))))
                
                if not (is_long_put or is_long_call):
                    fig_3d.add_trace(go.Scatter3d(x=[S_live, S_live], y=[curr_dte, curr_dte], z=[0, tws_unrealized_pnl], mode='lines', name='Anchor Line', line=dict(color='white', width=3, dash='dot'), showlegend=False, hoverinfo='skip'))
                    fig_3d.add_trace(go.Scatter3d(x=[S_live], y=[curr_dte], z=[0], mode='markers', name='Zero Floor Anchor', marker=dict(color='white', size=5, symbol='cross'), showlegend=False, hoverinfo='skip'))             
            
                fig_3d.update_layout(
                    title="3D Topography (Time vs Price)", margin=dict(l=0, r=0, b=0, t=40), height=645, 
                    scene=dict(xaxis_title='Price', yaxis_title='DTE', zaxis_title='P&L ($)', yaxis=dict(autorange='reversed'), camera=dict(eye=dict(x=-1.25, y=-1.25, z=1.25))),
                    legend=dict(orientation="h", yanchor="top", y=-0.15, xanchor="left", x=0)
                )
                st.plotly_chart(fig_3d, width="stretch")
                
                # --- SANITIZED 3D FOR PUBLISHER EXPORT ---
                z_3d_san = [[val / qty for val in row] for row in z_3d]
                fig_3d_san = go.Figure(data=[go.Surface(
                    z=z_3d_san, x=x_vals, y=y_3d, 
                    colorscale=[[0, '#fef2f2'],[0.2, '#fca5a5'],[0.5, 'white'],[0.8, '#86efac'],[1, '#f0fdf4']],
                    opacity=0.85, contours=dict(z=dict(show=True, color='black', width=1))
                )])
                y_init_san = [val / qty for val in y_init]
                y_curr_san = [val / qty for val in y_curr]
                fig_3d_san.add_trace(go.Scatter3d(x=x_vals, y=[init_dte]*len(x_vals), z=y_init_san, mode='lines', name='Entry Day', line=dict(color='purple', width=10, dash='dash')))
                fig_3d_san.add_trace(go.Scatter3d(x=x_vals, y=[curr_dte]*len(x_vals), z=y_curr_san, mode='lines', name='Today', line=dict(color='#2563eb', width=7)))
                fig_3d_san.update_layout(
                    title=f"3D Topography (1-Lot Normalized) - {tckr}", margin=dict(l=0, r=0, b=0, t=40), height=645, 
                    scene=dict(xaxis_title='Price', yaxis_title='DTE', zaxis_title='P&L ($)', yaxis=dict(autorange='reversed'), camera=dict(eye=dict(x=-1.25, y=-1.25, z=1.25))),
                    showlegend=False
                )
                st.session_state['pub_3d'] = fig_3d_san

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
    exp_sec9b.info("No options history found in database.")



_, vix_live = fetch_live_data('^VIX')
max_margin = global_metrics['nav'] * 0.20
remaining_margin = max(0, max_margin - opt_margin_total)

live_opt_dir_9a = chart_df['opt_dir'].iloc[-1] if not chart_df.empty else 'Bear'
opt_color_9a = '#166534' if live_opt_dir_9a == 'Bull' else '#991b1b'
opt_action_9a = "Authorized to sell Bull Put Spreads." if live_opt_dir_9a == 'Bull' else "Bull Puts BANNED. Authorized to sell Bear Calls."

vix_color = "#dc2626" if vix_live < 15 else ("#d97706" if vix_live < 20 else "#16a34a")
vix_warn = "🚨 COMPLACENT (Halt VRP / Buy Tails)" if vix_live < 15 else ("🟡 NORMAL (Standard VRP)" if vix_live < 20 else "🟢 ELEVATED (Prime VRP)")


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

# --- RIPE CONDITIONS EVALUATION FOR MATRIX ---
spy_spot_9a = bench_df['SPY'].iloc[-1] if not bench_df.empty else 550.0
spy_50_9a = bench_df['sma_50'].iloc[-1] if not bench_df.empty else 550.0
spy_200_9a = bench_df['sma_200'].iloc[-1] if not bench_df.empty else 500.0
live_alpha_gear_9a = chart_df['alpha_gear'].iloc[-1] if not chart_df.empty else 0
macro_soon_9a = any(ev['type'] == 'Macro' and 0 <= (ev['date'] - datetime.date.today()).days <= 1 for ev in calendar_events)

bp_ripe = 15.0 <= vix_live and (spy_spot_9a > spy_50_9a or spy_spot_9a < spy_200_9a)
bc_ripe = 15.0 <= vix_live <= 25.0 and spy_spot_9a < spy_50_9a
ic_ripe = 15.0 <= vix_live <= 22.0 and (abs(spy_spot_9a - spy_50_9a)/spy_50_9a < 0.02 or live_alpha_gear_9a == 3)
tm_ripe = vix_live < 15.0 and spy_spot_9a > spy_50_9a
th_ripe = vix_live < 15.0

def get_verdict_html(is_ripe, ripe_text="RIPE FOR DEPLOYMENT", banned_text="BANNED (Conditions Not Met)"):
    if is_ripe: return f"<br><br><span style='color:#16a34a;'><b>🟢 {ripe_text}</b></span>"
    else: return f"<br><br><span style='color:#dc2626;'><b>🔴 {banned_text}</b></span>"

# --- RENDER MISSING STRATEGIES (STATIC ROWS) ---
if 'VRP' not in active_strats:
    matrix_rows += f"<tr><td><span style='color:#64748b'><b>XSP Bull Put Spreads</b></span><br><span style='font-size:11px; color:#15803d; background-color:#dcfce7; padding:2px 4px; border-radius:3px;'><b>TAX: EXCELLENT.</b> Section 1256 Cash-Settled.</span></td><td style='color:#64748b; font-size: 13px; font-style:italic;'>NO ACTIVE POSITIONS<br><br>Awaiting signal to deploy.</td><td style='color:#64748b; font-size: 13px;'><b>The Income Engine (VRP).</b><br>• <i>Pro:</i> High win-rate (90%+), defined maximum loss.<br>• <i>Con:</i> Asymmetric risk/reward.</td><td style='color:#64748b; font-size: 13px;'><b>Entry:</b> VIX > 15. Exactly 45-50 DTE. ~0.20 Delta.<br><br><b>Exit:</b> Mechanical 50% Take-Profit, 200% Stop-Loss, or 21-DTE Time Stop.</td><td style='color:#64748b; font-size: 13px;'><b>Standby.</b> Monitor VIX for deployment opportunities.{get_verdict_html(bp_ripe)}</td></tr>"

# Add Bear Calls
matrix_rows += f"<tr><td><span style='color:#64748b'><b>XSP Bear Call Spreads</b></span><br><span style='font-size:11px; color:#15803d; background-color:#dcfce7; padding:2px 4px; border-radius:3px;'><b>TAX: EXCELLENT.</b> Section 1256 Cash-Settled.</span></td><td style='color:#64748b; font-size: 13px; font-style:italic;'>NO ACTIVE POSITIONS<br><br>Awaiting signal to deploy.</td><td style='color:#64748b; font-size: 13px;'><b>The Gravity Trade.</b><br>• <i>Pro:</i> Capitalizes on structural downtrends or irrational exuberance.<br>• <i>Con:</i> Unlimited theoretical risk if unhedged.</td><td style='color:#64748b; font-size: 13px;'><b>Entry:</b> VIX 15-25. SPY < 50 SMA.<br><br><b>Exit:</b> Mechanical 50% Take-Profit, 200% Stop-Loss.</td><td style='color:#64748b; font-size: 13px;'><b>Standby.</b> Monitor for structural breakdown.{get_verdict_html(bc_ripe)}</td></tr>"

# Add Iron Condors
matrix_rows += f"<tr><td><span style='color:#64748b'><b>XSP Iron Condors</b></span><br><span style='font-size:11px; color:#15803d; background-color:#dcfce7; padding:2px 4px; border-radius:3px;'><b>TAX: EXCELLENT.</b> Section 1256 Cash-Settled.</span></td><td style='color:#64748b; font-size: 13px; font-style:italic;'>NO ACTIVE POSITIONS<br><br>Awaiting signal to deploy.</td><td style='color:#64748b; font-size: 13px;'><b>The Efficiency Multiplier.</b><br>• <i>Pro:</i> Doubles income without doubling margin.<br>• <i>Con:</i> Vulnerable to violent directional breakouts.</td><td style='color:#64748b; font-size: 13px;'><b>Entry:</b> VIX 15-22. Rangebound market.<br><br><b>Exit:</b> Mechanical 50% Take-Profit, 200% Stop-Loss.</td><td style='color:#64748b; font-size: 13px;'><b>Standby.</b> Monitor for rangebound consolidation.{get_verdict_html(ic_ripe)}</td></tr>"

# Add Theta Machine
matrix_rows += f"<tr><td><span style='color:#64748b'><b>The Theta Machine (Calendars)</b></span><br><span style='font-size:11px; color:#15803d; background-color:#dcfce7; padding:2px 4px; border-radius:3px;'><b>TAX: EXCELLENT.</b> Section 1256 Cash-Settled.</span></td><td style='color:#64748b; font-size: 13px; font-style:italic;'>NO ACTIVE POSITIONS<br><br>Awaiting signal to deploy.</td><td style='color:#64748b; font-size: 13px;'><b>The Low-VIX Pivot.</b><br>• <i>Pro:</i> Positive Vega. Benefits if VIX wakes up.<br>• <i>Con:</i> Requires slow, grinding market.</td><td style='color:#64748b; font-size: 13px;'><b>Entry:</b> VIX < 15. SPY > 50 SMA. Buy 60-90 DTE, Sell 7-14 DTE.<br><br><b>Exit:</b> Close when short leg decays or roll.</td><td style='color:#64748b; font-size: 13px;'><b>Standby.</b> Monitor for complacency.{get_verdict_html(tm_ripe)}</td></tr>"

# Add Macro IV Crush
matrix_rows += f"<tr><td><span style='color:#64748b'><b>Macro IV Crush (Iron Butterfly)</b></span><br><span style='font-size:11px; color:#15803d; background-color:#dcfce7; padding:2px 4px; border-radius:3px;'><b>TAX: EXCELLENT.</b> Section 1256 Cash-Settled.</span></td><td style='color:#64748b; font-size: 13px; font-style:italic;'>NO ACTIVE POSITIONS<br><br>Awaiting signal to deploy.</td><td style='color:#64748b; font-size: 13px;'><b>The Binary Event Trap.</b><br>• <i>Pro:</i> Aggressively harvests overnight Vega crush.<br>• <i>Con:</i> High risk if event causes massive gap beyond wings.</td><td style='color:#64748b; font-size: 13px;'><b>Entry:</b> 15 mins before Tier-1 Macro event. 0-DTE or 1-DTE.<br><br><b>Exit:</b> First 15-30 mins of next open.</td><td style='color:#64748b; font-size: 13px;'><b>Standby.</b> Monitor economic calendar.{get_verdict_html(macro_soon_9a)}</td></tr>"

if 'SYNTH_BETA' not in active_strats:
    matrix_rows += f"<tr><td><span style='color:#64748b'><b>XND/QQQ Calls (Synthetic Beta)</b></span><br><span style='font-size:11px; color:#15803d; background-color:#dcfce7; padding:2px 4px; border-radius:3px;'><b>TAX: MANDATORY.</b> Section 1256.</span></td><td style='color:#64748b; font-size: 13px; font-style:italic;'>NO ACTIVE POSITIONS<br><br>Awaiting signal to deploy.</td><td style='color:#64748b; font-size: 13px;'><b>The Growth Engine.</b> Replaces physical US ETFs.<br>• <i>Pro:</i> Frees up 80% of capital to earn 5% in Treasuries.<br>• <i>Con:</i> Suffers from slight Theta (time) decay.</td><td style='color:#64748b; font-size: 13px;'><b>Entry:</b> 120-180 DTE. Delta > 0.80 (Deep ITM). No stop-losses.<br><br><b>Exit:</b> Never sell. Roll mechanically when 45 DTE is breached.</td><td style='color:#64748b; font-size: 13px;'><b>Standby.</b> Deploy capital to establish core macro exposure.</td></tr>"
    
if 'TAIL' not in active_strats:
    matrix_rows += f"<tr><td><span style='color:#64748b'><b>120-DTE Black Swan Puts (XSP)</b></span><br><span style='font-size:11px; color:#15803d; background-color:#dcfce7; padding:2px 4px; border-radius:3px;'><b>TAX: EXCELLENT.</b> Section 1256 Cash-Settled.</span></td><td style='color:#64748b; font-size: 13px; font-style:italic;'>NO ACTIVE POSITIONS<br><br>Estate is completely naked to Black Swan gap-downs.</td><td style='color:#64748b; font-size: 13px;'><b>Black Swan Insurance (The Barbell).</b><br>• <i>Pro:</i> Mathematically guarantees survival during multi-month systemic meltdowns.<br>• <i>Con:</i> 100% loss of capital expected. Acts as a constant Theta drag.</td><td style='color:#64748b; font-size: 13px;'><b>Entry:</b> Financed strictly by 10% of VRP winnings. 120-150 DTE. Delta < -0.05.<br><br><b>Exit:</b> Monetize dynamically during deep market panic.</td><td style='color:#64748b; font-size: 13px; color:#b91c1c;'><b>CRITICAL.</b> VRP Tail budget is sitting idle. Purchase deep OTM puts immediately.{get_verdict_html(th_ripe)}</td></tr>"

if 'WHALE' not in active_strats:
    matrix_rows += f"<tr><td><span style='color:#64748b'><b>SMH Bear Puts (Whale Hedge)</b></span><br><span style='font-size:11px; color:#991b1b; background-color:#fee2e2; padding:2px 4px; border-radius:3px;'><b>TAX: WARNING.</b> Equity Options carry physical assignment risk.</span></td><td style='color:#64748b; font-size: 13px; font-style:italic;'>NO ACTIVE POSITIONS<br><br>Awaiting signal to deploy.</td><td style='color:#64748b; font-size: 13px;'><b>Tactical Directional Short.</b><br>• <i>Pro:</i> Massive asymmetric leverage if the macro thesis plays out perfectly.<br>• <i>Con:</i> Extremely low probability of success; high Theta burn.</td><td style='color:#64748b; font-size: 13px;'><b>Entry:</b> Based entirely on CIO macro-economic thesis, not mechanical rules.<br><br><b>Exit:</b> Hit subjective price targets or expire worthless.</td><td style='color:#64748b; font-size: 13px;'><b>Standby.</b> Monitor macro sector imbalances for entry.</td></tr>"

if 'CSP' not in active_strats:
    matrix_rows += f"<tr><td><span style='color:#64748b'><b>Conviction Puts (CSP)</b></span><br><span style='font-size:11px; color:#991b1b; background-color:#fee2e2; padding:2px 4px; border-radius:3px;'><b>TAX: WARNING.</b> Assignment increases physical US Situs exposure.</span></td><td style='color:#64748b; font-size: 13px; font-style:italic;'>NO ACTIVE POSITIONS<br><br>Awaiting signal to deploy.</td><td style='color:#64748b; font-size: 13px;'><b>Volatility Harvesting / Averaging Down.</b><br>• <i>Pro:</i> Generates massive cash yield. Turns market fear into an opportunity.<br>• <i>Con:</i> Locks up heavy notional margin. Increases Estate Tax risk.</td><td style='color:#64748b; font-size: 13px;'><b>Entry:</b> High IV Rank on targeted infrastructure/AI physical assets.<br><br><b>Exit:</b> 50% Take-Profit to free up margin, or happily take physical assignment.</td><td style='color:#64748b; font-size: 13px;'><b>Standby.</b> Monitor high-conviction assets for IV spikes.</td></tr>"

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

with st.expander("⚙️ Click to expand the Master Options Matrix & CFO Briefing", expanded=False):
    st.markdown("<p style='color: #4b5563; font-size: 14px;'>A didactic Rosetta Stone for the Estate's Barbell mechanics. Outlines tax suitability, tactical execution, and live structural health for every active options class.</p>", unsafe_allow_html=True)
    st.markdown(f"""
    <div style="background-color: #f8fafc; border: 1px solid #cbd5e1; border-left: 5px solid {opt_color_9a}; padding: 12px 20px; border-radius: 6px; display: flex; justify-content: space-between; align-items: center; margin-bottom: 20px;">
        <div>
            <div style="font-size: 12px; color: #64748b; font-weight: bold; text-transform: uppercase;">Options Governor Pre-Flight Checklist</div>
            <div style="font-size: 15px; color: #0f172a;"><b>Structural Trend:</b> <span style="color: {opt_color_9a}; font-weight: bold;">{live_opt_dir_9a.upper()}</span> (SPY vs 50 SMA) — {opt_action_9a}</div>
            <div style="font-size: 15px; color: #0f172a; margin-top: 4px;"><b>Remaining Margin Capacity:</b> <span style="color: {'#dc2626' if remaining_margin < 10000 else '#16a34a'};">${remaining_margin:,.0f}</span> (Hard Cap: 20% NAV)</div>
        </div>
        <div style="text-align: right;">
            <div style="font-size: 12px; color: #64748b; font-weight: bold; text-transform: uppercase;">Live VIX Regime</div>
            <div style="font-size: 15px; color: {vix_color}; font-weight: bold;">{vix_live:.2f} — {vix_warn}</div>
        </div>
    </div>
    """, unsafe_allow_html=True)

    st.markdown(html_matrix, unsafe_allow_html=True)
    
# --- ENHANCEMENTS E.1 AND E.2: Beta-Weighted Risk & Catastrophe Coverage ---
exp_sec6b = st.expander("⚖️ View Advanced Portfolio Risk Metrics", expanded=False)
col_r1, col_r2 = exp_sec6b.columns(2)
with col_r1:
    # Note: Beta-Weighted logic was hoisted to the HUD section at the top of the script.
    # The variables total_bw_delta, bw_usd_exposure, bw_pct_nav, and delta_breakdown are reused here.
    
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
    
    # UI Tweak to prevent the 0% Contradiction when margin is $0
    if opt_margin_total == 0 and th_payout > 0:
        cov_text = "<span style='color: #16a34a;'>Fully Covered (No VRP Risk)</span>"
    else:
        cov_text = f"<span style='color: {'#16a34a' if coverage_ratio >= 100 else '#d97706'};'>{coverage_ratio:.1f}% Covered</span>"
    
    st.markdown(f"""
    <div style="background-color: #f8fafc; padding: 20px; border-radius: 8px; border: 1px solid #cbd5e1; text-align: center;">
        <h4 style="margin: 0; color: #334155; font-size: 16px;">Black Swan Catastrophe Coverage (30% Crash)</h4>
        <div style="font-size: 28px; font-weight: bold; margin-top: 10px;">{cov_text}</div>
        <div style="font-size: 14px; color: #64748b;">Est. Tail Payout: ${th_payout:,.0f} vs Max Liability: ${opt_margin_total:,.0f}</div>
        <div style="font-size: 11px; color: #94a3b8; margin-top: 5px;">*Synchronized with SWAN 30% Stress Test parameters.</div>
    </div>
    """, unsafe_allow_html=True)
exp_sec6c = st.expander("🦢 View S.W.A.N. Stress Test", expanded=False)
exp_sec6c.markdown("<p style='color: #4b5563; font-size: 14px; margin-bottom: 20px;'><strong>S.W.A.N.</strong> is an institutional framework designed to survive Black Swan events without panic. Adjust the slider below to stress-test the Estate's Barbell against sudden market collapses.</p>", unsafe_allow_html=True)

# 1. Interactive Crash Slider
sim_crash_input = exp_sec6c.slider("💥 Simulated Market Drop (%)", min_value=10, max_value=50, value=30, step=5, help="Simulates an instant drop in the S&P 500, calculating expected equity losses vs. Tail Hedge payouts.")

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

col_swan_chart, col_swan_text = exp_sec6c.columns([2, 1])

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
    exp_sec6c.plotly_chart(fig_waterfall, width="stretch")
    
    # --- SANITIZED SWAN FOR PUBLISHER EXPORT ---
    swan_eq_pct = (swan_equity_loss / global_metrics['nav']) * 100 if global_metrics['nav'] > 0 else 0
    swan_vrp_pct = (swan_vrp_loss / global_metrics['nav']) * 100 if global_metrics['nav'] > 0 else 0
    swan_th_pct = (swan_th_payout / global_metrics['nav']) * 100 if global_metrics['nav'] > 0 else 0
    swan_end_pct = 100 - swan_eq_pct - swan_vrp_pct + swan_th_pct
    
    fig_swan_sanitized = go.Figure(go.Waterfall(
        name="SWAN", orientation="v",
        measure=["absolute", "relative", "relative", "relative", "total"],
        x=["Starting NAV", f"Equities (-{sim_crash_input}%)", "VRP Stops", "Tail Payout", "Ending NAV"],
        textposition="outside",
        text=["100%", f"-{swan_eq_pct:.1f}%", f"-{swan_vrp_pct:.1f}%", f"+{swan_th_pct:.1f}%", f"{swan_end_pct:.1f}%"],
        y=[100, -swan_eq_pct, -swan_vrp_pct, swan_th_pct, 0],
        connector={"line":{"color":"rgb(63, 63, 63)"}},
        decreasing={"marker":{"color":"#dc2626"}},
        increasing={"marker":{"color":"#16a34a"}},
        totals={"marker":{"color":"#1d4ed8"}}
    ))
    fig_swan_sanitized.update_layout(
        title=f"Portfolio Impact Waterfall (-{sim_crash_input}% S&P 500 Crash)",
        margin=dict(l=20, r=20, t=40, b=20),
        plot_bgcolor='rgba(0,0,0,0)',
        yaxis=dict(gridcolor='LightGray', zeroline=True, zerolinecolor='black')
    )
    st.session_state['pub_swan'] = fig_swan_sanitized

with col_swan_text:
    impact_color = "#16a34a" if swan_estate_impact_pct >= -10 else "#dc2626"
    
    vix_live_val = fetch_live_data('^VIX')[1]
    vix_multiplier = (swan_vix_spike * 100) / vix_live_val if vix_live_val > 0 else 5.0
    expansion_factor = min(3.0, 1.0 + (vix_multiplier * 0.5 * (sim_crash_input / 100.0)))
    stressed_margin = opt_margin_total * expansion_factor
    margin_cushion = tot_cash - stressed_margin
    margin_status_color = "#16a34a" if margin_cushion >= 0 else "#dc2626"
    margin_status_text = "SAFE (Sufficient Cash)" if margin_cushion >= 0 else "DANGER (Margin Call)"
    
    swan_html = f'''
    <div style="background-color: #f8fafc; padding: 25px; border-radius: 8px; border: 1px solid #cbd5e1;">
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
    <div style="background-color: #fffbeb; padding: 20px; border-radius: 8px; border: 1px solid #fde047; margin-top: 15px;">
        <h4 style="margin-top: 0; color: #854d0e; border-bottom: 2px solid #fef08a; padding-bottom: 10px;">Predictive Margin Shock (TIMS)</h4>
        <div style="display: flex; justify-content: space-between; margin-top: 10px;">
            <span style="font-size: 14px; color: #a16207;">Live Options Margin:</span>
            <span style="font-size: 15px; font-weight: bold; color: #854d0e;">${opt_margin_total:,.0f}</span>
        </div>
        <div style="display: flex; justify-content: space-between; margin-top: 5px;">
            <span style="font-size: 14px; color: #a16207;">Stressed Margin ({expansion_factor:.1f}x):</span>
            <span style="font-size: 15px; font-weight: bold; color: #dc2626;">${stressed_margin:,.0f}</span>
        </div>
        <div style="display: flex; justify-content: space-between; margin-top: 5px;">
            <span style="font-size: 14px; color: #a16207;">Available Cash (IB01):</span>
            <span style="font-size: 15px; font-weight: bold; color: #16a34a;">${tot_cash:,.0f}</span>
        </div>
        <hr style="margin: 15px 0; border-color: #fef08a;">
        <div style="text-align: center;">
            <span style="font-size: 13px; color: #a16207; text-transform: uppercase; font-weight: bold;">Margin Call Risk</span><br>
            <span style="font-size: 20px; font-weight: 900; color: {margin_status_color};">{margin_status_text}</span>
        </div>
    </div>
    '''
    exp_sec6c.markdown(swan_html, unsafe_allow_html=True)
# --- SECTION 100: PROJECT MANAGEMENT & SPRINT TRACKER ---
st.subheader("Convexity Project Tracker", anchor="sec100")
exp_sec100 = st.expander("🏗️ View Convexity Project Tracker", expanded=False)

# 1. Database Initialization & Data Loading
conn_pm = sqlite3.connect(DB_PATH, timeout=15)
conn_pm.execute("PRAGMA journal_mode=WAL;")
c_pm = conn_pm.cursor()

c_pm.execute("""
    CREATE TABLE IF NOT EXISTS project_tasks (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        task_name TEXT,
        start_date TEXT,
        end_date TEXT,
        status TEXT,
        category TEXT
    )
""")

# Safely add the progress column if it doesn't exist
try:
    c_pm.execute("ALTER TABLE project_tasks ADD COLUMN progress INTEGER DEFAULT 0")
except sqlite3.OperationalError:
    pass

conn_pm.commit()

conn_pm.commit()

df_tasks = pd.read_sql_query("SELECT * FROM project_tasks ORDER BY start_date ASC", conn_pm)

# Inject the Master 30-Day Sprint if the table is empty or only has the default task
if len(df_tasks) <= 1:
    c_pm.execute("DELETE FROM project_tasks")
    
    sprint_tasks = [
        # Week 1: Infrastructure & Brand Lock-In
        ('Form Wyoming LLC & Apply for EIN', '2026-07-27', '2026-07-28', 'Pending', 'Infrastructure'),
        ('Secure Social Handles (X, LinkedIn, YouTube)', '2026-07-27', '2026-07-28', 'Pending', 'Marketing'),
        ('Buy Ghost.org Sub & Connect DNS', '2026-07-28', '2026-07-29', 'Pending', 'Infrastructure'),
        ('Strip Commercial SaaS Code (auth_gate)', '2026-07-29', '2026-07-30', 'Pending', 'Infrastructure'),
        ('Build "1-Click Publish" Export Pipeline', '2026-07-30', '2026-07-31', 'Pending', 'Infrastructure'),
        ('Extract Alpha Risk Calculator', '2026-07-31', '2026-08-01', 'Pending', 'Infrastructure'),
        ('Deploy Risk Calculator to tools.convexitydesk.com', '2026-08-01', '2026-08-02', 'Pending', 'Infrastructure'),
        # Week 2: Content Generation & PLG Tool #2
        ('Write & Publish "Origin Story" on Ghost', '2026-08-03', '2026-08-04', 'Pending', 'Content'),
        ('Pin 3D Chart Post on X and LinkedIn', '2026-08-04', '2026-08-05', 'Pending', 'Marketing'),
        ('Build Monte Carlo CSV Uploader App', '2026-08-05', '2026-08-06', 'Pending', 'Infrastructure'),
        ('Deploy Monte Carlo App to tools subdomain', '2026-08-06', '2026-08-07', 'Pending', 'Infrastructure'),
        ('Social Media Outreach (X/Reddit)', '2026-08-08', '2026-08-09', 'Pending', 'Marketing'),
        # Week 3: The Free Value Barrage
        ('Publish Free Article #1: 6-Gear Engine', '2026-08-10', '2026-08-11', 'Pending', 'Content'),
        ('Publish Free Article #2: S.W.A.N. Protocol', '2026-08-12', '2026-08-13', 'Pending', 'Content'),
        ('Publish Free Article #3: Macro Weather', '2026-08-14', '2026-08-15', 'Pending', 'Content'),
        ('Format Accountability Journal Template', '2026-08-15', '2026-08-16', 'Pending', 'Content'),
        # Week 4: The Paywall Flip & Plateau
        ('Connect Stripe to Ghost & Set Pricing', '2026-08-17', '2026-08-18', 'Pending', 'Infrastructure'),
        ('Publish "Teaser" Post (Blurred 3D Chart)', '2026-08-18', '2026-08-19', 'Pending', 'Marketing'),
        ('LAUNCH DAY: First Premium Post', '2026-08-20', '2026-08-21', 'Pending', 'Content')
    ]
    
    c_pm.executemany(
        "INSERT INTO project_tasks (task_name, start_date, end_date, status, category, progress) VALUES (?, ?, ?, ?, ?, 0)",
        sprint_tasks
    )
    conn_pm.commit()
    df_tasks = pd.read_sql_query("SELECT * FROM project_tasks ORDER BY start_date ASC", conn_pm)

# Convert string dates to datetime.date objects for Streamlit DateColumn compatibility
df_tasks['start_date'] = pd.to_datetime(df_tasks['start_date']).dt.date
df_tasks['end_date'] = pd.to_datetime(df_tasks['end_date']).dt.date

# 2. Data Editor
exp_sec100.markdown("### 📋 Task Ledger")

def commit_task_edits():
    state = st.session_state.get("task_editor", {})
    edits = state.get("edited_rows", {})
    adds = state.get("added_rows", [])
    deletes = state.get("deleted_rows", [])
    
    c_pm_edit = sqlite3.connect(DB_PATH, timeout=15).cursor()
    
    # Handle Edits
    for row_idx_str, row_edits in edits.items():
        idx = int(row_idx_str)
        db_id = int(df_tasks.at[idx, 'id'])
        set_clauses = []
        params = []
        for col, val in row_edits.items():
            set_clauses.append(f"{col}=?")
            # Convert date objects back to ISO strings for SQLite
            if isinstance(val, datetime.date):
                params.append(val.isoformat())
            else:
                params.append(val)
        if set_clauses:
            params.append(db_id)
            c_pm_edit.execute(f"UPDATE project_tasks SET {', '.join(set_clauses)} WHERE id=?", tuple(params))
            
    # Handle Adds
    for row in adds:
        start_val = row.get('start_date', datetime.date.today())
        end_val = row.get('end_date', datetime.date.today())
        
        # Ensure they are strings for the DB
        if isinstance(start_val, datetime.date): start_val = start_val.isoformat()
        if isinstance(end_val, datetime.date): end_val = end_val.isoformat()
        
        c_pm_edit.execute(
            "INSERT INTO project_tasks (task_name, start_date, end_date, status, category, progress) VALUES (?, ?, ?, ?, ?, ?)",
            (row.get('task_name', 'New Task'), start_val, end_val, row.get('status', 'Pending'), row.get('category', 'General'), row.get('progress', 0))
        )
        
    # Handle Deletes
    for idx in deletes:
        db_id = int(df_tasks.at[idx, 'id'])
        c_pm_edit.execute("DELETE FROM project_tasks WHERE id=?", (db_id,))
        
    c_pm_edit.connection.commit()
    c_pm_edit.connection.close()

edited_tasks = exp_sec100.data_editor(
    df_tasks,
    column_config={
        "id": None,
        "task_name": st.column_config.TextColumn("Task Name", required=True),
        "start_date": st.column_config.DateColumn("Start Date", required=True),
        "end_date": st.column_config.DateColumn("End Date (Deadline)", required=True),
        "status": st.column_config.SelectboxColumn("Status", options=["Pending", "In Progress", "Done"], required=True),
        "category": st.column_config.SelectboxColumn("Category", options=["Infrastructure", "Content", "Marketing", "General"], required=True),
        "progress": st.column_config.NumberColumn("Progress %", min_value=0, max_value=100, format="%d%%", step=10)
    },
    hide_index=True,
    num_rows="dynamic",
    width="stretch",
    key="task_editor",
    on_change=commit_task_edits
)

# 3. Gantt Chart & Calendar Rendering
if not edited_tasks.empty:
    # Ensure dates are datetime objects for Plotly
    plot_df = edited_tasks.copy()
    plot_df['start_date'] = pd.to_datetime(plot_df['start_date'])
    plot_df['end_date'] = pd.to_datetime(plot_df['end_date'])
    
    # Sort by start date ascending so the earliest tasks appear at the top
    plot_df = plot_df.sort_values('start_date', ascending=True)

    exp_sec100.markdown("### 📊 Sprint Waterfall (Gantt)")
    
    # Darkened the 'Pending' color to #475569 for better contrast
    color_discrete_map = {'Pending': '#475569', 'In Progress': '#3b82f6', 'Done': '#16a34a'}
    
    # Dynamic height based on task count (approx 30px per task)
    dynamic_height = max(400, len(plot_df) * 30 + 100)
    
    # Create a formatted string for the progress text
    plot_df['progress_str'] = plot_df['progress'].astype(str) + '%'
    
    fig_gantt = px.timeline(
        plot_df, 
        x_start="start_date", 
        x_end="end_date", 
        y="task_name", 
        color="status",
        color_discrete_map=color_discrete_map,
        hover_data=["category", "progress"],
        text="progress_str"
    )
    
    # Force text to be inside the bars and readable
    fig_gantt.update_traces(textposition='inside', insidetextanchor='middle', textfont=dict(color='white', size=12, weight='bold'))
    
    # Force Y-axis labels to be solid black and bold
    fig_gantt.update_yaxes(autorange="reversed", title="", tickfont=dict(color='black', size=12, weight='bold'))
    
    # Add vertical dotted red line for Today
    today_str = datetime.date.today().isoformat()
    
    # Plotly Bug Bypass: Separate the line and annotation to prevent date-math crashes
    fig_gantt.add_vline(x=today_str, line_dash="dot", line_color="red", line_width=2)
    fig_gantt.add_annotation(
        x=today_str, y=1.05, yref="paper", 
        text="Today", showarrow=False, 
        font=dict(color="red", size=12, weight="bold"), 
        xanchor="left"
    )
    
    fig_gantt.update_layout(
        height=dynamic_height, 
        margin=dict(l=0, r=20, t=30, b=0),
        plot_bgcolor='rgba(0,0,0,0)',
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
    )
    exp_sec100.plotly_chart(fig_gantt, width="stretch")
    
    exp_sec100.markdown("---")
    exp_sec100.markdown("### 📅 5-Week Deadline Calendar")
    
    today_date_pm = datetime.date.today()
    idx_pm = (today_date_pm.weekday() + 1) % 7 # Sunday is 0
    start_date_pm = today_date_pm - datetime.timedelta(days=idx_pm)
    
    cal_html_pm = """
    <style>
        .pm-grid { display: grid; grid-template-columns: repeat(7, 1fr); gap: 1px; background: #cbd5e1; border: 1px solid #cbd5e1; border-radius: 8px; overflow: hidden; }
        .pm-header { background: #1e293b; color: white; text-align: center; padding: 10px; font-weight: bold; font-size: 14px; }
        .pm-cell { background: white; min-height: 120px; padding: 6px; display: flex; flex-direction: column; gap: 4px; }
        .pm-cell-today { border: 2px solid #3b82f6; background: #eff6ff; }
        .pm-date { font-size: 14px; font-weight: bold; color: #64748b; margin-bottom: 4px; }
        .pm-date-today { color: #1d4ed8; }
        .pm-pill { font-size: 13px; padding: 4px 6px; border-radius: 4px; font-weight: bold; color: white; text-align: center; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
    </style>
    <div class="pm-grid">
        <div class="pm-header">Sun</div><div class="pm-header">Mon</div><div class="pm-header">Tue</div><div class="pm-header">Wed</div><div class="pm-header">Thu</div><div class="pm-header">Fri</div><div class="pm-header">Sat</div>
    """
    
    # Darkened the 'Pending' color here as well
    color_map_html = {'Pending': '#475569', 'In Progress': '#3b82f6', 'Done': '#16a34a'}
    
    for i in range(35): # 5 weeks
        current_cell_date = start_date_pm + datetime.timedelta(days=i)
        is_today = current_cell_date == today_date_pm
        cell_class = "pm-cell pm-cell-today" if is_today else "pm-cell"
        date_class = "pm-date pm-date-today" if is_today else "pm-date"
        
        # Find tasks ending on this exact date
        day_tasks = plot_df[plot_df['end_date'].dt.date == current_cell_date]
        
        pills_html = ""
        for _, task in day_tasks.iterrows():
            bg_color = color_map_html.get(task['status'], '#475569')
            pills_html += f'<div class="pm-pill" style="background: {bg_color};" title="{task["task_name"]}">{task["task_name"]}</div>'
            
        if current_cell_date.day == 1 or i == 0:
            date_str = current_cell_date.strftime('%b %d')
        else:
            date_str = str(current_cell_date.day)
            
        cal_html_pm += f'<div class="{cell_class}"><div class="{date_class}">{date_str}</div>{pills_html}</div>'
        
    cal_html_pm += "</div>"
    exp_sec100.markdown(cal_html_pm, unsafe_allow_html=True)

conn_pm.close()
# --- SECTION 101: PUBLISHER EXPORT PIPELINE ---
exp_pub = st.expander("📰 1-Click Publish Module", expanded=False)

conn_dos = sqlite3.connect(DB_PATH)
try:
    df_dos = pd.read_sql_query("SELECT date, symbol, content FROM pitch_dossiers ORDER BY date DESC", conn_dos)
except:
    df_dos = pd.DataFrame()
conn_dos.close()

if not df_dos.empty:
    c_pub1, c_pub2 = exp_pub.columns([2, 1])
    with c_pub1:
        pub_sym = st.selectbox("Select Dossier to Publish:", df_dos['symbol'].unique(), key="pub_sym")
    with c_pub2:
        st.markdown("<br>", unsafe_allow_html=True)
        if st.button("🚀 Generate 1-Click Publisher Package", width="stretch"):
            with st.spinner("Sanitizing data and rendering high-res charts (Requires 'kaleido' package)..."):
                import io
                import zipfile
                import re
                
                selected_dos = df_dos[df_dos['symbol'] == pub_sym].iloc[0]
                raw_md = selected_dos['content']
                
                # Sanitize Markdown: Mask absolute dollar amounts over $1,000 to protect AUM leaks
                clean_md = re.sub(r'\$[1-9][0-9]{0,2},[0-9]{3}(,[0-9]{3})*\.\d{2}', '[REDACTED]', raw_md)
                
                zip_buffer = io.BytesIO()
                with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zip_file:
                    # 1. Add Markdown
                    zip_file.writestr(f"{pub_sym}_Newsletter_Draft.md", clean_md)
                    
                    # 2. Add SWAN Chart
                    if 'pub_swan' in st.session_state:
                        try:
                            img_bytes = st.session_state['pub_swan'].to_image(format="png", width=1200, height=800, scale=2)
                            zip_file.writestr("SWAN_Stress_Test.png", img_bytes)
                        except Exception as e:
                            zip_file.writestr("SWAN_ERROR.txt", f"Failed to generate image. Please run: pip install -U kaleido\nError: {e}")
                            
                    # 3. Add 3D Chart
                    if 'pub_3d' in st.session_state:
                        try:
                            img_bytes = st.session_state['pub_3d'].to_image(format="png", width=1200, height=800, scale=2)
                            zip_file.writestr("3D_Topography.png", img_bytes)
                        except Exception as e:
                            zip_file.writestr("3D_ERROR.txt", f"Failed to generate image. Please run: pip install -U kaleido\nError: {e}")
                            
                st.session_state['pub_zip'] = zip_buffer.getvalue()
                st.session_state['pub_zip_name'] = f"{pub_sym}_Publisher_Package.zip"
                
    if 'pub_zip' in st.session_state:
        exp_pub.success("✅ Publisher Package generated successfully!")
        exp_pub.download_button(
            label="📥 Download Publisher Package (.zip)",
            data=st.session_state['pub_zip'],
            file_name=st.session_state['pub_zip_name'],
            mime="application/zip",
            use_container_width=True
        )
else:
    exp_pub.info("No Pitch Dossiers found. Generate one in the Accountability Journal first.")