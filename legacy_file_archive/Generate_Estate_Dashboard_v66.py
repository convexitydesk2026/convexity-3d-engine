r"""
=============================================================================
Script Name: Generate_Estate_Dashboard_v66.py
Purpose: Generates the Interactive Family Estate Dashboard.
         VERSION 66 UPGRADES:
         - Upgraded to ingest pristine Math from the v22 Local DB Engine.
         - Options Velocity pulls natively from IBKR Closed Lots DB.
         - Versioning tags updated to match new Data Pipeline.
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
full_file_path = os.path.join(target_directory, "Family_Estate_Dashboard_v66.html")

if not os.path.exists(target_directory): os.makedirs(target_directory)

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
    if df_acc.empty or len(df_acc) < 2: return "N/A", "N/A", "N/A", "N/A", "0", "N/A", "N/A", 0
    df_acc = df_acc.sort_values('Date').reset_index(drop=True)
    df_acc['Prev_NAV'] = df_acc['NAV'].shift(1)
    df_acc['Daily_Return'] = (df_acc['NAV'] - df_acc['CashFlow'] - df_acc['Prev_NAV']) / df_acc['Prev_NAV']
    df_acc['Daily_Return'] = df_acc['Daily_Return'].replace([np.inf, -np.inf], np.nan).fillna(0)
    
    active_mask = df_acc['NAV'] > 0
    calc_df = df_acc.iloc[active_mask.idxmax():].copy() if active_mask.any() else df_acc.copy()
    
    sharpe_str = "N/A"
    if calc_df['Daily_Return'].std() > 0:
        excess_returns = calc_df['Daily_Return'] - (0.045 / 252)
        sharpe = np.sqrt(252) * (excess_returns.mean() / calc_df['Daily_Return'].std())
        sharpe_str = f"{sharpe:.2f}"
    
    total_pnl = df_acc['NAV'].iloc[-1] - df_acc['CashFlow'].sum()
    calc_df['Cum_Return_Index'] = (1 + calc_df['Daily_Return']).cumprod()
    calc_df['Peak'] = calc_df['Cum_Return_Index'].cummax()
    calc_df['Drawdown'] = (calc_df['Cum_Return_Index'] - calc_df['Peak']) / calc_df['Peak'].replace(0, np.nan)
    max_dd = calc_df['Drawdown'].min() * 100
    
    peak_date = calc_df['Date'].iloc[0]
    max_dd_days = 0
    for idx, row in calc_df.iterrows():
        if row['Cum_Return_Index'] >= row['Peak']: peak_date = row['Date']
        else: max_dd_days = max(max_dd_days, (row['Date'] - peak_date).days)
    
    df_acc['IRR_CF'] = -df_acc['CashFlow']
    cfs = df_acc['IRR_CF'].tolist() + [df_acc['NAV'].iloc[-1]]
    dates_series = pd.to_datetime(pd.Series(df_acc['Date'].tolist() +[df_acc['Date'].iloc[-1]]))
    irr = calculate_xirr(dates_series, cfs)
    
    calmar_str = f"{(irr * 100) / abs(max_dd):.2f}" if max_dd < 0 and irr != 0 else ("Inf" if max_dd == 0 and irr > 0 else "N/A")
    max_cap = max(df_acc['CashFlow'].cumsum().max(), df_acc['NAV'].max() - total_pnl)
    roc_str = f"{(total_pnl / max_cap) * 100:.2f}%" if max_cap > 0 else "N/A"

    return f"{(irr * 100):.2f}%" if irr != 0 else "N/A", sharpe_str, f"${total_pnl:,.2f}", f"{max_dd:.2f}%", str(max_dd_days), calmar_str, roc_str, df_acc['NAV'].iloc[-1]

def get_color_class(val_str, theme="light"):
    if "N/A" in val_str or "--" in val_str: return "text-gray-600"
    return "text-red-600" if "-" in val_str else "text-green-700"

def to_js_array(data, is_date=False):
    vals = data.tolist() if isinstance(data, pd.Series) else list(data)
    clean =[]
    for v in vals:
        try:
            if pd.isna(v) or str(v).lower() in ['nan', 'inf', '-inf', 'nat']: clean.append("null")
            elif is_date: clean.append(f'"{v}"')
            else: clean.append(str(round(float(v), 2)))
        except: clean.append("null")
    return "[" + ",".join(clean) + "]"

metrics = {acc: {"irr": "--", "sharpe": "--", "pnl": "--", "maxdd": "--", "dd_days": "--", "calmar": "--", "roc": "--", "nav": 0} for acc in["ESTATE", "U23144948", "U23139264", "U23154199", "U25218481"]}
global_df, bench_df, silo_returns = pd.DataFrame(), pd.DataFrame(), {}

dates_js, estate_js, spy_js, qqq_js = "[]", "[]", "[]", "[]"
silo_a_js, silo_b_js, silo_c_js, silo_d_js = "[]", "[]", "[]", "[]"
dates_pnl_js, silo_a_pnl, silo_b_pnl, silo_c_pnl, silo_d_pnl = "[]", "[]", "[]", "[]", "[]"
dates_cum_pnl_js, estate_cum_pnl_js, spy_cum_pnl_js, qqq_cum_pnl_js = "[]", "[]", "[]", "[]"
mc_visuals_js, mc_avg_js, mc_orig_js, mc_stats_js = "[]", "[]", "[]", "{}"
status_js, tor_js = "[]", "[]" 
spy_alpha_str, spy_corr_str, spy_sharpe_str = "N/A", "N/A", "N/A"
qqq_alpha_str, qqq_corr_str, qqq_sharpe_str = "N/A", "N/A", "N/A"
attr_dates_js, attr_a1_js, attr_a2_js, attr_a3_js, attr_a4_js, attr_a5_js = "[]", "[]", "[]", "[]", "[]", "[]"
total_a1 = total_a2 = total_a3 = total_a4 = total_a5 = 0.0

print("\n========================================================")
print("             CIO DIAGNOSTICS & LOGGING (v66)            ")
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
            silo_returns[acc] = acc_df[['Date', 'Daily_Return']].replace([np.inf, -np.inf], np.nan).fillna(0).rename(columns={'Daily_Return': f'{acc}_Ret'})

        nav_pivot = raw_df.pivot_table(index='Date', columns='AccountID', values='NAV', aggfunc='last').ffill().fillna(0)
        cf_pivot = raw_df.pivot_table(index='Date', columns='AccountID', values='CashFlow', aggfunc='sum').fillna(0)
        global_df = pd.DataFrame({'Date': nav_pivot.index, 'NAV': nav_pivot.sum(axis=1), 'CashFlow': cf_pivot.sum(axis=1)}).reset_index(drop=True)

        i, s, p, m, d, c, r, n = process_metrics(global_df)
        metrics["ESTATE"] = {"irr": i, "sharpe": s, "pnl": p, "maxdd": m, "dd_days": d, "calmar": c, "roc": r, "nav": n}
        
        global_df['Prev_NAV'] = global_df['NAV'].shift(1)
        global_df['Daily_Return'] = ((global_df['NAV'] - global_df['CashFlow'] - global_df['Prev_NAV']) / global_df['Prev_NAV']).replace([np.inf, -np.inf], np.nan).fillna(0)

        pnl_df = raw_df.groupby(['AccountID', 'Date']).agg({'NAV': 'last', 'CashFlow': 'sum'}).reset_index()
        pnl_df['Prev_NAV'] = pnl_df.groupby('AccountID')['NAV'].shift(1)
        pnl_df['Daily_PnL'] = (pnl_df['NAV'] - pnl_df['CashFlow'] - pnl_df['Prev_NAV'].fillna(pnl_df['NAV'] - pnl_df['CashFlow'])).replace([np.inf, -np.inf], 0).fillna(0).round(0)
        
        if not pnl_df.empty:
            min_date = pnl_df['Date'].min()
            full_dates = pd.bdate_range(start=min_date, end=min_date + pd.DateOffset(years=1))
            pnl_pivot = pnl_df.pivot(index='Date', columns='AccountID', values='Daily_PnL').reindex(full_dates).fillna(0)
            dates_pnl_js = to_js_array(pnl_pivot.index.strftime('%Y-%m-%d'), is_date=True)
            for silo, acc in zip(['a', 'b', 'c', 'd'],["U23144948", "U23139264", "U23154199", "U25218481"]):
                globals()[f'silo_{silo}_pnl'] = to_js_array(pnl_pivot[acc] if acc in pnl_pivot else [0]*len(full_dates))

        print(f"[OK] IBKR Data Parsed: {len(global_df)} trading days processed.")
    except Exception as e: print(f"[ERROR] Parsing IBKR CSV: {e}")

if os.path.exists(spy_qqq_file_path):
    try:
        bench_df = pd.read_csv(spy_qqq_file_path)
        bench_df['Date'] = pd.to_datetime(bench_df['Date'], format='%d-%b-%y')
    except Exception as e: print(f"[ERROR] Parsing Benchmarks: {e}")

attr_csv_path = os.path.join(target_directory, 'Daily_PnL_Attribution.csv')
if os.path.exists(attr_csv_path):
    try:
        attr_df = pd.read_csv(attr_csv_path).sort_values('Date').reset_index(drop=True)
        attr_dates_js = to_js_array(pd.to_datetime(attr_df['Date'].astype(str), format='%Y%m%d').dt.strftime('%Y-%m-%d'), is_date=True)
        for i in range(1, 6):
            globals()[f'attr_a{i}_js'] = to_js_array(attr_df[f'a{i}_{["Yield", "Beta", "VRP", "Alpha", "Fees"][i-1]}'].cumsum())
            globals()[f'total_a{i}'] = attr_df[f'a{i}_{["Yield", "Beta", "VRP", "Alpha", "Fees"][i-1]}'].sum()
        print(f"[OK] Perfect PnL Attribution Parsed.")
    except Exception as e: print(f"[ERROR] Parsing PnL Attribution: {e}")

if not bench_df.empty and not global_df.empty:
    master_bench = pd.merge(global_df, bench_df[['Date', 'SPY Close', 'QQQ Close', 'Status', 'Set TOR']], on='Date', how='inner')
    master_bench['SPY_Ret'] = master_bench['SPY Close'].pct_change().fillna(0)
    master_bench['QQQ_Ret'] = master_bench['QQQ Close'].pct_change().fillna(0)
    master_bench.rename(columns={'Daily_Return': 'Estate_Ret'}, inplace=True)
    
    for acc in["U23144948", "U23139264", "U23154199", "U25218481"]:
        if acc in silo_returns: master_bench = pd.merge(master_bench, silo_returns[acc], on='Date', how='left')
    
    ret_cols = ['Estate_Ret'] + [f"{acc}_Ret" for acc in["U23144948", "U23139264", "U23154199", "U25218481"]]
    master_bench[ret_cols] = master_bench.reindex(columns=ret_cols).replace([np.inf, -np.inf], 0).fillna(0)
    
    for col in ['SPY_Ret', 'QQQ_Ret'] + ret_cols: master_bench[col.replace('_Ret', '_Cum')] = ((1 + master_bench[col]).cumprod() - 1).fillna(0)
        
    master_bench['Estate_Daily_PnL'] = master_bench['NAV'] - master_bench['CashFlow'] - master_bench['Prev_NAV'].fillna(master_bench['NAV'] - master_bench['CashFlow'])
    master_bench['Estate_Daily_PnL'] = master_bench['Estate_Daily_PnL'].fillna(0)

    s_pnl, q_pnl = [master_bench['Estate_Daily_PnL'].iloc[0]], [master_bench['Estate_Daily_PnL'].iloc[0]]
    c_s, c_q = master_bench['NAV'].iloc[0], master_bench['NAV'].iloc[0]

    for i in range(1, len(master_bench)):
        cf, s_ret, q_ret = master_bench['CashFlow'].iloc[i], master_bench['SPY_Ret'].iloc[i], master_bench['QQQ_Ret'].iloc[i]
        s_pnl.append(c_s * s_ret); q_pnl.append(c_q * q_ret)
        c_s, c_q = c_s + (c_s * s_ret) + cf, c_q + (c_q * q_ret) + cf

    master_bench['SPY_Cum_PnL'] = pd.Series(s_pnl).cumsum()
    master_bench['QQQ_Cum_PnL'] = pd.Series(q_pnl).cumsum()
    master_bench['Estate_Cum_PnL'] = master_bench['Estate_Daily_PnL'].cumsum()

    dates_js = to_js_array(master_bench['Date'].dt.strftime('%Y-%m-%d'), is_date=True)
    estate_js, spy_js, qqq_js = to_js_array(master_bench['Estate_Cum']*100), to_js_array(master_bench['SPY_Cum']*100), to_js_array(master_bench['QQQ_Cum']*100)
    silo_a_js, silo_b_js = to_js_array(master_bench['U23144948_Cum']*100), to_js_array(master_bench['U23139264_Cum']*100)
    silo_c_js, silo_d_js = to_js_array(master_bench['U23154199_Cum']*100), to_js_array(master_bench['U25218481_Cum']*100)
    
    dates_cum_pnl_js = dates_js
    estate_cum_pnl_js = to_js_array(master_bench['Estate_Cum_PnL'])
    spy_cum_pnl_js, qqq_cum_pnl_js = to_js_array(master_bench['SPY_Cum_PnL']), to_js_array(master_bench['QQQ_Cum_PnL'])
    
    status_js = json.dumps(master_bench['Status'].fillna('').astype(str).tolist())
    tor_js = json.dumps([str(int(float(v))) if pd.notna(v) and str(v).strip() != '' else '' for v in master_bench['Set TOR']])

    if master_bench['SPY_Ret'].std() > 0:
        rf = 0.045
        for b, ret_col, pref in[('SPY', 'SPY_Ret', 'spy'), ('QQQ', 'QQQ_Ret', 'qqq')]:
            ann_est, ann_b = master_bench['Estate_Ret'].mean() * 252, master_bench[ret_col].mean() * 252
            var_b = master_bench[ret_col].var()
            beta = master_bench['Estate_Ret'].cov(master_bench[ret_col]) / var_b if var_b > 0 else 0
            alpha = ann_est - (rf + beta * (ann_b - rf))
            sharpe = (ann_b - rf) / (master_bench[ret_col].std() * np.sqrt(252)) if master_bench[ret_col].std() > 0 else 0
            corr = master_bench['Estate_Ret'].corr(master_bench[ret_col])
            
            globals()[f'{pref}_alpha_str'] = f'<span class="{"text-green-700" if alpha > 0 else "text-red-600"} font-black text-lg">{alpha*100:.2f}%</span>'
            globals()[f'{pref}_corr_str'] = f'<span class="{"text-green-700" if corr < 0.5 else ("text-indigo-700" if corr < 0.8 else "text-red-600")} font-black text-lg">{corr:.2f}</span>'
            globals()[f'{pref}_sharpe_str'] = f'<span class="{"text-green-700" if sharpe > 1 else "text-gray-800"} font-black text-lg">{sharpe:.2f}</span>'

    dpnl = master_bench['Estate_Daily_PnL'].values
    if len(dpnl) > 0:
        sim = np.cumsum(np.random.choice(dpnl, size=(10000, len(dpnl)), replace=True), axis=1)
        orig_cum = np.cumsum(dpnl)
        mc_stats_js = json.dumps({'orig_dd': float(np.max(np.maximum.accumulate(orig_cum) - orig_cum)), 'best_dd': float(np.min(np.max(np.maximum.accumulate(sim, axis=1) - sim, axis=1))), 'worst_dd': float(np.max(np.max(np.maximum.accumulate(sim, axis=1) - sim, axis=1))), 'avg_dd': float(np.mean(np.max(np.maximum.accumulate(sim, axis=1) - sim, axis=1)))})
        mc_visuals_js, mc_avg_js, mc_orig_js = json.dumps(sim[:100].round(2).tolist()), to_js_array(np.mean(sim, axis=0)), to_js_array(orig_cum)

html_content = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Estate Master Dashboard v66</title>
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
            <p class="text-gray-500 mt-2 font-medium">Silo Allocation & Institutional Data Engine v66</p>
            
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
                                <div class="text-center col-span-2 mt-1">ROC%: <span class="VAR_COLOR_D_ROC font-black text-sm">VAR_D_ROC</span></div>
                            </div>
                        </div>
                    </div>
                </div>

                <div class="bg-gray-50 p-4 rounded-xl border shadow-sm mt-4">
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
                    
                    <div class="grid grid-cols-1 lg:grid-cols-4 gap-4">
                        
                        <!-- Silo A -->
                        <div class="bg-blue-50 p-4 rounded-lg border border-blue-400 shadow-inner flex flex-col justify-between">
                            <div>
                                <h4 class="font-black text-gray-900 mb-2 text-sm border-b border-blue-400 pb-1">Silo A (Central Bank)</h4> 
                                <div class="flex gap-2 mb-1"><input type="text" id="a_ib01_lbl" value="IB01" class="w-1/2 text-[10px] p-1 border rounded bg-gray-100 font-bold" readonly><input type="number" id="a_ib01" value="0" class="w-1/2 text-[10px] p-1 border rounded" oninput="updateUI()"></div>
                                <div class="flex gap-2 mb-1"><input type="text" id="a_cspx_lbl" value="CSPX" class="w-1/2 text-[10px] p-1 border rounded bg-gray-100 font-bold" readonly><input type="number" id="a_cspx" value="0" class="w-1/2 text-[10px] p-1 border rounded" oninput="updateUI()"></div>
                                <div class="flex gap-2 mb-1"><input type="text" id="a_cndx_lbl" value="CNDX" class="w-1/2 text-[10px] p-1 border rounded bg-gray-100 font-bold" readonly><input type="number" id="a_cndx" value="0" class="w-1/2 text-[10px] p-1 border rounded" oninput="updateUI()"></div>
                                <div class="flex gap-2 mb-1"><input type="text" id="a_itwn_lbl" value="ITWN" class="w-1/2 text-[10px] p-1 border rounded bg-gray-100 font-bold" readonly><input type="number" id="a_itwn" value="0" class="w-1/2 text-[10px] p-1 border rounded" oninput="updateUI()"></div>
                                <div class="flex gap-2 mb-1"><input type="text" id="a_cskr_lbl" value="CSKR" class="w-1/2 text-[10px] p-1 border rounded bg-gray-100 font-bold" readonly><input type="number" id="a_cskr" value="0" class="w-1/2 text-[10px] p-1 border rounded" oninput="updateUI()"></div>
                                <div class="flex gap-2 mb-1"><input type="text" id="a_cnya_lbl" value="CNYA" class="w-1/2 text-[10px] p-1 border rounded bg-gray-100 font-bold" readonly><input type="number" id="a_cnya" value="0" class="w-1/2 text-[10px] p-1 border rounded" oninput="updateUI()"></div>
                                <div class="flex gap-2 mb-1"><input type="text" id="a_crypto_lbl" value="Crypto" class="w-1/2 text-[10px] p-1 border rounded bg-gray-100 font-bold" readonly><input type="number" id="a_crypto" value="0" class="w-1/2 text-[10px] p-1 border rounded" oninput="updateUI()"></div>
                                <div class="flex gap-2 mb-1"><input type="text" id="a_cash_lbl" value="Cash" class="w-1/2 text-[10px] p-1 border rounded bg-gray-100 font-bold" readonly><input type="number" id="a_cash" value="0" class="w-1/2 text-[10px] p-1 border rounded" oninput="updateUI()"></div>
                                <p class="text-[10px] text-green-600 font-bold mt-1 h-4" id="a_warning"></p>
                                
                                <p class="text-[10px] font-bold text-gray-800 mt-2 mb-1 uppercase tracking-wide border-t border-blue-400 pt-2">Margin Overlay</p>
                                <div class="flex gap-2 mb-1"><input type="text" value="Opt Liab" class="w-1/2 text-[10px] p-1 border border-red-300 rounded bg-red-100 font-bold text-red-800" readonly><input type="number" id="a_opt_mkt" value="0" class="w-1/2 text-[10px] p-1 border border-red-300 rounded text-red-800 bg-white" oninput="updateUI()"></div>
                                <div class="flex gap-2 mb-1"><input type="text" value="Opt Margin" class="w-1/2 text-[10px] p-1 border border-green-300 rounded bg-green-100 font-bold text-green-800" readonly><input type="number" id="a_xsp" value="0" class="w-1/2 text-[10px] p-1 border border-green-300 rounded text-green-800 bg-white" oninput="updateUI()"></div>
                            </div>
                        </div>

                        <!-- Silo B -->
                        <div class="bg-purple-50 p-4 rounded-lg border border-purple-400 shadow-inner flex flex-col justify-between">
                            <div>
                                <h4 class="font-black text-gray-900 mb-2 text-sm border-b border-purple-400 pb-1">Silo B (Sandbox)</h4> 
                                <div class="flex gap-2 mb-1"><input type="text" id="b_cash_lbl" value="Cash" class="w-1/2 text-[10px] p-1 border rounded bg-gray-100 font-bold" readonly><input type="number" id="b_cash" value="0" class="w-1/2 text-[10px] p-1 border rounded" oninput="updateUI()"></div>
                                <div class="flex gap-2 mb-1"><input type="text" id="b_cfd_lbl" value="US Tech CFDs" class="w-1/2 text-[10px] p-1 border rounded bg-gray-100 font-bold" readonly><input type="number" id="b_cfd" value="0" class="w-1/2 text-[10px] p-1 border rounded" oninput="updateUI()"></div>
                                <div class="flex gap-2 mb-1"><input type="text" id="b_intl_lbl" value="Intl Stocks" class="w-1/2 text-[10px] p-1 border rounded bg-gray-100 font-bold" readonly><input type="number" id="b_intl" value="0" class="w-1/2 text-[10px] p-1 border rounded" oninput="updateUI()"></div>
                                <p class="text-[10px] text-green-600 font-bold mt-1 h-4" id="b_warning"></p>
                            </div>
                        </div>

                        <!-- Silo C -->
                        <div class="bg-green-50 p-4 rounded-lg border border-green-400 shadow-inner flex flex-col justify-between">
                            <div>
                                <h4 class="font-black text-gray-900 mb-2 text-sm border-b border-green-400 pb-1">Silo C (Options)</h4> 
                                <div class="flex gap-2 mb-1"><input type="text" id="c_ib01_lbl" value="IB01" class="w-1/2 text-[10px] p-1 border rounded bg-gray-100 font-bold" readonly><input type="number" id="c_ib01" value="0" class="w-1/2 text-[10px] p-1 border rounded" oninput="updateUI()"></div>
                                <div class="flex gap-2 mb-1"><input type="text" id="c_cspx_lbl" value="CSPX" class="w-1/2 text-[10px] p-1 border rounded bg-gray-100 font-bold" readonly><input type="number" id="c_cspx" value="0" class="w-1/2 text-[10px] p-1 border rounded" oninput="updateUI()"></div>
                                <div class="flex gap-2 mb-1"><input type="text" id="c_cndx_lbl" value="CNDX" class="w-1/2 text-[10px] p-1 border rounded bg-gray-100 font-bold" readonly><input type="number" id="c_cndx" value="0" class="w-1/2 text-[10px] p-1 border rounded" oninput="updateUI()"></div>
                                <div class="flex gap-2 mb-1"><input type="text" id="c_itwn_lbl" value="ITWN" class="w-1/2 text-[10px] p-1 border rounded bg-gray-100 font-bold" readonly><input type="number" id="c_itwn" value="0" class="w-1/2 text-[10px] p-1 border rounded" oninput="updateUI()"></div>
                                <div class="flex gap-2 mb-1"><input type="text" id="c_cskr_lbl" value="CSKR" class="w-1/2 text-[10px] p-1 border rounded bg-gray-100 font-bold" readonly><input type="number" id="c_cskr" value="0" class="w-1/2 text-[10px] p-1 border rounded" oninput="updateUI()"></div>
                                <div class="flex gap-2 mb-1"><input type="text" id="c_cnya_lbl" value="CNYA" class="w-1/2 text-[10px] p-1 border rounded bg-gray-100 font-bold" readonly><input type="number" id="c_cnya" value="0" class="w-1/2 text-[10px] p-1 border rounded" oninput="updateUI()"></div>
                                <div class="flex gap-2 mb-1"><input type="text" id="c_crypto_lbl" value="Crypto" class="w-1/2 text-[10px] p-1 border rounded bg-gray-100 font-bold" readonly><input type="number" id="c_crypto" value="0" class="w-1/2 text-[10px] p-1 border rounded" oninput="updateUI()"></div>
                                <div class="flex gap-2 mb-1"><input type="text" id="c_cash_lbl" value="Cash" class="w-1/2 text-[10px] p-1 border rounded bg-gray-100 font-bold" readonly><input type="number" id="c_cash" value="0" class="w-1/2 text-[10px] p-1 border rounded" oninput="updateUI()"></div>
                                <p class="text-[10px] text-green-600 font-bold mt-1 h-4" id="c_warning"></p>
                                
                                <p class="text-[10px] font-bold text-gray-800 mt-2 mb-1 uppercase tracking-wide border-t border-green-400 pt-2">Margin Overlay</p>
                                <div class="flex gap-2 mb-1"><input type="text" value="Opt Liab" class="w-1/2 text-[10px] p-1 border border-red-300 rounded bg-red-100 font-bold text-red-800" readonly><input type="number" id="c_opt_mkt" value="0" class="w-1/2 text-[10px] p-1 border border-red-300 rounded text-red-800 bg-white" oninput="updateUI()"></div>
                                <div class="flex gap-2 mb-1"><input type="text" value="Opt Margin" class="w-1/2 text-[10px] p-1 border border-green-300 rounded bg-green-100 font-bold text-green-800" readonly><input type="number" id="c_xsp" value="0" class="w-1/2 text-[10px] p-1 border border-green-300 rounded text-green-800 bg-white" oninput="updateUI()"></div>
                            </div>
                        </div>

                        <!-- Silo D -->
                        <div class="bg-yellow-50 p-4 rounded-lg border border-yellow-400 shadow-inner flex flex-col justify-between">
                            <div>
                                <h4 class="font-black text-gray-900 mb-2 text-sm border-b border-yellow-400 pb-1">Silo D (13F Alpha)</h4> 
                                <div class="flex gap-2 mb-1"><input type="text" id="d_lbl_1" placeholder="Ticker 1" class="w-1/2 text-[10px] p-1 border rounded font-bold bg-white"><input type="number" id="d_val_1" value="0" class="w-1/2 text-[10px] p-1 border rounded" oninput="updateUI()"></div>
                                <div class="flex gap-2 mb-1"><input type="text" id="d_lbl_2" placeholder="Ticker 2" class="w-1/2 text-[10px] p-1 border rounded font-bold bg-white"><input type="number" id="d_val_2" value="0" class="w-1/2 text-[10px] p-1 border rounded" oninput="updateUI()"></div>
                                <div class="flex gap-2 mb-1"><input type="text" id="d_lbl_3" placeholder="Ticker 3" class="w-1/2 text-[10px] p-1 border rounded font-bold bg-white"><input type="number" id="d_val_3" value="0" class="w-1/2 text-[10px] p-1 border rounded" oninput="updateUI()"></div>
                                <div class="flex gap-2 mb-1"><input type="text" id="d_lbl_4" placeholder="Ticker 4" class="w-1/2 text-[10px] p-1 border rounded font-bold bg-white"><input type="number" id="d_val_4" value="0" class="w-1/2 text-[10px] p-1 border rounded" oninput="updateUI()"></div>
                                <div class="flex gap-2 mb-1"><input type="text" id="d_lbl_5" placeholder="Ticker 5" class="w-1/2 text-[10px] p-1 border rounded font-bold bg-white"><input type="number" id="d_val_5" value="0" class="w-1/2 text-[10px] p-1 border rounded" oninput="updateUI()"></div>
                                <div class="flex gap-2 mb-1"><input type="text" id="d_lbl_6" placeholder="Ticker 6" class="w-1/2 text-[10px] p-1 border rounded font-bold bg-white"><input type="number" id="d_val_6" value="0" class="w-1/2 text-[10px] p-1 border rounded" oninput="updateUI()"></div>
                                <div class="flex gap-2 mb-1"><input type="text" id="d_lbl_7" placeholder="Ticker 7" class="w-1/2 text-[10px] p-1 border rounded font-bold bg-white"><input type="number" id="d_val_7" value="0" class="w-1/2 text-[10px] p-1 border rounded" oninput="updateUI()"></div>
                                <div class="flex gap-2 mb-1"><input type="text" id="d_lbl_8" placeholder="Ticker 8" class="w-1/2 text-[10px] p-1 border rounded font-bold bg-white"><input type="number" id="d_val_8" value="0" class="w-1/2 text-[10px] p-1 border rounded" oninput="updateUI()"></div>
                                <div class="flex gap-2 mb-1"><input type="text" id="d_lbl_9" placeholder="Ticker 9" class="w-1/2 text-[10px] p-1 border rounded font-bold bg-white"><input type="number" id="d_val_9" value="0" class="w-1/2 text-[10px] p-1 border rounded" oninput="updateUI()"></div>
                                <div class="flex gap-2 mb-1"><input type="text" id="d_lbl_10" placeholder="Ticker 10" class="w-1/2 text-[10px] p-1 border rounded font-bold bg-white"><input type="number" id="d_val_10" value="0" class="w-1/2 text-[10px] p-1 border rounded" oninput="updateUI()"></div>
                                <div class="flex gap-2 mb-1 mt-3 border-t border-yellow-300 pt-2"><input type="text" value="Cash Bal" class="w-1/2 text-[10px] p-1 border rounded bg-gray-100 font-bold" readonly><input type="number" id="d_val_cash" value="0" class="w-1/2 text-[10px] p-1 border rounded" oninput="updateUI()"></div>
                                <p class="text-[10px] text-green-600 font-bold mt-1 h-4" id="d_warning"></p>
                            </div>
                        </div>
                    </div>
                </div>
            </div>

            <!-- DAILY PNL HISTOGRAM -->
            <div class="xl:col-span-12 mt-2">
                <div class="bg-white border rounded-xl p-4 shadow-sm overflow-hidden">
                    <h3 class="text-xl font-bold mb-4 text-gray-800 border-b pb-2">3. Daily PnL per Silo</h3>
                    <div id="daily-pnl-chart" class="w-full h-[400px]"></div>
                </div>
            </div>

            <!-- MONTE CARLO & PNL ATTRIBUTION -->
            <div class="xl:col-span-12 mt-2 grid grid-cols-1 xl:grid-cols-12 gap-4">
                <div class="xl:col-span-6 bg-white border rounded-xl p-4 shadow-sm flex flex-col">
                    <h3 class="text-xl font-bold mb-4 text-gray-800 border-b pb-2">4. Estate Montecarlo PnL Simulation</h3>
                    <div id="montecarlo-chart" class="w-full flex-grow min-h-[450px]"></div>
                </div>
                                       
                <div class="xl:col-span-6 bg-white border rounded-xl p-4 shadow-sm flex flex-col">
                    <h3 class="text-xl font-bold mb-4 text-gray-800 border-b pb-2">PnL Attribution & Capital Velocity</h3>
                    <div class="grid grid-cols-1 lg:grid-cols-2 gap-4 flex-grow mb-4 border-b border-gray-100 pb-2">
                        <div id="pnl-bar-chart" class="w-full h-[320px]"></div>
                        <div id="pnl-line-chart" class="w-full h-[320px]"></div>
                    </div>
                    
                    <div class="flex flex-col justify-end">
                        <h4 class="text-xs font-black text-gray-500 uppercase tracking-widest mb-3">Options Engine Velocity (v66 Automated)</h4>                        
                        <div class="grid grid-cols-2 gap-3">
                            <div class="bg-gray-50 border border-gray-200 rounded-lg p-3 text-center">
                                <p class="text-[10px] text-gray-500 font-bold uppercase mb-1">Win Rate</p>
                                <p class="text-xl font-black text-green-700">VAR_VEL_WINRATE%</p>
                            </div>
                            <div class="bg-gray-50 border border-gray-200 rounded-lg p-3 text-center">
                                <p class="text-[10px] text-gray-500 font-bold uppercase mb-1">Avg Days in Trade</p>
                                <p class="text-xl font-black text-blue-700">VAR_VEL_AVGDAYS d</p>
                            </div>
                        </div>
                    </div>
                </div>
            </div>

            <!-- INSTRUMENT MATRIX -->
            <div class="xl:col-span-12 mt-2">
                <div class="bg-white border rounded-xl p-4 shadow-sm overflow-x-auto">
                    <h3 class="text-xl font-bold mb-4 text-gray-800 border-b pb-2">5. The Master Instrument Matrix</h3>
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
                            </tr>
                        </thead>
                        <tbody class="divide-y divide-gray-200 whitespace-normal" id="matrix-body"></tbody>                      
                        <tfoot class="bg-gray-100 font-bold text-gray-900 border-t-2 border-gray-400">
                            <tr>
                                <td colspan="9" class="py-3 px-3 text-right leading-tight">GROSS PHYSICAL ASSETS:<br><span class="text-[10px] text-red-600">OPTIONS LIABILITY DRAG:</span><br>TRUE NET ESTATE CHECKSUM:</td>
                                <td class="py-3 px-3 text-center text-blue-700 text-sm leading-tight" id="alloc_total">0.00%<br><span class="text-[10px] text-red-600">0.00%</span><br>0.00%</td>
                                <td colspan="2" class="py-3 px-3 text-left text-[10px] text-gray-500 whitespace-nowrap align-bottom">Must exactly equal 100.00%</td>
                            </tr>
                        </tfoot>
                    </table>
                </div>
            </div>

            <!-- CAPACITY TRACKER -->
            <div class="xl:col-span-12 mt-2">
                <div class="bg-white border rounded-xl p-4 shadow-sm">
                    <h3 class="text-xl font-bold mb-4 text-gray-800 border-b pb-2">6. Capital Deployment & Margin Capacity Tracker</h3>
                    <div class="grid grid-cols-1 md:grid-cols-3 gap-6">
                        
                        <div class="bg-gray-50 border border-gray-200 rounded-lg p-4 relative overflow-hidden flex flex-col justify-between">
                            <div>
                                <div class="absolute right-0 top-0 w-2 h-full bg-blue-400"></div>
                                <h4 class="text-sm font-black text-gray-800 uppercase tracking-wide mb-1">Bedrock Cash Buffer (IB01 + USD)</h4>
                                <div class="flex justify-between items-end mb-1"><span class="text-2xl font-black text-blue-700" id="trk_cash_val">$0</span><span class="text-sm font-bold text-gray-700" id="trk_cash_pct">0%</span></div>
                                <div class="w-full bg-white border border-gray-300 rounded-full h-3 mb-1 flex overflow-hidden" id="trk_cash_bar_container"></div>
                                <p class="text-[11px] text-gray-600 font-bold mt-2" id="trk_cash_status">Status: Calculating...</p>                                                              
                            </div>
                        </div>

                        <div class="bg-gray-50 border border-gray-200 rounded-lg p-4 relative overflow-hidden flex flex-col justify-between">
                            <div>
                                <div class="absolute right-0 top-0 w-2 h-full bg-green-500"></div>
                                <h4 class="text-sm font-black text-gray-800 uppercase tracking-wide mb-1">Options Margin Utilization</h4>
                                <div class="flex justify-between items-end mb-1"><span class="text-2xl font-black text-green-700" id="trk_margin_val">$0</span><span class="text-sm font-bold text-gray-700" id="trk_margin_pct">0%</span></div>
                                <div class="w-full bg-gray-200 rounded-full h-3 mb-1 overflow-hidden"><div class="bg-green-500 h-full" id="trk_margin_bar" style="width: 0%"></div></div>
                            </div>
                            <p class="text-[11px] text-gray-600 font-bold mt-2" id="trk_margin_status">Status: Calculating...</p>
                        </div>

                        <div class="bg-gray-50 border border-gray-200 rounded-lg p-4 relative overflow-hidden">
                            <div class="absolute right-0 top-0 w-2 h-full bg-purple-500"></div>
                            <h4 class="text-sm font-black text-gray-800 uppercase tracking-wide mb-1">DCA Deployment Schedule</h4>
                            <div class="flex flex-col justify-center mt-2"><span class="text-xs font-medium text-gray-800 leading-relaxed" id="trk_dca_action">Awaiting Regime Data...</span></div>
                        </div>

                    </div>
                </div>
            </div>

        </div>
    </div>

    <script>
        function fmtCur(val) { return ' USD ' + Math.round(val).toLocaleString('en-US'); }
        function safeParse(jsonStr) { try { return (!jsonStr || jsonStr.startsWith('VAR_')) ? [] : JSON.parse(jsonStr); } catch (e) { return[]; } }
        
        const palette = { siloA: '#93c5fd', siloB: '#d8b4fe', siloC: '#86efac', siloD: '#fde047', cspx: '#f97316', cndx: '#8b5cf6', cfd_intl: '#a855f7', optMktVal: '#ef4444', crypto: '#0ea5e9', itwn: '#14b8a6', cskr: '#f472b6', cnya: '#fb923c' };

        const instruments =[
            { id: "cash", inst: "USD Cash", type: "Currency", risk: "Risk-Free", alpha: "Zero", sharpe: "Stabilizer", strat: "Liquidity", jur: "US (IBKR)", tax: "Exempt (Bank Deposit)", min: "1%", max: "100%", rec: "Splendid", class: "splendid" },
            { id: "ib01", inst: "IB01", type: "UCITS ETF", risk: "Risk-Free", alpha: "Zero", sharpe: "High", strat: "Collateral", jur: "Ireland", tax: "Exempt (Irish Domicile)", min: "10%", max: "100%", rec: "Splendid", class: "splendid" },
            { id: "xsp", inst: "XSP Put Spreads", type: "Index Option", risk: "Moderate", alpha: "High (VRP)", sharpe: "High", strat: "Weekly Income", jur: "US (Cboe)", tax: "Exempt (Cash-Settled)", min: "0%", max: "25%", rec: "Splendid", class: "splendid" },
            { id: "xnd", inst: "XND Put Spreads", type: "Index Option", risk: "Mod/High", alpha: "High", sharpe: "Moderate", strat: "Satellite Income", jur: "US (Cboe)", tax: "Exempt (Cash-Settled)", min: "0%", max: "10%", rec: "Great", class: "great" },
            { id: "cspx", inst: "CSPX", type: "UCITS ETF", risk: "Moderate", alpha: "Zero", sharpe: "Baseline", strat: "Long Term", jur: "Ireland", tax: "Exempt (Irish Domicile)", min: "0%", max: "60%", rec: "Great", class: "great" },
            { id: "cndx", inst: "CNDX", type: "UCITS ETF", risk: "Aggressive", alpha: "High", sharpe: "Moderate", strat: "Long Term", jur: "Ireland", tax: "Exempt (Irish Domicile)", min: "0%", max: "40%", rec: "Great", class: "great" },
            { id: "itwn", inst: "ITWN (Taiwan)", type: "UCITS ETF", risk: "Aggressive", alpha: "High", sharpe: "Moderate", strat: "Momentum", jur: "Ireland", tax: "Exempt (Irish Domicile)", min: "0%", max: "20%", rec: "Great", class: "great" },
            { id: "cskr", inst: "CSKR (Korea)", type: "UCITS ETF", risk: "Aggressive", alpha: "High", sharpe: "Moderate", strat: "Momentum", jur: "Ireland", tax: "Exempt (Irish Domicile)", min: "0%", max: "15%", rec: "Great", class: "great" },
            { id: "cnya", inst: "CNYA (China)", type: "UCITS ETF", risk: "Aggressive", alpha: "High", sharpe: "Volatile", strat: "Momentum", jur: "Ireland", tax: "Exempt (Irish Domicile)", min: "0%", max: "10%", rec: "Great", class: "great" },
            { id: "gold", inst: "SGLN / IGLN (Gold)", type: "UCITS ETC", risk: "Moderate", alpha: "Crisis Alpha", sharpe: "Stabilizer", strat: "Tail Hedge", jur: "Ireland", tax: "Exempt (Irish Domicile)", min: "0%", max: "10%", rec: "Good", class: "good" },
            { id: "crypto", inst: "BTC/ETH ETPs", type: "Crypto ETP", risk: "Aggressive", alpha: "High", sharpe: "Volatile", strat: "Uncorrelated", jur: "Europe (Jersey/CH)", tax: "Exempt (Offshore Wrapper)", min: "0%", max: "5%", rec: "Good", class: "good" },
            { id: "cfd", inst: "US Tech CFDs", type: "OTC Contract", risk: "Aggressive", alpha: "High", sharpe: "Negative", strat: "Swing Trading", jur: "UK/Offshore", tax: "Exempt (OTC Derivative)", min: "0%", max: "3%", rec: "Good", class: "good" },
            { id: "intl", inst: "International Stocks", type: "Direct Equity", risk: "Aggressive", alpha: "High", sharpe: "Negative", strat: "Swing Trading", jur: "Europe/Asia", tax: "Exempt", min: "0%", max: "3%", rec: "Good", class: "good" },
            { id: "mes", inst: "/MES Put Spreads", type: "Futures Option", risk: "Moderate", alpha: "Highest (SPAN)", sharpe: "High", strat: "Capital Efficiency", jur: "US (CME)", tax: "Exempt (Section 1256)", min: "0%", max: "25%", rec: "Contingent", class: "contingent" },
            { id: "cta", inst: "Managed Futures (CTAs)", type: "UCITS Fund", risk: "Moderate", alpha: "Crisis Alpha", sharpe: "High (Uncorrel.)", strat: "Trend Following", jur: "Ireland", tax: "Exempt (Irish Domicile)", min: "0%", max: "15%", rec: "Contingent", class: "contingent" },
            { id: "phys", inst: "Physical US Stocks", type: "Stock", risk: "Extreme", alpha: "High", sharpe: "Baseline", strat: "Swing", jur: "US", tax: "LETHAL (40% Estate Tax)", min: "0%", max: "0%", rec: "Avoid", class: "avoid" }
        ];

        function populateTable() {
            let html = "";
            instruments.forEach(i => {
                html += `<tr class="hover:bg-gray-50 border-b border-gray-100"><td class="py-2 px-3 font-semibold text-gray-900">${i.inst}</td><td class="py-2 px-3">${i.type}</td><td class="py-2 px-3">${i.risk}</td><td class="py-2 px-3">${i.alpha}</td><td class="py-2 px-3 font-medium text-indigo-700">${i.sharpe}</td><td class="py-2 px-3">${i.strat}</td><td class="py-2 px-3">${i.jur}</td><td class="py-2 px-3">${i.tax}</td><td class="py-2 px-3 font-bold text-center text-gray-500 border-l border-gray-200 bg-gray-50">${i.min}</td><td class="py-2 px-3 font-black text-center text-blue-700 bg-blue-50" id="alloc_${i.id}">0.00%</td><td class="py-2 px-3 font-bold text-center border-r border-gray-200 bg-gray-50">${i.max}</td><td class="py-2 px-3 ${i.class} text-center rounded">${i.rec}</td></tr>`;
            });
            document.getElementById('matrix-body').innerHTML = html;
        }

        function updateUI() {
            const sA = parseFloat(document.getElementById('siloA').value) || 0;
            const sB = parseFloat(document.getElementById('siloB').value) || 0;
            const sC = parseFloat(document.getElementById('siloC').value) || 0;
            const sD = parseFloat(document.getElementById('siloD').value) || 0;
            let totalEstate = sA + sB + sC + sD;
            
            const progExp = safeParse('VAR_PROG_EXP');
            if (progExp && progExp.Silo_B) {
                let b = progExp.Silo_B; document.getElementById('b_tier_lbl').innerText = `Advisory: Base $${(b.suggested_base/1000).toFixed(0)}k (${b.current_tier})`;
                document.getElementById('b_tier_next').innerText = `Next: ${b.next_threshold === "MAX" ? 'MAX' : '$'+(b.next_threshold/1000).toFixed(1)+'k'}`;
                document.getElementById('b_tier_dist').innerText = `Profit: $${b.profit.toLocaleString()} | Shortfall: $${b.distance_to_next.toLocaleString()}`;
                document.getElementById('b_tier_bar').style.width = (b.next_threshold === "MAX" ? 100 : Math.max(0, Math.min(100, (b.profit / b.next_threshold) * 100))) + "%";
            }
            if (progExp && progExp.Silo_D) {
                let d = progExp.Silo_D; document.getElementById('d_tier_lbl').innerText = `Advisory: Base $${(d.suggested_base/1000).toFixed(0)}k (${d.current_tier})`;
                document.getElementById('d_tier_next').innerText = `Next: ${d.next_threshold === "MAX" ? 'MAX' : '$'+(d.next_threshold/1000).toFixed(1)+'k'}`;
                document.getElementById('d_tier_dist').innerText = `Profit: $${d.profit.toLocaleString()} | Shortfall: $${d.distance_to_next.toLocaleString()}`;
                document.getElementById('d_tier_bar').style.width = (d.next_threshold === "MAX" ? 100 : Math.max(0, Math.min(100, (d.profit / d.next_threshold) * 100))) + "%";
            }

            const getV = (id) => parseFloat(document.getElementById(id).value) || 0;
            const setL = (id, val, siloVal) => document.getElementById(id).value = `${id.split('_')[1].toUpperCase()} (${siloVal>0 ? (val/siloVal*100).toFixed(1) : 0}%)`;
            
            let vA = {ib01: getV('a_ib01'), cspx: getV('a_cspx'), cndx: getV('a_cndx'), itwn: getV('a_itwn'), cskr: getV('a_cskr'), cnya: getV('a_cnya'), crypto: getV('a_crypto'), cash: getV('a_cash'), opt: getV('a_opt_mkt'), xsp: getV('a_xsp')};
            setL('a_ib01_lbl', vA.ib01, sA); setL('a_cspx_lbl', vA.cspx, sA); setL('a_cndx_lbl', vA.cndx, sA); setL('a_itwn_lbl', vA.itwn, sA); setL('a_cskr_lbl', vA.cskr, sA); setL('a_cnya_lbl', vA.cnya, sA); setL('a_crypto_lbl', vA.crypto, sA); setL('a_cash_lbl', vA.cash, sA);
            document.getElementById('a_warning').innerText = Math.abs(sA - (vA.ib01+vA.cspx+vA.cndx+vA.itwn+vA.cskr+vA.cnya+vA.crypto+vA.cash+vA.opt)) > 1 ? `Unallocated: $${(sA - (vA.ib01+vA.cspx+vA.cndx+vA.itwn+vA.cskr+vA.cnya+vA.crypto+vA.cash+vA.opt)).toFixed(2)}` : "Balanced: OK";

            let vB = {cash: getV('b_cash'), cfd: getV('b_cfd'), intl: getV('b_intl')};
            setL('b_cash_lbl', vB.cash, sB); setL('b_cfd_lbl', vB.cfd, sB); setL('b_intl_lbl', vB.intl, sB);
            document.getElementById('b_warning').innerText = Math.abs(sB - (vB.cash+vB.cfd+vB.intl)) > 1 ? `Unallocated: $${(sB - (vB.cash+vB.cfd+vB.intl)).toFixed(2)}` : "Balanced: OK";

            let vC = {ib01: getV('c_ib01'), cspx: getV('c_cspx'), cndx: getV('c_cndx'), itwn: getV('c_itwn'), cskr: getV('c_cskr'), cnya: getV('c_cnya'), crypto: getV('c_crypto'), cash: getV('c_cash'), opt: getV('c_opt_mkt'), xsp: getV('c_xsp')};
            setL('c_ib01_lbl', vC.ib01, sC); setL('c_cspx_lbl', vC.cspx, sC); setL('c_cndx_lbl', vC.cndx, sC); setL('c_itwn_lbl', vC.itwn, sC); setL('c_cskr_lbl', vC.cskr, sC); setL('c_cnya_lbl', vC.cnya, sC); setL('c_crypto_lbl', vC.crypto, sC); setL('c_cash_lbl', vC.cash, sC);
            document.getElementById('c_warning').innerText = Math.abs(sC - (vC.ib01+vC.cspx+vC.cndx+vC.itwn+vC.cskr+vC.cnya+vC.crypto+vC.cash+vC.opt)) > 1 ? `Unallocated: $${(sC - (vC.ib01+vC.cspx+vC.cndx+vC.itwn+vC.cskr+vC.cnya+vC.crypto+vC.cash+vC.opt)).toFixed(2)}` : "Balanced: OK";

            let vD_cfd = [1,2,3,4,5,6,7,8,9,10].reduce((sum, i) => sum + getV('d_val_'+i), 0);
            let vD = {cash: getV('d_val_cash'), cfd: vD_cfd};
            document.getElementById('d_warning').innerText = Math.abs(sD - (vD.cash+vD.cfd)) > 1 ? `Unallocated: $${(sD - (vD.cash+vD.cfd)).toFixed(2)}` : "Balanced: OK";

            let alloc = {"USD Cash": vA.cash+vB.cash+vC.cash+vD.cash, "IB01": vA.ib01+vC.ib01, "CSPX": vA.cspx+vC.cspx, "CNDX": vA.cndx+vC.cndx, "ITWN (Taiwan)": vA.itwn+vC.itwn, "CSKR (Korea)": vA.cskr+vC.cskr, "CNYA (China)": vA.cnya+vC.cnya, "BTC/ETH ETPs": vA.crypto+vC.crypto, "US Tech CFDs": vB.cfd+vD.cfd, "International Stocks": vB.intl};
            let totP = 0;
            instruments.forEach(i => {
                let el = document.getElementById(`alloc_${i.id}`);
                if (el) {
                    if (alloc[i.inst] !== undefined) {
                        let pct = (totalEstate > 0) ? (alloc[i.inst] / totalEstate) * 100 : 0;
                        el.innerText = pct.toFixed(2) + "%"; totP += pct;
                    } else { el.innerText = "N/A"; el.className = el.className.replace('text-blue-700', 'text-gray-400'); }
                }
            });
            let optPct = (totalEstate > 0) ? ((vA.opt + vC.opt) / totalEstate) * 100 : 0;
            document.getElementById('alloc_total').innerHTML = `${totP.toFixed(2)}%<br><span class="text-[10px] text-red-600">${optPct.toFixed(2)}%</span><br><span class="text-black font-black">${(totP + optPct).toFixed(2)}%</span>`;

            const xLabels =['Silo A', 'Silo B', 'Silo C', 'Silo D'];
            Plotly.react('bar-chart', [
                { x: xLabels, y:[vA.ib01, 0, vC.ib01, 0], name: 'IB01', type: 'bar', marker: {color: palette.siloA} },
                { x: xLabels, y:[vA.cspx, 0, vC.cspx, 0], name: 'CSPX', type: 'bar', marker: {color: palette.cspx} },
                { x: xLabels, y:[vA.cndx, 0, vC.cndx, 0], name: 'CNDX', type: 'bar', marker: {color: palette.cndx} },
                { x: xLabels, y:[vA.itwn, 0, vC.itwn, 0], name: 'ITWN', type: 'bar', marker: {color: palette.itwn} },
                { x: xLabels, y: [vA.cskr, 0, vC.cskr, 0], name: 'CSKR', type: 'bar', marker: {color: palette.cskr} },
                { x: xLabels, y:[vA.cnya, 0, vC.cnya, 0], name: 'CNYA', type: 'bar', marker: {color: palette.cnya} },
                { x: xLabels, y:[vA.crypto, 0, vC.crypto, 0], name: 'Crypto', type: 'bar', marker: {color: palette.crypto} },
                { x: xLabels, y:[0, (vB.cfd+vB.intl), 0, vD.cfd], name: 'CFDs/Intl', type: 'bar', marker: {color: palette.cfd_intl} },
                { x: xLabels, y:[vA.cash, vB.cash, vC.cash, vD.cash], name: 'Cash', type: 'bar', marker: {color: palette.siloC} },
                { x: xLabels, y: [vA.opt, 0, vC.opt, 0], name: 'Opt Liab', type: 'bar', marker: {color: palette.optMktVal} },
                { x: ['Silo A', 'Silo C'], y:[vA.xsp, vC.xsp], name: 'Margin Lock', type: 'scatter', mode: 'markers', marker: {symbol: 'diamond', size: 14, color: '#ef4444'} }
            ], { barmode: 'relative', title: 'GAAP Balance Sheet per Silo (USD)', margin: {b: 40, t: 80}, paper_bgcolor: 'rgba(0,0,0,0)', plot_bgcolor: 'rgba(0,0,0,0)' }, {displayModeBar: false, responsive: true});

            Plotly.react('pie-chart', [{ 
                values:[vA.ib01+vC.ib01, vA.cspx+vC.cspx, vA.cndx+vC.cndx, vA.itwn+vC.itwn, vA.cskr+vC.cskr, vA.cnya+vC.cnya, vB.cfd+vB.intl+vD.cfd, vA.cash+vB.cash+vC.cash+vD.cash, vA.crypto+vC.crypto, Math.abs(vA.opt+vC.opt)], 
                labels:['IB01', 'CSPX', 'CNDX', 'ITWN', 'CSKR', 'CNYA', 'Active Swing', 'Cash', 'Crypto', 'Opt Liab'], 
                type: 'pie', hole: .4, textinfo: 'label+percent', marker: {colors:[palette.siloA, palette.cspx, palette.cndx, palette.itwn, palette.cskr, palette.cnya, palette.cfd_intl, palette.siloC, palette.crypto, palette.optMktVal]} 
            }], { title: `Gross Asset Allocation`, margin: {t: 40, b: 20}, paper_bgcolor: 'rgba(0,0,0,0)' }, {displayModeBar: false, responsive: true});

            let cashPct = totalEstate > 0 ? ((vA.ib01+vC.ib01+vA.cash+vB.cash+vC.cash+vD.cash) / totalEstate) * 100 : 0;
            document.getElementById('trk_cash_val').innerText = fmtCur(vA.ib01+vC.ib01+vA.cash+vB.cash+vC.cash+vD.cash);
            document.getElementById('trk_cash_pct').innerText = cashPct.toFixed(1) + "%";
            document.getElementById('trk_cash_bar_container').innerHTML = `<div class="bg-red-500 h-full" style="width: ${Math.min(cashPct, 40)}%"></div><div class="bg-green-500 h-full" style="width: ${Math.max(0, Math.min(cashPct - 40, 60))}%"></div>`;
            document.getElementById('trk_cash_status').innerHTML = cashPct >= 40 ? `<span class="text-green-700 font-black">✓ SAFE</span>` : `<span class="text-red-600 font-black">⚠️ DANGER: Cache Breach</span>`;

            let marginPct = totalEstate > 0 ? ((vA.xsp+vC.xsp) / totalEstate) * 100 : 0;
            document.getElementById('trk_margin_val').innerText = fmtCur(vA.xsp+vC.xsp);
            document.getElementById('trk_margin_pct').innerText = marginPct.toFixed(1) + "% of Estate";
            document.getElementById('trk_margin_bar').style.width = Math.min(((vA.xsp+vC.xsp) / (totalEstate * 0.25)) * 100, 100) + "%";
            
            const attrDates = safeParse('VAR_ATTR_DATES');
            if (attrDates.length > 0) {
                Plotly.react('pnl-bar-chart', [{ x:['Yield', 'Beta', 'VRP', 'Alpha', 'Fees'], y:[VAR_TOTAL_A1, VAR_TOTAL_A2, VAR_TOTAL_A3, VAR_TOTAL_A4, VAR_TOTAL_A5], type: 'bar', text:[VAR_TOTAL_A1, VAR_TOTAL_A2, VAR_TOTAL_A3, VAR_TOTAL_A4, VAR_TOTAL_A5].map(v=>fmtCur(v)), textposition: 'auto', marker: { color:['#3b82f6', '#f97316', '#86efac', '#a855f7', '#ef4444'] } }], { title: 'Absolute PnL by Strategy', margin: {t: 30, b: 30, l: 40, r: 10}, paper_bgcolor: 'rgba(0,0,0,0)', plot_bgcolor: 'rgba(0,0,0,0)' }, {displayModeBar: false, responsive: true});
                Plotly.react('pnl-line-chart',[{x: attrDates, y: safeParse('VAR_ATTR_A1'), name: 'Yield', type: 'scatter', mode: 'lines', line: {color: '#3b82f6', width: 2}}, {x: attrDates, y: safeParse('VAR_ATTR_A2'), name: 'Beta', type: 'scatter', mode: 'lines', line: {color: '#f97316', width: 2}}, {x: attrDates, y: safeParse('VAR_ATTR_A3'), name: 'VRP', type: 'scatter', mode: 'lines', line: {color: '#86efac', width: 2}}, {x: attrDates, y: safeParse('VAR_ATTR_A4'), name: 'Alpha', type: 'scatter', mode: 'lines', line: {color: '#a855f7', width: 2}}, {x: attrDates, y: safeParse('VAR_ATTR_A5'), name: 'Fees', type: 'scatter', mode: 'lines', line: {color: '#ef4444', width: 2}}], { title: 'Cumulative Trajectory', margin: {t: 30, b: 30, l: 40, r: 10}, paper_bgcolor: 'rgba(0,0,0,0)', plot_bgcolor: 'rgba(0,0,0,0)' }, {displayModeBar: false, responsive: true});                               
            }
        }
        document.querySelectorAll('input').forEach(i => i.addEventListener('input', updateUI));
        
        const benchDates = safeParse('VAR_BENCH_DATES');
        if (benchDates.length > 0) {
            Plotly.react('benchmark-chart',[{x: benchDates, y: safeParse('VAR_ESTATE_CUM'), name: 'Estate', type: 'scatter', mode: 'lines', line: {color: 'black', width: 4}}, {x: benchDates, y: safeParse('VAR_SPY_CUM'), name: 'SPY', type: 'scatter', mode: 'lines', line: {color: '#3b82f6', width: 2}}, {x: benchDates, y: safeParse('VAR_QQQ_CUM'), name: 'QQQ', type: 'scatter', mode: 'lines', line: {color: '#dc2626', width: 2}}], { margin: {t: 10, b: 30, l: 40, r: 20}, paper_bgcolor: 'rgba(0,0,0,0)', plot_bgcolor: 'rgba(0,0,0,0)' }, {displayModeBar: false, responsive: true});
            let smLayout = { margin: {t: 20, b: 20, l: 30, r: 10}, paper_bgcolor: 'rgba(0,0,0,0)', plot_bgcolor: 'rgba(0,0,0,0)', xaxis: { showticklabels: false, showgrid: false, zeroline: false }};
            Plotly.react('chart-silo-a',[{x: benchDates, y: safeParse('VAR_SILOA_CUM'), type: 'scatter', mode: 'lines', line: {color: 'black', width: 3}}], smLayout, {displayModeBar: false, responsive: true});
            Plotly.react('chart-silo-b',[{x: benchDates, y: safeParse('VAR_SILOB_CUM'), type: 'scatter', mode: 'lines', line: {color: 'black', width: 3}}], smLayout, {displayModeBar: false, responsive: true});
            Plotly.react('chart-silo-c',[{x: benchDates, y: safeParse('VAR_SILOC_CUM'), type: 'scatter', mode: 'lines', line: {color: 'black', width: 3}}], smLayout, {displayModeBar: false, responsive: true});
            Plotly.react('chart-silo-d',[{x: benchDates, y: safeParse('VAR_SILOD_CUM'), type: 'scatter', mode: 'lines', line: {color: 'black', width: 3}}], smLayout, {displayModeBar: false, responsive: true});
            
            Plotly.react('daily-pnl-chart',[
                {x: safeParse('VAR_DATES_PNL'), y: safeParse('VAR_SILOA_PNL'), type: 'bar', marker: {color: palette.siloA}},
                {x: safeParse('VAR_DATES_PNL'), y: safeParse('VAR_SILOB_PNL'), type: 'bar', marker: {color: palette.siloB}},
                {x: safeParse('VAR_DATES_PNL'), y: safeParse('VAR_SILOC_PNL'), type: 'bar', marker: {color: palette.siloC}},
                {x: safeParse('VAR_DATES_PNL'), y: safeParse('VAR_SILOD_PNL'), type: 'bar', marker: {color: palette.siloD}},
                {x: safeParse('VAR_DATES_CUM_PNL'), y: safeParse('VAR_ESTATE_CUM_PNL'), type: 'scatter', mode: 'lines', line: {color: 'black', width: 4}, yaxis: 'y2'}
            ], { barmode: 'relative', margin: {t: 20, b: 50, l: 60, r: 60}, paper_bgcolor: 'rgba(0,0,0,0)', plot_bgcolor: 'rgba(0,0,0,0)', yaxis2: { side: 'right', overlaying: 'y'} }, {displayModeBar: false, responsive: true});
        }

        const mcOrig = safeParse('VAR_MC_ORIG');
        if (mcOrig.length > 0) {
            let mcTraces = safeParse('VAR_MC_VISUALS').map(tr => ({y: tr, type: 'scatter', mode: 'lines', line: {color: 'rgba(100,100,200,0.1)', width: 1}, showlegend: false}));
            mcTraces.push({ y: safeParse('VAR_MC_AVG'), name: 'Avg Path', type: 'scatter', mode: 'lines', line: {color: 'blue', width: 3} });
            mcTraces.push({ y: mcOrig, name: 'Original', type: 'scatter', mode: 'lines', line: {color: 'black', width: 3} });
            Plotly.react('montecarlo-chart', mcTraces, { margin: {t: 20, b: 40, l: 60, r: 20}, paper_bgcolor: 'rgba(0,0,0,0)', plot_bgcolor: 'rgba(0,0,0,0)' }, {displayModeBar: false, responsive: true});
        }

        const liveAlloc = safeParse('VAR_LIVE_ALLOCATIONS');
        if (Object.keys(liveAlloc).length > 0) {['A', 'B', 'C'].forEach(s => {
                if (liveAlloc[s]) {
                    Object.keys(liveAlloc[s]).forEach(k => {
                        let el = document.getElementById(`${s.toLowerCase()}_${k.toLowerCase()}`);
                        if (el) el.value = liveAlloc[s][k];
                    });
                }
            });
            if (liveAlloc['A'] && liveAlloc['A']['OPT_LIAB']) document.getElementById('a_opt_mkt').value = liveAlloc['A']['OPT_LIAB'];
            if (liveAlloc['C'] && liveAlloc['C']['OPT_LIAB']) document.getElementById('c_opt_mkt').value = liveAlloc['C']['OPT_LIAB'];
            if (liveAlloc['A'] && liveAlloc['A']['OPT_MARGIN']) document.getElementById('a_xsp').value = liveAlloc['A']['OPT_MARGIN'];
            if (liveAlloc['C'] && liveAlloc['C']['OPT_MARGIN']) document.getElementById('c_xsp').value = liveAlloc['C']['OPT_MARGIN'];
        }

        const siloD = safeParse('VAR_SILOD_HOLDINGS');
        siloD.forEach((h, i) => {
            if (i < 10) {
                document.getElementById(`d_lbl_${i+1}`).value = h.ticker;
                document.getElementById(`d_val_${i+1}`).value = h.value;
            }
        });
        if (liveAlloc['D']) document.getElementById('d_val_cash').value = liveAlloc['D']['CASH'] || 0;

        populateTable();
        updateUI();
    </script>
</body>
</html>
"""

for acc, pref in[("ESTATE", "ESTATE"), ("U23144948", "A"), ("U23139264", "B"), ("U23154199", "C"), ("U25218481", "D")]:
    html_content = html_content.replace(f"VAR_COLOR_{pref}_IRR", get_color_class(metrics[acc]["irr"]))
    html_content = html_content.replace(f"VAR_{pref}_IRR", metrics[acc]["irr"])
    html_content = html_content.replace(f"VAR_COLOR_{pref}_SHARPE", get_color_class(metrics[acc]["sharpe"]))
    html_content = html_content.replace(f"VAR_{pref}_SHARPE", metrics[acc]["sharpe"])
    html_content = html_content.replace(f"VAR_COLOR_{pref}_PNL", get_color_class(metrics[acc]["pnl"]))
    html_content = html_content.replace(f"VAR_{pref}_PNL", metrics[acc]["pnl"])
    html_content = html_content.replace(f"VAR_{pref}_MAXDD", metrics[acc]["maxdd"])
    html_content = html_content.replace(f"VAR_{pref}_DD_DAYS", metrics[acc]["dd_days"])
    html_content = html_content.replace(f"VAR_{pref}_CALMAR", metrics[acc]["calmar"])
    html_content = html_content.replace(f"VAR_COLOR_{pref}_ROC", get_color_class(metrics[acc]["roc"]))
    html_content = html_content.replace(f"VAR_{pref}_ROC", metrics[acc]["roc"])
    html_content = html_content.replace(f"VAR_{pref}_NAV_FMT", f" USD {metrics[acc]['nav']:,.2f}")
    if pref != "ESTATE": html_content = html_content.replace(f"VAR_NAV_{pref}", str(round(metrics[acc]["nav"], 2)))

html_content = html_content.replace("'VAR_BENCH_DATES'", f"'{dates_js}'")
for tag, data in[("ESTATE_CUM", estate_js), ("SPY_CUM", spy_js), ("QQQ_CUM", qqq_js), ("SILOA_CUM", silo_a_js), ("SILOB_CUM", silo_b_js), ("SILOC_CUM", silo_c_js), ("SILOD_CUM", silo_d_js), ("DATES_PNL", dates_pnl_js), ("SILOA_PNL", silo_a_pnl), ("SILOB_PNL", silo_b_pnl), ("SILOC_PNL", silo_c_pnl), ("SILOD_PNL", silo_d_pnl), ("DATES_CUM_PNL", dates_cum_pnl_js), ("ESTATE_CUM_PNL", estate_cum_pnl_js), ("SPY_CUM_PNL", spy_cum_pnl_js), ("QQQ_CUM_PNL", qqq_cum_pnl_js)]:
    html_content = html_content.replace(f"'VAR_{tag}'", f"'{data}'")

html_content = html_content.replace("'VAR_REGIME_STATUS'", f"'{status_js}'").replace("'VAR_REGIME_TOR'", f"'{tor_js}'")
html_content = html_content.replace("'VAR_MC_VISUALS'", f"'{mc_visuals_js}'").replace("'VAR_MC_AVG'", f"'{mc_avg_js}'").replace("'VAR_MC_ORIG'", f"'{mc_orig_js}'").replace("'VAR_MC_STATS'", f"'{mc_stats_js}'")

for tag, val in[("SPY_ALPHA", spy_alpha_str), ("SPY_CORR", spy_corr_str), ("QQQ_ALPHA", qqq_alpha_str), ("QQQ_CORR", qqq_corr_str), ("SPY_SHARPE", spy_sharpe_str), ("QQQ_SHARPE", qqq_sharpe_str)]:
    html_content = html_content.replace(f"VAR_{tag}", val)

def load_json(f): return open(os.path.join(target_directory, f), 'r').read() if os.path.exists(os.path.join(target_directory, f)) else "{}"
html_content = html_content.replace("'VAR_LIVE_ALLOCATIONS'", f"'{load_json('Live_Allocations.json')}'")
html_content = html_content.replace("'VAR_SILOD_HOLDINGS'", f"'{load_json('Silo_D_Holdings.json')}'")
html_content = html_content.replace("'VAR_PROG_EXP'", f"'{load_json('Progressive_Exposure.json')}'")

vel_data = json.loads(load_json('Velocity_Metrics.json'))
html_content = html_content.replace("VAR_VEL_WINRATE", str(vel_data.get("win_rate", 0)))
html_content = html_content.replace("VAR_VEL_AVGDAYS", str(vel_data.get("avg_days", 0)))

for i in range(1, 6):
    html_content = html_content.replace(f"'VAR_ATTR_A{i}'", f"'{globals().get(f'attr_a{i}_js', '[]')}'")
    html_content = html_content.replace(f"VAR_TOTAL_A{i}", str(globals().get(f'total_a{i}', 0)))
html_content = html_content.replace("'VAR_ATTR_DATES'", f"'{attr_dates_js}'")

html_content = html_content.replace("VAR_SYNC_TIME", datetime.datetime.now().strftime("%B %d, %Y | %I:%M %p"))

try:
    with open(full_file_path, "w", encoding="utf-8") as f: f.write(html_content)
    print(f"SUCCESS! Estate Dashboard v66 created at: {full_file_path}")
except Exception as e: print(f"[ERROR] Saving File: {e}")