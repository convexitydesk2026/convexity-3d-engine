r"""
=============================================================================
Script Name: Generate_Estate_Dashboard_v68.py
Purpose: Generates the Interactive Family Estate Dashboard.
         VERSION 68 UPGRADES:
         - Fully restored all unminified v65 aesthetic & functional components.
         - Synchronized with Estate_Orchestrator_v25 to render the new "Ghost-Free"
           Single Source of Truth databases.
         - Options Velocity widget labeled as (v68 Automated).
=============================================================================
"""

import os
import pandas as pd
import numpy as np
import json
import datetime

target_directory = r"C:\Users\donca\Desktop\Desktop HP Envy x360 al 22Abr24\Docs Manuel\IBKR_Options"
csv_file_path = os.path.join(target_directory, "IBKR_Daily_Data.csv")
spy_qqq_file_path = os.path.join(target_directory, "SPY_QQQ_Close.csv")
full_file_path = os.path.join(target_directory, "Family_Estate_Dashboard_v68.html")

if not os.path.exists(target_directory):
    os.makedirs(target_directory)

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
    except:
        return 0.0

def process_metrics(df_acc):
    if df_acc.empty or len(df_acc) < 2: return "N/A", "N/A", "N/A", "N/A", "0", "N/A", "N/A", 0
    df_acc = df_acc.sort_values('Date').reset_index(drop=True)
    df_acc['Prev_NAV'] = df_acc['NAV'].shift(1)
    df_acc['Daily_Return'] = (df_acc['NAV'] - df_acc['CashFlow'] - df_acc['Prev_NAV']) / df_acc['Prev_NAV']
    df_acc['Daily_Return'] = df_acc['Daily_Return'].replace([np.inf, -np.inf], np.nan).fillna(0)
    
    active_mask = df_acc['NAV'] > 0
    calc_df = df_acc.iloc[active_mask.idxmax():].copy() if active_mask.any() else df_acc.copy()
    
    sharpe_str = "N/A"
    if calc_df['Daily_Return'].std() > 0:
        daily_rf = 0.045 / 252 
        excess_returns = calc_df['Daily_Return'] - daily_rf
        sharpe = np.sqrt(252) * (excess_returns.mean() / calc_df['Daily_Return'].std())
        sharpe_str = f"{sharpe:.2f}"
    
    total_deposits = df_acc['CashFlow'].sum()
    final_nav = df_acc['NAV'].iloc[-1]
    total_pnl = final_nav - total_deposits
    pnl_str = f"${total_pnl:,.2f}"
    
    calc_df['Cum_Return_Index'] = (1 + calc_df['Daily_Return']).cumprod()
    calc_df['Peak'] = calc_df['Cum_Return_Index'].cummax()
    calc_df['Drawdown'] = (calc_df['Cum_Return_Index'] - calc_df['Peak']) / calc_df['Peak'].replace(0, np.nan)
    max_dd = calc_df['Drawdown'].min() * 100
    max_dd_str = f"{max_dd:.2f}%"

    peak_date = calc_df['Date'].iloc[0]
    max_dd_days = 0
    for idx, row in calc_df.iterrows():
        if row['Cum_Return_Index'] >= row['Peak']: peak_date = row['Date']
        else:
            duration = (row['Date'] - peak_date).days
            if duration > max_dd_days: max_dd_days = duration
    
    df_acc['IRR_CF'] = -df_acc['CashFlow']
    cfs = df_acc['IRR_CF'].tolist()
    dates = df_acc['Date'].tolist()
    cfs.append(final_nav)
    dates.append(dates[-1])
    dates_series = pd.to_datetime(pd.Series(dates))
    irr = calculate_xirr(dates_series, cfs)
    irr_str = f"{(irr * 100):.2f}%" if irr != 0.0 else "N/A"

    calmar_str = "N/A"
    if max_dd < 0 and irr != 0.0: calmar = (irr * 100) / abs(max_dd); calmar_str = f"{calmar:.2f}"
    elif max_dd == 0 and irr > 0: calmar_str = "Inf"

    df_acc['Cum_CashFlow'] = df_acc['CashFlow'].cumsum()
    max_capital_employed = df_acc['Cum_CashFlow'].max()
    if max_capital_employed <= 0: max_capital_employed = df_acc['NAV'].max() - total_pnl
    if max_capital_employed > 0: roc = (total_pnl / max_capital_employed) * 100; roc_str = f"{roc:.2f}%"
    else: roc_str = "N/A"

    return irr_str, sharpe_str, pnl_str, max_dd_str, str(max_dd_days), calmar_str, roc_str, final_nav

def get_color_class(val_str, theme="light"):
    if "N/A" in val_str or "Awaiting" in val_str or "--" in val_str: return "text-gray-600"
    if "-" in val_str: return "text-red-600"
    return "text-green-700"

def to_js_array(data, is_date=False):
    if isinstance(data, pd.Series): vals = data.tolist()
    else: vals = list(data)
    clean =[]
    for v in vals:
        try:
            if pd.isna(v) or str(v).lower() in['nan', 'inf', '-inf', 'nat']: clean.append("null")
            else:
                if is_date: clean.append(f'"{v}"')
                else:
                    f_val = float(v)
                    if np.isnan(f_val) or np.isinf(f_val): clean.append("null")
                    else: clean.append(str(round(f_val, 2)))
        except: clean.append("null")
    return "[" + ",".join(clean) + "]"

metrics = {
    "ESTATE": {"irr": "--", "sharpe": "--", "pnl": "--", "maxdd": "--", "dd_days": "--", "calmar": "--", "roc": "--", "nav": 0},
    "U23144948": {"irr": "--", "sharpe": "--", "pnl": "--", "maxdd": "--", "dd_days": "--", "calmar": "--", "roc": "--", "nav": 0},
    "U23139264": {"irr": "--", "sharpe": "--", "pnl": "--", "maxdd": "--", "dd_days": "--", "calmar": "--", "roc": "--", "nav": 0},
    "U23154199": {"irr": "--", "sharpe": "--", "pnl": "--", "maxdd": "--", "dd_days": "--", "calmar": "--", "roc": "--", "nav": 0},
    "U25218481": {"irr": "--", "sharpe": "--", "pnl": "--", "maxdd": "--", "dd_days": "--", "calmar": "--", "roc": "--", "nav": 0}
}

global_df = pd.DataFrame()
bench_df = pd.DataFrame()
silo_returns = {}

dates_js, estate_js, spy_js, qqq_js = "[]", "[]", "[]", "[]"
silo_a_js, silo_b_js, silo_c_js, silo_d_js = "[]", "[]", "[]", "[]"
dates_pnl_js, silo_a_pnl, silo_b_pnl, silo_c_pnl, silo_d_pnl = "[]", "[]", "[]", "[]", "[]"
dates_cum_pnl_js, estate_cum_pnl_js, spy_cum_pnl_js, qqq_cum_pnl_js = "[]", "[]", "[]", "[]"
mc_visuals_js, mc_avg_js, mc_orig_js, mc_stats_js = "[]", "[]", "[]", "{}"
status_js, tor_js = "[]", "[]" 
spy_alpha_str, spy_corr_str, spy_sharpe_str = "N/A", "N/A", "N/A"
qqq_alpha_str, qqq_corr_str, qqq_sharpe_str = "N/A", "N/A", "N/A"

# PnL Attribution Arrays
attr_dates_js, attr_a1_js, attr_a2_js, attr_a3_js, attr_a4_js, attr_a5_js = "[]", "[]", "[]", "[]", "[]", "[]"
total_a1 = total_a2 = total_a3 = total_a4 = total_a5 = 0.0

print("\n========================================================")
print("             CIO DIAGNOSTICS & LOGGING (v68)            ")
print("========================================================")

if os.path.exists(csv_file_path):
    try:
        raw_df = pd.read_csv(csv_file_path)
        raw_df['Date'] = pd.to_datetime(raw_df['Date'].astype(str), format='%Y%m%d')
        
        df_grouped = raw_df.groupby(['AccountID', 'Date']).agg({'NAV': 'last', 'CashFlow': 'sum'}).reset_index()
        for acc in["U23144948", "U23139264", "U23154199", "U25218481"]:
            acc_df = df_grouped[df_grouped['AccountID'] == acc].copy()
            i, s, p, m, d, c, r, n = process_metrics(acc_df)
            if n != 0: metrics[acc] = {"irr": i, "sharpe": s, "pnl": p, "maxdd": m, "dd_days": d, "calmar": c, "roc": r, "nav": n}
            
            acc_df['Prev_NAV'] = acc_df['NAV'].shift(1)
            acc_df['Daily_Return'] = (acc_df['NAV'] - acc_df['CashFlow'] - acc_df['Prev_NAV']) / acc_df['Prev_NAV']
            acc_df['Daily_Return'] = acc_df['Daily_Return'].replace([np.inf, -np.inf], np.nan).fillna(0)
            silo_returns[acc] = acc_df[['Date', 'Daily_Return']].rename(columns={'Daily_Return': f'{acc}_Ret'})

        nav_pivot = raw_df.pivot_table(index='Date', columns='AccountID', values='NAV', aggfunc='last').ffill().fillna(0)
        cf_pivot = raw_df.pivot_table(index='Date', columns='AccountID', values='CashFlow', aggfunc='sum').fillna(0)
        global_df = pd.DataFrame({'Date': nav_pivot.index, 'NAV': nav_pivot.sum(axis=1), 'CashFlow': cf_pivot.sum(axis=1)}).reset_index(drop=True)

        i, s, p, m, d, c, r, n = process_metrics(global_df)
        metrics["ESTATE"] = {"irr": i, "sharpe": s, "pnl": p, "maxdd": m, "dd_days": d, "calmar": c, "roc": r, "nav": n}
        
        global_df['Prev_NAV'] = global_df['NAV'].shift(1)
        global_df['Daily_Return'] = (global_df['NAV'] - global_df['CashFlow'] - global_df['Prev_NAV']) / global_df['Prev_NAV']
        global_df['Daily_Return'] = global_df['Daily_Return'].replace([np.inf, -np.inf], np.nan).fillna(0)

        pnl_df = raw_df.groupby(['AccountID', 'Date']).agg({'NAV': 'last', 'CashFlow': 'sum'}).reset_index()
        pnl_df['Prev_NAV'] = pnl_df.groupby('AccountID')['NAV'].shift(1)
        pnl_df['Daily_PnL'] = pnl_df['NAV'] - pnl_df['CashFlow'] - pnl_df['Prev_NAV'].fillna(pnl_df['NAV'] - pnl_df['CashFlow'])
        pnl_df['Daily_PnL'] = pnl_df['Daily_PnL'].replace([np.inf, -np.inf], 0).fillna(0).round(0)
        
        if not pnl_df.empty:
            min_date = pnl_df['Date'].min()
            full_dates = pd.bdate_range(start=min_date, end=min_date + pd.DateOffset(years=1))
            pnl_pivot = pnl_df.pivot(index='Date', columns='AccountID', values='Daily_PnL').reindex(full_dates).fillna(0)
            
            dates_pnl_js = to_js_array(pnl_pivot.index.strftime('%Y-%m-%d'), is_date=True)
            silo_a_pnl = to_js_array(pnl_pivot['U23144948'] if 'U23144948' in pnl_pivot else [0]*len(full_dates))
            silo_b_pnl = to_js_array(pnl_pivot['U23139264'] if 'U23139264' in pnl_pivot else [0]*len(full_dates))
            silo_c_pnl = to_js_array(pnl_pivot['U23154199'] if 'U23154199' in pnl_pivot else[0]*len(full_dates))
            silo_d_pnl = to_js_array(pnl_pivot['U25218481'] if 'U25218481' in pnl_pivot else [0]*len(full_dates))

        print(f"[OK] IBKR Data Parsed: {len(global_df)} trading days processed.")
    except Exception as e:
        print(f"[ERROR] Parsing IBKR CSV: {e}")

if os.path.exists(spy_qqq_file_path):
    try:
        bench_df = pd.read_csv(spy_qqq_file_path)
        bench_df['Date'] = pd.to_datetime(bench_df['Date'], format='%d-%b-%y')
        for col in['Status', 'Min TOR', 'Max TOR', 'Set TOR']:
            if col not in bench_df.columns: bench_df[col] = ''
        print(f"[OK] Benchmark Data Parsed: {len(bench_df)} trading days found.")
    except Exception as e:
        print(f"[ERROR] Parsing SPY/QQQ CSV: {e}")

# Process Daily PnL Attribution for v68 Charts
attr_csv_path = os.path.join(target_directory, 'Daily_PnL_Attribution.csv')
if os.path.exists(attr_csv_path):
    try:
        attr_df = pd.read_csv(attr_csv_path)
        if not attr_df.empty:
            attr_df = attr_df.sort_values('Date').reset_index(drop=True)
            attr_dates_js = to_js_array(pd.to_datetime(attr_df['Date'].astype(str), format='%Y%m%d').dt.strftime('%Y-%m-%d'), is_date=True)
            
            # Cumulative sums for line chart
            attr_a1_js = to_js_array(attr_df['a1_Yield'].cumsum())
            attr_a2_js = to_js_array(attr_df['a2_Beta'].cumsum())
            attr_a3_js = to_js_array(attr_df['a3_VRP'].cumsum())
            attr_a4_js = to_js_array(attr_df['a4_Alpha'].cumsum())
            attr_a5_js = to_js_array(attr_df['a5_Fees'].cumsum())
            
            # Totals for Bar chart
            total_a1 = attr_df['a1_Yield'].sum()
            total_a2 = attr_df['a2_Beta'].sum()
            total_a3 = attr_df['a3_VRP'].sum()
            total_a4 = attr_df['a4_Alpha'].sum()
            total_a5 = attr_df['a5_Fees'].sum()
            print(f"[OK] Daily PnL Attribution Data Parsed.")
    except Exception as e:
        print(f"[ERROR] Parsing PnL Attribution CSV: {e}")

if not bench_df.empty and not global_df.empty:
    overlap_dates = sorted(list(set(global_df['Date']).intersection(set(bench_df['Date']))))
    first_date = overlap_dates[0] if overlap_dates else None
    
    if first_date:
        master_bench = global_df[global_df['Date'] >= first_date].copy().reset_index(drop=True)
        master_bench = pd.merge(master_bench, bench_df[['Date', 'SPY Close', 'QQQ Close', 'Status', 'Set TOR']], on='Date', how='left')
        master_bench['SPY Close'] = master_bench['SPY Close'].ffill()
        master_bench['QQQ Close'] = master_bench['QQQ Close'].ffill()
        master_bench['SPY_Ret'] = master_bench['SPY Close'].pct_change().fillna(0)
        master_bench['QQQ_Ret'] = master_bench['QQQ Close'].pct_change().fillna(0)
        master_bench = master_bench.rename(columns={'Daily_Return': 'Estate_Ret'})
        
        for acc in["U23144948", "U23139264", "U23154199", "U25218481"]:
            if acc in silo_returns: master_bench = pd.merge(master_bench, silo_returns[acc], on='Date', how='left')
        
        ret_cols =['Estate_Ret', 'U23144948_Ret', 'U23139264_Ret', 'U23154199_Ret', 'U25218481_Ret']
        for c in ret_cols:
            if c not in master_bench.columns: master_bench[c] = 0.0
            
        master_bench[ret_cols] = master_bench[ret_cols].replace([np.inf, -np.inf], 0).fillna(0)
        
        active_days = master_bench[master_bench['Estate_Ret'] != 0.0]
        if not active_days.empty:
            first_active_idx = active_days.index[0]
            start_idx = first_active_idx - 1 if first_active_idx > 0 else first_active_idx
            master_bench = master_bench.iloc[start_idx:].copy().reset_index(drop=True)
        
        master_bench.loc[0, ret_cols +['SPY_Ret', 'QQQ_Ret']] = 0.0
        
        for col in['SPY_Ret', 'QQQ_Ret'] + ret_cols:
            cum_col = col.replace('_Ret', '_Cum')
            master_bench[cum_col] = ((1 + master_bench[col]).cumprod() - 1).replace([np.inf, -np.inf], 0).fillna(0)
            
        master_bench['Estate_Daily_PnL'] = master_bench['NAV'] - master_bench['CashFlow'] - master_bench['Prev_NAV'].fillna(master_bench['NAV'] - master_bench['CashFlow'])
        master_bench['Estate_Daily_PnL'] = master_bench['Estate_Daily_PnL'].replace([np.inf, -np.inf], 0).fillna(0)

        spy_daily_pnl, qqq_daily_pnl = [],[]
        curr_spy_nav = master_bench['NAV'].iloc[0] if pd.notna(master_bench['NAV'].iloc[0]) else 0
        curr_qqq_nav = master_bench['NAV'].iloc[0] if pd.notna(master_bench['NAV'].iloc[0]) else 0

        spy_daily_pnl.append(master_bench['Estate_Daily_PnL'].iloc[0])
        qqq_daily_pnl.append(master_bench['Estate_Daily_PnL'].iloc[0])

        for i in range(1, len(master_bench)):
            cf = master_bench['CashFlow'].iloc[i] if pd.notna(master_bench['CashFlow'].iloc[i]) else 0
            s_ret = master_bench['SPY_Ret'].iloc[i]
            q_ret = master_bench['QQQ_Ret'].iloc[i]

            s_pnl = curr_spy_nav * s_ret
            q_pnl = curr_qqq_nav * q_ret

            spy_daily_pnl.append(s_pnl)
            qqq_daily_pnl.append(q_pnl)

            curr_spy_nav = curr_spy_nav + s_pnl + cf
            curr_qqq_nav = curr_qqq_nav + q_pnl + cf

        master_bench['SPY_Daily_PnL'] = spy_daily_pnl
        master_bench['QQQ_Daily_PnL'] = qqq_daily_pnl

        master_bench['Estate_Cum_PnL'] = master_bench['Estate_Daily_PnL'].cumsum().fillna(0)
        master_bench['SPY_Cum_PnL'] = master_bench['SPY_Daily_PnL'].cumsum().fillna(0)
        master_bench['QQQ_Cum_PnL'] = master_bench['QQQ_Daily_PnL'].cumsum().fillna(0)

        dates_js = to_js_array(master_bench['Date'].dt.strftime('%Y-%m-%d'), is_date=True)
        spy_js = to_js_array(master_bench['SPY_Cum'] * 100)
        qqq_js = to_js_array(master_bench['QQQ_Cum'] * 100)
        estate_js = to_js_array(master_bench['Estate_Cum'] * 100)
        
        silo_a_js = to_js_array(master_bench['U23144948_Cum'] * 100)
        silo_b_js = to_js_array(master_bench['U23139264_Cum'] * 100)
        silo_c_js = to_js_array(master_bench['U23154199_Cum'] * 100)
        silo_d_js = to_js_array(master_bench['U25218481_Cum'] * 100)

        dates_cum_pnl_js = to_js_array(master_bench['Date'].dt.strftime('%Y-%m-%d'), is_date=True)
        estate_cum_pnl_js = to_js_array(master_bench['Estate_Cum_PnL'])
        spy_cum_pnl_js = to_js_array(master_bench['SPY_Cum_PnL'])
        qqq_cum_pnl_js = to_js_array(master_bench['QQQ_Cum_PnL'])

        status_js = json.dumps(master_bench['Status'].fillna('').astype(str).tolist())
        
        tor_clean =[]
        for val in master_bench['Set TOR']:
            try:
                if pd.isna(val) or str(val).strip() == '': tor_clean.append('')
                else: tor_clean.append(str(int(float(val))))
            except: tor_clean.append(str(val))
        tor_js = json.dumps(tor_clean)

        if len(global_df) > 1 and len(bench_df) > 1 and 'SPY_Ret' in master_bench.columns:
            if master_bench['SPY_Ret'].std() > 0:
                rf = 0.045
                est_ann_ret = master_bench['Estate_Ret'].mean() * 252
                spy_ann_ret = master_bench['SPY_Ret'].mean() * 252
                qqq_ann_ret = master_bench['QQQ_Ret'].mean() * 252
                
                corr_spy = master_bench['Estate_Ret'].corr(master_bench['SPY_Ret'])
                cov_spy = master_bench['Estate_Ret'].cov(master_bench['SPY_Ret'])
                var_spy = master_bench['SPY_Ret'].var()
                beta_spy = cov_spy / var_spy if var_spy > 0 else 0
                alpha_spy = est_ann_ret - (rf + beta_spy * (spy_ann_ret - rf))
                
                spy_daily_std = master_bench['SPY_Ret'].std()
                spy_sharpe = (spy_ann_ret - rf) / (spy_daily_std * np.sqrt(252)) if spy_daily_std > 0 else 0
                
                corr_qqq = master_bench['Estate_Ret'].corr(master_bench['QQQ_Ret'])
                cov_qqq = master_bench['Estate_Ret'].cov(master_bench['QQQ_Ret'])
                var_qqq = master_bench['QQQ_Ret'].var()
                beta_qqq = cov_qqq / var_qqq if var_qqq > 0 else 0
                alpha_qqq = est_ann_ret - (rf + beta_qqq * (qqq_ann_ret - rf))
                
                qqq_daily_std = master_bench['QQQ_Ret'].std()
                qqq_sharpe = (qqq_ann_ret - rf) / (qqq_daily_std * np.sqrt(252)) if qqq_daily_std > 0 else 0
                
                spy_a_color = "text-green-700" if alpha_spy > 0 else "text-red-600"
                spy_alpha_str = f'<span class="{spy_a_color} font-black text-lg">{alpha_spy * 100:.2f}%</span>'
                spy_c_color = "text-green-700" if corr_spy < 0.5 else ("text-indigo-700" if corr_spy < 0.8 else "text-red-600")
                spy_corr_str = f'<span class="{spy_c_color} font-black text-lg">{corr_spy:.2f}</span>'
                spy_s_color = "text-green-700" if spy_sharpe > 1 else "text-gray-800"
                spy_sharpe_str = f'<span class="{spy_s_color} font-black text-lg">{spy_sharpe:.2f}</span>'

                qqq_a_color = "text-green-700" if alpha_qqq > 0 else "text-red-600"
                qqq_alpha_str = f'<span class="{qqq_a_color} font-black text-lg">{alpha_qqq * 100:.2f}%</span>'
                qqq_c_color = "text-green-700" if corr_qqq < 0.5 else ("text-indigo-700" if corr_qqq < 0.8 else "text-red-600")
                qqq_corr_str = f'<span class="{qqq_c_color} font-black text-lg">{corr_qqq:.2f}</span>'
                qqq_s_color = "text-green-700" if qqq_sharpe > 1 else "text-gray-800"
                qqq_sharpe_str = f'<span class="{qqq_s_color} font-black text-lg">{qqq_sharpe:.2f}</span>'
        
        daily_pnl_array = master_bench['Estate_Daily_PnL'].values
        sim_length = len(daily_pnl_array)
        if sim_length > 0:
            sim_data = np.random.choice(daily_pnl_array, size=(10000, sim_length), replace=True)
            cum_sim = np.cumsum(sim_data, axis=1)
            peaks = np.maximum.accumulate(cum_sim, axis=1)
            drawdowns = peaks - cum_sim
            max_dds = np.max(drawdowns, axis=1)
            
            mc_avg_dd = float(np.mean(max_dds))
            mc_best_dd = float(np.min(max_dds))
            mc_worst_dd = float(np.max(max_dds))
            mc_avg_path = np.mean(cum_sim, axis=0).round(2).tolist()
            mc_visuals = cum_sim[:100].round(2).tolist()
            
            orig_cum = np.cumsum(daily_pnl_array)
            orig_peaks = np.maximum.accumulate(orig_cum)
            orig_dd = float(np.max(orig_peaks - orig_cum))
            mc_orig_path = orig_cum.round(2).tolist()
            
            mc_stats = {'orig_dd': orig_dd, 'best_dd': mc_best_dd, 'worst_dd': mc_worst_dd, 'avg_dd': mc_avg_dd}
            mc_visuals_js = json.dumps(mc_visuals) 
            mc_avg_js = to_js_array(mc_avg_path)
            mc_orig_js = to_js_array(mc_orig_path)
            mc_stats_js = json.dumps(mc_stats)

html_content = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Estate Master Dashboard v68</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <script src="https://cdn.plot.ly/plotly-2.24.1.min.js"></script>
    <style>
        .splendid { background-color: #dcfce7; color: #166534; font-weight: bold;}
        .great { background-color: #ecfccb; color: #15803d; font-weight: bold;}
        .good { background-color: #fef9c3; color: #4d7c0f; font-weight: bold;}
        .contingent { background-color: #e0e7ff; color: #1e40af; font-weight: bold;}
        .bad { background-color: #ffedd5; color: #b91c1c; font-weight: bold;}
        .avoid { background-color: #fecaca; color: #991b1b; font-weight: bold;}
    </style>
</head>

<body class="bg-slate-50 text-gray-800 font-sans p-4 md:p-6">

    <div class="max-w-[98%] 2xl:max-w-[2400px] mx-auto bg-white rounded-xl shadow-xl p-6 border border-gray-200">
        
        <div class="text-center mb-8 relative">
            <h1 class="text-4xl font-extrabold text-gray-900 tracking-tight">Estate Master Dashboard</h1>
            <p class="text-gray-500 mt-2 font-medium">Silo Allocation & Institutional Data Engine v68</p>
            
            <div class="absolute top-0 right-0 bg-slate-800 text-white text-[11px] font-mono px-3 py-1.5 rounded-lg shadow-md border border-slate-600 flex items-center">
                <span class="inline-block w-2 h-2 bg-green-400 rounded-full animate-pulse mr-2"></span>
                LAST SYNC: VAR_SYNC_TIME
            </div>
        </div>

        <div class="grid grid-cols-1 xl:grid-cols-12 gap-8">
           
            <div class="xl:col-span-6 flex flex-col gap-6">
                
                <div class="bg-gray-100 p-4 rounded-xl shadow-md border border-gray-300 relative">
                    <h4 class="text-lg text-gray-800 uppercase tracking-widest font-black text-center">Master Estate Aggregation</h4>
                    <div class="grid grid-cols-2 md:grid-cols-7 gap-4 text-sm mt-3 border-t border-gray-300 pt-3 font-mono text-center">
                        <div>Static Balance<br><span class="text-blue-700 font-black text-lg">VAR_ESTATE_NAV_FMT</span></div>
                        <div>IRR<br><span class="VAR_COLOR_ESTATE_IRR font-black text-lg">VAR_ESTATE_IRR</span></div>
                        <div>Global P&L<br><span class="VAR_COLOR_ESTATE_PNL font-black text-lg">VAR_ESTATE_PNL</span></div>
                        <div>Global Sharpe<br><span class="VAR_COLOR_ESTATE_SHARPE font-black text-lg">VAR_ESTATE_SHARPE</span></div>
                        <div>SPY Sharpe<br>VAR_SPY_SHARPE</div>
                        <div>QQQ Sharpe<br>VAR_QQQ_SHARPE</div>
                        <div>Max DD<br><span class="text-red-600 font-black text-lg">VAR_ESTATE_MAXDD</span></div>
                        
                        <div>DD Duration<br><span class="text-gray-800 font-black text-lg">VAR_ESTATE_DD_DAYS d</span></div>
                        <div>Calmar<br><span class="text-gray-800 font-black text-lg">VAR_ESTATE_CALMAR</span></div>
                        <div>Est. ROC%<br><span class="VAR_COLOR_ESTATE_ROC font-black text-lg">VAR_ESTATE_ROC</span></div>
                        <div>SPY Alpha<br>VAR_SPY_ALPHA</div>
                        <div>SPY Corr.<br>VAR_SPY_CORR</div>
                        <div>QQQ Alpha<br>VAR_QQQ_ALPHA</div>
                        <div>QQQ Corr.<br>VAR_QQQ_CORR</div>
                    </div>
                    <div class="mt-4 pt-3 border-t border-gray-300 text-[11px] text-gray-500 font-mono flex justify-center gap-6 flex-wrap">
                        <span class="font-bold text-gray-700">OPTIMAL RANGES:</span>
                        <span>IRR: >10%</span>
                        <span>Sharpe: 1.0 to 2.0+</span>
                        <span>Max DD: > -15%</span>
                        <span>Calmar: > 1.0</span>
                        <span>Alpha: > 0%</span>
                        <span>Corr: 0.30 to 0.60</span>
                    </div>
                </div>

                <div id="risk-alerts" class="w-full flex flex-col gap-2"></div>

                <div class="bg-gray-100 p-4 rounded-xl shadow-md border border-gray-300">
                    <h4 class="text-sm text-gray-800 uppercase tracking-widest font-black text-center mb-2">Estate vs Benchmarks (Cumulative Return %)</h4>
                    <div id="benchmark-chart" class="w-full h-[250px]"></div>
                </div>

                <div class="grid grid-cols-1 sm:grid-cols-2 2xl:grid-cols-4 gap-4">
                    
                    <div class="flex flex-col gap-3">
                        <div class="bg-blue-300 border border-blue-400 rounded-xl p-2 h-[160px] shadow-sm relative">
                            <span class="absolute top-1 left-2 text-[10px] font-bold text-gray-800 uppercase z-10">Silo A vs Benchmarks</span>
                            <div id="chart-silo-a" class="w-full h-full"></div>
                        </div>
                        <div class="bg-blue-300 text-gray-900 p-4 rounded-xl shadow-md text-center border-b-4 border-blue-400 flex-grow">
                            <h4 class="text-sm text-gray-900 uppercase tracking-widest font-black mb-1">Silo A</h4>
                            <p class="text-xs mb-1 text-gray-800">Persons 1 and 2 &bull; U*****948</p>
                            <div class="bg-white/50 rounded py-1 mb-2 border border-white/50"><p class="text-sm font-black text-gray-900">Bal: VAR_A_NAV_FMT</p></div>
                            <div class="grid grid-cols-2 text-xs mt-3 border-t border-blue-400 pt-3 gap-y-2 font-mono">
                                <div class="text-left font-bold">IRR: <span class="VAR_COLOR_A_IRR font-black">VAR_A_IRR</span></div>
                                <div class="text-right font-bold">Sharpe: <span class="VAR_COLOR_A_SHARPE font-black">VAR_A_SHARPE</span></div>
                                <div class="text-left font-bold">P&L: <span class="VAR_COLOR_A_PNL font-black">VAR_A_PNL</span></div>
                                <div class="text-right font-bold">Max DD: <span class="text-red-600 font-black">VAR_A_MAXDD</span></div>
                                <div class="text-left font-bold">DD Days: <span class="text-gray-900 font-black">VAR_A_DD_DAYS</span></div>
                                <div class="text-right font-bold">Calmar: <span class="text-gray-900 font-black">VAR_A_CALMAR</span></div>
                                <div class="text-center col-span-2 mt-1">ROC%: <span class="VAR_COLOR_A_ROC font-black text-sm">VAR_A_ROC</span></div>
                            </div>
                        </div>
                    </div>

                    <div class="flex flex-col gap-3">
                        <div class="bg-purple-300 border border-purple-400 rounded-xl p-2 h-[160px] shadow-sm relative">
                            <span class="absolute top-1 left-2 text-[10px] font-bold text-gray-800 uppercase z-10">Silo B vs Benchmarks</span>
                            <div id="chart-silo-b" class="w-full h-full"></div>
                        </div>
                        <div class="bg-purple-300 text-gray-900 p-4 rounded-xl shadow-md text-center border-b-4 border-purple-400 flex-grow relative">
                            <h4 class="text-sm text-gray-900 uppercase tracking-widest font-black mb-1">Silo B</h4>
                            <p class="text-xs mb-1 text-gray-800">Persons 1 and 2 &bull; U*****264</p>
                            <div class="bg-white/50 rounded py-1 mb-2 border border-white/50"><p class="text-sm font-black text-gray-900">Bal: VAR_B_NAV_FMT</p></div>
                            
                            <!-- Silo B Progressive Exposure Advisory Widget -->
                            <div class="mt-2 mb-2 p-2 bg-purple-100 border border-purple-400 rounded text-[10px] text-left shadow-inner">
                                <div class="flex justify-between font-black text-purple-900 mb-1">
                                    <span id="b_tier_lbl">Advisory: Base $30,000 (Tier 1)</span>
                                    <span id="b_tier_next">Next: $3k</span>
                                </div>
                                <div class="w-full bg-white rounded-full h-2 border border-purple-300">
                                    <div class="bg-purple-600 h-full rounded-full transition-all duration-500" id="b_tier_bar" style="width: 0%"></div>
                                </div>
                                <div class="text-[9px] text-purple-700 font-bold mt-1 text-right tracking-tight" id="b_tier_dist">Distance: $0</div>
                            </div>

                            <div class="grid grid-cols-2 text-xs mt-3 border-t border-purple-400 pt-3 gap-y-2 font-mono">
                                <div class="text-left font-bold">IRR: <span class="VAR_COLOR_B_IRR font-black">VAR_B_IRR</span></div>
                                <div class="text-right font-bold">Sharpe: <span class="VAR_COLOR_B_SHARPE font-black">VAR_B_SHARPE</span></div>
                                <div class="text-left font-bold">P&L: <span class="VAR_COLOR_B_PNL font-black">VAR_B_PNL</span></div>
                                <div class="text-right font-bold">Max DD: <span class="text-red-600 font-black">VAR_B_MAXDD</span></div>
                                <div class="text-left font-bold">DD Days: <span class="text-gray-900 font-black">VAR_B_DD_DAYS</span></div>
                                <div class="text-right font-bold">Calmar: <span class="text-gray-900 font-black">VAR_B_CALMAR</span></div>
                                <div class="text-center col-span-2 mt-1">ROC%: <span class="VAR_COLOR_B_ROC font-black text-sm">VAR_B_ROC</span></div>
                            </div>
                        </div>
                    </div>

                    <div class="flex flex-col gap-3">
                        <div class="bg-green-300 border border-green-400 rounded-xl p-2 h-[160px] shadow-sm relative">
                            <span class="absolute top-1 left-2 text-[10px] font-bold text-gray-800 uppercase z-10">Silo C vs Benchmarks</span>
                            <div id="chart-silo-c" class="w-full h-full"></div>
                        </div>
                        <div class="bg-green-300 text-gray-900 p-4 rounded-xl shadow-md text-center border-b-4 border-green-400 flex-grow">
                            <h4 class="text-sm text-gray-900 uppercase tracking-widest font-black mb-1">Silo C</h4>
                            <p class="text-xs mb-1 text-gray-800">Persons 1 and 3 &bull; U*****199</p>
                            <div class="bg-white/50 rounded py-1 mb-2 border border-white/50"><p class="text-sm font-black text-gray-900">Bal: VAR_C_NAV_FMT</p></div>
                            <div class="grid grid-cols-2 text-xs mt-3 border-t border-green-400 pt-3 gap-y-2 font-mono">
                                <div class="text-left font-bold">IRR: <span class="VAR_COLOR_C_IRR font-black">VAR_C_IRR</span></div>
                                <div class="text-right font-bold">Sharpe: <span class="VAR_COLOR_C_SHARPE font-black">VAR_C_SHARPE</span></div>
                                <div class="text-left font-bold">P&L: <span class="VAR_COLOR_C_PNL font-black">VAR_C_PNL</span></div>
                                <div class="text-right font-bold">Max DD: <span class="text-red-600 font-black">VAR_C_MAXDD</span></div>
                                <div class="text-left font-bold">DD Days: <span class="text-gray-900 font-black">VAR_C_DD_DAYS</span></div>
                                <div class="text-right font-bold">Calmar: <span class="text-gray-900 font-black">VAR_C_CALMAR</span></div>
                                <div class="text-center col-span-2 mt-1">ROC%: <span class="VAR_COLOR_C_ROC font-black text-sm">VAR_C_ROC</span></div>
                            </div>
                        </div>
                    </div>

                    <div class="flex flex-col gap-3">
                        <div class="bg-yellow-300 border border-yellow-400 rounded-xl p-2 h-[160px] shadow-sm relative">
                            <span class="absolute top-1 left-2 text-[10px] font-bold text-gray-800 uppercase z-10">Silo D vs Benchmarks</span>
                            <div id="chart-silo-d" class="w-full h-full"></div>
                        </div>
                        <div class="bg-yellow-300 text-gray-900 p-4 rounded-xl shadow-md text-center border-b-4 border-yellow-400 flex-grow relative">
                            <h4 class="text-sm text-gray-900 uppercase tracking-widest font-black mb-1">Silo D</h4>
                            <p class="text-xs mb-1 text-gray-800">Persons 1 and 4 &bull; U*****481</p>
                            <div class="bg-white/50 rounded py-1 mb-2 border border-white/50"><p class="text-sm font-black text-gray-900">Bal: VAR_D_NAV_FMT</p></div>
                            
                            <!-- Silo D Progressive Exposure Advisory Widget -->
                            <div class="mt-2 mb-2 p-2 bg-yellow-100 border border-yellow-500 rounded text-[10px] text-left shadow-inner">
                                <div class="flex justify-between font-black text-yellow-900 mb-1">
                                    <span id="d_tier_lbl">Advisory: Base $30,000 (Base)</span>
                                    <span id="d_tier_next">Next: $3k</span>
                                </div>
                                <div class="w-full bg-white rounded-full h-2 border border-yellow-400">
                                    <div class="bg-yellow-500 h-full rounded-full transition-all duration-500" id="d_tier_bar" style="width: 0%"></div>
                                </div>
                                <div class="text-[9px] text-yellow-800 font-bold mt-1 text-right tracking-tight" id="d_tier_dist">Distance: $0</div>
                            </div>

                            <div class="grid grid-cols-2 text-xs mt-3 border-t border-yellow-500 pt-3 gap-y-2 font-mono">
                                <div class="text-left font-bold">IRR: <span class="VAR_COLOR_D_IRR font-black">VAR_D_IRR</span></div>
                                <div class="text-right font-bold">Sharpe: <span class="VAR_COLOR_D_SHARPE font-black">VAR_D_SHARPE</span></div>
                                <div class="text-left font-bold">P&L: <span class="VAR_COLOR_D_PNL font-black">VAR_D_PNL</span></div>
                                <div class="text-right font-bold">Max DD: <span class="text-red-600 font-black">VAR_D_MAXDD</span></div>
                                <div class="text-left font-bold">DD Days: <span class="text-gray-900 font-black">VAR_D_DD_DAYS</span></div>
                                <div class="text-right font-bold">Calmar: <span class="text-gray-900 font-black">VAR_D_CALMAR</span></div>
                                <div class="text-center col-span-2 mt-1">ROC%: <span class="VAR_COLOR_D_ROC font-black text-sm">VAR_D_ROC</span></div>
                            </div>
                        </div>
                    </div>
                </div>

                <div class="bg-gray-50 p-4 rounded-xl border shadow-sm">
                    <h3 class="text-xl font-bold mb-2 text-gray-800">1. Estate Capital (Net Liquidation Value)</h3>
                    <p class="text-sm text-gray-500 mb-4 border-b pb-2">Fields auto-populated from IBKR. Modify manually below for real-time simulations.</p>
                    <div class="grid grid-cols-2 md:grid-cols-4 gap-4">
                        <div><label class="block text-sm font-bold text-gray-700">Silo A (USD)</label><input type="number" id="siloA" value="VAR_NAV_A" class="mt-1 w-full rounded-md p-2 border" oninput="updateUI()"></div>
                        <div><label class="block text-sm font-bold text-gray-700">Silo B (USD)</label><input type="number" id="siloB" value="VAR_NAV_B" class="mt-1 w-full rounded-md p-2 border" oninput="updateUI()"></div>
                        <div><label class="block text-sm font-bold text-gray-700">Silo C (USD)</label><input type="number" id="siloC" value="VAR_NAV_C" class="mt-1 w-full rounded-md p-2 border" oninput="updateUI()"></div>
                        <div><label class="block text-sm font-bold text-gray-700">Silo D (USD)</label><input type="number" id="siloD" value="VAR_NAV_D" class="mt-1 w-full rounded-md p-2 border" oninput="updateUI()"></div>
                    </div>
                </div>

            </div>

            <!-- RIGHT COLUMN -->
            <div class="xl:col-span-6 flex flex-col gap-6">
                
                <div class="grid grid-cols-1 lg:grid-cols-2 gap-4">
                    <div class="bg-white border rounded-xl p-4 shadow-sm"><div id="bar-chart" class="w-full h-[400px]"></div></div>
                    <div class="bg-white border rounded-xl p-4 shadow-sm"><div id="pie-chart" class="w-full h-[400px]"></div></div>
                </div>
                
                <div class="bg-white p-4 rounded-xl border shadow-sm">
                    <h3 class="text-xl font-bold mb-2 text-gray-800">2. Target Portfolio Composition</h3> 
                    <p class="text-sm text-gray-500 mb-4 border-b pb-2">Physical assets must mathematically equal 100%. Adjust manually below.</p>
                    
                    <div class="grid grid-cols-1 lg:grid-cols-4 gap-4">
                        
                        <!-- Silo A -->
                        <div class="bg-blue-50 p-4 rounded-lg border border-blue-400 shadow-inner flex flex-col justify-between">
                            <div>
                                <h4 class="font-black text-gray-900 mb-2 text-sm border-b border-blue-400 pb-1">Silo A (The Central Bank)</h4> 
                                <p class="text-[10px] font-bold text-gray-800 mb-2 uppercase tracking-wide">Physical Balance Sheet</p>
                                
                                <div class="flex gap-2 mb-1"><input type="text" id="a_ib01_lbl" value="IB01" class="w-1/2 text-[10px] p-1 border border-gray-300 rounded bg-gray-100 font-bold text-gray-700" readonly><input type="number" id="a_ib01" value="0" class="w-1/2 text-[10px] p-1 border border-gray-300 rounded bg-white" oninput="updateUI()"></div>
                                <div class="flex gap-2 mb-1"><input type="text" id="a_cspx_lbl" value="CSPX" class="w-1/2 text-[10px] p-1 border border-gray-300 rounded bg-gray-100 font-bold text-gray-700" readonly><input type="number" id="a_cspx" value="0" class="w-1/2 text-[10px] p-1 border border-gray-300 rounded bg-white" oninput="updateUI()"></div>
                                <div class="flex gap-2 mb-1"><input type="text" id="a_cndx_lbl" value="CNDX" class="w-1/2 text-[10px] p-1 border border-gray-300 rounded bg-gray-100 font-bold text-gray-700" readonly><input type="number" id="a_cndx" value="0" class="w-1/2 text-[10px] p-1 border border-gray-300 rounded bg-white" oninput="updateUI()"></div>
                                <div class="flex gap-2 mb-1"><input type="text" id="a_itwn_lbl" value="ITWN (Taiwan)" class="w-1/2 text-[10px] p-1 border border-gray-300 rounded bg-gray-100 font-bold text-gray-700" readonly><input type="number" id="a_itwn" value="0" class="w-1/2 text-[10px] p-1 border border-gray-300 rounded bg-white" oninput="updateUI()"></div>
                                <div class="flex gap-2 mb-1"><input type="text" id="a_cskr_lbl" value="CSKR (Korea)" class="w-1/2 text-[10px] p-1 border border-gray-300 rounded bg-gray-100 font-bold text-gray-700" readonly><input type="number" id="a_cskr" value="0" class="w-1/2 text-[10px] p-1 border border-gray-300 rounded bg-white" oninput="updateUI()"></div>
                                <div class="flex gap-2 mb-1"><input type="text" id="a_cnya_lbl" value="CNYA (China)" class="w-1/2 text-[10px] p-1 border border-gray-300 rounded bg-gray-100 font-bold text-gray-700" readonly><input type="number" id="a_cnya" value="0" class="w-1/2 text-[10px] p-1 border border-gray-300 rounded bg-white" oninput="updateUI()"></div>
                                <div class="flex gap-2 mb-1"><input type="text" id="a_crypto_lbl" value="Crypto ETPs" class="w-1/2 text-[10px] p-1 border border-gray-300 rounded bg-gray-100 font-bold text-gray-700" readonly><input type="number" id="a_crypto" value="0" class="w-1/2 text-[10px] p-1 border border-gray-300 rounded bg-white" oninput="updateUI()"></div>
                                <div class="flex gap-2 mb-1"><input type="text" id="a_cash_lbl" value="Cash" class="w-1/2 text-[10px] p-1 border border-gray-300 rounded bg-gray-100 font-bold text-gray-700" readonly><input type="number" id="a_cash" value="0" class="w-1/2 text-[10px] p-1 border border-gray-300 rounded bg-white" oninput="updateUI()"></div>
                                
                                <p class="text-[10px] text-green-600 font-bold mt-1 h-4" id="a_warning"></p>
                                
                                <p class="text-[10px] font-bold text-gray-800 mt-2 mb-1 uppercase tracking-wide border-t border-blue-400 pt-2">Margin Overlay</p>
                                <div class="flex gap-2 mb-1"><input type="text" value="Opt Liab" class="w-1/2 text-[10px] p-1 border border-red-300 rounded bg-red-100 font-bold text-red-800" readonly><input type="number" id="a_opt_mkt" value="0" class="w-1/2 text-[10px] p-1 border border-red-300 rounded text-red-800 bg-white" oninput="updateUI()"></div>
                                <div class="flex gap-2 mb-1"><input type="text" value="Opt Margin" class="w-1/2 text-[10px] p-1 border border-green-300 rounded bg-green-100 font-bold text-green-800" readonly><input type="number" id="a_xsp" value="0" class="w-1/2 text-[10px] p-1 border border-green-300 rounded text-green-800 bg-white" oninput="updateUI()"></div>
                            </div>
                            <p class="text-[10px] text-gray-600 italic mt-2 border-t border-blue-200 pt-2"><b>CENTRAL BANK & PTJ RULE:</b> Holds bedrock wealth in UCITS. Distributes $10k tranches to Alpha Silos based on merit. <span class="text-red-600 font-bold">PTJ RULE:</span> If SPY closes below 200-Day SMA, halt all equity DCA. Reroute 100% of new cash flow to IB01.</p>
                        </div>

                        <!-- Silo B -->
                        <div class="bg-purple-50 p-4 rounded-lg border border-purple-400 shadow-inner flex flex-col justify-between">
                            <div>
                                <h4 class="font-black text-gray-900 mb-2 text-sm border-b border-purple-400 pb-1">Silo B (The Momentum Sandbox)</h4> 
                                <p class="text-[10px] font-bold text-gray-800 mb-2 uppercase tracking-wide">Physical Balance Sheet</p>
                                
                                <div class="flex gap-2 mb-1"><input type="text" id="b_cash_lbl" value="Cash" class="w-1/2 text-[10px] p-1 border border-gray-300 rounded bg-gray-100 font-bold text-gray-700" readonly><input type="number" id="b_cash" value="0" class="w-1/2 text-[10px] p-1 border border-gray-300 rounded bg-white" oninput="updateUI()"></div>
                                <div class="flex gap-2 mb-1"><input type="text" id="b_cfd_lbl" value="US Tech CFDs" class="w-1/2 text-[10px] p-1 border border-gray-300 rounded bg-gray-100 font-bold text-gray-700" readonly><input type="number" id="b_cfd" value="0" class="w-1/2 text-[10px] p-1 border border-gray-300 rounded bg-white" oninput="updateUI()"></div>
                                <div class="flex gap-2 mb-1"><input type="text" id="b_intl_lbl" value="Intl Stocks" class="w-1/2 text-[10px] p-1 border border-gray-300 rounded bg-gray-100 font-bold text-gray-700" readonly><input type="number" id="b_intl" value="0" class="w-1/2 text-[10px] p-1 border border-gray-300 rounded bg-white" oninput="updateUI()"></div>
                                
                                <p class="text-[10px] text-green-600 font-bold mt-1 h-4" id="b_warning"></p>
                            </div>
                            <p class="text-[10px] text-gray-600 italic mt-2 border-t border-purple-200 pt-2">Pure, unadulterated Minervini technical swing trading (VCPs, breakouts).</p>
                        </div>

                        <!-- Silo C -->
                        <div class="bg-green-50 p-4 rounded-lg border border-green-400 shadow-inner flex flex-col justify-between">
                            <div>
                                <h4 class="font-black text-gray-900 mb-2 text-sm border-b border-green-400 pb-1">Silo C (The Options Engine)</h4> 
                                <p class="text-[10px] font-bold text-gray-800 mb-2 uppercase tracking-wide">Physical Balance Sheet</p>
                                
                                <div class="flex gap-2 mb-1"><input type="text" id="c_ib01_lbl" value="IB01" class="w-1/2 text-[10px] p-1 border border-gray-300 rounded bg-gray-100 font-bold text-gray-700" readonly><input type="number" id="c_ib01" value="0" class="w-1/2 text-[10px] p-1 border border-gray-300 rounded bg-white" oninput="updateUI()"></div>
                                <div class="flex gap-2 mb-1"><input type="text" id="c_cspx_lbl" value="CSPX" class="w-1/2 text-[10px] p-1 border border-gray-300 rounded bg-gray-100 font-bold text-gray-700" readonly><input type="number" id="c_cspx" value="0" class="w-1/2 text-[10px] p-1 border border-gray-300 rounded bg-white" oninput="updateUI()"></div>
                                <div class="flex gap-2 mb-1"><input type="text" id="c_cndx_lbl" value="CNDX" class="w-1/2 text-[10px] p-1 border border-gray-300 rounded bg-gray-100 font-bold text-gray-700" readonly><input type="number" id="c_cndx" value="0" class="w-1/2 text-[10px] p-1 border border-gray-300 rounded bg-white" oninput="updateUI()"></div>
                                <div class="flex gap-2 mb-1"><input type="text" id="c_itwn_lbl" value="ITWN (Taiwan)" class="w-1/2 text-[10px] p-1 border border-gray-300 rounded bg-gray-100 font-bold text-gray-700" readonly><input type="number" id="c_itwn" value="0" class="w-1/2 text-[10px] p-1 border border-gray-300 rounded bg-white" oninput="updateUI()"></div>
                                <div class="flex gap-2 mb-1"><input type="text" id="c_cskr_lbl" value="CSKR (Korea)" class="w-1/2 text-[10px] p-1 border border-gray-300 rounded bg-gray-100 font-bold text-gray-700" readonly><input type="number" id="c_cskr" value="0" class="w-1/2 text-[10px] p-1 border border-gray-300 rounded bg-white" oninput="updateUI()"></div>
                                <div class="flex gap-2 mb-1"><input type="text" id="c_cnya_lbl" value="CNYA (China)" class="w-1/2 text-[10px] p-1 border border-gray-300 rounded bg-gray-100 font-bold text-gray-700" readonly><input type="number" id="c_cnya" value="0" class="w-1/2 text-[10px] p-1 border border-gray-300 rounded bg-white" oninput="updateUI()"></div>
                                <div class="flex gap-2 mb-1"><input type="text" id="c_crypto_lbl" value="Crypto ETPs" class="w-1/2 text-[10px] p-1 border border-gray-300 rounded bg-gray-100 font-bold text-gray-700" readonly><input type="number" id="c_crypto" value="0" class="w-1/2 text-[10px] p-1 border border-gray-300 rounded bg-white" oninput="updateUI()"></div>
                                <div class="flex gap-2 mb-1"><input type="text" id="c_cash_lbl" value="Cash" class="w-1/2 text-[10px] p-1 border border-gray-300 rounded bg-gray-100 font-bold text-gray-700" readonly><input type="number" id="c_cash" value="0" class="w-1/2 text-[10px] p-1 border border-gray-300 rounded bg-white" oninput="updateUI()"></div>
                                
                                <p class="text-[10px] text-green-600 font-bold mt-1 h-4" id="c_warning"></p>
                                
                                <p class="text-[10px] font-bold text-gray-800 mt-2 mb-1 uppercase tracking-wide border-t border-green-400 pt-2">Margin Overlay</p>
                                <div class="flex gap-2 mb-1"><input type="text" value="Opt Liab" class="w-1/2 text-[10px] p-1 border border-red-300 rounded bg-red-100 font-bold text-red-800" readonly><input type="number" id="c_opt_mkt" value="0" class="w-1/2 text-[10px] p-1 border border-red-300 rounded text-red-800 bg-white" oninput="updateUI()"></div>
                                <div class="flex gap-2 mb-1"><input type="text" value="Opt Margin" class="w-1/2 text-[10px] p-1 border border-green-300 rounded bg-green-100 font-bold text-green-800" readonly><input type="number" id="c_xsp" value="0" class="w-1/2 text-[10px] p-1 border border-green-300 rounded text-green-800 bg-white" oninput="updateUI()"></div>
                            </div>
                            <p class="text-[10px] text-gray-600 italic mt-2 border-t border-green-200 pt-2"><b>OPTIONS ENGINE & TAIL HEDGE:</b> Mirrors Silo A to safely sell XSP/XND insurance (VRP). <span class="text-red-600 font-bold">TALEB RULE:</span> Once Estate Physical Equity > 40%, divert 2-3% of weekly premium to buy 90-DTE deep OTM SPX Puts (Black Swan Insurance).</p>
                        </div>

                        <!-- Silo D -->
                        <div class="bg-yellow-50 p-4 rounded-lg border border-yellow-400 shadow-inner flex flex-col justify-between">
                            <div>
                                <h4 class="font-black text-gray-900 mb-2 text-sm border-b border-yellow-400 pb-1">Silo D (The Smart Money Sandbox)</h4> 
                                <p class="text-[10px] font-bold text-gray-800 mb-2 uppercase tracking-wide">13F / Smart Money Holdings</p>
                                
                                <div class="flex gap-2 mb-1"><input type="text" id="d_lbl_1" placeholder="Ticker 1" class="w-1/2 text-[10px] p-1 border border-gray-300 rounded font-bold text-gray-700 bg-white"><input type="number" id="d_val_1" placeholder="$ Value" value="0" class="w-1/2 text-[10px] p-1 border border-gray-300 rounded bg-white" oninput="updateUI()"></div>
                                <div class="flex gap-2 mb-1"><input type="text" id="d_lbl_2" placeholder="Ticker 2" class="w-1/2 text-[10px] p-1 border border-gray-300 rounded font-bold text-gray-700 bg-white"><input type="number" id="d_val_2" placeholder="$ Value" value="0" class="w-1/2 text-[10px] p-1 border border-gray-300 rounded bg-white" oninput="updateUI()"></div>
                                <div class="flex gap-2 mb-1"><input type="text" id="d_lbl_3" placeholder="Ticker 3" class="w-1/2 text-[10px] p-1 border border-gray-300 rounded font-bold text-gray-700 bg-white"><input type="number" id="d_val_3" placeholder="$ Value" value="0" class="w-1/2 text-[10px] p-1 border border-gray-300 rounded bg-white" oninput="updateUI()"></div>
                                <div class="flex gap-2 mb-1"><input type="text" id="d_lbl_4" placeholder="Ticker 4" class="w-1/2 text-[10px] p-1 border border-gray-300 rounded font-bold text-gray-700 bg-white"><input type="number" id="d_val_4" placeholder="$ Value" value="0" class="w-1/2 text-[10px] p-1 border border-gray-300 rounded bg-white" oninput="updateUI()"></div>
                                <div class="flex gap-2 mb-1"><input type="text" id="d_lbl_5" placeholder="Ticker 5" class="w-1/2 text-[10px] p-1 border border-gray-300 rounded font-bold text-gray-700 bg-white"><input type="number" id="d_val_5" placeholder="$ Value" value="0" class="w-1/2 text-[10px] p-1 border border-gray-300 rounded bg-white" oninput="updateUI()"></div>
                                <div class="flex gap-2 mb-1"><input type="text" id="d_lbl_6" placeholder="Ticker 6" class="w-1/2 text-[10px] p-1 border border-gray-300 rounded font-bold text-gray-700 bg-white"><input type="number" id="d_val_6" placeholder="$ Value" value="0" class="w-1/2 text-[10px] p-1 border border-gray-300 rounded bg-white" oninput="updateUI()"></div>
                                <div class="flex gap-2 mb-1"><input type="text" id="d_lbl_7" placeholder="Ticker 7" class="w-1/2 text-[10px] p-1 border border-gray-300 rounded font-bold text-gray-700 bg-white"><input type="number" id="d_val_7" placeholder="$ Value" value="0" class="w-1/2 text-[10px] p-1 border border-gray-300 rounded bg-white" oninput="updateUI()"></div>
                                <div class="flex gap-2 mb-1"><input type="text" id="d_lbl_8" placeholder="Ticker 8" class="w-1/2 text-[10px] p-1 border border-gray-300 rounded font-bold text-gray-700 bg-white"><input type="number" id="d_val_8" placeholder="$ Value" value="0" class="w-1/2 text-[10px] p-1 border border-gray-300 rounded bg-white" oninput="updateUI()"></div>
                                <div class="flex gap-2 mb-1"><input type="text" id="d_lbl_9" placeholder="Ticker 9" class="w-1/2 text-[10px] p-1 border border-gray-300 rounded font-bold text-gray-700 bg-white"><input type="number" id="d_val_9" placeholder="$ Value" value="0" class="w-1/2 text-[10px] p-1 border border-gray-300 rounded bg-white" oninput="updateUI()"></div>
                                <div class="flex gap-2 mb-1"><input type="text" id="d_lbl_10" placeholder="Ticker 10" class="w-1/2 text-[10px] p-1 border border-gray-300 rounded font-bold text-gray-700 bg-white"><input type="number" id="d_val_10" placeholder="$ Value" value="0" class="w-1/2 text-[10px] p-1 border border-gray-300 rounded bg-white" oninput="updateUI()"></div>
                                
                                <div class="flex gap-2 mb-1 mt-3 border-t border-yellow-300 pt-2">
                                    <input type="text" id="d_cash_lbl" value="Cash Bal" class="w-1/2 text-[10px] p-1 border border-gray-300 rounded bg-gray-100 font-bold text-gray-700" readonly>
                                    <input type="number" id="d_val_cash" value="0" class="w-1/2 text-[10px] p-1 border border-gray-300 rounded bg-white" oninput="updateUI()">
                                </div>
                                
                                <p class="text-[10px] text-green-600 font-bold mt-1 h-4" id="d_warning"></p>
                            </div>
                            <p class="text-[10px] text-gray-600 italic mt-2 border-t border-yellow-200 pt-2">Fundamental and Sentiment-based Alpha. Tracks 13F institutional conviction via Thematic UCITS, and high-conviction social sentiment (Shay) via short-term CFDs. Ruthlessly cut losers.</p>
                        </div>
                    </div>
                    
                    <div class="grid grid-cols-1 lg:grid-cols-4 gap-4 mt-6 border-t border-gray-200 pt-4">
                        <div class="text-[11px] text-gray-700 leading-relaxed pr-2 border-r border-gray-100">
                            <span class="font-bold text-blue-800 block mb-1">STRATEGY & EXECUTION:</span>
                            No stop-losses on broad index ETFs as long as Global Cash/IB01 > 40%. The cash buffer naturally absorbs systemic shocks. DCA systematically every 2 weeks. Accelerate/Double the DCA amount during SPY pullbacks (Yellow/Red regimes). Review assets quarterly; avoid over-trading the vaults.
                        </div>
                        <div class="text-[11px] text-gray-700 leading-relaxed pr-2 border-r border-gray-100">
                            <span class="font-bold text-purple-800 block mb-1">STRATEGY & EXECUTION:</span>
                            <b>Regime Filter:</b> Green (3-5R TOR), Yellow (1-3R), Red (0-1R). <b>Entry:</b> 2-3 tranches on momentum. Initial Stop at Low of Day (LOD). <b>Management:</b> Move stop to breakeven at +1R profit. Scale out 30-50% on Day 3-5 (Afzal) and trail the runner with the 10/20 SMA. No shorting.
                        </div>
                        <div class="text-[11px] text-gray-700 leading-relaxed pr-2 border-r border-gray-100">
                            <span class="font-bold text-green-800 block mb-1">STRATEGY & EXECUTION:</span>
                            Adheres to Silo A's 40% cash buffer (no individual stops; spread width caps max loss). Execute XSP/XND spreads weekly at 45-50 DTE near -0.20 Delta. Strict 8% premium floor. 50% GTC take-profit set instantly. Never manually close before 21 DTE to avoid Gamma risk.
                        </div>
                        <div class="text-[11px] text-gray-700 leading-relaxed pr-2">
                            <span class="font-bold text-yellow-800 block mb-1">STRATEGY & EXECUTION:</span>
                            13F Themes (Druckenmiller, Ackman) executed via Sector UCITS ETFs to eliminate CFD financing drag. High-conviction social sentiment (Shay, Pelosi, UncleAlpha) executed via CFDs with strict 30-45 day time-stops to cap overnight fees. Ruthlessly cut losers.
                        </div>
                    </div>

                </div>

            </div>

            <!-- DAILY PNL HISTOGRAM -->
            <div class="xl:col-span-12 mt-2">
                <div class="bg-white border rounded-xl p-4 shadow-sm overflow-hidden">
                    <h3 class="text-xl font-bold mb-4 text-gray-800 border-b pb-2">3. Daily PnL per Silo</h3>
                    <div id="daily-pnl-chart" class="w-full h-[400px]"></div>
                    
                    <div class="mt-4 pt-3 border-t border-gray-200 text-[11px] text-gray-600 leading-relaxed bg-gray-50 p-3 rounded-lg border">
                        <span class="font-bold text-gray-800 uppercase tracking-wide">TOR (Total Open Risk) Tracker:</span> 
                        Applies strictly to <b>Silo B</b> (Active Swing). TOR is the sum of risk across all open positions (Distance from Entry to Stop Loss). Once a trade reaches +1R profit, moving the stop to break-even reduces its specific TOR contribution to 0.<br>
                        
                        <div class="mt-2 flex flex-wrap gap-4 items-center">
                            <span class="font-bold text-gray-800 uppercase tracking-wide">Regime Key:</span> 
                            <span class="flex items-center"><span class="inline-block w-3 h-3 bg-green-600 rounded-full mr-1"></span><b>Green (3-5 TOR):</b> SPY > 10 SMA > 20 SMA. Low VIX permits max risk exposure.</span>
                            <span class="flex items-center"><span class="inline-block w-3 h-3 bg-yellow-400 rounded-full mr-1"></span><b>Yellow (1-3 TOR):</b> Pullbacks/Transitions. Risk is throttled.</span>
                            <span class="flex items-center"><span class="inline-block w-3 h-3 bg-red-600 rounded-full mr-1"></span><b>Red (0-1 TOR):</b> SPY < 20 SMA < 10 SMA. Defensive stance. VIX > 25 halts all active trading (TOR = 0).</span>
                        </div>
                    </div>
                </div>
            </div>

            <!-- SECTION 4: MONTE CARLO & PNL ATTRIBUTION -->
            <div class="xl:col-span-12 mt-2 grid grid-cols-1 xl:grid-cols-12 gap-4">
                
                <!-- MONTE CARLO (Left - 6 cols) -->
                <div class="xl:col-span-6 bg-white border rounded-xl p-4 shadow-sm overflow-hidden flex flex-col">
                    <h3 class="text-xl font-bold mb-4 text-gray-800 border-b pb-2">4. Estate Montecarlo PnL Simulation - Projections vs History</h3>
                    <div id="montecarlo-chart" class="w-full flex-grow min-h-[450px]"></div>
                </div>
                                       
                <!-- PNL ATTRIBUTION & VELOCITY (Right - 6 cols) -->
                <div class="xl:col-span-6 bg-white border rounded-xl p-4 shadow-sm flex flex-col">
                    <h3 class="text-xl font-bold mb-4 text-gray-800 border-b pb-2">PnL Attribution & Capital Velocity</h3>
                    
                    <div class="grid grid-cols-1 lg:grid-cols-2 gap-4 flex-grow mb-4 border-b border-gray-100 pb-2">
                        <div id="pnl-bar-chart" class="w-full h-[320px]"></div>
                        <div id="pnl-line-chart" class="w-full h-[320px]"></div>
                    </div>
                    
                    <!-- PnL Legend / Footer Updates -->
                    <div class="mb-4 text-[10px] text-gray-600 leading-tight bg-gray-50 p-2 rounded border border-gray-200">
                        <span class="text-blue-500 font-bold">Risk-Free Yield (a1):</span> T-Bill Interest (IB01/Cash).<br>
                        <span class="text-orange-500 font-bold">Core Beta (a2):</span> Long-term physical equities (CSPX/CNDX).<br>
                        <span class="text-green-500 font-bold">VRP Engine (a3):</span> Options premium (Silos A & C XSP/XND Puts).<br>
                        <span class="text-purple-500 font-bold">Active Alpha (a4):</span> Swing/Momentum plays & explicit regional ETFs.<br>
                        <span class="text-red-500 font-bold">Commissions & Fees (a5):</span> Explicit friction pulled directly from IBKR Ledger.
                    </div>
                    
                    <div class="flex flex-col justify-end">
                        <h4 class="text-xs font-black text-gray-500 uppercase tracking-widest mb-3">Options Engine (Silos A & C) Velocity (v68 Automated)</h4>                        
                        
                        <div class="grid grid-cols-2 gap-3">
                            <div class="bg-gray-50 border border-gray-200 rounded-lg p-3 text-center">
                                <p class="text-[10px] text-gray-500 font-bold uppercase mb-1">Win Rate</p>
                                <p class="text-xl font-black text-green-700">VAR_VEL_WINRATE%</p>
                            </div>
                            <div class="bg-gray-50 border border-gray-200 rounded-lg p-3 text-center">
                                <p class="text-[10px] text-gray-500 font-bold uppercase mb-1">Avg Days in Trade</p>
                                <p class="text-xl font-black text-blue-700">VAR_VEL_AVGDAYS d</p>
                            </div>
                            <div class="bg-gray-50 border border-gray-200 rounded-lg p-3 text-center col-span-2 flex justify-between items-center px-4">
                                <span class="text-[10px] text-gray-500 font-bold uppercase">Target Profit Hit</span>
                                <span class="text-sm font-black text-gray-800">50% GTC</span>
                            </div>
                        </div>
                    </div>
                </div>
            </div>

            <!-- BOTTOM ROW: THE DYNAMIC MATRIX -->
            <div class="xl:col-span-12 mt-2">
                <div class="bg-white border rounded-xl p-4 shadow-sm overflow-x-auto">
                    <h3 class="text-xl font-bold mb-4 text-gray-800 border-b pb-2">5. The Master Instrument Matrix (Tax, Alpha, & Sharpe Grading)</h3>
                    <table class="min-w-full bg-white text-[12px] whitespace-nowrap border-collapse">
                        <thead class="bg-slate-800 text-white">
                            <tr>
                                <th class="py-3 px-3 text-left">Instrument</th>
                                <th class="py-3 px-3 text-left">Type</th>
                                <th class="py-3 px-3 text-left">Risk Profile</th>
                                <th class="py-3 px-3 text-left">Alpha Potential</th>
                                <th class="py-3 px-3 text-left">Sharpe Impact</th>
                                <th class="py-3 px-3 text-left">Trading Strategy</th>
                                <th class="py-3 px-3 text-left">Jurisdiction</th>
                                <th class="py-3 px-3 text-left">Tax Treatment</th>
                                <th class="py-3 px-3 text-center border-l border-gray-600 bg-slate-700">CIO Min<br>Alloc. %</th>
                                <th class="py-3 px-3 text-center bg-slate-700 font-bold text-yellow-300">Current Global<br>Alloc. %</th>
                                <th class="py-3 px-3 text-center border-r border-gray-600 bg-slate-700">CIO Max<br>Alloc. %</th>
                                <th class="py-3 px-3 text-center">CIO<br>Grading</th>
                                <th class="py-3 px-3 text-left w-1/4">Noteworthy Comments</th>
                            </tr>
                        </thead>
                        <tbody class="divide-y divide-gray-200 whitespace-normal" id="matrix-body">
                        </tbody>                      

                        <tfoot class="bg-gray-100 font-bold text-gray-900 border-t-2 border-gray-400">
                            <tr>
                                <td colspan="9" class="py-3 px-3 text-right leading-tight">
                                    GROSS PHYSICAL ASSETS:<br>
                                    <span class="text-[10px] text-red-600">OPTIONS LIABILITY DRAG:</span><br>
                                    TRUE NET ESTATE CHECKSUM:
                                </td>
                                <td class="py-3 px-3 text-center text-blue-700 text-sm leading-tight" id="alloc_total">
                                    0.00%<br>
                                    <span class="text-[10px] text-red-600">0.00%</span><br>
                                    0.00%
                                </td>
                                <td colspan="3" class="py-3 px-3 text-left text-[10px] text-gray-500 whitespace-nowrap align-bottom">Must exactly equal 100.00%</td>
                            </tr>
                        </tfoot>
                    </table>
                </div>
            </div>

            <!-- ========================================================= -->
            <!-- PANEL 6: DEPLOYMENT & CAPACITY TRACKER                    -->
            <!-- ========================================================= -->
            <div class="xl:col-span-12 mt-2">
                <div class="bg-white border rounded-xl p-4 shadow-sm">
                    <h3 class="text-xl font-bold mb-4 text-gray-800 border-b pb-2">6. Capital Deployment & Margin Capacity Tracker</h3>
                    <div class="grid grid-cols-1 md:grid-cols-3 gap-6">
                        
                        <!-- Cash Buffer -->
                        <div class="bg-gray-50 border border-gray-200 rounded-lg p-4 relative overflow-hidden flex flex-col justify-between">
                            <div>
                                <div class="absolute right-0 top-0 w-2 h-full bg-blue-400"></div>
                                <h4 class="text-sm font-black text-gray-800 uppercase tracking-wide mb-1">Bedrock Cash Buffer (IB01 + USD)</h4>
                                <p class="text-xs text-gray-500 mb-3 border-b pb-2">Target Minimum: 40% of Estate</p>
                                <div class="flex justify-between items-end mb-1">
                                    <span class="text-2xl font-black text-blue-700" id="trk_cash_val">$0</span>
                                    <span class="text-sm font-bold text-gray-700" id="trk_cash_pct">0%</span>
                                </div>
                                <div class="w-full bg-white border border-gray-300 rounded-full h-3 mb-1 flex overflow-hidden" id="trk_cash_bar_container"></div>
                                <div class="flex justify-between text-[9px] text-gray-400 font-bold px-1 mb-2">
                                    <span>0%</span><span class="text-red-500 font-black">| 40% Min Floor</span><span>100%</span>
                                </div>
                                <p class="text-[11px] text-gray-600 font-bold mt-2" id="trk_cash_status">Status: Calculating...</p>                                
                                                              
                                <div class="mt-4 pt-3 border-t border-gray-200 bg-white p-2 rounded border border-gray-100 shadow-sm">
                                    <h5 class="text-[10px] font-black text-gray-700 uppercase mb-1.5 flex justify-between"><span>Upcoming Deployments</span><span class="text-blue-600" id="dyn_total_deploy">Calculating...</span></h5>
                                    <ul class="text-[10px] text-gray-600 font-mono space-y-1" id="dyn_schedule_list">
                                        <!-- JS will inject dynamic dates and amounts here -->
                                    </ul>
                                </div>                                
                            </div>
                        </div>

                        <!-- Options Margin -->
                        <div class="bg-gray-50 border border-gray-200 rounded-lg p-4 relative overflow-hidden flex flex-col justify-between">
                            <div>
                                <div class="absolute right-0 top-0 w-2 h-full bg-green-500"></div>
                                <h4 class="text-sm font-black text-gray-800 uppercase tracking-wide mb-1">Options Margin Utilization</h4>
                                <p class="text-xs text-gray-500 mb-3 border-b pb-2" id="trk_margin_sub">Estate Safety Cap: 25% of Net Liq</p>
                                <div class="flex justify-between items-end mb-1">
                                    <span class="text-2xl font-black text-green-700" id="trk_margin_val">$0</span>
                                    <span class="text-sm font-bold text-gray-700" id="trk_margin_pct">0%</span>
                                </div>
                                <div class="w-full bg-gray-200 rounded-full h-3 mb-1 overflow-hidden">
                                    <div class="bg-green-500 h-full" id="trk_margin_bar" style="width: 0%"></div>
                                </div>
                                <div class="flex justify-between text-[9px] text-gray-400 font-bold px-1 mb-2">
                                    <span>0% Capacity</span><span>100% of Allowed Capacity</span>
                                </div>
                            </div>
                            <p class="text-[11px] text-gray-600 font-bold mt-2" id="trk_margin_status">Status: Calculating...</p>
                        </div>

                        <!-- Action Plan -->
                        <div class="bg-gray-50 border border-gray-200 rounded-lg p-4 relative overflow-hidden">
                            <div class="absolute right-0 top-0 w-2 h-full bg-purple-500"></div>
                            <h4 class="text-sm font-black text-gray-800 uppercase tracking-wide mb-1">DCA Deployment Schedule</h4>
                            <p class="text-xs text-gray-500 mb-3 border-b pb-2">Based on current Market Regime</p>
                            <div class="flex flex-col justify-center mt-2">
                                <span class="text-xs font-medium text-gray-800 leading-relaxed" id="trk_dca_action">Awaiting Regime Data...</span>
                            </div>
                        </div>

                    </div>
                </div>
            </div>
            <!-- End Panel 6 -->

        </div>
    </div>

    <script>

        function fmtCur(val) { return ' USD ' + Math.round(val).toLocaleString('en-US'); }
        function safeParse(jsonStr) {
            try {
                if (!jsonStr || jsonStr.startsWith('VAR_')) return[]; 
                return JSON.parse(jsonStr);
            } catch (e) { return[]; }
        }
        
        const palette = {
            siloA: '#93c5fd', siloB: '#d8b4fe', siloC: '#86efac', siloD: '#fde047',
            cspx: '#f97316', cndx: '#8b5cf6', cfd_intl: '#a855f7', optMktVal: '#ef4444', 
            crypto: '#0ea5e9', itwn: '#14b8a6', cskr: '#f472b6', cnya: '#fb923c'
        };

        const instruments =[
            { id: "cash", inst: "USD Cash", type: "Currency", risk: "Risk-Free", alpha: "Zero", sharpe: "Stabilizer", strat: "Liquidity", jur: "US (IBKR)", tax: "Exempt (Bank Deposit)", min: "1%", max: "100%", rec: "Splendid", class: "splendid", comm: "Uninvested USD held in IBKR. Mandatory margin collateral." },
            { id: "ib01", inst: "IB01", type: "UCITS ETF", risk: "Risk-Free", alpha: "Zero", sharpe: "High", strat: "Collateral", jur: "Ireland", tax: "Exempt (Irish Domicile)", min: "10%", max: "100%", rec: "Splendid", class: "splendid", comm: "Irish-domiciled short-term US Treasury fund. Accumulates ~4.5% tax-free." },
            { id: "xsp", inst: "XSP Put Spreads", type: "Index Option", risk: "Moderate", alpha: "High (VRP)", sharpe: "High", strat: "Weekly Income", jur: "US (Cboe)", tax: "Exempt (Cash-Settled)", min: "0%", max: "25%", rec: "Splendid", class: "splendid", comm: "Cash-settled S&P 500 options. 100% safe from IRS." },
            { id: "xnd", inst: "XND Put Spreads", type: "Index Option", risk: "Mod/High", alpha: "High", sharpe: "Moderate", strat: "Satellite Income", jur: "US (Cboe)", tax: "Exempt (Cash-Settled)", min: "0%", max: "10%", rec: "Great", class: "great", comm: "Micro-Nasdaq 100. Cash-settled. IRS Safe. Higher volatility than XSP." },
            { id: "cspx", inst: "CSPX", type: "UCITS ETF", risk: "Moderate", alpha: "Zero", sharpe: "Baseline", strat: "Long Term", jur: "Ireland", tax: "Exempt (Irish Domicile)", min: "0%", max: "60%", rec: "Great", class: "great", comm: "Irish-domiciled S&P 500. Shields against 40% Estate Tax." },
            { id: "cndx", inst: "CNDX", type: "UCITS ETF", risk: "Aggressive", alpha: "High", sharpe: "Moderate", strat: "Long Term", jur: "Ireland", tax: "Exempt (Irish Domicile)", min: "0%", max: "40%", rec: "Great", class: "great", comm: "Irish-domiciled Nasdaq 100. Shields against 40% Estate Tax. High beta tech exposure." },
            { id: "itwn", inst: "ITWN (Taiwan)", type: "UCITS ETF", risk: "Aggressive", alpha: "High", sharpe: "Moderate", strat: "Momentum", jur: "Ireland", tax: "Exempt (Irish Domicile)", min: "0%", max: "20%", rec: "Great", class: "great", comm: "Geographic tech alpha via Irish wrapper." },
            { id: "cskr", inst: "CSKR (Korea)", type: "UCITS ETF", risk: "Aggressive", alpha: "High", sharpe: "Moderate", strat: "Momentum", jur: "Ireland", tax: "Exempt (Irish Domicile)", min: "0%", max: "15%", rec: "Great", class: "great", comm: "Geographic tech alpha via Irish wrapper." },
            { id: "cnya", inst: "CNYA (China)", type: "UCITS ETF", risk: "Aggressive", alpha: "High", sharpe: "Volatile", strat: "Momentum", jur: "Ireland", tax: "Exempt (Irish Domicile)", min: "0%", max: "10%", rec: "Great", class: "great", comm: "Geographic tech alpha via Irish wrapper." },
            { id: "gold", inst: "SGLN / IGLN (Gold)", type: "UCITS ETC", risk: "Moderate", alpha: "Crisis Alpha", sharpe: "Stabilizer", strat: "Tail Hedge", jur: "Ireland", tax: "Exempt (Irish Domicile)", min: "0%", max: "10%", rec: "Good", class: "good", comm: "Geopolitical crisis hedge. Rises during interest rate cuts and wars." },
            { id: "crypto", inst: "BTC/ETH ETPs", type: "Crypto ETP", risk: "Aggressive", alpha: "High", sharpe: "Volatile", strat: "Uncorrelated", jur: "Europe (Jersey/CH)", tax: "Exempt (Offshore Wrapper)", min: "0%", max: "5%", rec: "Good", class: "good", comm: "Offshore crypto wrappers (e.g. CoinShares). IRS safe spot exposure." },
            { id: "cfd", inst: "US Tech CFDs", type: "OTC Contract", risk: "Aggressive", alpha: "High", sharpe: "Negative", strat: "Swing Trading", jur: "UK/Offshore", tax: "Exempt (OTC Derivative)", min: "0%", max: "3%", rec: "Good", class: "good", comm: "Synthetic derivatives. 0% IRS risk. Quarantined to Silo B." },
            { id: "intl", inst: "International Stocks", type: "Direct Equity", risk: "Aggressive", alpha: "High", sharpe: "Negative", strat: "Swing Trading", jur: "Europe/Asia", tax: "Exempt", min: "0%", max: "3%", rec: "Good", class: "good", comm: "Safe from IRS. Suffers from wider bid/ask spreads compared to US market." },
            { id: "mes", inst: "/MES Put Spreads", type: "Futures Option", risk: "Moderate", alpha: "Highest (SPAN)", sharpe: "High", strat: "Capital Efficiency", jur: "US (CME)", tax: "Exempt (Section 1256)", min: "0%", max: "25%", rec: "Contingent", class: "contingent", comm: "Contingent on mastering XSP mechanics. SPAN margin halves collateral, doubling ROC." },
            { id: "cta", inst: "Managed Futures (CTAs)", type: "UCITS Fund", risk: "Moderate", alpha: "Crisis Alpha", sharpe: "High (Uncorrel.)", strat: "Trend Following", jur: "Ireland", tax: "Exempt (Irish Domicile)", min: "0%", max: "15%", rec: "Contingent", class: "contingent", comm: "Contingent on risk tolerance change. Shorts commodities & bonds to protect during crashes." },
            { id: "leaps", inst: "XSP LEAPS", type: "Index Option", risk: "Aggressive", alpha: "Low", sharpe: "Negative", strat: "Leverage", jur: "US (Cboe)", tax: "Exempt (Cash-Settled)", min: "0%", max: "0%", rec: "Bad", class: "bad", comm: "IRS safe, but mathematical drag of Theta and lost dividends destroys edge." },
            { id: "phys", inst: "Physical US Stocks", type: "Stock", risk: "Extreme", alpha: "High", sharpe: "Baseline", strat: "Swing", jur: "US", tax: "LETHAL (40% Estate Tax)", min: "0%", max: "0%", rec: "Avoid", class: "avoid", comm: "LETHAL. Triggers 40% US Estate Tax and 30% Dividend Withholding." },
            { id: "us_crypto", inst: "US Spot BTC/ETH", type: "US ETF", risk: "Extreme", alpha: "N/A", sharpe: "N/A", strat: "N/A", jur: "US", tax: "LETHAL (40% Estate Tax)", min: "0%", max: "0%", rec: "Avoid", class: "avoid", comm: "LETHAL. Standard ETFs (IBIT/FBTC) are US-situs property. Will trigger Estate Tax confiscation." },
            { id: "tqqq", inst: "TQQQ", type: "Physical ETF", risk: "Extreme", alpha: "Negative", sharpe: "Negative", strat: "Speculation", jur: "US", tax: "LETHAL (40% Estate Tax)", min: "0%", max: "0%", rec: "Avoid", class: "avoid", comm: "LETHAL. Widow-maker. Combines IRS Tax Trap with massive Beta Slippage decay." }
        ];

        function populateTable() {
            const tbody = document.getElementById('matrix-body');
            let html = "";
            instruments.forEach(i => {
                html += `<tr class="hover:bg-gray-50 border-b border-gray-100">
                    <td class="py-2 px-3 font-semibold text-gray-900">${i.inst}</td>
                    <td class="py-2 px-3">${i.type}</td>
                    <td class="py-2 px-3">${i.risk}</td>
                    <td class="py-2 px-3">${i.alpha}</td>
                    <td class="py-2 px-3 font-medium text-indigo-700">${i.sharpe}</td>
                    <td class="py-2 px-3">${i.strat}</td>
                    <td class="py-2 px-3">${i.jur}</td>
                    <td class="py-2 px-3">${i.tax}</td>
                    <td class="py-2 px-3 font-bold text-center text-gray-500 border-l border-gray-200 bg-gray-50">${i.min}</td>
                    <td class="py-2 px-3 font-black text-center text-blue-700 bg-blue-50" id="alloc_${i.id}">0.00%</td>
                    <td class="py-2 px-3 font-bold text-center border-r border-gray-200 bg-gray-50">${i.max}</td>
                    <td class="py-2 px-3 ${i.class} text-center rounded">${i.rec}</td>
                    <td class="py-2 px-3 text-xs text-gray-700">${i.comm}</td>
                </tr>`;
            });
            tbody.innerHTML = html;
        }

        function updateUI() {
            const sA = parseFloat(document.getElementById('siloA').value) || 0;
            const sB = parseFloat(document.getElementById('siloB').value) || 0;
            const sC = parseFloat(document.getElementById('siloC').value) || 0;
            const sD = parseFloat(document.getElementById('siloD').value) || 0;
            
            let amt_D_cfd = 0;
            for(let i=1; i<=10; i++) {
                amt_D_cfd += parseFloat(document.getElementById('d_val_'+i).value) || 0;
            }
            let amt_D_cash = parseFloat(document.getElementById('d_val_cash').value) || 0;
            let totalEstate = sA + sB + sC + sD;

            // v68 Progressive Exposure Advisor Inject
            const progExp = safeParse('VAR_PROG_EXP');
            if (progExp && progExp.Silo_B) {
                let b = progExp.Silo_B;
                document.getElementById('b_tier_lbl').innerText = `Advisory: Base $${(b.suggested_base/1000).toFixed(0)}k (${b.current_tier})`;
                document.getElementById('b_tier_next').innerText = `Next: ${b.next_threshold === "MAX" ? 'MAX' : '$'+(b.next_threshold/1000).toFixed(1)+'k'}`;
                document.getElementById('b_tier_dist').innerText = `Profit: $${b.profit.toLocaleString()} | Shortfall: $${b.distance_to_next.toLocaleString()}`;
                let pct = b.next_threshold === "MAX" ? 100 : Math.max(0, Math.min(100, (b.profit / b.next_threshold) * 100));
                document.getElementById('b_tier_bar').style.width = pct + "%";
            }
            
            if (progExp && progExp.Silo_D) {
                let d = progExp.Silo_D;
                document.getElementById('d_tier_lbl').innerText = `Advisory: Base $${(d.suggested_base/1000).toFixed(0)}k (${d.current_tier})`;
                document.getElementById('d_tier_next').innerText = `Next: ${d.next_threshold === "MAX" ? 'MAX' : '$'+(d.next_threshold/1000).toFixed(1)+'k'}`;
                document.getElementById('d_tier_dist').innerText = `Profit: $${d.profit.toLocaleString()} | Shortfall: $${d.distance_to_next.toLocaleString()}`;
                let pct = d.next_threshold === "MAX" ? 100 : Math.max(0, Math.min(100, (d.profit / d.next_threshold) * 100));
                document.getElementById('d_tier_bar').style.width = pct + "%";
            }

            // Silo A
            let amt_A_ib01 = parseFloat(document.getElementById('a_ib01').value) || 0; let amt_A_cspx = parseFloat(document.getElementById('a_cspx').value) || 0;
            let amt_A_cndx = parseFloat(document.getElementById('a_cndx').value) || 0; let amt_A_crypto = parseFloat(document.getElementById('a_crypto').value) || 0; 
            let amt_A_cash = parseFloat(document.getElementById('a_cash').value) || 0; let amt_A_itwn = parseFloat(document.getElementById('a_itwn').value) || 0;
            let amt_A_cskr = parseFloat(document.getElementById('a_cskr').value) || 0; let amt_A_cnya = parseFloat(document.getElementById('a_cnya').value) || 0;
            let amt_A_opt_mkt = parseFloat(document.getElementById('a_opt_mkt').value) || 0; let amt_A_xsp = parseFloat(document.getElementById('a_xsp').value) || 0;
            
            document.getElementById('a_ib01_lbl').value = `IB01 (${sA>0 ? (amt_A_ib01/sA*100).toFixed(1) : 0}%)`;
            document.getElementById('a_cspx_lbl').value = `CSPX (${sA>0 ? (amt_A_cspx/sA*100).toFixed(1) : 0}%)`;
            document.getElementById('a_cndx_lbl').value = `CNDX (${sA>0 ? (amt_A_cndx/sA*100).toFixed(1) : 0}%)`;
            document.getElementById('a_itwn_lbl').value = `ITWN (${sA>0 ? (amt_A_itwn/sA*100).toFixed(1) : 0}%)`;
            document.getElementById('a_cskr_lbl').value = `CSKR (${sA>0 ? (amt_A_cskr/sA*100).toFixed(1) : 0}%)`;
            document.getElementById('a_cnya_lbl').value = `CNYA (${sA>0 ? (amt_A_cnya/sA*100).toFixed(1) : 0}%)`;
            document.getElementById('a_crypto_lbl').value = `Crypto (${sA>0 ? (amt_A_crypto/sA*100).toFixed(1) : 0}%)`;
            document.getElementById('a_cash_lbl').value = `Cash (${sA>0 ? (amt_A_cash/sA*100).toFixed(1) : 0}%)`;
            
            let a_tot_phys = amt_A_ib01 + amt_A_cspx + amt_A_cndx + amt_A_itwn + amt_A_cskr + amt_A_cnya + amt_A_crypto + amt_A_cash;
            let diffA = sA - (a_tot_phys + amt_A_opt_mkt);
            if (Math.abs(diffA) > 1.0) {
                document.getElementById('a_warning').innerText = `Unallocated: $${diffA.toFixed(2)}`;
                document.getElementById('a_warning').className = "text-[10px] text-red-600 font-bold mt-1 h-4";
            } else {
                document.getElementById('a_warning').innerText = "Balanced: OK";
                document.getElementById('a_warning').className = "text-[10px] text-green-600 font-bold mt-1 h-4";
            }

            // Silo B
            let amt_B_cash = parseFloat(document.getElementById('b_cash').value) || 0; 
            let amt_B_cfd = parseFloat(document.getElementById('b_cfd').value) || 0; 
            let amt_B_intl = parseFloat(document.getElementById('b_intl').value) || 0;
            
            document.getElementById('b_cash_lbl').value = `Cash (${sB>0 ? (amt_B_cash/sB*100).toFixed(1) : 0}%)`;
            document.getElementById('b_cfd_lbl').value = `US Tech CFDs (${sB>0 ? (amt_B_cfd/sB*100).toFixed(1) : 0}%)`;
            document.getElementById('b_intl_lbl').value = `Intl Stocks (${sB>0 ? (amt_B_intl/sB*100).toFixed(1) : 0}%)`;

            let b_tot_phys = amt_B_cash + amt_B_cfd + amt_B_intl;
            let diffB = sB - b_tot_phys;
            if (Math.abs(diffB) > 1.0) {
                document.getElementById('b_warning').innerText = `Unallocated: $${diffB.toFixed(2)}`;
                document.getElementById('b_warning').className = "text-[10px] text-red-600 font-bold mt-1 h-4";
            } else {
                document.getElementById('b_warning').innerText = "Balanced: OK";
                document.getElementById('b_warning').className = "text-[10px] text-green-600 font-bold mt-1 h-4";
            }

            // Silo C
            let amt_C_ib01 = parseFloat(document.getElementById('c_ib01').value) || 0; let amt_C_cspx = parseFloat(document.getElementById('c_cspx').value) || 0;
            let amt_C_cndx = parseFloat(document.getElementById('c_cndx').value) || 0; let amt_C_crypto = parseFloat(document.getElementById('c_crypto').value) || 0; 
            let amt_C_cash = parseFloat(document.getElementById('c_cash').value) || 0; let amt_C_itwn = parseFloat(document.getElementById('c_itwn').value) || 0;
            let amt_C_cskr = parseFloat(document.getElementById('c_cskr').value) || 0; let amt_C_cnya = parseFloat(document.getElementById('c_cnya').value) || 0;
            let amt_C_opt_mkt = parseFloat(document.getElementById('c_opt_mkt').value) || 0; let amt_C_xsp = parseFloat(document.getElementById('c_xsp').value) || 0;
            
            document.getElementById('c_ib01_lbl').value = `IB01 (${sC>0 ? (amt_C_ib01/sC*100).toFixed(1) : 0}%)`;
            document.getElementById('c_cspx_lbl').value = `CSPX (${sC>0 ? (amt_C_cspx/sC*100).toFixed(1) : 0}%)`;
            document.getElementById('c_cndx_lbl').value = `CNDX (${sC>0 ? (amt_C_cndx/sC*100).toFixed(1) : 0}%)`;
            document.getElementById('c_itwn_lbl').value = `ITWN (${sC>0 ? (amt_C_itwn/sC*100).toFixed(1) : 0}%)`;
            document.getElementById('c_cskr_lbl').value = `CSKR (${sC>0 ? (amt_C_cskr/sC*100).toFixed(1) : 0}%)`;
            document.getElementById('c_cnya_lbl').value = `CNYA (${sC>0 ? (amt_C_cnya/sC*100).toFixed(1) : 0}%)`;
            document.getElementById('c_crypto_lbl').value = `Crypto (${sC>0 ? (amt_C_crypto/sC*100).toFixed(1) : 0}%)`;
            document.getElementById('c_cash_lbl').value = `Cash (${sC>0 ? (amt_C_cash/sC*100).toFixed(1) : 0}%)`;
            
            let c_tot_phys = amt_C_ib01 + amt_C_cspx + amt_C_cndx + amt_C_itwn + amt_C_cskr + amt_C_cnya + amt_C_crypto + amt_C_cash;
            let diffC = sC - (c_tot_phys + amt_C_opt_mkt);
            if (Math.abs(diffC) > 1.0) {
                document.getElementById('c_warning').innerText = `Unallocated: $${diffC.toFixed(2)}`;
                document.getElementById('c_warning').className = "text-[10px] text-red-600 font-bold mt-1 h-4";
            } else {
                document.getElementById('c_warning').innerText = "Balanced: OK";
                document.getElementById('c_warning').className = "text-[10px] text-green-600 font-bold mt-1 h-4";
            }

            // Silo D
            document.getElementById('d_cash_lbl').value = `Cash Bal (${sD>0 ? (amt_D_cash/sD*100).toFixed(1) : 0}%)`;

            let d_tot_phys = amt_D_cfd + amt_D_cash;
            let diffD = sD - d_tot_phys;
            if (Math.abs(diffD) > 1.0) {
                document.getElementById('d_warning').innerText = `Unallocated: $${diffD.toFixed(2)}`;
                document.getElementById('d_warning').className = "text-[10px] text-red-600 font-bold mt-1 h-4";
            } else {
                document.getElementById('d_warning').innerText = "Balanced: OK";
                document.getElementById('d_warning').className = "text-[10px] text-green-600 font-bold mt-1 h-4";
            }

            // Aggregation & Risk Radars
            let tot_ib01 = amt_A_ib01 + 0 + amt_C_ib01 + 0;
            let tot_cspx = amt_A_cspx + amt_C_cspx + 0;
            let tot_cndx = amt_A_cndx + amt_C_cndx + 0;
            let tot_itwn = amt_A_itwn + 0 + amt_C_itwn + 0;
            let tot_cskr = amt_A_cskr + 0 + amt_C_cskr + 0;
            let tot_cnya = amt_A_cnya + 0 + amt_C_cnya + 0;
            let tot_crypto = amt_A_crypto + amt_C_crypto + 0;
            let tot_cash = amt_A_cash + amt_B_cash + amt_C_cash + amt_D_cash;
            let tot_opt_mkt = amt_A_opt_mkt + amt_C_opt_mkt;
            let tot_cfd = amt_B_cfd + amt_D_cfd; 
            let tot_intl = amt_B_intl; 

            // Risk Alerts Logic
            let techSemiPct = totalEstate > 0 ? ((tot_cndx + tot_itwn + tot_cskr + tot_cfd) / totalEstate) * 100 : 0; 
            let asiaPct = totalEstate > 0 ? ((tot_itwn + tot_cskr + tot_cnya) / totalEstate) * 100 : 0;
            let cashPct = totalEstate > 0 ? ((tot_ib01 + tot_cash) / totalEstate) * 100 : 0;

            let alertsHtml = "";
            if (techSemiPct > 40) {
                alertsHtml += `<div class="bg-red-100 border-l-4 border-red-600 text-red-800 p-3 text-sm font-bold shadow-sm rounded-r">⚠️ SECTOR RADAR: Tech/Semi concentration is ${techSemiPct.toFixed(1)}% (>40% safe threshold). Vulnerability to Nasdaq crash detected.</div>`;
            }
            if (asiaPct > 30) {
                alertsHtml += `<div class="bg-orange-100 border-l-4 border-orange-500 text-orange-800 p-3 text-sm font-bold shadow-sm rounded-r">⚠️ GEO RADAR: Asian exposure (Taiwan/Korea/China) is ${asiaPct.toFixed(1)}% (>30% threshold).</div>`;
            }
            if (cashPct > 60) {
                alertsHtml += `<div class="bg-blue-100 border-l-4 border-blue-500 text-blue-800 p-3 text-sm font-bold shadow-sm rounded-r">ℹ️ CASH DRAG: Unleveraged Cash/IB01 is ${cashPct.toFixed(1)}%. Consider deploying to Vaults if market is in uptrend.</div>`;
            }
            document.getElementById('risk-alerts').innerHTML = alertsHtml;

            // Dynamic Matrix Injection & Total Checksum
            const allocMap = {
                "USD Cash": tot_cash, "IB01": tot_ib01, "CSPX": tot_cspx, "CNDX": tot_cndx,
                "ITWN (Taiwan)": tot_itwn, "CSKR (Korea)": tot_cskr, "CNYA (China)": tot_cnya,
                "BTC/ETH ETPs": tot_crypto, "US Tech CFDs": tot_cfd, "International Stocks": tot_intl 
            };

            let totalPhysicalAllocPct = 0;
            instruments.forEach(i => {
                let el = document.getElementById(`alloc_${i.id}`);
                if (el) {
                    if (allocMap[i.inst] !== undefined) {
                        let pct = (totalEstate > 0) ? (allocMap[i.inst] / totalEstate) * 100 : 0;
                        el.innerText = pct.toFixed(2) + "%";
                        totalPhysicalAllocPct += pct;
                    } else {
                        el.innerText = "N/A"; 
                        el.classList.replace('text-blue-700', 'text-gray-400');
                    }
                }
            });
            
            let optLiabPct = (totalEstate > 0) ? (tot_opt_mkt / totalEstate) * 100 : 0;
            let trueNetChecksum = totalPhysicalAllocPct + optLiabPct;
            
            let totalEl = document.getElementById('alloc_total');
            totalEl.innerHTML = `${totalPhysicalAllocPct.toFixed(2)}%<br><span class="text-[10px] text-red-600">${optLiabPct.toFixed(2)}%</span><br><span class="text-black font-black">${trueNetChecksum.toFixed(2)}%</span>`;
            
            if (Math.abs(trueNetChecksum - 100) > 0.05) {
                totalEl.classList.replace('text-blue-700', 'text-red-600');
            } else {
                totalEl.classList.replace('text-red-600', 'text-blue-700');
            }

            // Charts Formatting Logic
            const xLabels =['Silo A', 'Silo B', 'Silo C', 'Silo D'];
            let barData = [
                { x: xLabels, y:[amt_A_ib01, 0, amt_C_ib01, 0], name: 'IB01', type: 'bar', marker: {color: palette.siloA} },
                { x: xLabels, y: [amt_A_cspx, 0, amt_C_cspx, 0], name: 'CSPX', type: 'bar', marker: {color: palette.cspx} },
                { x: xLabels, y:[amt_A_cndx, 0, amt_C_cndx, 0], name: 'CNDX', type: 'bar', marker: {color: palette.cndx} },
                { x: xLabels, y:[amt_A_itwn, 0, amt_C_itwn, 0], name: 'ITWN', type: 'bar', marker: {color: palette.itwn} },
                { x: xLabels, y:[amt_A_cskr, 0, amt_C_cskr, 0], name: 'CSKR', type: 'bar', marker: {color: palette.cskr} },
                { x: xLabels, y:[amt_A_cnya, 0, amt_C_cnya, 0], name: 'CNYA', type: 'bar', marker: {color: palette.cnya} },
                { x: xLabels, y:[amt_A_crypto, 0, amt_C_crypto, 0], name: 'Crypto', type: 'bar', marker: {color: palette.crypto} },
                { x: xLabels, y:[0, (amt_B_cfd+amt_B_intl), 0, amt_D_cfd], name: 'CFDs/Intl', type: 'bar', marker: {color: palette.cfd_intl} },
                { x: xLabels, y:[amt_A_cash, amt_B_cash, amt_C_cash, amt_D_cash], name: 'Cash', type: 'bar', marker: {color: palette.siloC} }
            ];

            if (Math.abs(tot_opt_mkt) > 0) {
                barData.push({ x: xLabels, y:[amt_A_opt_mkt, 0, amt_C_opt_mkt, 0], name: 'Opt Liab', type: 'bar', marker: {color: palette.optMktVal} });
            }
            if (amt_A_xsp > 0 || amt_C_xsp > 0) {
                barData.push({ x:['Silo A', 'Silo C'], y:[amt_A_xsp, amt_C_xsp], name: 'Margin Lock', type: 'scatter', mode: 'markers', marker: {symbol: 'diamond', size: 14, color: '#ef4444'} });
            }

            // PANEL 6 LOGIC (Deployment Tracker)
            let totalCashBuffer = tot_ib01 + tot_cash;
            let cashBufferPct = totalEstate > 0 ? (totalCashBuffer / totalEstate) * 100 : 0;
            document.getElementById('trk_cash_val').innerText = fmtCur(totalCashBuffer);
            document.getElementById('trk_cash_pct').innerText = cashBufferPct.toFixed(1) + "%";
            
            let redWidth = Math.min(cashBufferPct, 40);
            let greenWidth = Math.max(0, Math.min(cashBufferPct - 40, 60));
            document.getElementById('trk_cash_bar_container').innerHTML = `
                <div class="bg-red-500 h-full" style="width: ${redWidth}%" title="Restricted Min Buffer (40%)"></div>
                <div class="bg-green-500 h-full" style="width: ${greenWidth}%" title="Deployable Excess"></div>
            `;

            let excessCash = totalCashBuffer - (totalEstate * 0.40);
            
            if (cashBufferPct >= 40) {
                document.getElementById('trk_cash_status').innerHTML = `<span class="text-green-700 font-black">✓ SAFE:</span> You have <span class="font-black text-green-700">${fmtCur(excessCash)}</span> available for scheduled deployments.`;
            } else {
                document.getElementById('trk_cash_status').innerHTML = `<span class="text-red-600 font-black">⚠️ WARNING:</span> Buffer breached 40% floor. Halt all Equity DCA.`;
                excessCash = 0;
            }

            let baseTranche = excessCash > 0 ? (excessCash / 10) : 0; 
            let dcaAmount = Math.max(baseTranche, 10000); 
            if (excessCash > 0 && excessCash < 10000) dcaAmount = excessCash;

            let todayDate = new Date();
            let twoWeeks = new Date(todayDate.getTime() + (14 * 24 * 60 * 60 * 1000));
            let fmtDate = (d) => d.toLocaleDateString('en-US', { month: 'short', day: 'numeric' });

            if (excessCash > 0) {
                document.getElementById('dyn_total_deploy').innerText = "Tranche Size: " + fmtCur(dcaAmount);
                document.getElementById('dyn_schedule_list').innerHTML = `
                    <li class="flex justify-between items-center"><span class="flex items-center"><span class="w-1.5 h-1.5 bg-blue-400 rounded-full mr-1.5"></span>Silos A & C (Mirror UCITS DCA)</span><span class="font-bold text-green-700">IMMEDIATE</span></li>
                    <li class="flex justify-between items-center"><span class="flex items-center"><span class="w-1.5 h-1.5 bg-blue-400 rounded-full mr-1.5"></span>Silos A & C (Mirror UCITS DCA)</span><span class="font-bold text-gray-800">Scheduled: ${fmtDate(twoWeeks)}</span></li>
                    <li class="flex justify-between items-center"><span class="flex items-center"><span class="w-1.5 h-1.5 bg-purple-400 rounded-full mr-1.5"></span>Silos B & D (Alpha Merit)</span><span class="font-bold text-gray-800">On Performance Metric</span></li>
                `;
            } else {
                document.getElementById('dyn_total_deploy').innerText = "Locked";
                document.getElementById('dyn_schedule_list').innerHTML = `<li class="text-red-600 font-bold">No excess cash available for deployment.</li>`;
            }

            let totalMarginLocked = amt_A_xsp + amt_C_xsp;
            let marginPct = totalEstate > 0 ? (totalMarginLocked / totalEstate) * 100 : 0;
            let maxMarginAllowed = totalEstate * 0.25;
            let capacityUtilized = maxMarginAllowed > 0 ? (totalMarginLocked / maxMarginAllowed) * 100 : 0;
            
            document.getElementById('trk_margin_sub').innerText = `25% Safety Cap = ${fmtCur(maxMarginAllowed)} (Max Allowed)`;
            document.getElementById('trk_margin_val').innerText = fmtCur(totalMarginLocked);
            document.getElementById('trk_margin_pct').innerText = marginPct.toFixed(1) + "% of Estate";
            document.getElementById('trk_margin_bar').style.width = Math.min(capacityUtilized, 100) + "%";
            
            if (capacityUtilized <= 100) {
                document.getElementById('trk_margin_status').innerHTML = `<span class="text-green-700 font-black">✓ OPTIMAL:</span> You have <span class="font-black text-green-700">${fmtCur(maxMarginAllowed - totalMarginLocked)}</span> in remaining margin capacity.`;
                document.getElementById('trk_margin_bar').className = "bg-green-500 h-full";
            } else {
                document.getElementById('trk_margin_status').innerHTML = `<span class="text-red-600 font-black">⚠️ CAP BREACHED:</span> Close spreads immediately to restore margin.`;
                document.getElementById('trk_margin_bar').className = "bg-red-600 h-full";
            }

            try {
                let lastRegime = regimeStatus && regimeStatus.length > 0 ? regimeStatus[regimeStatus.length - 1].toLowerCase() : 'yellow';
                let actionText = "";
                if (lastRegime === 'green') { 
                    actionText = "<span class='text-green-700 font-black text-sm uppercase tracking-wide mb-1 block'>🟢 Green Regime (Risk On)</span><b>Silos A & C (Equities):</b> Transfer funds from IB01 to purchase physical CSPX/CNDX equity.<br><br><b>Silo C (Options):</b> Clear to sell new XSP/XND Put Spreads up to 25% margin cap."; 
                } else if (lastRegime === 'yellow') { 
                    actionText = "<span class='text-yellow-600 font-black text-sm uppercase tracking-wide mb-1 block'>🟡 Yellow Regime (Transition)</span><b>Silos A & C (Equities):</b> HOLD current equity DCA. Funnel all new cash deposits strictly into IB01.<br><br><b>Silo C (Options):</b> Throttle new Put Spreads to strict 45 DTE. Require higher premium floor."; 
                } else if (lastRegime === 'red') { 
                    actionText = "<span class='text-red-600 font-black text-sm uppercase tracking-wide mb-1 block'>🔴 Red Regime (Defense)</span><b>All Silos:</b> HALT all active equity purchases. Defend the 40% Cash Buffer.<br><br><b>Silo C (Options):</b> If VIX spikes violently, buy 90-DTE SPX Puts (Taleb Tail-Hedge) to protect physical assets."; 
                }
                document.getElementById('trk_dca_action').innerHTML = actionText;
            } catch(e) {}            

            const pctA = totalEstate > 0 ? ((sA / totalEstate) * 100).toFixed(1) : "0.0";
            const pctB = totalEstate > 0 ? ((sB / totalEstate) * 100).toFixed(1) : "0.0";
            const pctC = totalEstate > 0 ? ((sC / totalEstate) * 100).toFixed(1) : "0.0";
            const pctD = totalEstate > 0 ? ((sD / totalEstate) * 100).toFixed(1) : "0.0";

            let barLayout = { 
                barmode: 'relative', 
                title: 'GAAP Balance Sheet per Silo (USD)', 
                margin: {b: 40, t: 80}, 
                paper_bgcolor: 'rgba(0,0,0,0)',
                plot_bgcolor: 'rgba(0,0,0,0)',
                annotations:[
                    { x: xLabels[0], y: sA, text: `${(sA/1000).toFixed(0)}k<br>(${pctA}%)`, showarrow: false, yanchor: 'bottom', font: {bold: true, size: 13}},
                    { x: xLabels[1], y: sB, text: `${(sB/1000).toFixed(0)}k<br>(${pctB}%)`, showarrow: false, yanchor: 'bottom', font: {bold: true, size: 13}},
                    { x: xLabels[2], y: sC, text: `${(sC/1000).toFixed(0)}k<br>(${pctC}%)`, showarrow: false, yanchor: 'bottom', font: {bold: true, size: 13}},
                    { x: xLabels[3], y: sD, text: `${(sD/1000).toFixed(0)}k<br>(${pctD}%)`, showarrow: false, yanchor: 'bottom', font: {bold: true, size: 13}}
                ]
            };
            Plotly.react('bar-chart', barData, barLayout, {displayModeBar: false, responsive: true});

            let rawPieData =[
                {v: tot_ib01, l: `IB01: ${fmtCur(tot_ib01)}`, c: palette.siloA}, 
                {v: tot_cspx, l: `CSPX: ${fmtCur(tot_cspx)}`, c: palette.cspx},
                {v: tot_cndx, l: `CNDX: ${fmtCur(tot_cndx)}`, c: palette.cndx}, 
                {v: tot_itwn, l: `ITWN: ${fmtCur(tot_itwn)}`, c: palette.itwn},
                {v: tot_cskr, l: `CSKR: ${fmtCur(tot_cskr)}`, c: palette.cskr}, 
                {v: tot_cnya, l: `CNYA: ${fmtCur(tot_cnya)}`, c: palette.cnya},
                {v: (tot_cfd + tot_intl), l: `Active Swing: ${fmtCur(tot_cfd + tot_intl)}`, c: palette.cfd_intl}, 
                {v: tot_cash, l: `Cash: ${fmtCur(tot_cash)}`, c: palette.siloC}
            ];
            
            if (tot_crypto > 0) rawPieData.push({v: tot_crypto, l: `Crypto: ${fmtCur(tot_crypto)}`, c: palette.crypto});
            if (Math.abs(tot_opt_mkt) > 0) rawPieData.push({v: Math.abs(tot_opt_mkt), l: `Opt Liab: ${fmtCur(Math.abs(tot_opt_mkt))}`, c: palette.optMktVal});

            let pieData =[{ 
                values: rawPieData.map(d=>d.v), 
                labels: rawPieData.map(d=>d.l), 
                type: 'pie', 
                text: rawPieData.map(d => (totalEstate > 0 ? (d.v / totalEstate * 100).toFixed(2) + '%' : '0%')),
                textinfo: 'text', 
                hoverinfo: 'label+text',
                hole: .4, 
                marker: {colors: rawPieData.map(d=>d.c)} 
            }];
        
            let pieLayout = { 
                title: `Gross Asset Allocation`, 
                margin: {t: 40, b: 20}, 
                paper_bgcolor: 'rgba(0,0,0,0)' 
            };
            Plotly.react('pie-chart', pieData, pieLayout, {displayModeBar: false, responsive: true});
            
            // -------------------------------------------------------------
            // v68: USD-Denominated PnL Bar Chart & Cumulative Trajectory
            // -------------------------------------------------------------
            const attrDates = safeParse('VAR_ATTR_DATES');
            const attrA1 = safeParse('VAR_ATTR_A1');
            const attrA2 = safeParse('VAR_ATTR_A2');
            const attrA3 = safeParse('VAR_ATTR_A3');
            const attrA4 = safeParse('VAR_ATTR_A4');
            const attrA5 = safeParse('VAR_ATTR_A5');
            
            if (attrDates.length > 0) {
                let pnlBarData = [{
                    x:['Yield (a1)', 'Beta (a2)', 'VRP (a3)', 'Alpha (a4)', 'Fees (a5)'],
                    y:[VAR_TOTAL_A1, VAR_TOTAL_A2, VAR_TOTAL_A3, VAR_TOTAL_A4, VAR_TOTAL_A5],
                    type: 'bar',
                    text:[VAR_TOTAL_A1, VAR_TOTAL_A2, VAR_TOTAL_A3, VAR_TOTAL_A4, VAR_TOTAL_A5].map(v => fmtCur(v)),
                    textposition: 'auto',
                    marker: { color:['#3b82f6', '#f97316', '#86efac', '#a855f7', '#ef4444'] }
                }];
                
                let pnlBarLayout = {
                    title: 'Absolute PnL by Strategy',
                    margin: {t: 30, b: 50, l: 40, r: 10},
                    paper_bgcolor: 'rgba(0,0,0,0)', plot_bgcolor: 'rgba(0,0,0,0)',
                    yaxis: { title: 'Total PnL (USD)', zeroline: true, zerolinecolor: '#000', zerolinewidth: 2, gridcolor: '#e5e7eb' },
                    xaxis: { tickangle: -15 }
                };
                Plotly.react('pnl-bar-chart', pnlBarData, pnlBarLayout, {displayModeBar: false, responsive: true});
                
                let pnlLineData =[
                    { x: attrDates, y: attrA1, name: 'Yield', type: 'scatter', mode: 'lines', line: {color: '#3b82f6', width: 2} },
                    { x: attrDates, y: attrA2, name: 'Beta', type: 'scatter', mode: 'lines', line: {color: '#f97316', width: 2} },
                    { x: attrDates, y: attrA3, name: 'VRP', type: 'scatter', mode: 'lines', line: {color: '#86efac', width: 2} },
                    { x: attrDates, y: attrA4, name: 'Alpha', type: 'scatter', mode: 'lines', line: {color: '#a855f7', width: 2} },
                    { x: attrDates, y: attrA5, name: 'Fees', type: 'scatter', mode: 'lines', line: {color: '#ef4444', width: 2} }
                ];

                // Find first active date to crop dead air
                let firstAttrIdx = 0;
                for(let i=0; i<attrA2.length; i++) {
                    if(Math.abs(attrA2[i]) > 0.1 || Math.abs(attrA4[i]) > 0.1) {
                        firstAttrIdx = i > 0 ? i - 1 : 0;
                        break;
                    }
                }
                let sDateLine = new Date(attrDates[firstAttrIdx]);
                sDateLine.setDate(sDateLine.getDate() - 12);
                let eDateLine = new Date(attrDates[attrDates.length - 1]);
                eDateLine.setDate(eDateLine.getDate() + 5);

                let pnlLineLayout = {
                    title: 'Cumulative Trajectory',
                    margin: {t: 30, b: 50, l: 40, r: 10},
                    paper_bgcolor: 'rgba(0,0,0,0)', plot_bgcolor: 'rgba(0,0,0,0)',
                    yaxis: { title: 'Cum. PnL (USD)', zeroline: true, zerolinecolor: '#000', zerolinewidth: 2, gridcolor: '#e5e7eb' },
                    xaxis: { range:[sDateLine.toISOString().split('T')[0], eDateLine.toISOString().split('T')[0]] },
                    legend: { orientation: 'h', y: -0.20, x: 0.5, xanchor: 'center' }
                };
                Plotly.react('pnl-line-chart', pnlLineData, pnlLineLayout, {displayModeBar: false, responsive: true});                               
            }
        }

        document.querySelectorAll('input').forEach(i => i.addEventListener('input', updateUI));
        
        const benchDates = safeParse('VAR_BENCH_DATES');
        const estateData = safeParse('VAR_ESTATE_CUM');
        const spyData = safeParse('VAR_SPY_CUM');
        const qqqData = safeParse('VAR_QQQ_CUM');

        if (benchDates && benchDates.length > 0) {
            let traceE = { x: benchDates, y: estateData, name: 'Estate', type: 'scatter', mode: 'lines', line: {color: 'black', width: 4} };
            let traceS = { x: benchDates, y: spyData, name: 'SPY', type: 'scatter', mode: 'lines', line: {color: '#3b82f6', width: 2} }; 
            let traceQ = { x: benchDates, y: qqqData, name: 'QQQ', type: 'scatter', mode: 'lines', line: {color: '#dc2626', width: 2} }; 
            
            let benchLayout = { 
                margin: {t: 10, b: 30, l: 40, r: 20}, 
                paper_bgcolor: 'rgba(0,0,0,0)',
                plot_bgcolor: 'rgba(0,0,0,0)', 
                yaxis: { ticksuffix: '%' }, 
                legend: { orientation: 'h', y: 1.1, x: 0.5, xanchor: 'center' } 
            };
            Plotly.react('benchmark-chart',[traceE, traceS, traceQ], benchLayout, {displayModeBar: false, responsive: true});

            let layoutSm = { 
                margin: {t: 20, b: 20, l: 30, r: 10}, 
                paper_bgcolor: 'rgba(0,0,0,0)',
                plot_bgcolor: 'rgba(0,0,0,0)', 
                xaxis: { showticklabels: false, showgrid: false, zeroline: false }, 
                yaxis: { ticksuffix: '%', hoverformat: '.2f%', showgrid: true, gridcolor: '#e5e7eb', zeroline: true, zerolinecolor: '#9ca3af', zerolinewidth: 2 } 
            };

            let trSPY_sm = { x: benchDates, y: spyData, type: 'scatter', mode: 'lines', line: {color: '#3b82f6', width: 1.5}, showlegend: false, hoverinfo: 'skip' };
            let trQQQ_sm = { x: benchDates, y: qqqData, type: 'scatter', mode: 'lines', line: {color: '#dc2626', width: 1.5}, showlegend: false, hoverinfo: 'skip' };

            let trSiloA = { x: benchDates, y: safeParse('VAR_SILOA_CUM'), name: 'Silo A', type: 'scatter', mode: 'lines', line: {color: 'black', width: 4.5}, showlegend: false };
            Plotly.react('chart-silo-a',[trSiloA, trSPY_sm, trQQQ_sm], layoutSm, {displayModeBar: false, responsive: true});

            let trSiloB = { x: benchDates, y: safeParse('VAR_SILOB_CUM'), name: 'Silo B', type: 'scatter', mode: 'lines', line: {color: 'black', width: 4.5}, showlegend: false };
            Plotly.react('chart-silo-b',[trSiloB, trSPY_sm, trQQQ_sm], layoutSm, {displayModeBar: false, responsive: true});

            let trSiloC = { x: benchDates, y: safeParse('VAR_SILOC_CUM'), name: 'Silo C', type: 'scatter', mode: 'lines', line: {color: 'black', width: 4.5}, showlegend: false };
            Plotly.react('chart-silo-c',[trSiloC, trSPY_sm, trQQQ_sm], layoutSm, {displayModeBar: false, responsive: true});

            let trSiloD = { x: benchDates, y: safeParse('VAR_SILOD_CUM'), name: 'Silo D', type: 'scatter', mode: 'lines', line: {color: 'black', width: 4.5}, showlegend: false };
            Plotly.react('chart-silo-d',[trSiloD, trSPY_sm, trQQQ_sm], layoutSm, {displayModeBar: false, responsive: true});
        }

        const datesPnl = safeParse('VAR_DATES_PNL');
        const pnlA = safeParse('VAR_SILOA_PNL');
        const pnlB = safeParse('VAR_SILOB_PNL');
        const pnlC = safeParse('VAR_SILOC_PNL');
        const pnlD = safeParse('VAR_SILOD_PNL');
        const estateCumPnl = safeParse('VAR_ESTATE_CUM_PNL');
        const spyCumPnl = safeParse('VAR_SPY_CUM_PNL');
        const qqqCumPnl = safeParse('VAR_QQQ_CUM_PNL');
        const datesCumPnl = safeParse('VAR_DATES_CUM_PNL');
        
        const regimeStatus = safeParse('VAR_REGIME_STATUS');
        const regimeTor = safeParse('VAR_REGIME_TOR');

        if (datesPnl && datesPnl.length > 0) {
            let traceA = { x: datesPnl, y: pnlA, name: 'Silo A', type: 'bar', marker: {color: palette.siloA} };
            let traceB = { x: datesPnl, y: pnlB, name: 'Silo B', type: 'bar', marker: {color: palette.siloB} };
            let traceC = { x: datesPnl, y: pnlC, name: 'Silo C', type: 'bar', marker: {color: palette.siloC} };
            let traceD = { x: datesPnl, y: pnlD, name: 'Silo D', type: 'bar', marker: {color: palette.siloD} };

            let traceEstateLine = { x: datesCumPnl, y: estateCumPnl, name: 'Estate (Cum PnL USD)', type: 'scatter', mode: 'lines', line: {color: 'black', width: 6}, yaxis: 'y2' };
            let traceSPYLine = { x: datesCumPnl, y: spyCumPnl, name: 'SPY (Cum PnL USD)', type: 'scatter', mode: 'lines', line: {color: '#3b82f6', width: 2}, yaxis: 'y2' };
            let traceQQQLine = { x: datesCumPnl, y: qqqCumPnl, name: 'QQQ (Cum PnL USD)', type: 'scatter', mode: 'lines', line: {color: '#dc2626', width: 2}, yaxis: 'y2' };

            let regimeColors = [];
            let regimeFonts =[];
            let regimeText =[];
            let regimeY =[];
            
            for(let i=0; i<datesCumPnl.length; i++) {
                let s = regimeStatus[i] ? regimeStatus[i].toString().toLowerCase() : '';
                let t = regimeTor[i] ? regimeTor[i].toString() : '';
                regimeText.push(t);
                regimeY.push(1); 
                
                if(s === 'red') { regimeColors.push('#FF0000'); regimeFonts.push('#FFFFFF'); }
                else if(s === 'green') { regimeColors.push('#008000'); regimeFonts.push('#FFFFFF'); }
                else if(s === 'yellow') { regimeColors.push('#FFFF00'); regimeFonts.push('#000000'); }
                else { regimeColors.push('rgba(0,0,0,0)'); regimeFonts.push('#000000'); }
            }
            
            let traceRegime = {
                x: datesCumPnl,
                y: regimeY,
                type: 'bar',
                xaxis: 'x',
                yaxis: 'y3', 
                marker: {color: regimeColors},
                text: regimeText,
                textposition: 'inside',
                insidetextanchor: 'middle',
                insidetextfont: {color: regimeFonts, size: 16, family: 'Arial Black'}, 
                hoverinfo: 'text',
                hovertext: datesCumPnl.map((d, i) => `US Regime (SPY): ${regimeStatus[i] || 'N/A'} | Global TOR: ${regimeTor[i] || 'N/A'}`),
                showlegend: false
            };

            let firstIdx = 0;
            for (let i = 0; i < estateCumPnl.length; i++) {
                if (Math.abs(estateCumPnl[i]) > 0.1) {
                    firstIdx = i > 0 ? i - 1 : 0;
                    break;
                }
            }
            
            let sDate = new Date(datesCumPnl[firstIdx]);
            sDate.setDate(sDate.getDate() - 12); 
            let eDate = new Date(datesCumPnl[datesCumPnl.length - 1]);
            eDate.setDate(eDate.getDate() + 5);

            let pnlLayout = {
                barmode: 'relative',
                margin: {t: 20, b: 50, l: 60, r: 60}, 
                paper_bgcolor: 'rgba(0,0,0,0)',
                plot_bgcolor: 'rgba(0,0,0,0)',
                xaxis: { 
                    type: 'date', 
                    showgrid: false, 
                    fixedrange: false, 
                    anchor: 'y3',
                    range:[sDate.toISOString().split('T')[0], eDate.toISOString().split('T')[0]] 
                }, 
                yaxis: { title: 'Daily PnL (USD)', side: 'left', showgrid: true, gridcolor: '#e5e7eb', zeroline: true, zerolinecolor: '#9ca3af', zerolinewidth: 2, fixedrange: true, domain: [0.09, 1] }, 
                yaxis2: { title: 'Cumulative PnL (USD)', side: 'right', overlaying: 'y', showgrid: false, zeroline: false, fixedrange: true, domain: [0.09, 1] }, 
                yaxis3: { domain: [0, 0.06], visible: false, fixedrange: true }, 
                legend: { orientation: 'h', y: 1.1, x: 0.5, xanchor: 'center' }
            };
            
            let pnlConfig = {displayModeBar: false, responsive: true, scrollZoom: true};
            Plotly.react('daily-pnl-chart',[traceA, traceB, traceC, traceD, traceEstateLine, traceSPYLine, traceQQQLine, traceRegime], pnlLayout, pnlConfig);
        }

        const mcOrig = safeParse('VAR_MC_ORIG');
        const mcStats = safeParse('VAR_MC_STATS');
        if (mcOrig && mcOrig.length > 0) {
            let mcTraces =[];
            
            safeParse('VAR_MC_VISUALS').forEach(tr => {
                let r = Math.floor(Math.random() * 150 + 50);
                let g = Math.floor(Math.random() * 150 + 50);
                let b = Math.floor(Math.random() * 150 + 50);
                mcTraces.push({
                    y: tr, 
                    type: 'scatter', 
                    mode: 'lines', 
                    line: {color: `rgba(${r}, ${g}, ${b}, 0.2)`, width: 1.5}, 
                    showlegend: false, 
                    hoverinfo: 'skip'
                });
            });
            
            mcTraces.push({ y: safeParse('VAR_MC_AVG'), name: 'Avg Path (Stable)', type: 'scatter', mode: 'lines', line: {color: 'blue', width: 4.5} });
            mcTraces.push({ y: mcOrig, name: 'Original History', type: 'scatter', mode: 'lines', line: {color: 'black', width: 4.5} });
            
            const fmtDlr = (val) => val ? '$' + val.toLocaleString('en-US', {minimumFractionDigits: 2, maximumFractionDigits: 2}) : '$0.00';

            let mcLayout = {
                margin: {t: 20, b: 40, l: 60, r: 20},
                paper_bgcolor: 'rgba(0,0,0,0)',
                plot_bgcolor: 'rgba(0,0,0,0)',
                xaxis: { title: 'Trading Days Forward', showgrid: true, gridcolor: '#e5e7eb' },
                yaxis: { title: 'Cumulative Net Profit (USD)', showgrid: true, gridcolor: '#e5e7eb', zeroline: true, zerolinecolor: '#000000', zerolinewidth: 2 },
                showlegend: true,
                legend: { orientation: 'h', y: 1.1, x: 0.5, xanchor: 'center' },
                annotations:[
                    {
                        x: 0.01, y: 0.95, xref: 'paper', yref: 'paper',
                        text: `<b>ORIGINAL HISTORY:</b><br>Max Drawdown: ${fmtDlr(mcStats.orig_dd)}<br><br><b>SIMULATION (10,000 runs):</b><br>Best Case DD: ${fmtDlr(mcStats.best_dd)}<br>Worst Case DD: ${fmtDlr(mcStats.worst_dd)}<br>Avg Drawdown: ${fmtDlr(mcStats.avg_dd)}`,
                        showarrow: false,
                        align: 'left',
                        bgcolor: 'rgba(255, 255, 255, 0.9)',
                        bordercolor: 'black',
                        borderwidth: 1,
                        font: {size: 11}
                    }
                ]
            };
            Plotly.react('montecarlo-chart', mcTraces, mcLayout, {displayModeBar: false, responsive: true});
        }

        const liveAlloc = safeParse('VAR_LIVE_ALLOCATIONS');
        if (Object.keys(liveAlloc).length > 0) {
            
            if (liveAlloc['A']) {
                document.getElementById('a_ib01').value = liveAlloc['A']['IB01'] || 0;
                document.getElementById('a_cspx').value = liveAlloc['A']['CSPX'] || 0;
                document.getElementById('a_cndx').value = liveAlloc['A']['CNDX'] || 0;
                document.getElementById('a_itwn').value = liveAlloc['A']['ITWN'] || 0;
                document.getElementById('a_cskr').value = liveAlloc['A']['CSKR'] || 0;
                document.getElementById('a_cnya').value = liveAlloc['A']['CNYA'] || 0;
                document.getElementById('a_crypto').value = liveAlloc['A']['CRYPTO'] || 0;
                document.getElementById('a_cash').value = liveAlloc['A']['CASH'] || 0;
                document.getElementById('a_opt_mkt').value = liveAlloc['A']['OPT_LIAB'] || 0;
                document.getElementById('a_xsp').value = liveAlloc['A']['OPT_MARGIN'] || 0; 
            }
            
            if (liveAlloc['B']) {
                document.getElementById('b_cash').value = liveAlloc['B']['CASH'] || 0;
                document.getElementById('b_cfd').value = liveAlloc['B']['CFD'] || 0;
                document.getElementById('b_intl').value = liveAlloc['B']['INTL'] || 0;
            }

            if (liveAlloc['C']) {
                document.getElementById('c_ib01').value = liveAlloc['C']['IB01'] || 0;
                document.getElementById('c_cspx').value = liveAlloc['C']['CSPX'] || 0;
                document.getElementById('c_cndx').value = liveAlloc['C']['CNDX'] || 0;
                document.getElementById('c_itwn').value = liveAlloc['C']['ITWN'] || 0;
                document.getElementById('c_cskr').value = liveAlloc['C']['CSKR'] || 0;
                document.getElementById('c_cnya').value = liveAlloc['C']['CNYA'] || 0;
                document.getElementById('c_crypto').value = liveAlloc['C']['CRYPTO'] || 0;
                document.getElementById('c_cash').value = liveAlloc['C']['CASH'] || 0;
                document.getElementById('c_opt_mkt').value = liveAlloc['C']['OPT_LIAB'] || 0;
                document.getElementById('c_xsp').value = liveAlloc['C']['OPT_MARGIN'] || 0; 
            }
        }

        const siloDHoldings = safeParse('VAR_SILOD_HOLDINGS');
        for (let i = 0; i < 10; i++) {
            if (siloDHoldings[i]) {
                let lbl = document.getElementById('d_lbl_' + (i+1));
                let val = document.getElementById('d_val_' + (i+1));
                if(lbl && val) {
                    lbl.value = siloDHoldings[i].ticker;
                    val.value = siloDHoldings[i].value;
                }
            }
        }
        
        if (liveAlloc && liveAlloc['D']) {
             document.getElementById('d_val_cash').value = liveAlloc['D']['CASH'] || 0;
        }

        populateTable();
        updateUI();
    </script>
</body>
</html>
"""

for acc, prefix in[("ESTATE", "ESTATE"), ("U23144948", "A"), ("U23139264", "B"), ("U23154199", "C"), ("U25218481", "D")]:
    html_content = html_content.replace(f"VAR_COLOR_{prefix}_IRR", get_color_class(metrics[acc]["irr"], "light"))
    html_content = html_content.replace(f"VAR_{prefix}_IRR", metrics[acc]["irr"])
    
    html_content = html_content.replace(f"VAR_COLOR_{prefix}_SHARPE", get_color_class(metrics[acc]["sharpe"], "light"))
    html_content = html_content.replace(f"VAR_{prefix}_SHARPE", metrics[acc]["sharpe"])
    
    html_content = html_content.replace(f"VAR_COLOR_{prefix}_PNL", get_color_class(metrics[acc]["pnl"], "light"))
    html_content = html_content.replace(f"VAR_{prefix}_PNL", metrics[acc]["pnl"])
    
    html_content = html_content.replace(f"VAR_{prefix}_MAXDD", metrics[acc]["maxdd"])
    html_content = html_content.replace(f"VAR_{prefix}_DD_DAYS", metrics[acc]["dd_days"])
    html_content = html_content.replace(f"VAR_{prefix}_CALMAR", metrics[acc]["calmar"])
    
    html_content = html_content.replace(f"VAR_COLOR_{prefix}_ROC", get_color_class(metrics[acc]["roc"], "light"))
    html_content = html_content.replace(f"VAR_{prefix}_ROC", metrics[acc]["roc"])

    nav_val = metrics[acc]["nav"]
    html_content = html_content.replace(f"VAR_{prefix}_NAV_FMT", f" USD {nav_val:,.2f}")

    if prefix != "ESTATE":
        html_content = html_content.replace(f"VAR_NAV_{prefix}", str(round(nav_val, 2)))

# Benchmarks
html_content = html_content.replace("'VAR_BENCH_DATES'", f"'{dates_js}'")
html_content = html_content.replace("'VAR_ESTATE_CUM'", f"'{estate_js}'")
html_content = html_content.replace("'VAR_SPY_CUM'", f"'{spy_js}'")
html_content = html_content.replace("'VAR_QQQ_CUM'", f"'{qqq_js}'")
html_content = html_content.replace("'VAR_SILOA_CUM'", f"'{silo_a_js}'")
html_content = html_content.replace("'VAR_SILOB_CUM'", f"'{silo_b_js}'")
html_content = html_content.replace("'VAR_SILOC_CUM'", f"'{silo_c_js}'")
html_content = html_content.replace("'VAR_SILOD_CUM'", f"'{silo_d_js}'")

# Daily PnL
html_content = html_content.replace("'VAR_DATES_PNL'", f"'{dates_pnl_js}'")
html_content = html_content.replace("'VAR_SILOA_PNL'", f"'{silo_a_pnl}'")
html_content = html_content.replace("'VAR_SILOB_PNL'", f"'{silo_b_pnl}'")
html_content = html_content.replace("'VAR_SILOC_PNL'", f"'{silo_c_pnl}'")
html_content = html_content.replace("'VAR_SILOD_PNL'", f"'{silo_d_pnl}'")
html_content = html_content.replace("'VAR_DATES_CUM_PNL'", f"'{dates_cum_pnl_js}'")
html_content = html_content.replace("'VAR_ESTATE_CUM_PNL'", f"'{estate_cum_pnl_js}'")
html_content = html_content.replace("'VAR_SPY_CUM_PNL'", f"'{spy_cum_pnl_js}'")
html_content = html_content.replace("'VAR_QQQ_CUM_PNL'", f"'{qqq_cum_pnl_js}'")

# Regime Data
html_content = html_content.replace("'VAR_REGIME_STATUS'", f"'{status_js}'")
html_content = html_content.replace("'VAR_REGIME_TOR'", f"'{tor_js}'")

# Monte Carlo
html_content = html_content.replace("'VAR_MC_VISUALS'", f"'{mc_visuals_js}'")
html_content = html_content.replace("'VAR_MC_AVG'", f"'{mc_avg_js}'")
html_content = html_content.replace("'VAR_MC_ORIG'", f"'{mc_orig_js}'")
html_content = html_content.replace("'VAR_MC_STATS'", f"'{mc_stats_js}'")

# Global KPIs
html_content = html_content.replace("VAR_SPY_ALPHA", spy_alpha_str)
html_content = html_content.replace("VAR_SPY_CORR", spy_corr_str)
html_content = html_content.replace("VAR_QQQ_ALPHA", qqq_alpha_str)
html_content = html_content.replace("VAR_QQQ_CORR", qqq_corr_str)
html_content = html_content.replace("VAR_SPY_SHARPE", spy_sharpe_str)
html_content = html_content.replace("VAR_QQQ_SHARPE", qqq_sharpe_str)

# Live Portfolio Data
alloc_json_path = os.path.join(target_directory, 'Live_Allocations.json')
live_alloc_js = "{}"
if os.path.exists(alloc_json_path):
    with open(alloc_json_path, 'r') as f:
        live_alloc_js = f.read()
html_content = html_content.replace("'VAR_LIVE_ALLOCATIONS'", f"'{live_alloc_js}'")

silo_d_json_path = os.path.join(target_directory, 'Silo_D_Holdings.json')
silo_d_holdings_js = str([]) 
if os.path.exists(silo_d_json_path):
    with open(silo_d_json_path, 'r') as f:
        silo_d_holdings_js = f.read()
html_content = html_content.replace("'VAR_SILOD_HOLDINGS'", f"'{silo_d_holdings_js}'")

# --- v68 PROGRESSIVE EXPOSURE ADVISORY INJECTION ---
prog_exp_path = os.path.join(target_directory, 'Progressive_Exposure.json')
prog_exp_js = "{}"
if os.path.exists(prog_exp_path):
    with open(prog_exp_path, 'r') as f:
        prog_exp_js = f.read()
html_content = html_content.replace("'VAR_PROG_EXP'", f"'{prog_exp_js}'")

# --- v68 PNL ATTRIBUTION INJECTION ---
html_content = html_content.replace("'VAR_ATTR_DATES'", f"'{attr_dates_js}'")
html_content = html_content.replace("'VAR_ATTR_A1'", f"'{attr_a1_js}'")
html_content = html_content.replace("'VAR_ATTR_A2'", f"'{attr_a2_js}'")
html_content = html_content.replace("'VAR_ATTR_A3'", f"'{attr_a3_js}'")
html_content = html_content.replace("'VAR_ATTR_A4'", f"'{attr_a4_js}'")
html_content = html_content.replace("'VAR_ATTR_A5'", f"'{attr_a5_js}'")

html_content = html_content.replace("VAR_TOTAL_A1", str(total_a1))
html_content = html_content.replace("VAR_TOTAL_A2", str(total_a2))
html_content = html_content.replace("VAR_TOTAL_A3", str(total_a3))
html_content = html_content.replace("VAR_TOTAL_A4", str(total_a4))
html_content = html_content.replace("VAR_TOTAL_A5", str(total_a5))

# --- CAPITAL VELOCITY INJECTION ---
vel_json_path = os.path.join(target_directory, 'Velocity_Metrics.json')
vel_winrate = "0"
vel_avgdays = "0"
if os.path.exists(vel_json_path):
    try:
        with open(vel_json_path, 'r') as f:
            v_data = json.load(f)
            vel_winrate = str(v_data.get("win_rate", 0))
            vel_avgdays = str(v_data.get("avg_days", 0))
    except Exception as e:
        print(f"[ERROR] Reading Velocity JSON: {e}")

html_content = html_content.replace("VAR_VEL_WINRATE", vel_winrate)
html_content = html_content.replace("VAR_VEL_AVGDAYS", vel_avgdays)

# --- TIMESTAMP GENERATION ---
sync_time = datetime.datetime.now().strftime("%B %d, %Y | %I:%M %p")
html_content = html_content.replace("VAR_SYNC_TIME", sync_time)

try:
    with open(full_file_path, "w", encoding="utf-8") as f:
        f.write(html_content)
    print("====================================================================")
    print(f"SUCCESS! Estate Dashboard v68 created.")
    print(f"Path: {full_file_path}")
    print("====================================================================")
except Exception as e:
    print(f"[ERROR] Saving File: {e}")