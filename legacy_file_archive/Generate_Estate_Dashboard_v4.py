r"""
=============================================================================
Script Name: Generate_Estate_Dashboard_v4.py
Purpose: Generates a standalone, interactive HTML dashboard for the Family 
         Estate. 
         VERSION 4: 
         - Explicitly integrates XSP vs. XND in the Master Instrument Matrix.
         - Adds structural UI placeholders for the upcoming Python IRR/Sharpe 
           data ingestion engine.
Author: Chief Investment Officer AI Advisor
Date: April 7, 2026

Target Path: C:\Users\donca\Desktop\Desktop HP Envy x360 al 22Abr24\Docs Manuel\IBKR_Options
=============================================================================
"""

import os

target_directory = r"C:\Users\donca\Desktop\Desktop HP Envy x360 al 22Abr24\Docs Manuel\IBKR_Options"
file_name = "Family_Estate_Dashboard_v4.html"
full_file_path = os.path.join(target_directory, file_name)

if not os.path.exists(target_directory):
    os.makedirs(target_directory)

html_content = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Family Estate Master Allocator v4</title>
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

    <div class="max-w-[1600px] mx-auto bg-white rounded-xl shadow-xl p-6 border border-gray-200">
        
        <div class="text-center mb-6">
            <h1 class="text-4xl font-extrabold text-gray-900 tracking-tight">Family Estate Master Dashboard</h1>
            <p class="text-gray-500 mt-2 font-medium">Silo Allocation & Institutional Instrument Matrix v4</p>
        </div>

        <!-- Performance Placeholders (To be populated by Python CSV Reader in future iteration) -->
        <div class="mb-8 grid grid-cols-1 md:grid-cols-4 gap-4">
            <div class="bg-blue-900 text-white p-4 rounded-xl shadow-md text-center">
                <h4 class="text-sm text-blue-200 uppercase tracking-widest font-bold">Silo A (Vault 1)</h4>
                <p class="text-xs text-blue-300 mb-1">U23144948</p>
                <div class="flex justify-between text-sm mt-2 border-t border-blue-700 pt-2">
                    <span>IRR: <span class="font-mono text-gray-400">Awaiting Data</span></span>
                    <span>Sharpe: <span class="font-mono text-gray-400">--</span></span>
                </div>
            </div>
            <div class="bg-purple-900 text-white p-4 rounded-xl shadow-md text-center">
                <h4 class="text-sm text-purple-200 uppercase tracking-widest font-bold">Silo B (Active)</h4>
                <p class="text-xs text-purple-300 mb-1">U23139264</p>
                <div class="flex justify-between text-sm mt-2 border-t border-purple-700 pt-2">
                    <span>IRR: <span class="font-mono text-gray-400">Awaiting Data</span></span>
                    <span>Sharpe: <span class="font-mono text-gray-400">--</span></span>
                </div>
            </div>
            <div class="bg-green-900 text-white p-4 rounded-xl shadow-md text-center">
                <h4 class="text-sm text-green-200 uppercase tracking-widest font-bold">Silo C (Options)</h4>
                <p class="text-xs text-green-300 mb-1">U23154199</p>
                <div class="flex justify-between text-sm mt-2 border-t border-green-700 pt-2">
                    <span>IRR: <span class="font-mono text-gray-400">Awaiting Data</span></span>
                    <span>Sharpe: <span class="font-mono text-gray-400">--</span></span>
                </div>
            </div>
            <div class="bg-indigo-900 text-white p-4 rounded-xl shadow-md text-center">
                <h4 class="text-sm text-indigo-200 uppercase tracking-widest font-bold">Silo D (Vault 2)</h4>
                <p class="text-xs text-indigo-300 mb-1">U25218481</p>
                <div class="flex justify-between text-sm mt-2 border-t border-indigo-700 pt-2">
                    <span>IRR: <span class="font-mono text-gray-400">Awaiting Data</span></span>
                    <span>Sharpe: <span class="font-mono text-gray-400">--</span></span>
                </div>
            </div>
        </div>

        <!-- Silo Inputs Section -->
        <div class="mb-8 bg-gray-50 p-4 rounded-xl border shadow-sm">
            <h3 class="text-xl font-bold mb-4 text-gray-800 border-b pb-2">1. Estate Capital (Adjustable Silo Balances)</h3>
            <div class="grid grid-cols-2 md:grid-cols-4 gap-4">
                <div><label class="block text-sm font-bold text-gray-700">Silo A ($) - Vault 1</label><input type="number" id="siloA" value="740000" class="mt-1 w-full rounded-md p-2 border"></div>
                <div><label class="block text-sm font-bold text-gray-700">Silo B ($) - Active</label><input type="number" id="siloB" value="30000" class="mt-1 w-full rounded-md p-2 border"></div>
                <div><label class="block text-sm font-bold text-gray-700">Silo C ($) - Options</label><input type="number" id="siloC" value="285000" class="mt-1 w-full rounded-md p-2 border"></div>
                <div><label class="block text-sm font-bold text-gray-700">Silo D ($) - Vault 2</label><input type="number" id="siloD" value="150000" class="mt-1 w-full rounded-md p-2 border"></div>
            </div>
        </div>

        <!-- Target Allocation Sliders -->
        <div class="mb-8 bg-white p-4 rounded-xl border shadow-sm">
            <h3 class="text-xl font-bold mb-4 text-gray-800 border-b pb-2">2. Target Portfolio Composition (%)</h3>
            
            <div class="grid grid-cols-1 lg:grid-cols-4 gap-4">
                
                <!-- Silo A -->
                <div class="bg-blue-50 p-3 rounded-lg border border-blue-200">
                    <h4 class="font-bold text-blue-900 mb-2 text-sm border-b border-blue-200 pb-1">Silo A (Vault 1)</h4>
                    <label class="text-xs font-semibold">IB01: <span id="a_ib01_val">40</span>%</label>
                    <input type="range" id="a_ib01" min="0" max="100" value="40" class="w-full mb-1" oninput="updateUI()">
                    
                    <label class="text-xs font-semibold">CSPX: <span id="a_cspx_val">30</span>%</label>
                    <input type="range" id="a_cspx" min="0" max="100" value="30" class="w-full mb-1" oninput="updateUI()">
                    
                    <label class="text-xs font-semibold">XUSE: <span id="a_xuse_val">15</span>%</label>
                    <input type="range" id="a_xuse" min="0" max="100" value="15" class="w-full mb-1" oninput="updateUI()">
                    
                    <label class="text-xs font-semibold">EIMI: <span id="a_eimi_val">5</span>%</label>
                    <input type="range" id="a_eimi" min="0" max="100" value="5" class="w-full mb-1" oninput="updateUI()">
                    
                    <label class="text-xs font-semibold">Cash: <span id="a_cash_val">10</span>%</label>
                    <input type="range" id="a_cash" min="0" max="100" value="10" class="w-full mb-1" oninput="updateUI()">
                    <p class="text-xs text-red-600 font-bold mt-1 h-4" id="a_warning"></p>
                </div>

                <!-- Silo B -->
                <div class="bg-purple-50 p-3 rounded-lg border border-purple-200">
                    <h4 class="font-bold text-purple-900 mb-2 text-sm border-b border-purple-200 pb-1">Silo B (Active)</h4>
                    <label class="text-xs font-semibold">Cash (PDT Buffer): <span id="b_cash_val">85</span>%</label>
                    <input type="range" id="b_cash" min="0" max="100" value="85" class="w-full mb-1" oninput="updateUI()">
                    
                    <label class="text-xs font-semibold">CFDs / Intl Stocks: <span id="b_active_val">15</span>%</label>
                    <input type="range" id="b_active" min="0" max="100" value="15" class="w-full mb-1" oninput="updateUI()">
                    <p class="text-xs text-red-600 font-bold mt-1 h-4" id="b_warning"></p>
                </div>

                <!-- Silo C -->
                <div class="bg-green-50 p-3 rounded-lg border border-green-200">
                    <h4 class="font-bold text-green-900 mb-2 text-sm border-b border-green-200 pb-1">Silo C (Options)</h4>
                    <label class="text-xs font-semibold">XSP / XND Margin: <span id="c_dep_val">50</span>%</label>
                    <input type="range" id="c_dep" min="0" max="100" value="50" class="w-full mb-1" oninput="updateUI()">
                    
                    <label class="text-xs font-semibold">Black Swan Cash: <span id="c_cash_val">50</span>%</label>
                    <input type="range" id="c_cash" min="0" max="100" value="50" class="w-full mb-1" oninput="updateUI()">
                    <p class="text-xs text-red-600 font-bold mt-1 h-4" id="c_warning"></p>
                </div>

                <!-- Silo D -->
                <div class="bg-indigo-50 p-3 rounded-lg border border-indigo-200">
                    <h4 class="font-bold text-indigo-900 mb-2 text-sm border-b border-indigo-200 pb-1">Silo D (Vault 2)</h4>
                    <label class="text-xs font-semibold">IB01: <span id="d_ib01_val">40</span>%</label>
                    <input type="range" id="d_ib01" min="0" max="100" value="40" class="w-full mb-1" oninput="updateUI()">
                    
                    <label class="text-xs font-semibold">CSPX: <span id="d_cspx_val">30</span>%</label>
                    <input type="range" id="d_cspx" min="0" max="100" value="30" class="w-full mb-1" oninput="updateUI()">
                    
                    <label class="text-xs font-semibold">XUSE: <span id="d_xuse_val">15</span>%</label>
                    <input type="range" id="d_xuse" min="0" max="100" value="15" class="w-full mb-1" oninput="updateUI()">
                    
                    <label class="text-xs font-semibold">EIMI: <span id="d_eimi_val">5</span>%</label>
                    <input type="range" id="d_eimi" min="0" max="100" value="5" class="w-full mb-1" oninput="updateUI()">
                    
                    <label class="text-xs font-semibold">Cash: <span id="d_cash_val">10</span>%</label>
                    <input type="range" id="d_cash" min="0" max="100" value="10" class="w-full mb-1" oninput="updateUI()">
                    <p class="text-xs text-red-600 font-bold mt-1 h-4" id="d_warning"></p>
                </div>
            </div>
        </div>

        <!-- Charts -->
        <div class="grid grid-cols-1 xl:grid-cols-2 gap-8 mb-10">
            <div class="bg-white border rounded-xl p-4 shadow-sm"><div id="bar-chart" class="w-full h-[450px]"></div></div>
            <div class="bg-white border rounded-xl p-4 shadow-sm"><div id="pie-chart" class="w-full h-[450px]"></div></div>
        </div>

        <!-- Instrument Matrix -->
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
                        <!-- Populated by JS -->
                    </tbody>
                </table>
            </div>
        </div>

    </div>

    <script>
        const palette = {
            ib01: '#0284c7',       
            cspx: '#f97316',       
            xuse: '#16a34a',       
            eimi: '#dc2626',       
            vaultCash: '#64748b',  
            cfd: '#a855f7',        
            pdtCash: '#cbd5e1',    
            xspMargin: '#22c55e',  
            swanCash: '#0f172a'    
        };

        const instruments =[
            { inst: "USD Cash", type: "Currency", risk: "Risk-Free (Nominal)", alpha: "Zero", sharpe: "Massive Stabilizer (Drawdown Buffer)", strat: "Liquidity / Collateral", jur: "US (IBKR Custody)", min: "10%", max: "50%", rec: "Splendid", class: "splendid", 
              comm: "<strong>Uninvested US Dollars held in IBKR account.</strong><br>MANDATORY collateral for Options Silo C to avoid margin loans. The first $10k earns 0% interest; the rest earns ~4.5%. Prevents absolute ruin." },
              
            { inst: "XSP (S&P 500) Put Spreads", type: "Index Option", risk: "Moderate (Tail Risk)", alpha: "High (VRP)", sharpe: "High (Smooths equity curve)", strat: "Weekly Income (45 DTE)", jur: "US (Cboe)", min: "0%", max: "20%", rec: "Splendid", class: "splendid", 
              comm: "<strong>Cash-settled S&P 500 options. The bedrock income engine.</strong><br>1,000% safe from IRS. Capped risk. The 20% limit ensures a Black Swan only causes a highly manageable ~10% portfolio drawdown." },

            { inst: "XND (Nasdaq 100) Put Spreads", type: "Index Option", risk: "Moderate-High", alpha: "Very High (Vega)", sharpe: "Moderate (Faster Gamma)", strat: "Weekly Income (45 DTE)", jur: "US (Cboe)", min: "0%", max: "5%", rec: "Great", class: "great", 
              comm: "<strong>Cash-settled Micro-Nasdaq 100 options. The high-beta engine.</strong><br>1,000% safe from IRS. Pays significantly higher premium than XSP due to tech volatility, but drops much faster during corrections. Use as a satellite to XSP." },
            
            { inst: "IB01", type: "UCITS ETF", risk: "Risk-Free", alpha: "Zero", sharpe: "High (Zero volatility anchor)", strat: "Long Term Holding", jur: "Ireland (LSE)", min: "0%", max: "100%", rec: "Splendid", class: "splendid", 
              comm: "<strong>Accumulating Irish-domiciled short-term US Treasury fund.</strong><br>Ultimate USD parking vault for Silos A & D. Accumulates 4.5%+ interest tax-free. Allocation can be 100% during extreme macro uncertainty." },
            
            { inst: "CSPX", type: "UCITS ETF", risk: "Moderate (Market)", alpha: "Zero (Beta 1)", sharpe: "Baseline (Market Beta)", strat: "Long Term DCA", jur: "Ireland (LSE)", min: "0%", max: "60%", rec: "Great", class: "great", 
              comm: "<strong>Accumulating Irish-domiciled S&P 500 equity fund.</strong><br>Shields S&P 500 gains from 40% Estate Tax and 30% Dividend Withholding. 60% limit ensures the estate isn't completely overweight in the USA." },
            
            { inst: "XUSE & EIMI", type: "UCITS ETF", risk: "Moderate", alpha: "Moderate", sharpe: "High (Non-US Correlation)", strat: "Long Term DCA", jur: "Ireland (LSE)", min: "0%", max: "40%", rec: "Great", class: "great", 
              comm: "<strong>Accumulating Irish-domiciled Developed (Ex-US) and Emerging Market funds.</strong><br>True geographic diversification. Hedges against US Dollar decline. Balances the massive US bias in the rest of the portfolio." },
            
            { inst: "US Tech CFDs", type: "OTC Contract", risk: "Aggressive", alpha: "High (If Skilled)", sharpe: "Negative (Increases volatility)", strat: "Swing Trading", jur: "UK/Offshore", min: "0%", max: "3%", rec: "Good", class: "good", 
              comm: "<strong>Over-The-Counter synthetic derivatives tracking physical US tech stocks.</strong><br>0% IRS Estate Tax risk. Subject to overnight margin fees. 3% limit strictly quarantines aggressive Minervini/Champion trades in Silo B." },
            
            { inst: "XSP LEAPS", type: "Index Option", risk: "High (Time Risk)", alpha: "High (Leverage)", sharpe: "Negative (High leverage variance)", strat: "Multi-Year Swing", jur: "US (Cboe)", min: "0%", max: "10%", rec: "Good", class: "good", 
              comm: "<strong>Deep In-The-Money Call options expiring in 1 to 3 years.</strong><br>Capital efficient stock replacement safe from IRS. Suffers from 3.5% annual time/dividend drag. Strict 10% limit to prevent excessive Theta exposure." },
            
            { inst: "Intl Stocks (Direct)", type: "Stock", risk: "Aggressive", alpha: "High", sharpe: "Negative", strat: "Swing Trading", jur: "Europe/Asia", min: "0%", max: "3%", rec: "Neutral", class: "good", 
              comm: "<strong>Direct ownership of non-US physical equities.</strong><br>Safe from IRS. Wider bid/ask spreads and liquidity constraints compared to US Tech. Same 3% quarantine limit as CFDs." },
            
            { inst: "US Corp Bonds", type: "Bond/Stock", risk: "Moderate", alpha: "Negative", sharpe: "Negative (Credit Widening Risk)", strat: "Income", jur: "US / Ireland", min: "0%", max: "0%", rec: "Bad", class: "bad", 
              comm: "<strong>Debt issued by US corporations, or ETFs holding dividend-yielding equities.</strong><br>Di-worsification. Crashes during Black Swans alongside stocks. 0% allocation because tax drag on yields is too severe for NRAs." },
            
            { inst: "Physical US Stocks", type: "Stock", risk: "Aggressive", alpha: "High", sharpe: "Baseline", strat: "Swing / Hold", jur: "US (Nasdaq)", min: "0%", max: "0%", rec: "Avoid", class: "avoid", 
              comm: "<strong>Direct ownership of shares traded on US exchanges (e.g., AAPL, TSLA, SPY).</strong><br>LETHAL. Triggers 40% US Estate Tax and 30% Dividend Withholding. 0% absolute prohibition for Dominican Republic residents." },
            
            { inst: "US Stock Options", type: "Option", risk: "Extreme", alpha: "High", sharpe: "Negative", strat: "Speculation", jur: "US (Cboe)", min: "0%", max: "0%", rec: "Avoid", class: "avoid", 
              comm: "<strong>Contracts granting the right to buy/sell physical US property.</strong><br>LETHAL. IRS gray area. Brokers will aggressively freeze the account for months upon death. 0% absolute prohibition." }
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
                    <td class="py-3 px-3 font-bold text-center">${i.min}</td>
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

            let a_ib01 = parseFloat(document.getElementById('a_ib01').value);
            let a_cspx = parseFloat(document.getElementById('a_cspx').value);
            let a_xuse = parseFloat(document.getElementById('a_xuse').value);
            let a_eimi = parseFloat(document.getElementById('a_eimi').value);
            let a_cash = parseFloat(document.getElementById('a_cash').value);
            let a_tot = a_ib01 + a_cspx + a_xuse + a_eimi + a_cash;
            document.getElementById('a_warning').innerText = a_tot !== 100 ? `Total: ${a_tot}%. Must = 100%!` : "";
            document.getElementById('a_ib01_val').innerText = a_ib01; document.getElementById('a_cspx_val').innerText = a_cspx;
            document.getElementById('a_xuse_val').innerText = a_xuse; document.getElementById('a_eimi_val').innerText = a_eimi; document.getElementById('a_cash_val').innerText = a_cash;

            let b_cash = parseFloat(document.getElementById('b_cash').value);
            let b_active = parseFloat(document.getElementById('b_active').value);
            document.getElementById('b_warning').innerText = (b_cash + b_active) !== 100 ? `Total: ${b_cash + b_active}%. Must = 100%!` : "";
            document.getElementById('b_cash_val').innerText = b_cash; document.getElementById('b_active_val').innerText = b_active;

            let c_dep = parseFloat(document.getElementById('c_dep').value);
            let c_cash = parseFloat(document.getElementById('c_cash').value);
            document.getElementById('c_warning').innerText = (c_dep + c_cash) !== 100 ? `Total: ${c_dep + c_cash}%. Must = 100%!` : "";
            document.getElementById('c_dep_val').innerText = c_dep; document.getElementById('c_cash_val').innerText = c_cash;

            let d_ib01 = parseFloat(document.getElementById('d_ib01').value);
            let d_cspx = parseFloat(document.getElementById('d_cspx').value);
            let d_xuse = parseFloat(document.getElementById('d_xuse').value);
            let d_eimi = parseFloat(document.getElementById('d_eimi').value);
            let d_cash = parseFloat(document.getElementById('d_cash').value);
            let d_tot = d_ib01 + d_cspx + d_xuse + d_eimi + d_cash;
            document.getElementById('d_warning').innerText = d_tot !== 100 ? `Total: ${d_tot}%. Must = 100%!` : "";
            document.getElementById('d_ib01_val').innerText = d_ib01; document.getElementById('d_cspx_val').innerText = d_cspx;
            document.getElementById('d_xuse_val').innerText = d_xuse; document.getElementById('d_eimi_val').innerText = d_eimi; document.getElementById('d_cash_val').innerText = d_cash;

            const amt_A_ib01 = sA * (a_ib01/100); const amt_A_cspx = sA * (a_cspx/100); const amt_A_xuse = sA * (a_xuse/100); const amt_A_eimi = sA * (a_eimi/100); const amt_A_cash = sA * (a_cash/100);
            const amt_D_ib01 = sD * (d_ib01/100); const amt_D_cspx = sD * (d_cspx/100); const amt_D_xuse = sD * (d_xuse/100); const amt_D_eimi = sD * (d_eimi/100); const amt_D_cash = sD * (d_cash/100);
            
            const amt_B_cash = sB * (b_cash/100); const amt_B_act = sB * (b_active/100);
            const amt_C_dep = sC * (c_dep/100);   const amt_C_cash = sC * (c_cash/100);

            // Chart 1: Bar Chart Data Preparation
            const xLabels =['Silo A<br>(Vault 1)', 'Silo B<br>(Active)', 'Silo C<br>(Options)', 'Silo D<br>(Vault 2)'];
            let barData =[
                { x: xLabels, y:[amt_A_ib01, 0, 0, amt_D_ib01], name: 'IB01', type: 'bar', marker: {color: palette.ib01} },
                { x: xLabels, y:[amt_A_cspx, 0, 0, amt_D_cspx], name: 'CSPX', type: 'bar', marker: {color: palette.cspx} },
                { x: xLabels, y:[amt_A_xuse, 0, 0, amt_D_xuse], name: 'XUSE', type: 'bar', marker: {color: palette.xuse} },
                { x: xLabels, y:[amt_A_eimi, 0, 0, amt_D_eimi], name: 'EIMI', type: 'bar', marker: {color: palette.eimi} },
                { x: xLabels, y:[0, amt_B_act, 0, 0], name: 'CFDs/Intl', type: 'bar', marker: {color: palette.cfd} },
                { x: xLabels, y:[0, 0, amt_C_dep, 0], name: 'XSP / XND Options', type: 'bar', marker: {color: palette.xspMargin} },
                { x: xLabels, y:[amt_A_cash, 0, 0, amt_D_cash], name: 'Vault Cash', type: 'bar', marker: {color: palette.vaultCash} },
                { x: xLabels, y:[0, amt_B_cash, 0, 0], name: 'PDT Buffer', type: 'bar', marker: {color: palette.pdtCash} },
                { x: xLabels, y:[0, 0, amt_C_cash, 0], name: 'Black Swan Cash', type: 'bar', marker: {color: palette.swanCash} }
            ];

            // Calculate dynamic percentages and labels for the Bar Chart
            const pctA = ((sA / totalEstate) * 100).toFixed(2);
            const pctB = ((sB / totalEstate) * 100).toFixed(2);
            const pctC = ((sC / totalEstate) * 100).toFixed(2);
            const pctD = ((sD / totalEstate) * 100).toFixed(2);

            let barLayout = { 
                barmode: 'stack', 
                title: 'Capital Deployment per Silo ($ / %)', 
                margin: {b: 60, t: 80}, 
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

            // Chart 2: Pie Chart
            let tot_ib01 = amt_A_ib01 + amt_D_ib01;
            let tot_cspx = amt_A_cspx + amt_D_cspx;
            let tot_xuse = amt_A_xuse + amt_D_xuse;
            let tot_eimi = amt_A_eimi + amt_D_eimi;
            let tot_cash = amt_A_cash + amt_D_cash + amt_B_cash + amt_C_cash;

            let pieValues =[tot_ib01, tot_cspx, tot_xuse, tot_eimi, amt_B_act, amt_C_dep, tot_cash];
            let fmtPct = (val) => ((val / totalEstate) * 100).toFixed(1) + '%';
            let pieLabels =[
                `IB01 (${fmtPct(tot_ib01)})`, 
                `CSPX (${fmtPct(tot_cspx)})`, 
                `XUSE (${fmtPct(tot_xuse)})`, 
                `EIMI (${fmtPct(tot_eimi)})`, 
                `Active Swing (${fmtPct(amt_B_act)})`, 
                `Options Deployed (${fmtPct(amt_C_dep)})`, 
                `Total USD Cash (${fmtPct(tot_cash)})`
            ];
            
            let pieColors =[palette.ib01, palette.cspx, palette.xuse, palette.eimi, palette.cfd, palette.xspMargin, palette.vaultCash];

            let pieData =[{
                values: pieValues,
                labels: pieLabels,
                type: 'pie', 
                textinfo: 'percent', 
                hole: .4,
                marker: { colors: pieColors }
            }];
            let pieLayout = { title: `Total Estate Exposure ($${totalEstate.toLocaleString()})`, margin: {t: 50, b: 20, l: 0, r: 0}, paper_bgcolor: 'rgba(0,0,0,0)' };
            Plotly.react('pie-chart', pieData, pieLayout);
        }

        document.querySelectorAll('input').forEach(i => i.addEventListener('input', updateUI));
        populateTable();
        updateUI();
    </script>
</body>
</html>
"""

try:
    with open(full_file_path, "w", encoding="utf-8") as f:
        f.write(html_content)
    print("====================================================================")
    print(f"SUCCESS! Estate Dashboard v4 created.")
    print(f"Path: {full_file_path}")
    print("====================================================================")
except Exception as e:
    print(f"Error: {e}")