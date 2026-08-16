"""
=============================================================================
Script Name: core_math.py
Version: v1.0
Location: C:\\Users\\donca\\Desktop\\Desktop HP Envy x360 al 22Abr24\\Docs Manuel\\IBKR_Options
Purpose: Isolated quantitative engine for Cython compilation and IP protection.
         Contains the proprietary Black-Scholes topography math, Monte Carlo 
         simulation engine, and quantitative risk metrics.
=============================================================================
"""
import math
import numpy as np
import pandas as pd

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

    df_acc['prev_nav'] = df_acc['nav'].shift(1).fillna(0.0)
    df_acc['daily_pnl'] = df_acc['nav'] - df_acc['net_flow'] - df_acc['prev_nav']
    df_acc['daily_return'] = df_acc['daily_pnl'] / df_acc['prev_nav'].replace(0, np.nan)
    df_acc['daily_return'] = df_acc['daily_return'].fillna(0)
    
    total_pnl = df_acc['nav'].iloc[-1] - df_acc['net_flow'].sum()
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
        df_opt['base_tckr'] = df_opt['symbol'].apply(lambda x: x.split('_')[0])
        df_opt['strike'] = df_opt['symbol'].apply(lambda x: float(x.split('_')[2]))
        df_opt['exp'] = df_opt['symbol'].apply(lambda x: x.split('_')[1])
        df_opt['right'] = df_opt['symbol'].apply(lambda x: x.split('_')[3])
        
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

def generate_mc_paths(pnl_array):
    np.random.seed(len(pnl_array))
    sim_data = np.random.choice(pnl_array, size=(10000, len(pnl_array)), replace=True)
    c_sim = np.cumsum(sim_data, axis=1)
    z_col = np.zeros((10000, 1))
    c_sim = np.hstack((z_col, c_sim))
    
    pks = np.maximum.accumulate(c_sim, axis=1)
    a_dds = pks - c_sim
    m_dds = np.max(a_dds, axis=1)
    
    m_avg_dd = np.mean(m_dds)
    m_best_dd = np.min(m_dds)
    m_worst_dd = np.max(m_dds)
    m_avg_path = np.mean(c_sim, axis=0)
    
    return c_sim, m_dds, m_avg_dd, m_best_dd, m_worst_dd, m_avg_path