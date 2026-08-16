r"""
=============================================================================
Script Name: Generate_Estate_Dashboard_v21.py
Purpose: Generates the Interactive Family Estate Dashboard.
         VERSION 21 UPGRADES: 
         - Added "3. Daily PnL per Silo" Histogram (Full 1-Year Span).
         - Stacked bar chart colored by silo with vertically rotated, bottom-aligned PnL text.
         - Zero-line demarcation for Win/Loss visibility.
         - Renamed Master Instrument Matrix to Section 4.
Author: Chief Investment Officer AI Advisor
Date: April 2026
=============================================================================
"""

import os
import pandas as pd
import numpy as np

# ---------------------------------------------------------
# 1. Define Paths
# ---------------------------------------------------------
target_directory = r"C:\Users\donca\Desktop\Desktop HP Envy x360 al 22Abr24\Docs Manuel\IBKR_Options"
csv_file_path = os.path.join(target_directory, "IBKR_Daily_Data.csv")
spy_qqq_file_path = os.path.join(target_directory, "SPY_QQQ_Close.csv")
full_file_path = os.path.join(target_directory, "Family_Estate_Dashboard_v21.html")

if not os.path.exists(target_directory):
    os.makedirs(target_directory)

# ---------------------------------------------------------
# 2. The Quantitative Math Engine
# ---------------------------------------------------------
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
        return rate
    except:
        return 0.0

def process_metrics(df_acc):
    if df_acc.empty or len(df_acc) < 2:
        return "N/A", "N/A", "N/A", "N/A", "0", "N/A", "N/A", 0

    df_acc = df_acc.sort_values('Date').reset_index(drop=True)
    
    # --- Daily Returns ---
    df_acc['Prev_NAV'] = df_acc['NAV'].shift(1)
    df_acc['Daily_Return'] = (df_acc['NAV'] - df_acc['CashFlow'] - df_acc['Prev_NAV']) / df_acc['Prev_NAV']
    df_acc['Daily_Return'] = df_acc['Daily_Return'].replace([np.inf, -np.inf], np.nan).fillna(0)
    
    # --- Sharpe Ratio ---
    sharpe_str = "N/A"
    if df_acc['Daily_Return'].std() > 0:
        daily_rf = 0.045 / 252 
        excess_returns = df_acc['Daily_Return'] - daily_rf
        sharpe = np.sqrt(252) * (excess_returns.mean() / df_acc['Daily_Return'].std())
        sharpe_str = f"{sharpe:.2f}"
    
    # --- Total P&L (USD) ---
    total_deposits = df_acc['CashFlow'].sum()
    final_nav = df_acc['NAV'].iloc[-1]
    total_pnl = final_nav - total_deposits
    pnl_str = f"${total_pnl:,.2f}"
    
    # --- Max Drawdown & Duration ---
    df_acc['Cum_Return_Index'] = (1 + df_acc['Daily_Return']).cumprod()
    df_acc['Peak'] = df_acc['Cum_Return_Index'].cummax()
    df_acc['Drawdown'] = (df_acc['Cum_Return_Index'] - df_acc['Peak']) / df_acc['Peak'].replace(0, np.nan)
    max_dd = df_acc['Drawdown'].min() * 100
    max_dd_str = f"{max_dd:.2f}%"

    peak_date = df_acc['Date'].iloc[0]
    max_dd_days = 0
    for idx, row in df_acc.iterrows():
        if row['Cum_Return_Index'] >= row['Peak']:
            peak_date = row['Date']
        else:
            duration = (row['Date'] - peak_date).days
            if duration > max_dd_days: max_dd_days = duration
    
    # --- XIRR ---
    df_acc['IRR_CF'] = -df_acc['CashFlow']
    cfs = df_acc['IRR_CF'].tolist()
    dates = df_acc['Date'].tolist()
    cfs.append(final_nav)
    dates.append(dates[-1])
    dates_series = pd.to_datetime(pd.Series(dates))
    irr = calculate_xirr(dates_series, cfs)
    irr_str = f"{(irr * 100):.2f}%"

    # --- Calmar Ratio ---
    calmar_str = "N/A"
    if max_dd < 0:
        calmar = (irr * 100) / abs(max_dd)
        calmar_str = f"{calmar:.2f}"
    elif max_dd == 0 and irr > 0:
        calmar_str = "Inf"

    # --- ROC% (True Capital Employed) ---
    df_acc['Cum_CashFlow'] = df_acc['CashFlow'].cumsum()
    max_capital_employed = df_acc['Cum_CashFlow'].max()
    if max_capital_employed <= 0: max_capital_employed = df_acc['NAV'].max() - total_pnl
    if max_capital_employed > 0:
        roc = (total_pnl / max_capital_employed) * 100
        roc_str = f"{roc:.2f}%"
    else:
        roc_str = "N/A"

    return irr_str, sharpe_str, pnl_str, max_dd_str, str(max_dd_days), calmar_str, roc_str, final_nav

def get_color_class(val_str, theme="dark"):
    if "N/A" in val_str or "Awaiting" in val_str or "--" in val_str: 
        return "text-gray-400" if theme == "dark" else "text-gray-500"
    if "-" in val_str: 
        return "text-red-400" if theme == "dark" else "text-red-600"
    return "text-green-400" if theme == "dark" else "text-green-700"

# ---------------------------------------------------------
# 3. Read CSV and Calculate Individual & Global Metrics
# ---------------------------------------------------------
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

dates_js, estate_js, spy_js, qqq_js = [], [], [],[]
silo_a_js, silo_b_js, silo_c_js, silo_d_js = [], [], [],[]
dates_pnl_js, silo_a_pnl, silo_b_pnl, silo_c_pnl, silo_d_pnl = [], [], [], [],[]

if os.path.exists(csv_file_path):
    try:
        raw_df = pd.read_csv(csv_file_path)
        raw_df['Date'] = pd.to_datetime(raw_df['Date'].astype(str), format='%Y%m%d')
        
        # 3.a Calculate Individual Silos
        df_grouped = raw_df.groupby(['AccountID', 'Date']).agg({'NAV': 'last', 'CashFlow': 'sum'}).reset_index()
        for acc in["U23144948", "U23139264", "U23154199", "U25218481"]:
            acc_df = df_grouped[df_grouped['AccountID'] == acc].copy()
            i, s, p, m, d, c, r, n = process_metrics(acc_df)
            if n != 0: metrics[acc] = {"irr": i, "sharpe": s, "pnl": p, "maxdd": m, "dd_days": d, "calmar": c, "roc": r, "nav": n}
            
            # Save daily returns for benchmark parsing
            acc_df['Prev_NAV'] = acc_df['NAV'].shift(1)
            acc_df['Daily_Return'] = (acc_df['NAV'] - acc_df['CashFlow'] - acc_df['Prev_NAV']) / acc_df['Prev_NAV']
            acc_df['Daily_Return'] = acc_df['Daily_Return'].replace([np.inf, -np.inf], np.nan).fillna(0)
            silo_returns[acc] = acc_df[['Date', 'Daily_Return']].rename(columns={'Daily_Return': f'{acc}_Ret'})

        # 3.b Calculate Global Estate
        nav_pivot = raw_df.pivot_table(index='Date', columns='AccountID', values='NAV', aggfunc='last').ffill().fillna(0)
        cf_pivot = raw_df.pivot_table(index='Date', columns='AccountID', values='CashFlow', aggfunc='sum').fillna(0)
        
        global_df = pd.DataFrame({
            'Date': nav_pivot.index,
            'NAV': nav_pivot.sum(axis=1),
            'CashFlow': cf_pivot.sum(axis=1)
        }).reset_index(drop=True)

        i, s, p, m, d, c, r, n = process_metrics(global_df)
        metrics["ESTATE"] = {"irr": i, "sharpe": s, "pnl": p, "maxdd": m, "dd_days": d, "calmar": c, "roc": r, "nav": n}
        
        global_df['Prev_NAV'] = global_df['NAV'].shift(1)
        global_df['Daily_Return'] = (global_df['NAV'] - global_df['CashFlow'] - global_df['Prev_NAV']) / global_df['Prev_NAV']
        global_df['Daily_Return'] = global_df['Daily_Return'].replace([np.inf, -np.inf], np.nan).fillna(0)

        # 3.c Calculate Daily PnL Histogram Data (Full 1-Year Calendar)
        pnl_df = raw_df.groupby(['AccountID', 'Date']).agg({'NAV': 'last', 'CashFlow': 'sum'}).reset_index()
        pnl_df['Prev_NAV'] = pnl_df.groupby('AccountID')['NAV'].shift(1)
        pnl_df['Daily_PnL'] = pnl_df['NAV'] - pnl_df['CashFlow'] - pnl_df['Prev_NAV'].fillna(pnl_df['NAV'] - pnl_df['CashFlow'])
        pnl_df['Daily_PnL'] = pnl_df['Daily_PnL'].fillna(0).round(0)
        
        if not pnl_df.empty:
            min_date = pnl_df['Date'].min()
            # Generate exactly 1 year of business days
            full_dates = pd.bdate_range(start=min_date, end=min_date + pd.DateOffset(years=1))
            pnl_pivot = pnl_df.pivot(index='Date', columns='AccountID', values='Daily_PnL').reindex(full_dates).fillna(0)
            
            dates_pnl_js = pnl_pivot.index.strftime('%Y-%m-%d').tolist()
            silo_a_pnl = pnl_pivot['U23144948'].tolist() if 'U23144948' in pnl_pivot else [0]*len(full_dates)
            silo_b_pnl = pnl_pivot['U23139264'].tolist() if 'U23139264' in pnl_pivot else [0]*len(full_dates)
            silo_c_pnl = pnl_pivot['U23154199'].tolist() if 'U23154199' in pnl_pivot else[0]*len(full_dates)
            silo_d_pnl = pnl_pivot['U25218481'].tolist() if 'U25218481' in pnl_pivot else [0]*len(full_dates)

        print("Data successfully parsed. Global and Silo metrics calculated.")
    except Exception as e:
        print(f"Error parsing CSV: {e}")
else:
    print(f"Notice: CSV file not found at {csv_file_path}. Generating HTML with fallback values.")

# 3.d Benchmark Parsing & Integration (TWR Math for Estate + Individual Silos)
if os.path.exists(spy_qqq_file_path):
    try:
        bench_df = pd.read_csv(spy_qqq_file_path)
        bench_df['Date'] = pd.to_datetime(bench_df['Date'], format='%d-%b-%y')
    except Exception as e:
        print(f"Error parsing SPY/QQQ CSV: {e}")

if not bench_df.empty and not global_df.empty:
    overlap_dates = sorted(list(set(global_df['Date']).intersection(set(bench_df['Date']))))
    first_date = overlap_dates[0] if overlap_dates else None
    
    if first_date:
        master_bench = bench_df[bench_df['Date'] >= first_date].copy().reset_index(drop=True)
        master_bench['SPY_Ret'] = master_bench['SPY Close'].pct_change()
        master_bench['QQQ_Ret'] = master_bench['QQQ Close'].pct_change()
        master_bench.loc[0,['SPY_Ret', 'QQQ_Ret']] = 0.0
        
        # Merge Global Estate
        master_bench = pd.merge(master_bench, global_df[['Date', 'Daily_Return']].rename(columns={'Daily_Return': 'Estate_Ret'}), on='Date', how='left')
        
        # Merge Individual Silos
        for acc in["U23144948", "U23139264", "U23154199", "U25218481"]:
            if acc in silo_returns:
                master_bench = pd.merge(master_bench, silo_returns[acc], on='Date', how='left')
        
        # Isolate and clean the Return Columns
        ret_cols =['Estate_Ret', 'U23144948_Ret', 'U23139264_Ret', 'U23154199_Ret', 'U25218481_Ret']
        for c in ret_cols:
            if c not in master_bench.columns: master_bench[c] = 0.0
            
        master_bench[ret_cols] = master_bench[ret_cols].fillna(0)
        master_bench.loc[0, ret_cols] = 0.0  # Force zero start for fair race
        
        # Calculate Cumulatives
        for col in['SPY_Ret', 'QQQ_Ret'] + ret_cols:
            cum_col = col.replace('_Ret', '_Cum')
            master_bench[cum_col] = (1 + master_bench[col]).cumprod() - 1
            
        dates_js = master_bench['Date'].dt.strftime('%Y-%m-%d').tolist()
        spy_js = (master_bench['SPY_Cum'] * 100).round(2).tolist()
        qqq_js = (master_bench['QQQ_Cum'] * 100).round(2).tolist()
        estate_js = (master_bench['Estate_Cum'] * 100).round(2).tolist()
        
        silo_a_js = (master_bench['U23144948_Cum'] * 100).round(2).tolist()
        silo_b_js = (master_bench['U23139264_Cum'] * 100).round(2).tolist()
        silo_c_js = (master_bench['U23154199_Cum'] * 100).round(2).tolist()
        silo_d_js = (master_bench['U25218481_Cum'] * 100).round(2).tolist()

# ---------------------------------------------------------
# 4. Define HTML Payload
# ---------------------------------------------------------
html_content = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Family Estate Master Allocator v21</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <script src="https://cdn.plot.ly/plotly-2.24.1.min.js"></script>
    <style>
        .splendid { background-color: #dcfce7; color: #166534; font-weight: bold;}
        .great { background-color: #ecfccb; color: #15803d; font-weight: bold;}
        .good { background-color: #fef9c3; color: #4d7c0f; font-weight: bold;}
        .bad { background-color: #ffedd5; color: #b91c1c; font-weight: bold;}
        .avoid { background-color: #fecaca; color: #991b1b; font-weight: bold;}
        input[type=range] { height: 6px; accent-color: #3b82f6; }
    </style>
</head>
<body class="bg-slate-50 text-gray-800 font-sans p-4 md:p-6">

    <!-- WIDE LANDSCAPE CONTAINER -->
    <div class="max-w-[98%] 2xl:max-w-[2400px] mx-auto bg-white rounded-xl shadow-xl p-6 border border-gray-200">
        
        <div class="text-center mb-8">
            <h1 class="text-4xl font-extrabold text-gray-900 tracking-tight">Family Estate Master Dashboard</h1>
            <p class="text-gray-500 mt-2 font-medium">Silo Allocation & Institutional Data Engine v21</p>
        </div>

        <!-- 12-COLUMN LANDSCAPE GRID -->
        <div class="grid grid-cols-1 xl:grid-cols-12 gap-8">
            
            <!-- LEFT COLUMN: Operations & Performance (6 Columns wide) -->
            <div class="xl:col-span-6 flex flex-col gap-6">
                
                <!-- MASTER ESTATE AGGREGATION HEADER -->
                <div class="bg-gray-100 p-4 rounded-xl shadow-md text-center border border-gray-300">
                    <h4 class="text-lg text-gray-800 uppercase tracking-widest font-black">Master Estate Aggregation</h4>
                    <div class="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-8 gap-4 text-sm mt-3 border-t border-gray-300 pt-3 font-mono">
                        <div>Static Balance<br><span class="text-blue-700 font-black text-lg">VAR_ESTATE_NAV_FMT</span></div>
                        <div>IRR<br><span class="VAR_COLOR_ESTATE_IRR font-black text-lg">VAR_ESTATE_IRR</span></div>
                        <div>Global P&L<br><span class="VAR_COLOR_ESTATE_PNL font-black text-lg">VAR_ESTATE_PNL</span></div>
                        <div>Global Sharpe<br><span class="VAR_COLOR_ESTATE_SHARPE font-black text-lg">VAR_ESTATE_SHARPE</span></div>
                        <div>Max DD<br><span class="text-red-500 font-black text-lg">VAR_ESTATE_MAXDD</span></div>
                        <div>DD Duration<br><span class="text-gray-600 font-black text-lg">VAR_ESTATE_DD_DAYS d</span></div>
                        <div>Calmar<br><span class="text-gray-600 font-black text-lg">VAR_ESTATE_CALMAR</span></div>
                        <div>Est. ROC%<br><span class="VAR_COLOR_ESTATE_ROC font-black text-lg">VAR_ESTATE_ROC</span></div>
                    </div>
                </div>

                <!-- GLOBAL BENCHMARK CHART -->
                <div class="bg-gray-100 p-4 rounded-xl shadow-md border border-gray-300">
                    <h4 class="text-sm text-gray-800 uppercase tracking-widest font-black text-center mb-2">Estate vs Benchmarks (Cumulative Return %)</h4>
                    <div id="benchmark-chart" class="w-full h-[250px]"></div>
                </div>

                <!-- INDIVIDUAL SILOS (Charts + Headers locked in columns) -->
                <div class="grid grid-cols-1 sm:grid-cols-2 2xl:grid-cols-4 gap-4">
                    
                    <!-- SILO A COLUMN -->
                    <div class="flex flex-col gap-3">
                        <div class="bg-blue-50 border border-blue-200 rounded-xl p-2 h-[160px] shadow-sm relative">
                            <span class="absolute top-1 left-2 text-[10px] font-bold text-gray-500 uppercase z-10">Silo A vs Benchmarks</span>
                            <div id="chart-silo-a" class="w-full h-full"></div>
                        </div>
                        <div class="bg-blue-900 text-white p-4 rounded-xl shadow-md text-center border-b-4 border-blue-500 flex-grow">
                            <h4 class="text-sm text-blue-200 uppercase tracking-widest font-bold mb-1">Silo A</h4>
                            <p class="text-xs mb-1 text-gray-400">Persons 1 and 2 &bull; U*****948</p>
                            <div class="bg-blue-950 rounded py-1 mb-2 border border-blue-800"><p class="text-sm font-bold text-blue-100">Bal: VAR_A_NAV_FMT</p></div>
                            <div class="grid grid-cols-2 text-xs mt-3 border-t border-blue-700 pt-3 gap-y-2 font-mono">
                                <div class="text-left">IRR: <span class="VAR_COLOR_A_IRR font-bold">VAR_A_IRR</span></div>
                                <div class="text-right">Sharpe: <span class="VAR_COLOR_A_SHARPE font-bold">VAR_A_SHARPE</span></div>
                                <div class="text-left">P&L: <span class="VAR_COLOR_A_PNL font-bold">VAR_A_PNL</span></div>
                                <div class="text-right">Max DD: <span class="text-red-400 font-bold">VAR_A_MAXDD</span></div>
                                <div class="text-left">DD Days: <span class="text-gray-300 font-bold">VAR_A_DD_DAYS</span></div>
                                <div class="text-right">Calmar: <span class="text-gray-300 font-bold">VAR_A_CALMAR</span></div>
                                <div class="text-center col-span-2 mt-1">ROC%: <span class="VAR_COLOR_A_ROC font-bold">VAR_A_ROC</span></div>
                            </div>
                        </div>
                    </div>

                    <!-- SILO B COLUMN -->
                    <div class="flex flex-col gap-3">
                        <div class="bg-purple-50 border border-purple-200 rounded-xl p-2 h-[160px] shadow-sm relative">
                            <span class="absolute top-1 left-2 text-[10px] font-bold text-gray-500 uppercase z-10">Silo B vs Benchmarks</span>
                            <div id="chart-silo-b" class="w-full h-full"></div>
                        </div>
                        <div class="bg-purple-900 text-white p-4 rounded-xl shadow-md text-center border-b-4 border-purple-500 flex-grow">
                            <h4 class="text-sm text-purple-200 uppercase tracking-widest font-bold mb-1">Silo B</h4>
                            <p class="text-xs mb-1 text-gray-400">Persons 1 and 2 &bull; U*****264</p>
                            <div class="bg-purple-950 rounded py-1 mb-2 border border-purple-800"><p class="text-sm font-bold text-purple-100">Bal: VAR_B_NAV_FMT</p></div>
                            <div class="grid grid-cols-2 text-xs mt-3 border-t border-purple-700 pt-3 gap-y-2 font-mono">
                                <div class="text-left">IRR: <span class="VAR_COLOR_B_IRR font-bold">VAR_B_IRR</span></div>
                                <div class="text-right">Sharpe: <span class="VAR_COLOR_B_SHARPE font-bold">VAR_B_SHARPE</span></div>
                                <div class="text-left">P&L: <span class="VAR_COLOR_B_PNL font-bold">VAR_B_PNL</span></div>
                                <div class="text-right">Max DD: <span class="text-red-400 font-bold">VAR_B_MAXDD</span></div>
                                <div class="text-left">DD Days: <span class="text-gray-300 font-bold">VAR_B_DD_DAYS</span></div>
                                <div class="text-right">Calmar: <span class="text-gray-300 font-bold">VAR_B_CALMAR</span></div>
                                <div class="text-center col-span-2 mt-1">ROC%: <span class="VAR_COLOR_B_ROC font-bold">VAR_B_ROC</span></div>
                            </div>
                        </div>
                    </div>

                    <!-- SILO C COLUMN -->
                    <div class="flex flex-col gap-3">
                        <div class="bg-green-50 border border-green-200 rounded-xl p-2 h-[160px] shadow-sm relative">
                            <span class="absolute top-1 left-2 text-[10px] font-bold text-gray-500 uppercase z-10">Silo C vs Benchmarks</span>
                            <div id="chart-silo-c" class="w-full h-full"></div>
                        </div>
                        <div class="bg-green-900 text-white p-4 rounded-xl shadow-md text-center border-b-4 border-green-500 flex-grow">
                            <h4 class="text-sm text-green-200 uppercase tracking-widest font-bold mb-1">Silo C</h4>
                            <p class="text-xs mb-1 text-gray-400">Persons 1 and 3 &bull; U*****199</p>
                            <div class="bg-green-950 rounded py-1 mb-2 border border-green-800"><p class="text-sm font-bold text-green-100">Bal: VAR_C_NAV_FMT</p></div>
                            <div class="grid grid-cols-2 text-xs mt-3 border-t border-green-700 pt-3 gap-y-2 font-mono">
                                <div class="text-left">IRR: <span class="VAR_COLOR_C_IRR font-bold">VAR_C_IRR</span></div>
                                <div class="text-right">Sharpe: <span class="VAR_COLOR_C_SHARPE font-bold">VAR_C_SHARPE</span></div>
                                <div class="text-left">P&L: <span class="VAR_COLOR_C_PNL font-bold">VAR_C_PNL</span></div>
                                <div class="text-right">Max DD: <span class="text-red-400 font-bold">VAR_C_MAXDD</span></div>
                                <div class="text-left">DD Days: <span class="text-gray-300 font-bold">VAR_C_DD_DAYS</span></div>
                                <div class="text-right">Calmar: <span class="text-gray-300 font-bold">VAR_C_CALMAR</span></div>
                                <div class="text-center col-span-2 mt-1">ROC%: <span class="VAR_COLOR_C_ROC font-bold">VAR_C_ROC</span></div>
                            </div>
                        </div>
                    </div>

                    <!-- SILO D COLUMN -->
                    <div class="flex flex-col gap-3">
                        <div class="bg-yellow-100 border border-yellow-300 rounded-xl p-2 h-[160px] shadow-sm relative">
                            <span class="absolute top-1 left-2 text-[10px] font-bold text-gray-600 uppercase z-10">Silo D vs Benchmarks</span>
                            <div id="chart-silo-d" class="w-full h-full"></div>
                        </div>
                        <div class="bg-yellow-200 text-gray-900 p-4 rounded-xl shadow-md text-center border-b-4 border-yellow-400 flex-grow">
                            <h4 class="text-sm text-yellow-800 uppercase tracking-widest font-bold mb-1">Silo D</h4>
                            <p class="text-xs mb-1 text-gray-600">Persons 1 and 4 &bull; U*****481</p>
                            <div class="bg-yellow-300 rounded py-1 mb-2 border border-yellow-400"><p class="text-sm font-bold text-yellow-900">Bal: VAR_D_NAV_FMT</p></div>
                            <div class="grid grid-cols-2 text-xs mt-3 border-t border-yellow-400 pt-3 gap-y-2 font-mono">
                                <div class="text-left">IRR: <span class="VAR_COLOR_D_IRR font-bold">VAR_D_IRR</span></div>
                                <div class="text-right">Sharpe: <span class="VAR_COLOR_D_SHARPE font-bold">VAR_D_SHARPE</span></div>
                                <div class="text-left">P&L: <span class="VAR_COLOR_D_PNL font-bold">VAR_D_PNL</span></div>
                                <div class="text-right">Max DD: <span class="text-red-600 font-bold">VAR_D_MAXDD</span></div>
                                <div class="text-left">DD Days: <span class="text-gray-600 font-bold">VAR_D_DD_DAYS</span></div>
                                <div class="text-right">Calmar: <span class="text-gray-600 font-bold">VAR_D_CALMAR</span></div>
                                <div class="text-center col-span-2 mt-1">ROC%: <span class="VAR_COLOR_D_ROC font-bold">VAR_D_ROC</span></div>
                            </div>
                        </div>
                    </div>
                </div>

                <!-- SILO INPUTS (Estate Capital) -->
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

            <!-- RIGHT COLUMN: Visuals & Target Composition (6 Columns wide) -->
            <div class="xl:col-span-6 flex flex-col gap-6">
                
                <!-- Bar & Pie Charts Side-by-Side -->
                <div class="grid grid-cols-1 lg:grid-cols-2 gap-4">
                    <div class="bg-white border rounded-xl p-4 shadow-sm"><div id="bar-chart" class="w-full h-[400px]"></div></div>
                    <div class="bg-white border rounded-xl p-4 shadow-sm"><div id="pie-chart" class="w-full h-[400px]"></div></div>
                </div>
                
                <!-- TARGET ALLOCATION SLIDERS -->
                <div class="bg-white p-4 rounded-xl border shadow-sm flex-grow">
                    <h3 class="text-xl font-bold mb-2 text-gray-800">2. Target Portfolio Composition (%)</h3>
                    <p class="text-sm text-gray-500 mb-4 border-b pb-2">Set current options exposure to 0 to eliminate liabilities. Assets must mathematically equal 100%.</p>
                    
                    <div class="grid grid-cols-1 lg:grid-cols-4 gap-4">
                        
                        <!-- Silo A -->
                        <div class="bg-blue-50 p-3 rounded-lg border border-blue-200 shadow-inner">
                            <h4 class="font-bold text-blue-900 mb-2 text-sm border-b border-blue-200 pb-1">Silo A</h4>
                            <p class="text-[10px] font-bold text-gray-500 mb-1 uppercase tracking-wide">Physical Balance Sheet</p>
                            <label class="text-xs font-semibold" id="a_ib01_label">IB01: </label><input type="range" id="a_ib01" min="0" max="100" step="0.01" value="100.0" class="w-full mb-1" oninput="updateUI()">
                            <label class="text-xs font-semibold" id="a_cspx_label">CSPX: </label><input type="range" id="a_cspx" min="0" max="100" step="0.01" value="0.0" class="w-full mb-1" oninput="updateUI()">
                            <label class="text-xs font-semibold" id="a_cndx_label">CNDX: </label><input type="range" id="a_cndx" min="0" max="100" step="0.01" value="0.0" class="w-full mb-1" oninput="updateUI()">
                            <label class="text-xs font-semibold" id="a_crypto_label">Crypto ETPs: </label><input type="range" id="a_crypto" min="0" max="100" step="0.01" value="0.0" class="w-full mb-1" oninput="updateUI()">
                            <label class="text-xs font-semibold" id="a_cash_label">Cash: </label><input type="range" id="a_cash" min="-50" max="100" step="0.01" value="0.0" class="w-full mb-1" oninput="updateUI()">
                            
                            <label class="text-xs font-bold text-red-700" id="a_opt_mkt_label">Opt. Mkt Val (Liability): </label><input type="range" id="a_opt_mkt" min="-20" max="0" step="0.01" value="0.0" class="w-full mb-1" oninput="updateUI()">
                            <p class="text-[10px] text-red-600 font-bold mt-1 h-4" id="a_warning"></p>
                            
                            <p class="text-[10px] font-bold text-gray-500 mt-2 mb-1 uppercase tracking-wide border-t border-blue-200 pt-2">Margin Overlay</p>
                            <label class="text-xs font-semibold text-green-700" id="a_xsp_label">Options Margin: </label><input type="range" id="a_xsp" min="0" max="100" step="0.01" value="0.0" class="w-full mb-1" oninput="updateUI()">
                        </div>

                        <!-- Silo B -->
                        <div class="bg-purple-50 p-3 rounded-lg border border-purple-200 shadow-inner">
                            <h4 class="font-bold text-purple-900 mb-2 text-sm border-b border-purple-200 pb-1">Silo B</h4>
                            <p class="text-[10px] font-bold text-gray-500 mb-1 uppercase tracking-wide">Physical Balance Sheet</p>
                            <label class="text-xs font-semibold" id="b_ib01_label">IB01: </label><input type="range" id="b_ib01" min="0" max="100" step="0.01" value="41.15" class="w-full mb-1" oninput="updateUI()">
                            <label class="text-xs font-semibold" id="b_cash_label">Cash: </label><input type="range" id="b_cash" min="-50" max="100" step="0.01" value="58.85" class="w-full mb-1" oninput="updateUI()">
                            <label class="text-xs font-semibold" id="b_cfd_label">CFDs: </label><input type="range" id="b_cfd" min="0" max="100" step="0.01" value="0.0" class="w-full mb-1" oninput="updateUI()">
                            <label class="text-xs font-semibold" id="b_intl_label">Intl Stocks: </label><input type="range" id="b_intl" min="0" max="100" step="0.01" value="0.0" class="w-full mb-1" oninput="updateUI()">
                            <p class="text-[10px] text-red-600 font-bold mt-1 h-4" id="b_warning"></p>
                        </div>

                        <!-- Silo C -->
                        <div class="bg-green-50 p-3 rounded-lg border border-green-200 shadow-inner">
                            <h4 class="font-bold text-green-900 mb-2 text-sm border-b border-green-200 pb-1">Silo C</h4>
                            <p class="text-[10px] font-bold text-gray-500 mb-1 uppercase tracking-wide">Physical Balance Sheet</p>
                            <label class="text-xs font-semibold" id="c_ib01_label">IB01: </label><input type="range" id="c_ib01" min="0" max="100" step="0.01" value="100.0" class="w-full mb-1" oninput="updateUI()">
                            <label class="text-xs font-semibold" id="c_cspx_label">CSPX: </label><input type="range" id="c_cspx" min="0" max="100" step="0.01" value="0.0" class="w-full mb-1" oninput="updateUI()">
                            <label class="text-xs font-semibold" id="c_cndx_label">CNDX: </label><input type="range" id="c_cndx" min="0" max="100" step="0.01" value="0.0" class="w-full mb-1" oninput="updateUI()">
                            <label class="text-xs font-semibold" id="c_crypto_label">Crypto ETPs: </label><input type="range" id="c_crypto" min="0" max="100" step="0.01" value="0.0" class="w-full mb-1" oninput="updateUI()">
                            <label class="text-xs font-semibold" id="c_cash_label">Cash: </label><input type="range" id="c_cash" min="-50" max="100" step="0.01" value="0.0" class="w-full mb-1" oninput="updateUI()">
                            
                            <label class="text-xs font-bold text-red-700" id="c_opt_mkt_label">Opt. Mkt Val (Liability): </label><input type="range" id="c_opt_mkt" min="-20" max="0" step="0.01" value="0.0" class="w-full mb-1" oninput="updateUI()">
                            <p class="text-[10px] text-red-600 font-bold mt-1 h-4" id="c_warning"></p>

                            <p class="text-[10px] font-bold text-gray-500 mt-2 mb-1 uppercase tracking-wide border-t border-green-200 pt-2">Margin Overlay</p>
                            <label class="text-xs font-semibold text-green-700" id="c_xsp_label">Options Margin: </label><input type="range" id="c_xsp" min="0" max="100" step="0.01" value="0.0" class="w-full mb-1" oninput="updateUI()">
                        </div>

                        <!-- Silo D -->
                        <div class="bg-yellow-100 p-3 rounded-lg border border-yellow-400 shadow-inner">
                            <h4 class="font-bold text-yellow-900 mb-2 text-sm border-b border-yellow-400 pb-1">Silo D</h4>
                            <p class="text-[10px] font-bold text-gray-600 mb-1 uppercase tracking-wide">Physical Balance Sheet</p>
                            <label class="text-xs font-semibold text-gray-900" id="d_ib01_label">IB01: </label><input type="range" id="d_ib01" min="0" max="100" step="0.01" value="40.0" class="w-full mb-1" oninput="updateUI()">
                            <label class="text-xs font-semibold text-gray-900" id="d_cspx_label">CSPX: </label><input type="range" id="d_cspx" min="0" max="100" step="0.01" value="30.0" class="w-full mb-1" oninput="updateUI()">
                            <label class="text-xs font-semibold text-gray-900" id="d_cndx_label">CNDX: </label><input type="range" id="d_cndx" min="0" max="100" step="0.01" value="15.0" class="w-full mb-1" oninput="updateUI()">
                            <label class="text-xs font-semibold text-gray-900" id="d_crypto_label">Crypto ETPs: </label><input type="range" id="d_crypto" min="0" max="100" step="0.01" value="5.0" class="w-full mb-1" oninput="updateUI()">
                            <label class="text-xs font-semibold text-gray-900" id="d_cash_label">Cash: </label><input type="range" id="d_cash" min="-50" max="100" step="0.01" value="10.0" class="w-full mb-1" oninput="updateUI()">
                            <p class="text-[10px] text-red-600 font-bold mt-1 h-4" id="d_warning"></p>
                        </div>
                    </div>
                </div>

            </div>

            <!-- NEW DAILY PNL HISTOGRAM (12 Columns wide) -->
            <div class="xl:col-span-12 mt-2">
                <div class="bg-white border rounded-xl p-4 shadow-sm overflow-hidden">
                    <h3 class="text-xl font-bold mb-4 text-gray-800 border-b pb-2">3. Daily PnL per Silo</h3>
                    <div id="daily-pnl-chart" class="w-full h-[400px]"></div>
                </div>
            </div>

            <!-- BOTTOM ROW: The Matrix (12 Columns wide) -->
            <div class="xl:col-span-12 mt-2">
                <div class="bg-white border rounded-xl p-4 shadow-sm overflow-x-auto">
                    <h3 class="text-xl font-bold mb-4 text-gray-800 border-b pb-2">4. The Master Instrument Matrix (Tax, Alpha, & Sharpe Grading)</h3>
                    <table class="min-w-full bg-white text-[12px] whitespace-nowrap">
                        <thead class="bg-slate-800 text-white">
                            <tr>
                                <th class="py-3 px-3 text-left">Instrument</th>
                                <th class="py-3 px-3 text-left">Type</th>
                                <th class="py-3 px-3 text-left">Risk Profile</th>
                                <th class="py-3 px-3 text-left">Alpha Potential</th>
                                <th class="py-3 px-3 text-left">Sharpe / Vol Impact</th>
                                <th class="py-3 px-3 text-left">Trading Strategy</th>
                                <th class="py-3 px-3 text-left">Jurisdiction</th>
                                <th class="py-3 px-3 text-center">CIO Min<br>Alloc. %</th>
                                <th class="py-3 px-3 text-center">CIO Max<br>Alloc. %</th>
                                <th class="py-3 px-3 text-center">CIO<br>Grading</th>
                                <th class="py-3 px-3 text-left w-1/4">Noteworthy Comments</th>
                            </tr>
                        </thead>
                        <tbody class="divide-y divide-gray-200 whitespace-normal" id="matrix-body">
                        </tbody>
                    </table>
                </div>
            </div>

        </div>
    </div>

    <script>
        function fmtCur(val) { return ' USD ' + Math.round(val).toLocaleString('en-US'); }
        
        const palette = {
            ib01: '#0284c7', cspx: '#f97316', cndx: '#8b5cf6', 
            cash: '#64748b', cfd_intl: '#a855f7', optMktVal: '#ef4444', crypto: '#0ea5e9'
        };

        const instruments =[
            { inst: "USD Cash", type: "Currency", risk: "Risk-Free", alpha: "Zero", sharpe: "Stabilizer", strat: "Liquidity", jur: "US (IBKR)", min: "1%", max: "100%", rec: "Splendid", class: "splendid", comm: "Uninvested USD held in IBKR. Mandatory margin collateral." },
            { inst: "XSP Put Spreads", type: "Index Option", risk: "Moderate", alpha: "High (VRP)", sharpe: "High", strat: "Weekly Income", jur: "US (Cboe)", min: "0%", max: "25%", rec: "Splendid", class: "splendid", comm: "Cash-settled S&P 500 options. 100% safe from IRS." },
            { inst: "XND Put Spreads", type: "Index Option", risk: "Mod/High", alpha: "High", sharpe: "Moderate", strat: "Satellite Income", jur: "US (Cboe)", min: "0%", max: "10%", rec: "Great", class: "great", comm: "Micro-Nasdaq 100. Cash-settled. IRS Safe. Higher volatility than XSP." },
            { inst: "IB01", type: "UCITS ETF", risk: "Risk-Free", alpha: "Zero", sharpe: "High", strat: "Collateral", jur: "Ireland", min: "10%", max: "100%", rec: "Splendid", class: "splendid", comm: "Irish-domiciled short-term US Treasury fund. Accumulates ~4.5% tax-free." },
            { inst: "CSPX", type: "UCITS ETF", risk: "Moderate", alpha: "Zero", sharpe: "Baseline", strat: "Long Term", jur: "Ireland", min: "0%", max: "60%", rec: "Great", class: "great", comm: "Irish-domiciled S&P 500. Shields against 40% Estate Tax." },
            { inst: "CNDX", type: "UCITS ETF", risk: "Aggressive", alpha: "High", sharpe: "Moderate", strat: "Long Term", jur: "Ireland", min: "0%", max: "40%", rec: "Great", class: "great", comm: "Irish-domiciled Nasdaq 100. Shields against 40% Estate Tax. High beta tech exposure." },
            { inst: "BTC/ETH ETPs", type: "Crypto ETP", risk: "Aggressive", alpha: "High", sharpe: "Volatile", strat: "Uncorrelated", jur: "Europe (Jersey/CH)", min: "0%", max: "5%", rec: "Good", class: "good", comm: "Offshore crypto wrappers (e.g. CoinShares). IRS safe spot exposure." },
            { inst: "US Tech CFDs", type: "OTC Contract", risk: "Aggressive", alpha: "High", sharpe: "Negative", strat: "Swing Trading", jur: "UK/Offshore", min: "0%", max: "3%", rec: "Good", class: "good", comm: "Synthetic derivatives. 0% IRS risk. Quarantined to Silo B." },
            { inst: "XSP LEAPS", type: "Index Option", risk: "Aggressive", alpha: "Low", sharpe: "Negative", strat: "Leverage", jur: "US (Cboe)", min: "0%", max: "0%", rec: "Bad", class: "bad", comm: "IRS safe, but mathematical drag of Theta and lost dividends destroys edge." },
            { inst: "Physical US Stocks", type: "Stock", risk: "Extreme", alpha: "High", sharpe: "Baseline", strat: "Swing", jur: "US", min: "0%", max: "0%", rec: "Avoid", class: "avoid", comm: "LETHAL. Triggers 40% US Estate Tax and 30% Dividend Withholding." },
            { inst: "US Spot BTC/ETH", type: "US ETF", risk: "Extreme", alpha: "N/A", sharpe: "N/A", strat: "N/A", jur: "US", min: "0%", max: "0%", rec: "Avoid", class: "avoid", comm: "LETHAL. Standard ETFs (IBIT/FBTC) are US-situs property. Will trigger Estate Tax confiscation." },
            { inst: "TQQQ", type: "Physical ETF", risk: "Extreme", alpha: "Negative", sharpe: "Negative", strat: "Speculation", jur: "US", min: "0%", max: "0%", rec: "Avoid", class: "avoid", comm: "LETHAL. Widow-maker. Combines IRS Tax Trap with massive Beta Slippage decay." }
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
                    <td class="py-2 px-3 font-bold text-center text-gray-500">${i.min}</td>
                    <td class="py-2 px-3 font-bold text-center">${i.max}</td>
                    <td class="py-2 px-3 ${i.class} text-center rounded shadow-sm">${i.rec}</td>
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
            const totalEstate = sA + sB + sC + sD;

            // Silo A
            let a_ib01 = parseFloat(document.getElementById('a_ib01').value); let a_cspx = parseFloat(document.getElementById('a_cspx').value);
            let a_cndx = parseFloat(document.getElementById('a_cndx').value); 
            let a_crypto = parseFloat(document.getElementById('a_crypto').value); let a_cash = parseFloat(document.getElementById('a_cash').value); 
            let a_opt_mkt = parseFloat(document.getElementById('a_opt_mkt').value);
            
            let a_tot = a_ib01 + a_cspx + a_cndx + a_crypto + a_cash + a_opt_mkt;
            document.getElementById('a_warning').innerText = Math.abs(a_tot - 100) > 0.05 ? `Balance: ${a_tot.toFixed(2)}%. Must = 100%!` : "";
            
            let a_xsp = parseFloat(document.getElementById('a_xsp').value);
            const amt_A_ib01 = sA * (a_ib01/100); const amt_A_cspx = sA * (a_cspx/100); const amt_A_cndx = sA * (a_cndx/100); 
            const amt_A_crypto = sA * (a_crypto/100); const amt_A_cash = sA * (a_cash/100); 
            const amt_A_opt_mkt = sA * (a_opt_mkt/100); const amt_A_xsp = sA * (a_xsp/100);
            
            document.getElementById('a_ib01_label').innerText = `IB01: ${fmtCur(amt_A_ib01)} (${a_ib01.toFixed(2)}%)`;
            document.getElementById('a_cspx_label').innerText = `CSPX: ${fmtCur(amt_A_cspx)} (${a_cspx.toFixed(2)}%)`;
            document.getElementById('a_cndx_label').innerText = `CNDX: ${fmtCur(amt_A_cndx)} (${a_cndx.toFixed(2)}%)`;
            document.getElementById('a_crypto_label').innerText = `Crypto ETPs: ${fmtCur(amt_A_crypto)} (${a_crypto.toFixed(2)}%)`;
            document.getElementById('a_cash_label').innerText = `Cash: ${fmtCur(amt_A_cash)} (${a_cash.toFixed(2)}%)`;
            document.getElementById('a_opt_mkt_label').innerText = `Options Mkt Val (Liability): ${fmtCur(amt_A_opt_mkt)} (${a_opt_mkt.toFixed(2)}%)`;
            document.getElementById('a_xsp_label').innerText  = `Options Margin: ${fmtCur(amt_A_xsp)} (${a_xsp.toFixed(2)}%)`;

            // Silo B
            let b_ib01 = parseFloat(document.getElementById('b_ib01').value); let b_cash = parseFloat(document.getElementById('b_cash').value); 
            let b_cfd = parseFloat(document.getElementById('b_cfd').value);   let b_intl = parseFloat(document.getElementById('b_intl').value);
            let b_tot = b_ib01 + b_cash + b_cfd + b_intl;
            document.getElementById('b_warning').innerText = Math.abs(b_tot - 100) > 0.05 ? `Balance: ${b_tot.toFixed(2)}%. Must = 100%!` : "";
            
            const amt_B_ib01 = sB * (b_ib01/100); const amt_B_cash = sB * (b_cash/100);
            const amt_B_cfd  = sB * (b_cfd/100);  const amt_B_intl = sB * (b_intl/100);
            const amt_B_act  = amt_B_cfd + amt_B_intl;

            document.getElementById('b_ib01_label').innerText = `IB01: ${fmtCur(amt_B_ib01)} (${b_ib01.toFixed(2)}%)`;
            document.getElementById('b_cash_label').innerText = `Cash: ${fmtCur(amt_B_cash)} (${b_cash.toFixed(2)}%)`;
            document.getElementById('b_cfd_label').innerText  = `CFDs: ${fmtCur(amt_B_cfd)} (${b_cfd.toFixed(2)}%)`;
            document.getElementById('b_intl_label').innerText = `Intl Stocks: ${fmtCur(amt_B_intl)} (${b_intl.toFixed(2)}%)`;

            // Silo C
            let c_ib01 = parseFloat(document.getElementById('c_ib01').value); let c_cspx = parseFloat(document.getElementById('c_cspx').value);
            let c_cndx = parseFloat(document.getElementById('c_cndx').value); 
            let c_crypto = parseFloat(document.getElementById('c_crypto').value); let c_cash = parseFloat(document.getElementById('c_cash').value); 
            let c_opt_mkt = parseFloat(document.getElementById('c_opt_mkt').value);
            
            let c_tot = c_ib01 + c_cspx + c_cndx + c_crypto + c_cash + c_opt_mkt;
            document.getElementById('c_warning').innerText = Math.abs(c_tot - 100) > 0.05 ? `Balance: ${c_tot.toFixed(2)}%. Must = 100%!` : "";
            
            let c_xsp = parseFloat(document.getElementById('c_xsp').value);
            const amt_C_ib01 = sC * (c_ib01/100); const amt_C_cspx = sC * (c_cspx/100); const amt_C_cndx = sC * (c_cndx/100); 
            const amt_C_crypto = sC * (c_crypto/100); const amt_C_cash = sC * (c_cash/100); 
            const amt_C_opt_mkt = sC * (c_opt_mkt/100); const amt_C_xsp  = sC * (c_xsp/100);
            
            document.getElementById('c_ib01_label').innerText = `IB01: ${fmtCur(amt_C_ib01)} (${c_ib01.toFixed(2)}%)`;
            document.getElementById('c_cspx_label').innerText = `CSPX: ${fmtCur(amt_C_cspx)} (${c_cspx.toFixed(2)}%)`;
            document.getElementById('c_cndx_label').innerText = `CNDX: ${fmtCur(amt_C_cndx)} (${c_cndx.toFixed(2)}%)`;
            document.getElementById('c_crypto_label').innerText = `Crypto ETPs: ${fmtCur(amt_C_crypto)} (${c_crypto.toFixed(2)}%)`;
            document.getElementById('c_cash_label').innerText = `Cash: ${fmtCur(amt_C_cash)} (${c_cash.toFixed(2)}%)`;
            document.getElementById('c_opt_mkt_label').innerText = `Options Mkt Val (Liability): ${fmtCur(amt_C_opt_mkt)} (${c_opt_mkt.toFixed(2)}%)`;
            document.getElementById('c_xsp_label').innerText  = `Options Margin: ${fmtCur(amt_C_xsp)} (${c_xsp.toFixed(2)}%)`;

            // Silo D
            let d_ib01 = parseFloat(document.getElementById('d_ib01').value); let d_cspx = parseFloat(document.getElementById('d_cspx').value);
            let d_cndx = parseFloat(document.getElementById('d_cndx').value); 
            let d_crypto = parseFloat(document.getElementById('d_crypto').value); let d_cash = parseFloat(document.getElementById('d_cash').value);
            
            let d_tot = d_ib01 + d_cspx + d_cndx + d_crypto + d_cash;
            document.getElementById('d_warning').innerText = Math.abs(d_tot - 100) > 0.05 ? `Balance: ${d_tot.toFixed(2)}%. Must = 100%!` : "";
            
            const amt_D_ib01 = sD * (d_ib01/100); const amt_D_cspx = sD * (d_cspx/100); const amt_D_cndx = sD * (d_cndx/100); 
            const amt_D_crypto = sD * (d_crypto/100); const amt_D_cash = sD * (d_cash/100);

            document.getElementById('d_ib01_label').innerText = `IB01: ${fmtCur(amt_D_ib01)} (${d_ib01.toFixed(2)}%)`;
            document.getElementById('d_cspx_label').innerText = `CSPX: ${fmtCur(amt_D_cspx)} (${d_cspx.toFixed(2)}%)`;
            document.getElementById('d_cndx_label').innerText = `CNDX: ${fmtCur(amt_D_cndx)} (${d_cndx.toFixed(2)}%)`;
            document.getElementById('d_crypto_label').innerText = `Crypto ETPs: ${fmtCur(amt_D_crypto)} (${d_crypto.toFixed(2)}%)`;
            document.getElementById('d_cash_label').innerText = `Cash: ${fmtCur(amt_D_cash)} (${d_cash.toFixed(2)}%)`;

            // Chart Data Prep
            let tot_ib01 = amt_A_ib01 + amt_B_ib01 + amt_C_ib01 + amt_D_ib01;
            let tot_cspx = amt_A_cspx + amt_C_cspx + amt_D_cspx;
            let tot_cndx = amt_A_cndx + amt_C_cndx + amt_D_cndx;
            let tot_crypto = amt_A_crypto + amt_C_crypto + amt_D_crypto;
            let tot_cash = amt_A_cash + amt_B_cash + amt_C_cash + amt_D_cash;
            let tot_opt_mkt = amt_A_opt_mkt + amt_C_opt_mkt;

            const pctA = totalEstate > 0 ? ((sA / totalEstate) * 100).toFixed(1) : "0.0";
            const pctB = totalEstate > 0 ? ((sB / totalEstate) * 100).toFixed(1) : "0.0";
            const pctC = totalEstate > 0 ? ((sC / totalEstate) * 100).toFixed(1) : "0.0";
            const pctD = totalEstate > 0 ? ((sD / totalEstate) * 100).toFixed(1) : "0.0";
            const xLabels =['Silo A', 'Silo B', 'Silo C', 'Silo D'];

            // SMART BAR CHART LOGIC
            let barData =[
                { x: xLabels, y:[amt_A_ib01, amt_B_ib01, amt_C_ib01, amt_D_ib01], name: 'IB01', type: 'bar', marker: {color: palette.ib01} },
                { x: xLabels, y:[amt_A_cspx, 0,          amt_C_cspx, amt_D_cspx], name: 'CSPX', type: 'bar', marker: {color: palette.cspx} },
                { x: xLabels, y:[amt_A_cndx, 0,          amt_C_cndx, amt_D_cndx], name: 'CNDX', type: 'bar', marker: {color: palette.cndx} },
                { x: xLabels, y:[amt_A_crypto, 0,        amt_C_crypto, amt_D_crypto], name: 'Crypto ETPs', type: 'bar', marker: {color: palette.crypto} },
                { x: xLabels, y:[0,          amt_B_act,  0,          0         ], name: 'CFDs/Intl', type: 'bar', marker: {color: palette.cfd_intl} },
                { x: xLabels, y:[amt_A_cash, amt_B_cash, amt_C_cash, amt_D_cash], name: 'Cash', type: 'bar', marker: {color: palette.cash} }
            ];

            if (Math.abs(tot_opt_mkt) > 0) {
                barData.push({ x: xLabels, y:[amt_A_opt_mkt, 0, amt_C_opt_mkt, 0], name: 'Options Liability', type: 'bar', marker: {color: palette.optMktVal} });
            }
            if (amt_A_xsp > 0 || amt_C_xsp > 0) {
                barData.push({ x:['Silo A', 'Silo C'], y:[amt_A_xsp, amt_C_xsp], name: 'Margin Lock (Phantom)', type: 'scatter', mode: 'markers', marker: {symbol: 'diamond', size: 14, color: '#ef4444', line: {color: 'white', width: 1.5}} });
            }

            let barLayout = { 
                barmode: 'relative', title: 'GAAP Balance Sheet per Silo (USD / %)', 
                margin: {b: 40, t: 80}, paper_bgcolor: 'rgba(0,0,0,0)', plot_bgcolor: 'rgba(0,0,0,0)',
                annotations:[
                    { x: xLabels[0], y: sA, text: `${(sA/1000).toFixed(0)}k<br>(${pctA}%)`, showarrow: false, yanchor: 'bottom', font: {bold: true, size: 13}},
                    { x: xLabels[1], y: sB, text: `${(sB/1000).toFixed(0)}k<br>(${pctB}%)`, showarrow: false, yanchor: 'bottom', font: {bold: true, size: 13}},
                    { x: xLabels[2], y: sC, text: `${(sC/1000).toFixed(0)}k<br>(${pctC}%)`, showarrow: false, yanchor: 'bottom', font: {bold: true, size: 13}},
                    { x: xLabels[3], y: sD, text: `${(sD/1000).toFixed(0)}k<br>(${pctD}%)`, showarrow: false, yanchor: 'bottom', font: {bold: true, size: 13}}
                ]
            };
            Plotly.react('bar-chart', barData, barLayout);

            // SMART PIE CHART LOGIC
            let rawPieData =[
                {v: tot_ib01, l: `IB01: ${fmtCur(tot_ib01)}`, c: palette.ib01},
                {v: tot_cspx, l: `CSPX: ${fmtCur(tot_cspx)}`, c: palette.cspx},
                {v: tot_cndx, l: `CNDX: ${fmtCur(tot_cndx)}`, c: palette.cndx},
                {v: amt_B_act, l: `Active Swing: ${fmtCur(amt_B_act)}`, c: palette.cfd_intl},
                {v: tot_cash, l: `Total USD Cash: ${fmtCur(tot_cash)}`, c: palette.cash}
            ];
            
            if (tot_crypto > 0) {
                rawPieData.push({v: tot_crypto, l: `Crypto ETPs: ${fmtCur(tot_crypto)}`, c: palette.crypto});
            }
            if (Math.abs(tot_opt_mkt) > 0) {
                rawPieData.push({v: Math.abs(tot_opt_mkt), l: `Options Liability: ${fmtCur(Math.abs(tot_opt_mkt))}`, c: palette.optMktVal});
            }

            let pieData =[{
                values: rawPieData.map(d => d.v),
                labels: rawPieData.map(d => d.l),
                type: 'pie', textinfo: 'percent', hole: .4,
                marker: { colors: rawPieData.map(d => d.c) }
            }];
            
            let pieLayout = { title: `Gross Asset Allocation Weighting`, margin: {t: 50, b: 20, l: 0, r: 0}, paper_bgcolor: 'rgba(0,0,0,0)' };
            Plotly.react('pie-chart', pieData, pieLayout);
            
            // ---------------------------------------------------------
            // BENCHMARK CHARTS LOGIC (Global + 4 Silos)
            // ---------------------------------------------------------
            const benchDates = VAR_BENCH_DATES;
            const estateData = VAR_ESTATE_CUM;
            const spyData = VAR_SPY_CUM;
            const qqqData = VAR_QQQ_CUM;
            const siloAData = VAR_SILOA_CUM;
            const siloBData = VAR_SILOB_CUM;
            const siloCData = VAR_SILOC_CUM;
            const siloDData = VAR_SILOD_CUM;

            if (benchDates.length > 0) {
                // Global Chart
                let traceEstate = { x: benchDates, y: estateData, name: 'Estate', type: 'scatter', mode: 'lines', line: {color: 'black', width: 4} };
                let traceSPY = { x: benchDates, y: spyData, name: 'SPY', type: 'scatter', mode: 'lines', line: {color: '#3b82f6', width: 2} }; 
                let traceQQQ = { x: benchDates, y: qqqData, name: 'QQQ', type: 'scatter', mode: 'lines', line: {color: '#f97316', width: 2} }; 

                let benchLayout = {
                    margin: {t: 10, b: 30, l: 40, r: 20},
                    paper_bgcolor: 'rgba(0,0,0,0)',
                    plot_bgcolor: 'rgba(0,0,0,0)',
                    yaxis: { ticksuffix: '%', hoverformat: '.2f%' },
                    legend: { orientation: 'h', y: 1.1, x: 0.5, xanchor: 'center' }
                };
                Plotly.react('benchmark-chart',[traceEstate, traceSPY, traceQQQ], benchLayout, {responsive: true});

                // Small Silo Charts Config
                let trSPY_sm = { x: benchDates, y: spyData, type: 'scatter', mode: 'lines', line: {color: '#3b82f6', width: 1.5}, showlegend: false, hoverinfo: 'skip' };
                let trQQQ_sm = { x: benchDates, y: qqqData, type: 'scatter', mode: 'lines', line: {color: '#f97316', width: 1.5}, showlegend: false, hoverinfo: 'skip' };
                
                let layoutSmall = {
                    margin: {t: 20, b: 20, l: 30, r: 10},
                    paper_bgcolor: 'rgba(0,0,0,0)',
                    plot_bgcolor: 'rgba(0,0,0,0)',
                    xaxis: { showticklabels: false, showgrid: false, zeroline: false },
                    yaxis: { ticksuffix: '%', hoverformat: '.2f%', showgrid: true, gridcolor: 'rgba(0,0,0,0.05)', zeroline: true, zerolinecolor: '#ccc' }
                };

                let trSiloA = { x: benchDates, y: siloAData, name: 'Silo A', type: 'scatter', mode: 'lines', line: {color: 'black', width: 3}, showlegend: false };
                Plotly.react('chart-silo-a',[trSiloA, trSPY_sm, trQQQ_sm], layoutSmall, {responsive: true});

                let trSiloB = { x: benchDates, y: siloBData, name: 'Silo B', type: 'scatter', mode: 'lines', line: {color: 'black', width: 3}, showlegend: false };
                Plotly.react('chart-silo-b',[trSiloB, trSPY_sm, trQQQ_sm], layoutSmall, {responsive: true});

                let trSiloC = { x: benchDates, y: siloCData, name: 'Silo C', type: 'scatter', mode: 'lines', line: {color: 'black', width: 3}, showlegend: false };
                Plotly.react('chart-silo-c',[trSiloC, trSPY_sm, trQQQ_sm], layoutSmall, {responsive: true});

                let trSiloD = { x: benchDates, y: siloDData, name: 'Silo D', type: 'scatter', mode: 'lines', line: {color: 'black', width: 3}, showlegend: false };
                Plotly.react('chart-silo-d',[trSiloD, trSPY_sm, trQQQ_sm], layoutSmall, {responsive: true});
            }

            // ---------------------------------------------------------
            // DAILY PNL HISTOGRAM LOGIC
            // ---------------------------------------------------------
            const datesPnl = VAR_DATES_PNL;
            const pnlA = VAR_SILOA_PNL;
            const pnlB = VAR_SILOB_PNL;
            const pnlC = VAR_SILOC_PNL;
            const pnlD = VAR_SILOD_PNL;
            
            const textA = pnlA.map(v => v !== 0 ? Math.round(v).toString() : "");
            const textB = pnlB.map(v => v !== 0 ? Math.round(v).toString() : "");
            const textC = pnlC.map(v => v !== 0 ? Math.round(v).toString() : "");
            const textD = pnlD.map(v => v !== 0 ? Math.round(v).toString() : "");

            if (datesPnl.length > 0) {
                let traceA = { x: datesPnl, y: pnlA, text: textA, name: 'Silo A', type: 'bar', marker: {color: '#1d4ed8'}, textangle: -90, textposition: 'inside', insidetextanchor: 'start', textfont: {color: 'white', size: 10} };
                let traceB = { x: datesPnl, y: pnlB, text: textB, name: 'Silo B', type: 'bar', marker: {color: '#7e22ce'}, textangle: -90, textposition: 'inside', insidetextanchor: 'start', textfont: {color: 'white', size: 10} };
                let traceC = { x: datesPnl, y: pnlC, text: textC, name: 'Silo C', type: 'bar', marker: {color: '#15803d'}, textangle: -90, textposition: 'inside', insidetextanchor: 'start', textfont: {color: 'white', size: 10} };
                let traceD = { x: datesPnl, y: pnlD, text: textD, name: 'Silo D', type: 'bar', marker: {color: '#facc15'}, textangle: -90, textposition: 'inside', insidetextanchor: 'start', textfont: {color: 'black', size: 10} };

                let pnlLayout = {
                    barmode: 'relative',
                    margin: {t: 20, b: 40, l: 60, r: 20},
                    paper_bgcolor: 'rgba(0,0,0,0)',
                    plot_bgcolor: 'rgba(0,0,0,0)',
                    xaxis: { type: 'date', showgrid: false },
                    yaxis: { title: 'Daily PnL (USD)', zeroline: true, zerolinecolor: '#000000', zerolinewidth: 1 },
                    legend: { orientation: 'h', y: 1.1, x: 0.5, xanchor: 'center' }
                };
                Plotly.react('daily-pnl-chart', [traceA, traceB, traceC, traceD], pnlLayout, {responsive: true});
            }
        }

        document.querySelectorAll('input').forEach(i => i.addEventListener('input', updateUI));
        populateTable();
        updateUI();
    </script>
</body>
</html>
"""

# ---------------------------------------------------------
# 5. Inject Variables Automatically (Silos + Global Estate)
# ---------------------------------------------------------
for acc, prefix in[("ESTATE", "ESTATE"), ("U23144948", "A"), ("U23139264", "B"), ("U23154199", "C"), ("U25218481", "D")]:
    html_content = html_content.replace(f"VAR_COLOR_{prefix}_IRR", get_color_class(metrics[acc]["irr"]))
    html_content = html_content.replace(f"VAR_{prefix}_IRR", metrics[acc]["irr"])
    
    html_content = html_content.replace(f"VAR_COLOR_{prefix}_SHARPE", get_color_class(metrics[acc]["sharpe"]))
    html_content = html_content.replace(f"VAR_{prefix}_SHARPE", metrics[acc]["sharpe"])
    
    html_content = html_content.replace(f"VAR_COLOR_{prefix}_PNL", get_color_class(metrics[acc]["pnl"]))
    html_content = html_content.replace(f"VAR_{prefix}_PNL", metrics[acc]["pnl"])
    
    html_content = html_content.replace(f"VAR_{prefix}_MAXDD", metrics[acc]["maxdd"])
    html_content = html_content.replace(f"VAR_{prefix}_DD_DAYS", metrics[acc]["dd_days"])
    html_content = html_content.replace(f"VAR_{prefix}_CALMAR", metrics[acc]["calmar"])
    
    html_content = html_content.replace(f"VAR_COLOR_{prefix}_ROC", get_color_class(metrics[acc]["roc"]))
    html_content = html_content.replace(f"VAR_{prefix}_ROC", metrics[acc]["roc"])

    nav_val = metrics[acc]["nav"]
    html_content = html_content.replace(f"VAR_{prefix}_NAV_FMT", f" USD {nav_val:,.2f}")

    if prefix != "ESTATE":
        html_content = html_content.replace(f"VAR_NAV_{prefix}", str(round(nav_val, 2)))

html_content = html_content.replace("VAR_BENCH_DATES", str(dates_js))
html_content = html_content.replace("VAR_ESTATE_CUM", str(estate_js))
html_content = html_content.replace("VAR_SPY_CUM", str(spy_js))
html_content = html_content.replace("VAR_QQQ_CUM", str(qqq_js))

# Inject isolated Silo TWR returns
html_content = html_content.replace("VAR_SILOA_CUM", str(silo_a_js))
html_content = html_content.replace("VAR_SILOB_CUM", str(silo_b_js))
html_content = html_content.replace("VAR_SILOC_CUM", str(silo_c_js))
html_content = html_content.replace("VAR_SILOD_CUM", str(silo_d_js))

# Inject Daily PnL Histogram Data
html_content = html_content.replace("VAR_DATES_PNL", str(dates_pnl_js))
html_content = html_content.replace("VAR_SILOA_PNL", str(silo_a_pnl))
html_content = html_content.replace("VAR_SILOB_PNL", str(silo_b_pnl))
html_content = html_content.replace("VAR_SILOC_PNL", str(silo_c_pnl))
html_content = html_content.replace("VAR_SILOD_PNL", str(silo_d_pnl))

# ---------------------------------------------------------
# 6. Save the Output
# ---------------------------------------------------------
try:
    with open(full_file_path, "w", encoding="utf-8") as f:
        f.write(html_content)
    print("====================================================================")
    print(f"SUCCESS! Estate Dashboard v21 created.")
    print(f"Path: {full_file_path}")
    print("====================================================================")
except Exception as e:
    print(f"Error: {e}")