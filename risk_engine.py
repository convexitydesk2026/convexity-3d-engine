"""
=============================================================================
Script Name: risk_engine.py
Version: v1.1
Purpose: Isolated business logic (6-Gear System & Sector Veto) for Cython 
         compilation and IP protection.
         - v1.1 FIX: Replaced 0.5% hard-lock with Tiered Drawdown Scaling.
=============================================================================
"""
import pandas as pd
import yfinance as yf

def get_decoupled_regimes(row):
    rsp, spy = row['RSP'], row['SPY']
    rsp_10, rsp_20, rsp_50 = row['rsp_sma_10'], row['rsp_sma_20'], row['rsp_sma_50']
    spy_10, spy_20, spy_50 = row['sma_10'], row['sma_20'], row['sma_50']
    
    if pd.isna(rsp_50) or pd.isna(spy_50): 
        return 2, 'Bull'
        
    # 1. ALPHA ENGINE (Stocks) - Pure Price Action & Breadth
    if spy > spy_10 and rsp > rsp_10: alpha_gear = 5
    elif spy > spy_20 and rsp > rsp_20: alpha_gear = 4
    elif spy > spy_50 and rsp > rsp_50: alpha_gear = 3
    elif spy > spy_50 and rsp < rsp_50: alpha_gear = 2
    elif spy < spy_50 and rsp > rsp_50: alpha_gear = 1
    else: alpha_gear = 0
        
    # 2. OPTIONS ENGINE (VRP) - Structural Gatekeeper
    opt_dir = 'Bull' if spy > spy_50 else 'Bear'
        
    return alpha_gear, opt_dir

def check_sector_veto(sector_str):
    if not sector_str: return False
    sector_map = {
        'Technology': 'XLK', 'Financial Services': 'XLF', 'Healthcare': 'XLV',
        'Consumer Cyclical': 'XLY', 'Industrials': 'XLI', 'Utilities': 'XLU',
        'Consumer Defensive': 'XLP', 'Real Estate': 'XLRE', 'Energy': 'XLE',
        'Basic Materials': 'XLB', 'Communication Services': 'XLC'
    }
    etf_ticker = sector_map.get(sector_str)
    if not etf_ticker: return False
    try:
        hist = yf.Ticker(etf_ticker).history(period='100d')
        if not hist.empty and len(hist) >= 50:
            current_price = float(hist['Close'].iloc[-1])
            sma_50 = float(hist['Close'].rolling(window=50).mean().iloc[-1])
            return current_price < sma_50
    except Exception:
        pass
    return False
    
import sqlite3
from estate_env import DB_PATH

def calculate_hwm_budget(global_df, global_metrics_nav):
    """Calculates the High-Water Mark and Tiered Drawdown Multiplier."""
    v7_inception_date = pd.to_datetime('2026-07-17')
    
    # 1. Determine baseline HWM from historical global_df
    if not global_df.empty:
        v7_df = global_df[global_df['date'] >= v7_inception_date]
        if not v7_df.empty:
            baseline_hwm = v7_df['nav'].cummax().iloc[-1]
        else:
            baseline_hwm = global_metrics_nav
    else:
        baseline_hwm = global_metrics_nav

    # 2. Access the database to get the globally stored HWM
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("CREATE TABLE IF NOT EXISTS estate_hwm (id INTEGER PRIMARY KEY, peak_nav REAL)")
    
    c.execute("SELECT peak_nav FROM estate_hwm WHERE id = 1")
    row = c.fetchone()
    
    if row:
        stored_hwm = row[0]
    else:
        stored_hwm = baseline_hwm
        c.execute("INSERT INTO estate_hwm (id, peak_nav) VALUES (1, ?)", (stored_hwm,))
        conn.commit()

    # 3. Update the stored HWM if we breached it
    current_highest = max(baseline_hwm, global_metrics_nav)
    
    if current_highest > stored_hwm:
        stored_hwm = current_highest
        c.execute("UPDATE estate_hwm SET peak_nav = ? WHERE id = 1", (stored_hwm,))
        conn.commit()
        
    conn.close()

    hwm = stored_hwm
        
    # Calculate Drawdown Percentage from HWM
    dd_pct = ((global_metrics_nav - hwm) / hwm) * 100 if hwm > 0 else 0.0
    
    # Tiered Drawdown Scaling (The Rubber Band Model)
    if dd_pct >= -1.0:
        tier_multiplier = 1.0
        tier_name = "Tier 1 (Peak)"
    elif dd_pct >= -2.0:
        tier_multiplier = 0.5
        tier_name = "Tier 2 (Caution)"
    elif dd_pct >= -3.0:
        tier_multiplier = 0.25
        tier_name = "Tier 3 (Danger)"
    else:
        tier_multiplier = 0.0
        tier_name = "Tier 4 (Lockout)"
        
    return hwm, dd_pct, tier_multiplier, tier_name

def calculate_position_size(calc_nav, calc_risk_pct, entry_usd, stop_usd, fx_rate, is_ipo):
    """Calculates max allowable shares based on risk budget and notional caps."""
    risk_budget_usd = calc_nav * (calc_risk_pct / 100.0)
    new_risk_per_share_usd = abs(entry_usd - stop_usd)
    
    if new_risk_per_share_usd == 0:
        new_risk_per_share_usd = 0.0001 # Prevent division by zero
        
    proposed_shares = int(risk_budget_usd // new_risk_per_share_usd)
    
    # Absolute Notional Cap (Gate 2)
    max_notional_usd = calc_nav * (0.02 if is_ipo else 0.05)
    notional_value = proposed_shares * entry_usd
    
    if notional_value > max_notional_usd:
        proposed_shares = int(max_notional_usd // entry_usd)
        
    return proposed_shares, risk_budget_usd, new_risk_per_share_usd