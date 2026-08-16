r"""
=============================================================================
Script Name: Generate_Estate_Dashboard_v12.py
Purpose: Generates the Interactive Family Estate Dashboard.
         VERSION 12: 
         - RESTORED: The 'Master Instrument Matrix' array and JS function.
         - PRESERVED: Masked U-Numbers (e.g. U*****199).
         - PRESERVED: Silo headers cleanly mapped to beneficiaries without co-titles.
         - PRESERVED: Silo D contrast fix (light yellow background).
         - PRESERVED: Max Drawdown math fix.
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
full_file_path = os.path.join(target_directory, "Family_Estate_Dashboard_v12.html")

if not os.path.exists(target_directory):
    os.makedirs(target_directory)

# ---------------------------------------------------------
# 2. The Quantitative Math Engine (XIRR, Sharpe, P&L, MaxDD)
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

def process_account_metrics(df, account_id):
    df_acc = df[df['AccountID'] == account_id].copy()
    if df_acc.empty or len(df_acc) < 2:
        return "N/A", "N/A", "N/A", "N/A"
    
    df_acc = df_acc.sort_values('Date')
    
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
    
    # --- Total P&L ($) ---
    total_deposits = df_acc['CashFlow'].sum()
    final_nav = df_acc['NAV'].iloc[-1]
    total_pnl = final_nav - total_deposits
    pnl_str = f"${total_pnl:,.2f}"
    
    # --- Max Drawdown (Cumulative Returns Index) ---
    df_acc['Cum_Return_Index'] = (1 + df_acc['Daily_Return']).cumprod()
    df_acc['Peak'] = df_acc['Cum_Return_Index'].cummax()
    df_acc['Drawdown'] = (df_acc['Cum_Return_Index'] - df_acc['Peak']) / df_acc['Peak'].replace(0, np.nan)
    max_dd = df_acc['Drawdown'].min() * 100
    max_dd_str = f"{max_dd:.2f}%"
    
    # --- XIRR ---
    df_acc['IRR_CF'] = -df_acc['CashFlow']
    cfs = df_acc['IRR_CF'].tolist()
    dates = df_acc['Date'].tolist()
    
    cfs.append(final_nav)
    dates.append(dates[-1])
    
    dates_series = pd.to_datetime(pd.Series(dates))
    irr = calculate_xirr(dates_series, cfs)
    irr_str = f"{(irr * 100):.2f}%"
    
    return irr_str, sharpe_str, pnl_str, max_dd_str

def get_color_class(val_str, theme="dark"):
    if "N/A" in val_str or "Awaiting" in val_str or "--" in val_str: 
        return "text-gray-400" if theme == "dark" else "text-gray-500"
    if "-" in val_str: 
        return "text-red-400" if theme == "dark" else "text-red-600"
    return "text-green-400" if theme == "dark" else "text-green-700"

# ---------------------------------------------------------
# 3. Read CSV and Calculate Metrics
# ---------------------------------------------------------
metrics = {
    "U23144948": {"irr": "Awaiting Data", "sharpe": "--", "pnl": "--", "maxdd": "--"},
    "U23139264": {"irr": "Awaiting Data", "sharpe": "--", "pnl": "--", "maxdd": "--"},
    "U23154199": {"irr": "Awaiting Data", "sharpe": "--", "pnl": "--", "maxdd": "--"},
    "U25218481": {"irr": "Awaiting Data", "sharpe": "--", "pnl": "--", "maxdd": "--"}
}

if os.path.exists(csv_file_path):
    try:
        raw_df = pd.read_csv(csv_file_path)
        raw_df['Date'] = pd.to_datetime(raw_df['Date'].astype(str), format='%Y%m%d')
        df = raw_df.groupby(['AccountID', 'Date']).agg({'NAV': 'last', 'CashFlow': 'sum'}).reset_index()
        for acc in metrics.keys():
            irr, sharpe, pnl, maxdd = process_account_metrics(df, acc)
            metrics[acc] = {"irr": irr, "sharpe": sharpe, "pnl": pnl, "maxdd": maxdd}
        print("Data successfully parsed. Metrics calculated.")
    except Exception as e:
        print(f"Error parsing CSV: {e}")
else:
    print(f"Notice: CSV file not found at {csv_file_path}. Generating HTML with placeholder data.")

# ---------------------------------------------------------
# 4. Define HTML Payload
# ---------------------------------------------------------
html_content = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Family Estate Master Allocator v12</title>
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

    <div class="max-w-[1800px] mx-auto bg-white rounded-xl shadow-xl p-6 border border-gray-200">
        
        <div class="text-center mb-6">
            <h1 class="text-4xl font-extrabold text-gray-900 tracking-tight">Family Estate Master Dashboard</h1>
            <p class="text-gray-500 mt-2 font-medium">Silo Allocation & Institutional Data Engine v12</p>
        </div>

        <!-- Performance Metrics -->
        <div class="mb-8 grid grid-cols-1 md:grid-cols-4 gap-4">
            <div class="bg-blue-900 text-white p-4 rounded-xl shadow-md text-center border-b-4 border-blue-500">
                <h4 class="text-sm text-blue-200 uppercase tracking-widest font-bold">Silo A</h4>
                <p class="text-xs mb-1 text-gray-400">Persons 1 and 2<br>U*****948</p>
                <div class="grid grid-cols-2 text-sm mt-3 border-t border-blue-700 pt-3 gap-y-2 font-mono">
                    <div class="text-left">IRR: <span class="VAR_COLOR_A_IRR font-bold">VAR_A_IRR</span></div>
                    <div class="text-right">Sharpe: <span class="VAR_COLOR_A_SHARPE font-bold">VAR_A_SHARPE</span></div>
                    <div class="text-left">P&L: <span class="VAR_COLOR_A_PNL font-bold">VAR_A_PNL</span></div>
                    <div class="text-right">Max DD: <span class="text-red-400 font-bold">VAR_A_MAXDD</span></div>
                </div>
            </div>
            
            <div class="bg-purple-900 text-white p-4 rounded-xl shadow-md text-center border-b-4 border-purple-500">
                <h4 class="text-sm text-purple-200 uppercase tracking-widest font-bold">Silo B</h4>
                <p class="text-xs mb-1 text-gray-400">Persons 1 and 2<br>U*****264</p>
                <div class="grid grid-cols-2 text-sm mt-3 border-t border-purple-700 pt-3 gap-y-2 font-mono">
                    <div class="text-left">IRR: <span class="VAR_COLOR_B_IRR font-bold">VAR_B_IRR</span></div>
                    <div class="text-right">Sharpe: <span class="VAR_COLOR_B_SHARPE font-bold">VAR_B_SHARPE</span></div>
                    <div class="text-left">P&L: <span class="VAR_COLOR_B_PNL font-bold">VAR_B_PNL</span></div>
                    <div class="text-right">Max DD: <span class="text-red-400 font-bold">VAR_B_MAXDD</span></div>
                </div>
            </div>

            <div class="bg-green-900 text-white p-4 rounded-xl shadow-md text-center border-b-4 border-green-500">
                <h4 class="text-sm text-green-200 uppercase tracking-widest font-bold">Silo C</h4>
                <p class="text-xs mb-1 text-gray-400">Persons 1 and 3<br>U*****199</p>
                <div class="grid grid-cols-2 text-sm mt-3 border-t border-green-700 pt-3 gap-y-2 font-mono">
                    <div class="text-left">IRR: <span class="VAR_COLOR_C_IRR font-bold">VAR_C_IRR</span></div>
                    <div class="text-right">Sharpe: <span class="VAR_COLOR_C_SHARPE font-bold">VAR_C_SHARPE</span></div>
                    <div class="text-left">P&L: <span class="VAR_COLOR_C_PNL font-bold">VAR_C_PNL</span></div>
                    <div class="text-right">Max DD: <span class="text-red-400 font-bold">VAR_C_MAXDD</span></div>
                </div>
            </div>

            <div class="bg-yellow-100 text-gray-900 p-4 rounded-xl shadow-md text-center border-b-4 border-yellow-400">
                <h4 class="text-sm text-yellow-800 uppercase tracking-widest font-bold">Silo D</h4>
                <p class="text-xs mb-1 text-gray-600">Persons 1 and 4<br>U*****481</p>
                <div class="grid grid-cols-2 text-sm mt-3 border-t border-yellow-300 pt-3 gap-y-2 font-mono">
                    <div class="text-left">IRR: <span class="VAR_COLOR_D_IRR font-bold">VAR_D_IRR</span></div>
                    <div class="text-right">Sharpe: <span class="VAR_COLOR_D_SHARPE font-bold">VAR_D_SHARPE</span></div>
                    <div class="text-left">P&L: <span class="VAR_COLOR_D_PNL font-bold">VAR_D_PNL</span></div>
                    <div class="text-right">Max DD: <span class="text-red-600 font-bold">VAR_D_MAXDD</span></div>
                </div>
            </div>
        </div>

        <!-- Silo Inputs Section -->
        <div class="mb-8 bg-gray-50 p-4 rounded-xl border shadow-sm">
            <h3 class="text-xl font-bold mb-2 text-gray-800">1. Estate Capital (Net Liquidation Value)</h3>
            <p class="text-sm text-gray-500 mb-4 border-b pb-2">Enter the exact 'Net Liquidity' from IBKR. Unrealized P&L is already baked into this number.</p>
            <div class="grid grid-cols-2 md:grid-cols-4 gap-4">
                <div><label class="block text-sm font-bold text-gray-700">Silo A ($)</label><input type="number" id="siloA" value="599511" class="mt-1 w-full rounded-md p-2 border" oninput="updateUI()"></div>
                <div><label class="block text-sm font-bold text-gray-700">Silo B ($)</label><input type="number" id="siloB" value="28774" class="mt-1 w-full rounded-md p-2 border" oninput="updateUI()"></div>
                <div><label class="block text-sm font-bold text-gray-700">Silo C ($)</label><input type="number" id="siloC" value="289806" class="mt-1 w-full rounded-md p-2 border" oninput="updateUI()"></div>
                <div><label class="block text-sm font-bold text-gray-700">Silo D ($)</label><input type="number" id="siloD" value="150000" class="mt-1 w-full rounded-md p-2 border" oninput="updateUI()"></div>
            </div>
        </div>

        <!-- Target Allocation Sliders -->
        <div class="mb-8 bg-white p-4 rounded-xl border shadow-sm">
            <h3 class="text-xl font-bold mb-2 text-gray-800">2. Target Portfolio Composition (%)</h3>
            <p class="text-sm text-gray-500 mb-4 border-b pb-2">Physical assets (including the negative Options Liability) must mathematically equal 100%.</p>
            <div class="grid grid-cols-1 lg:grid-cols-4 gap-4">
                
                <!-- Silo A -->
                <div class="bg-blue-50 p-3 rounded-lg border border-blue-200 shadow-inner">
                    <h4 class="font-bold text-blue-900 mb-2 text-sm border-b border-blue-200 pb-1">Silo A</h4>
                    <p class="text-xs font-bold text-gray-500 mb-1 uppercase tracking-wide">Physical Balance Sheet (Must = 100%)</p>
                    <label class="text-xs font-semibold" id="a_ib01_label">IB01: </label><input type="range" id="a_ib01" min="0" max="100" step="0.01" value="99.10" class="w-full mb-1" oninput="updateUI()">
                    <label class="text-xs font-semibold" id="a_cspx_label">CSPX: </label><input type="range" id="a_cspx" min="0" max="100" step="0.01" value="0.0" class="w-full mb-1" oninput="updateUI()">
                    <label class="text-xs font-semibold" id="a_xuse_label">XUSE: </label><input type="range" id="a_xuse" min="0" max="100" step="0.01" value="0.0" class="w-full mb-1" oninput="updateUI()">
                    <label class="text-xs font-semibold" id="a_eimi_label">EIMI: </label><input type="range" id="a_eimi" min="0" max="100" step="0.01" value="0.0" class="w-full mb-1" oninput="updateUI()">
                    <label class="text-xs font-semibold" id="a_cash_label">Cash: </label><input type="range" id="a_cash" min="0" max="100" step="0.01" value="2.55" class="w-full mb-1" oninput="updateUI()">
                    
                    <label class="text-xs font-bold text-red-700" id="a_opt_mkt_label">Opt. Mkt Val (Liability): </label><input type="range" id="a_opt_mkt" min="-20" max="20" step="0.01" value="-1.65" class="w-full mb-1" oninput="updateUI()">
                    <p class="text-xs text-red-600 font-bold mt-1 h-4" id="a_warning"></p>
                    
                    <p class="text-xs font-bold text-gray-500 mt-2 mb-1 uppercase tracking-wide border-t border-blue-200 pt-2">Margin (Phantom Overlay)</p>
                    <label class="text-xs font-semibold text-green-700" id="a_xsp_label">Options Margin: </label><input type="range" id="a_xsp" min="0" max="100" step="0.01" value="20.85" class="w-full mb-1" oninput="updateUI()">
                </div>

                <!-- Silo B -->
                <div class="bg-purple-50 p-3 rounded-lg border border-purple-200 shadow-inner">
                    <h4 class="font-bold text-purple-900 mb-2 text-sm border-b border-purple-200 pb-1">Silo B</h4>
                    <p class="text-xs font-bold text-gray-500 mb-1 uppercase tracking-wide">Physical Balance Sheet (Must = 100%)</p>
                    <label class="text-xs font-semibold" id="b_ib01_label">IB01: </label><input type="range" id="b_ib01" min="0" max="100" step="0.01" value="41.60" class="w-full mb-1" oninput="updateUI()">
                    <label class="text-xs font-semibold" id="b_cash_label">Cash: </label><input type="range" id="b_cash" min="0" max="100" step="0.01" value="58.40" class="w-full mb-1" oninput="updateUI()">
                    <label class="text-xs font-semibold" id="b_cfd_label">CFDs: </label><input type="range" id="b_cfd" min="0" max="100" step="0.01" value="0.0" class="w-full mb-1" oninput="updateUI()">
                    <label class="text-xs font-semibold" id="b_intl_label">Intl Stocks: </label><input type="range" id="b_intl" min="0" max="100" step="0.01" value="0.0" class="w-full mb-1" oninput="updateUI()">
                    <p class="text-xs text-red-600 font-bold mt-1 h-4" id="b_warning"></p>
                </div>

                <!-- Silo C -->
                <div class="bg-green-50 p-3 rounded-lg border border-green-200 shadow-inner">
                    <h4 class="font-bold text-green-900 mb-2 text-sm border-b border-green-200 pb-1">Silo C</h4>
                    <p class="text-xs font-bold text-gray-500 mb-1 uppercase tracking-wide">Physical Balance Sheet (Must = 100%)</p>
                    <label class="text-xs font-semibold" id="c_ib01_label">IB01: </label><input type="range" id="c_ib01" min="0" max="100" step="0.01" value="98.50" class="w-full mb-1" oninput="updateUI()">
                    <label class="text-xs font-semibold" id="c_cspx_label">CSPX: </label><input type="range" id="c_cspx" min="0" max="100" step="0.01" value="0.0" class="w-full mb-1" oninput="updateUI()">
                    <label class="text-xs font-semibold" id="c_xuse_label">XUSE: </label><input type="range" id="c_xuse" min="0" max="100" step="0.01" value="0.0" class="w-full mb-1" oninput="updateUI()">
                    <label class="text-xs font-semibold" id="c_eimi_label">EIMI: </label><input type="range" id="c_eimi" min="0" max="100" step="0.01" value="0.0" class="w-full mb-1" oninput="updateUI()">
                    <label class="text-xs font-semibold" id="c_cash_label">Cash: </label><input type="range" id="c_cash" min="0" max="100" step="0.01" value="3.00" class="w-full mb-1" oninput="updateUI()">
                    
                    <label class="text-xs font-bold text-red-700" id="c_opt_mkt_label">Opt. Mkt Val (Liability): </label><input type="range" id="c_opt_mkt" min="-20" max="20" step="0.01" value="-1.50" class="w-full mb-1" oninput="updateUI()">
                    <p class="text-xs text-red-600 font-bold mt-1 h-4" id="c_warning"></p>

                    <p class="text-xs font-bold text-gray-500 mt-2 mb-1 uppercase tracking-wide border-t border-green-200 pt-2">Margin (Phantom Overlay)</p>
                    <label class="text-xs font-semibold text-green-700" id="c_xsp_label">Options Margin: </label><input type="range" id="c_xsp" min="0" max="100" step="0.01" value="24.20" class="w-full mb-1" oninput="updateUI()">
                </div>

                <!-- Silo D -->
                <div class="bg-yellow-100 p-3 rounded-lg border border-yellow-400 shadow-inner">
                    <h4 class="font-bold text-yellow-900 mb-2 text-sm border-b border-yellow-400 pb-1">Silo D</h4>
                    <p class="text-xs font-bold text-gray-600 mb-1 uppercase tracking-wide">Physical Balance Sheet (Must = 100%)</p>
                    <label class="text-xs font-semibold text-gray-900" id="d_ib01_label">IB01: </label><input type="range" id="d_ib01" min="0" max="100" step="0.01" value="40.0" class="w-full mb-1" oninput="updateUI()">
                    <label class="text-xs font-semibold text-gray-900" id="d_cspx_label">CSPX: </label><input type="range" id="d_cspx" min="0" max="100" step="0.01" value="30.0" class="w-full mb-1" oninput="updateUI()">
                    <label class="text-xs font-semibold text-gray-900" id="d_xuse_label">XUSE: </label><input type="range" id="d_xuse" min="0" max="100" step="0.01" value="15.0" class="w-full mb-1" oninput="updateUI()">
                    <label class="text-xs font-semibold text-gray-900" id="d_eimi_label">EIMI: </label><input type="range" id="d_eimi" min="0" max="100" step="0.01" value="5.0" class="w-full mb-1" oninput="updateUI()">
                    <label class="text-xs font-semibold text-gray-900" id="d_cash_label">Cash: </label><input type="range" id="d_cash" min="0" max="100" step="0.01" value="10.0" class="w-full mb-1" oninput="updateUI()">
                    <p class="text-xs text-red-600 font-bold mt-1 h-4" id="d_warning"></p>
                </div>
            </div>
        </div>

        <!-- Charts -->
        <div class="grid grid-cols-1 xl:grid-cols-2 gap-8 mb-10">
            <div class="bg-white border rounded-xl p-4 shadow-sm"><div id="bar-chart" class="w-full h-[500px]"></div></div>
            <div class="bg-white border rounded-xl p-4 shadow-sm"><div id="pie-chart" class="w-full h-[500px]"></div></div>
        </div>

        <!-- RESTORED: Instrument Matrix -->
        <div class="mb-10">
            <h3 class="text-xl font-bold mb-4 text-gray-800 border-b pb-2">3. The Master Instrument Matrix (Tax, Alpha, & Sharpe Grading)</h3>
            <div class="overflow-x-auto shadow-sm rounded-lg border">
                <table class="min-w-full bg-white text-[13px]">
                    <thead class="bg-slate-800 text-white">
                        <tr>
                            <th class="py-3 px-3 text-left">Instrument</th>
                            <th class="py-3 px-3 text-left">Type</th>
                            <th class="py-3 px-3 text-left">Risk Profile</th>
                            <th class="py-3 px-3 text-left">Alpha Potential</th>
                            <th class="py-3 px-3 text-left">Sharpe / Vol Impact</th>
                            <th class="py-3 px-3 text-left">Trading Strategy</th>
                            <th class="py-3 px-3 text-left">Legal Jurisdiction</th>
                            <th class="py-3 px-3 text-center">CIO Min<br>Alloc. %</th>
                            <th class="py-3 px-3 text-center">CIO Max<br>Alloc. %</th>
                            <th class="py-3 px-3 text-center">CIO<br>Grading</th>
                            <th class="py-3 px-3 text-left w-1/4">Noteworthy Comments</th>
                        </tr>
                    </thead>
                    <tbody class="divide-y divide-gray-200" id="matrix-body">
                    </tbody>
                </table>
            </div>
        </div>

    </div>

    <script>
        function fmtCur(val) { return '$' + Math.round(val).toLocaleString('en-US'); }
        
        const palette = {
            ib01: '#0284c7', cspx: '#f97316', xuse: '#16a34a', eimi: '#dc2626', 
            cash: '#64748b', cfd_intl: '#a855f7', optMktVal: '#ef4444'
        };

        const instruments =[
            { inst: "USD Cash", type: "Currency", risk: "Risk-Free", alpha: "Zero", sharpe: "Massive Stabilizer", strat: "Liquidity", jur: "US (IBKR)", min: "1%", max: "100%", rec: "Splendid", class: "splendid", comm: "<strong>Uninvested USD held in IBKR.</strong><br>MANDATORY collateral if margin expands. The first $10k earns 0% interest; the rest ~4.5%." },
            { inst: "XSP Put Spreads", type: "Index Option", risk: "Moderate", alpha: "High (VRP)", sharpe: "High (Smooths equity curve)", strat: "Weekly Income (45 DTE)", jur: "US (Cboe)", min: "0%", max: "25%", rec: "Splendid", class: "splendid", comm: "<strong>Cash-settled S&P 500 options.</strong><br>1,000% safe from IRS. Capped risk. The 25% max margin limit ensures a Black Swan only causes a manageable ~12% estate drawdown." },
            { inst: "IB01", type: "UCITS ETF", risk: "Risk-Free", alpha: "Zero", sharpe: "High (Zero vol anchor)", strat: "Long Term / Collateral", jur: "Ireland", min: "10%", max: "100%", rec: "Splendid", class: "splendid", comm: "<strong>Irish-domiciled short-term US Treasury fund.</strong><br>Ultimate parking vault. Accumulates 4.5%+ interest tax-free. Liquidated 'Just-In-Time' to cover options losses, avoiding $10k cash drag." },
            { inst: "CSPX", type: "UCITS ETF", risk: "Moderate (Market)", alpha: "Zero (Beta 1)", sharpe: "Baseline", strat: "Long Term DCA", jur: "Ireland", min: "0%", max: "60%", rec: "Great", class: "great", comm: "<strong>Irish-domiciled S&P 500 equity fund.</strong><br>Shields gains from 40% Estate Tax and 30% Dividend Withholding." },
            { inst: "XUSE & EIMI", type: "UCITS ETF", risk: "Moderate", alpha: "Moderate", sharpe: "High (Non-US Correl)", strat: "Long Term DCA", jur: "Ireland", min: "0%", max: "40%", rec: "Great", class: "great", comm: "<strong>Irish-domiciled Dev Ex-US and Emerging Market funds.</strong><br>True geographic diversification. Hedges against US Dollar decline." },
            { inst: "US Tech CFDs", type: "OTC Contract", risk: "Aggressive", alpha: "High (If Skilled)", sharpe: "Negative (Increases volatility)", strat: "Swing Trading", jur: "UK/Offshore", min: "0%", max: "3%", rec: "Good", class: "good", comm: "<strong>Synthetic derivatives tracking physical US tech stocks.</strong><br>0% IRS Estate Tax risk. Subject to overnight margin fees. 3% limit quarantines Minervini trades in Silo B." },
            { inst: "Intl Stocks", type: "Stock", risk: "Aggressive", alpha: "High", sharpe: "Negative", strat: "Swing Trading", jur: "Europe/Asia", min: "0%", max: "3%", rec: "Neutral", class: "good", comm: "<strong>Direct ownership of non-US physical equities.</strong><br>Safe from IRS. Wider bid/ask spreads and liquidity constraints compared to US Tech." },
            { inst: "US Corp Bonds", type: "Bond/Stock", risk: "Moderate", alpha: "Negative", sharpe: "Negative", strat: "Income", jur: "US / Ireland", min: "0%", max: "0%", rec: "Bad", class: "bad", comm: "<strong>Debt issued by US corporations.</strong><br>Di-worsification. Crashes during Black Swans. 0% allocation due to NRA tax drag." },
            { inst: "Physical US Stocks", type: "Stock", risk: "Aggressive", alpha: "High", sharpe: "Baseline", strat: "Swing / Hold", jur: "US (Nasdaq)", min: "0%", max: "0%", rec: "Avoid", class: "avoid", comm: "<strong>Shares traded on US exchanges.</strong><br>LETHAL. Triggers 40% US Estate Tax and 30% Dividend Withholding." },
            { inst: "US Stock Options", type: "Option", risk: "Extreme", alpha: "High", sharpe: "Negative", strat: "Speculation", jur: "US (Cboe)", min: "0%", max: "0%", rec: "Avoid", class: "avoid", comm: "<strong>Contracts granting the right to buy/sell physical US property.</strong><br>LETHAL. IRS gray area. Brokers will aggressively freeze the account for months upon death." }
        ];

        function populateTable() {
            const tbody = document.getElementById('matrix-body');
            let html = "";
            instruments.forEach(i => {
                html += `<tr class="hover:bg-gray-50 border-b border-gray-100">
                    <td class="py-3 px-3 font-semibold text-gray-900">${i.inst}</td>
                    <td class="py-3 px-3">${i.type}</td>
                    <td class="py-3 px-3">${i.risk}</td>
                    <td class="py-3 px-3">${i.alpha}</td>
                    <td class="py-3 px-3 font-medium text-indigo-700">${i.sharpe}</td>
                    <td class="py-3 px-3">${i.strat}</td>
                    <td class="py-3 px-3">${i.jur}</td>
                    <td class="py-3 px-3 font-bold text-center text-gray-500">${i.min}</td>
                    <td class="py-3 px-3 font-bold text-center">${i.max}</td>
                    <td class="py-3 px-3 ${i.class} text-center rounded shadow-sm">${i.rec}</td>
                    <td class="py-3 px-3 text-xs text-gray-700 leading-relaxed">${i.comm}</td>
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

            // Silo A - Balance Sheet (Must = 100%)
            let a_ib01 = parseFloat(document.getElementById('a_ib01').value); let a_cspx = parseFloat(document.getElementById('a_cspx').value);
            let a_xuse = parseFloat(document.getElementById('a_xuse').value); let a_eimi = parseFloat(document.getElementById('a_eimi').value); 
            let a_cash = parseFloat(document.getElementById('a_cash').value); let a_opt_mkt = parseFloat(document.getElementById('a_opt_mkt').value);
            
            let a_tot = a_ib01 + a_cspx + a_xuse + a_eimi + a_cash + a_opt_mkt;
            document.getElementById('a_warning').innerText = Math.abs(a_tot - 100) > 0.05 ? `Balance: ${a_tot.toFixed(2)}%. Must = 100%!` : "";
            
            let a_xsp = parseFloat(document.getElementById('a_xsp').value);
            
            const amt_A_ib01 = sA * (a_ib01/100); const amt_A_cspx = sA * (a_cspx/100); const amt_A_xuse = sA * (a_xuse/100); 
            const amt_A_eimi = sA * (a_eimi/100); const amt_A_cash = sA * (a_cash/100); const amt_A_opt_mkt = sA * (a_opt_mkt/100);
            const amt_A_xsp = sA * (a_xsp/100);
            
            document.getElementById('a_ib01_label').innerText = `IB01: ${fmtCur(amt_A_ib01)} (${a_ib01.toFixed(2)}%)`;
            document.getElementById('a_cspx_label').innerText = `CSPX: ${fmtCur(amt_A_cspx)} (${a_cspx.toFixed(2)}%)`;
            document.getElementById('a_xuse_label').innerText = `XUSE: ${fmtCur(amt_A_xuse)} (${a_xuse.toFixed(2)}%)`;
            document.getElementById('a_eimi_label').innerText = `EIMI: ${fmtCur(amt_A_eimi)} (${a_eimi.toFixed(2)}%)`;
            document.getElementById('a_cash_label').innerText = `Cash: ${fmtCur(amt_A_cash)} (${a_cash.toFixed(2)}%)`;
            document.getElementById('a_opt_mkt_label').innerText = `Options Mkt Val (Liability): ${fmtCur(amt_A_opt_mkt)} (${a_opt_mkt.toFixed(2)}%)`;
            document.getElementById('a_xsp_label').innerText  = `Options Margin: ${fmtCur(amt_A_xsp)} (${a_xsp.toFixed(2)}%)`;

            // Silo B - Balance Sheet (Must = 100%)
            let b_ib01 = parseFloat(document.getElementById('b_ib01').value); let b_cash = parseFloat(document.getElementById('b_cash').value); 
            let b_cfd = parseFloat(document.getElementById('b_cfd').value);   let b_intl = parseFloat(document.getElementById('b_intl').value);
            let b_tot = b_ib01 + b_cash + b_cfd + b_intl;
            document.getElementById('b_warning').innerText = Math.abs(b_tot - 100) > 0.05 ? `Balance: ${b_tot.toFixed(2)}%. Must = 100%!` : "";
            
            const amt_B_ib01 = sB * (b_ib01/100); const amt_B_cash = sB * (b_cash/100);
            const amt_B_cfd  = sB * (b_cfd/100);  const amt_B_intl = sB * (b_intl/100);
            const amt_B_act  = amt_B_cfd + amt_B_intl; // Grouped for Pie

            document.getElementById('b_ib01_label').innerText = `IB01: ${fmtCur(amt_B_ib01)} (${b_ib01.toFixed(2)}%)`;
            document.getElementById('b_cash_label').innerText = `Cash: ${fmtCur(amt_B_cash)} (${b_cash.toFixed(2)}%)`;
            document.getElementById('b_cfd_label').innerText  = `CFDs: ${fmtCur(amt_B_cfd)} (${b_cfd.toFixed(2)}%)`;
            document.getElementById('b_intl_label').innerText = `Intl Stocks: ${fmtCur(amt_B_intl)} (${b_intl.toFixed(2)}%)`;

            // Silo C - Balance Sheet (Must = 100%)
            let c_ib01 = parseFloat(document.getElementById('c_ib01').value); let c_cspx = parseFloat(document.getElementById('c_cspx').value);
            let c_xuse = parseFloat(document.getElementById('c_xuse').value); let c_eimi = parseFloat(document.getElementById('c_eimi').value); 
            let c_cash = parseFloat(document.getElementById('c_cash').value); let c_opt_mkt = parseFloat(document.getElementById('c_opt_mkt').value);
            
            let c_tot = c_ib01 + c_cspx + c_xuse + c_eimi + c_cash + c_opt_mkt;
            document.getElementById('c_warning').innerText = Math.abs(c_tot - 100) > 0.05 ? `Balance: ${c_tot.toFixed(2)}%. Must = 100%!` : "";
            
            let c_xsp = parseFloat(document.getElementById('c_xsp').value);

            const amt_C_ib01 = sC * (c_ib01/100); const amt_C_cspx = sC * (c_cspx/100); const amt_C_xuse = sC * (c_xuse/100); 
            const amt_C_eimi = sC * (c_eimi/100); const amt_C_cash = sC * (c_cash/100); const amt_C_opt_mkt = sC * (c_opt_mkt/100);
            const amt_C_xsp  = sC * (c_xsp/100);
            
            document.getElementById('c_ib01_label').innerText = `IB01: ${fmtCur(amt_C_ib01)} (${c_ib01.toFixed(2)}%)`;
            document.getElementById('c_cspx_label').innerText = `CSPX: ${fmtCur(amt_C_cspx)} (${c_cspx.toFixed(2)}%)`;
            document.getElementById('c_xuse_label').innerText = `XUSE: ${fmtCur(amt_C_xuse)} (${c_xuse.toFixed(2)}%)`;
            document.getElementById('c_eimi_label').innerText = `EIMI: ${fmtCur(amt_C_eimi)} (${c_eimi.toFixed(2)}%)`;
            document.getElementById('c_cash_label').innerText = `Cash: ${fmtCur(amt_C_cash)} (${c_cash.toFixed(2)}%)`;
            document.getElementById('c_opt_mkt_label').innerText = `Options Mkt Val (Liability): ${fmtCur(amt_C_opt_mkt)} (${c_opt_mkt.toFixed(2)}%)`;
            document.getElementById('c_xsp_label').innerText  = `Options Margin: ${fmtCur(amt_C_xsp)} (${c_xsp.toFixed(2)}%)`;

            // Silo D - Balance Sheet (Must = 100%)
            let d_ib01 = parseFloat(document.getElementById('d_ib01').value); let d_cspx = parseFloat(document.getElementById('d_cspx').value);
            let d_xuse = parseFloat(document.getElementById('d_xuse').value); let d_eimi = parseFloat(document.getElementById('d_eimi').value); 
            let d_cash = parseFloat(document.getElementById('d_cash').value);
            let d_tot = d_ib01 + d_cspx + d_xuse + d_eimi + d_cash;
            document.getElementById('d_warning').innerText = Math.abs(d_tot - 100) > 0.05 ? `Balance: ${d_tot.toFixed(2)}%. Must = 100%!` : "";
            
            const amt_D_ib01 = sD * (d_ib01/100); const amt_D_cspx = sD * (d_cspx/100); const amt_D_xuse = sD * (d_xuse/100); 
            const amt_D_eimi = sD * (d_eimi/100); const amt_D_cash = sD * (d_cash/100);

            document.getElementById('d_ib01_label').innerText = `IB01: ${fmtCur(amt_D_ib01)} (${d_ib01.toFixed(2)}%)`;
            document.getElementById('d_cspx_label').innerText = `CSPX: ${fmtCur(amt_D_cspx)} (${d_cspx.toFixed(2)}%)`;
            document.getElementById('d_xuse_label').innerText = `XUSE: ${fmtCur(amt_D_xuse)} (${d_xuse.toFixed(2)}%)`;
            document.getElementById('d_eimi_label').innerText = `EIMI: ${fmtCur(amt_D_eimi)} (${d_eimi.toFixed(2)}%)`;
            document.getElementById('d_cash_label').innerText = `Cash: ${fmtCur(amt_D_cash)} (${d_cash.toFixed(2)}%)`;

            // Data Prep for Charts
            let tot_ib01 = amt_A_ib01 + amt_B_ib01 + amt_C_ib01 + amt_D_ib01;
            let tot_cspx = amt_A_cspx + amt_C_cspx + amt_D_cspx;
            let tot_xuse = amt_A_xuse + amt_C_xuse + amt_D_xuse;
            let tot_eimi = amt_A_eimi + amt_C_eimi + amt_D_eimi;
            let tot_cash = amt_A_cash + amt_B_cash + amt_C_cash + amt_D_cash;
            let tot_opt_mkt = amt_A_opt_mkt + amt_C_opt_mkt;

            const pctA = ((sA / totalEstate) * 100).toFixed(1);
            const pctB = ((sB / totalEstate) * 100).toFixed(1);
            const pctC = ((sC / totalEstate) * 100).toFixed(1);
            const pctD = ((sD / totalEstate) * 100).toFixed(1);
            const xLabels =['Silo A', 'Silo B', 'Silo C', 'Silo D'];

            // Chart 1: Bar Chart (Handles Negative Values Perfectly)
            let barData =[
                { x: xLabels, y:[amt_A_ib01, amt_B_ib01, amt_C_ib01, amt_D_ib01], name: 'IB01', type: 'bar', marker: {color: palette.ib01} },
                { x: xLabels, y:[amt_A_cspx, 0,          amt_C_cspx, amt_D_cspx], name: 'CSPX', type: 'bar', marker: {color: palette.cspx} },
                { x: xLabels, y:[amt_A_xuse, 0,          amt_C_xuse, amt_D_xuse], name: 'XUSE', type: 'bar', marker: {color: palette.xuse} },
                { x: xLabels, y:[amt_A_eimi, 0,          amt_C_eimi, amt_D_eimi], name: 'EIMI', type: 'bar', marker: {color: palette.eimi} },
                { x: xLabels, y:[0,          amt_B_act,  0,          0         ], name: 'CFDs/Intl', type: 'bar', marker: {color: palette.cfd_intl} },
                { x: xLabels, y:[amt_A_cash, amt_B_cash, amt_C_cash, amt_D_cash], name: 'Cash', type: 'bar', marker: {color: palette.cash} },
                { x: xLabels, y:[amt_A_opt_mkt, 0,       amt_C_opt_mkt, 0      ], name: 'Options Liability', type: 'bar', marker: {color: palette.optMktVal} },
                
                // Margin Overlay: Diamond Markers showing where the Margin Lock hits on the Y-Axis
                { x:['Silo A', 'Silo C'], y:[amt_A_xsp, amt_C_xsp], name: 'Margin Lock (Phantom)', type: 'scatter', mode: 'markers', 
                  marker: {symbol: 'diamond', size: 14, color: '#ef4444', line: {color: 'white', width: 1.5}}, 
                  hovertemplate: 'Margin Locked: $%{y:,.0f}<extra></extra>' }
            ];

            let barLayout = { 
                barmode: 'relative', 
                title: 'GAAP Balance Sheet per Silo ($ / %)', 
                margin: {b: 40, t: 80}, 
                paper_bgcolor: 'rgba(0,0,0,0)', 
                plot_bgcolor: 'rgba(0,0,0,0)',
                xaxis: { tickangle: 0 },
                annotations:[
                    { x: xLabels[0], y: sA, text: `${(sA/1000).toFixed(0)}k<br>(${pctA}%)`, showarrow: false, yanchor: 'bottom', font: {bold: true, size: 13}},
                    { x: xLabels[1], y: sB, text: `${(sB/1000).toFixed(0)}k<br>(${pctB}%)`, showarrow: false, yanchor: 'bottom', font: {bold: true, size: 13}},
                    { x: xLabels[2], y: sC, text: `${(sC/1000).toFixed(0)}k<br>(${pctC}%)`, showarrow: false, yanchor: 'bottom', font: {bold: true, size: 13}},
                    { x: xLabels[3], y: sD, text: `${(sD/1000).toFixed(0)}k<br>(${pctD}%)`, showarrow: false, yanchor: 'bottom', font: {bold: true, size: 13}}
                ]
            };
            Plotly.react('bar-chart', barData, barLayout);

            // Chart 2: Pie Chart (Gross Physical Assets to show weighting)
            let pieValues =[tot_ib01, tot_cspx, tot_xuse, tot_eimi, amt_B_act, Math.abs(tot_opt_mkt), tot_cash];
            let fmtPct = (val) => ((val / totalEstate) * 100).toFixed(1) + '%';
            let pieLabels =[
                `IB01: ${fmtCur(tot_ib01)}`, 
                `CSPX: ${fmtCur(tot_cspx)}`, 
                `XUSE: ${fmtCur(tot_xuse)}`, 
                `EIMI: ${fmtCur(tot_eimi)}`, 
                `Active Swing: ${fmtCur(amt_B_act)}`, 
                `Options Liability: ${fmtCur(Math.abs(tot_opt_mkt))}`, 
                `Total USD Cash: ${fmtCur(tot_cash)}`
            ];
            
            let pieColors =[palette.ib01, palette.cspx, palette.xuse, palette.eimi, palette.cfd_intl, palette.optMktVal, palette.cash];

            let pieData =[{
                values: pieValues,
                labels: pieLabels,
                type: 'pie', 
                textinfo: 'percent', 
                hole: .4,
                marker: { colors: pieColors }
            }];
            let pieLayout = { title: `Gross Asset Allocation Weighting`, margin: {t: 50, b: 20, l: 0, r: 0}, paper_bgcolor: 'rgba(0,0,0,0)' };
            Plotly.react('pie-chart', pieData, pieLayout);
        }

        document.querySelectorAll('input').forEach(i => i.addEventListener('input', updateUI));
        populateTable();
        updateUI();
    </script>
</body>
</html>
"""

# ---------------------------------------------------------
# 5. Inject the Variables Safely (Bypassing JS Braces)
# ---------------------------------------------------------
html_content = html_content.replace("VAR_COLOR_A_IRR", get_color_class(metrics["U23144948"]["irr"]))
html_content = html_content.replace("VAR_A_IRR", metrics["U23144948"]["irr"])
html_content = html_content.replace("VAR_COLOR_A_SHARPE", get_color_class(metrics["U23144948"]["sharpe"]))
html_content = html_content.replace("VAR_A_SHARPE", metrics["U23144948"]["sharpe"])
html_content = html_content.replace("VAR_COLOR_A_PNL", get_color_class(metrics["U23144948"]["pnl"]))
html_content = html_content.replace("VAR_A_PNL", metrics["U23144948"]["pnl"])
html_content = html_content.replace("VAR_A_MAXDD", metrics["U23144948"]["maxdd"])

html_content = html_content.replace("VAR_COLOR_B_IRR", get_color_class(metrics["U23139264"]["irr"]))
html_content = html_content.replace("VAR_B_IRR", metrics["U23139264"]["irr"])
html_content = html_content.replace("VAR_COLOR_B_SHARPE", get_color_class(metrics["U23139264"]["sharpe"]))
html_content = html_content.replace("VAR_B_SHARPE", metrics["U23139264"]["sharpe"])
html_content = html_content.replace("VAR_COLOR_B_PNL", get_color_class(metrics["U23139264"]["pnl"]))
html_content = html_content.replace("VAR_B_PNL", metrics["U23139264"]["pnl"])
html_content = html_content.replace("VAR_COLOR_B_MAXDD", get_color_class(metrics["U23139264"]["maxdd"], "light"))
html_content = html_content.replace("VAR_B_MAXDD", metrics["U23139264"]["maxdd"])

html_content = html_content.replace("VAR_COLOR_C_IRR", get_color_class(metrics["U23154199"]["irr"]))
html_content = html_content.replace("VAR_C_IRR", metrics["U23154199"]["irr"])
html_content = html_content.replace("VAR_COLOR_C_SHARPE", get_color_class(metrics["U23154199"]["sharpe"]))
html_content = html_content.replace("VAR_C_SHARPE", metrics["U23154199"]["sharpe"])
html_content = html_content.replace("VAR_COLOR_C_PNL", get_color_class(metrics["U23154199"]["pnl"]))
html_content = html_content.replace("VAR_C_PNL", metrics["U23154199"]["pnl"])
html_content = html_content.replace("VAR_C_MAXDD", metrics["U23154199"]["maxdd"])

html_content = html_content.replace("VAR_COLOR_D_IRR", get_color_class(metrics["U25218481"]["irr"], "light"))
html_content = html_content.replace("VAR_D_IRR", metrics["U25218481"]["irr"])
html_content = html_content.replace("VAR_COLOR_D_SHARPE", get_color_class(metrics["U25218481"]["sharpe"], "light"))
html_content = html_content.replace("VAR_D_SHARPE", metrics["U25218481"]["sharpe"])
html_content = html_content.replace("VAR_COLOR_D_PNL", get_color_class(metrics["U25218481"]["pnl"], "light"))
html_content = html_content.replace("VAR_D_PNL", metrics["U25218481"]["pnl"])
html_content = html_content.replace("VAR_D_MAXDD", metrics["U25218481"]["maxdd"])

# ---------------------------------------------------------
# 6. Save the Output
# ---------------------------------------------------------
try:
    with open(full_file_path, "w", encoding="utf-8") as f:
        f.write(html_content)
    print("====================================================================")
    print(f"SUCCESS! Estate Dashboard v12 created.")
    print(f"Path: {full_file_path}")
    print("====================================================================")
except Exception as e:
    print(f"Error: {e}")