r"""
=============================================================================
Script Name: Generate_Long_Call_Visualizer_v2.py
Purpose: Generates a unified, interactive HTML dashboard to visualize 
         LONG CALL Options (Buying Options). 
         VERSION 2: Now includes dynamic Unrealized P&L Percentage.
Author: Chief Investment Officer AI Advisor
Date: April 2026

Target Path: C:\Users\donca\Desktop\Desktop HP Envy x360 al 22Abr24\Docs Manuel\IBKR_Options
=============================================================================
"""

import os

# Define the exact path using a raw string
target_directory = r"C:\Users\donca\Desktop\Desktop HP Envy x360 al 22Abr24\Docs Manuel\IBKR_Options"
file_name = "Long_Call_Visualizer_v2.html"
full_file_path = os.path.join(target_directory, file_name)

# Create the directory if it does not exist
if not os.path.exists(target_directory):
    os.makedirs(target_directory)

# The Unified HTML, CSS, and JS payload for a LONG CALL
html_content = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Long Call Option Visualizer v2</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <script src="https://cdn.plot.ly/plotly-2.24.1.min.js"></script>
    <style>
        body { transition: background-color 0.5s ease; }
        .profit-bg { background-color: #f0fdf4; }
        .loss-bg { background-color: #fef2f2; }   
        .neutral-bg { background-color: #f8fafc; }
    </style>
</head>
<body id="main-body" class="neutral-bg text-gray-800 font-sans p-4 md:p-8">

    <div class="max-w-[1400px] mx-auto bg-white rounded-xl shadow-xl p-6 md:p-8 border border-gray-200">
        
        <!-- Header & P&L Display -->
        <div class="text-center mb-8">
            <h1 class="text-4xl font-extrabold text-gray-900 tracking-tight">Long Call (Buyer) Master Visualizer</h1>
            <p class="text-gray-500 mt-2 font-medium">Demonstrating the Impact of Time Decay & Volatility on Bought Options</p>
            
            <div class="mt-6 p-6 rounded-xl border-2 inline-block min-w-[300px]" id="pnl-container">
                <h2 class="text-lg font-bold text-gray-500 uppercase tracking-wider">Unrealized P&L</h2>
                <p id="display-pnl" class="text-6xl font-black mt-2">$0.00</p>
                <p id="display-pnl-pct" class="text-2xl font-bold mt-1">(0.00%)</p>
                <p id="display-option-price" class="text-gray-600 mt-3 font-medium">Current Contract Value: $0.00</p>
            </div>
        </div>

        <!-- Charts Grid -->
        <div class="grid grid-cols-1 xl:grid-cols-2 gap-8 mb-10">
            <!-- 2D Chart -->
            <div class="bg-gray-50 border rounded-xl p-2 shadow-inner">
                <div id="plotly-2d" class="w-full h-[500px]"></div>
            </div>
            <!-- 3D Chart -->
            <div class="bg-gray-50 border rounded-xl p-2 shadow-inner">
                <div id="plotly-3d" class="w-full h-[500px]"></div>
            </div>
        </div>

        <!-- Inputs Section -->
        <div class="mb-10 bg-gray-50 p-6 rounded-xl border">
            <h3 class="text-2xl font-bold mb-6 text-gray-800 border-b pb-2">Manual Inputs (The Trade)</h3>
            <div class="grid grid-cols-2 md:grid-cols-4 gap-6">
                <div>
                    <label class="block text-sm font-bold text-gray-700">Ticker</label>
                    <input type="text" id="in_ticker" value="HAL" class="mt-1 block w-full rounded-md border-gray-300 shadow-sm p-2 border focus:ring-blue-500 focus:border-blue-500">
                </div>
                <div>
                    <label class="block text-sm font-bold text-gray-700">Current Stock Price ($)</label>
                    <input type="number" id="in_price" value="61.0" step="0.5" class="mt-1 block w-full rounded-md border-gray-300 shadow-sm p-2 border">
                </div>
                <div>
                    <label class="block text-sm font-bold text-gray-700">Call Strike Price ($)</label>
                    <input type="number" id="in_strike" value="60" step="1" class="mt-1 block w-full rounded-md border-gray-300 shadow-sm p-2 border">
                </div>
                <div>
                    <label class="block text-sm font-bold text-gray-700">Quantity of Contracts</label>
                    <input type="number" id="in_qty" value="1" step="1" class="mt-1 block w-full rounded-md border-gray-300 shadow-sm p-2 border">
                </div>
                <div>
                    <label class="block text-sm font-bold text-gray-700">Premium PAID ($)</label>
                    <input type="number" id="in_prem" value="8.00" step="0.01" class="mt-1 block w-full rounded-md border-gray-300 shadow-sm p-2 border">
                </div>
                <div>
                    <label class="block text-sm font-bold text-gray-700">Initial DTE (Entry)</label>
                    <input type="number" id="in_initial_dte" value="270" step="1" class="mt-1 block w-full rounded-md border-gray-300 shadow-sm p-2 border">
                </div>
                <div>
                    <label class="block text-sm font-bold text-gray-700">Current DTE (Today)</label>
                    <input type="number" id="in_current_dte" value="260" step="1" class="mt-1 block w-full rounded-md border-gray-300 shadow-sm p-2 border">
                </div>
                <div>
                    <label class="block text-sm font-bold text-gray-700">Implied Volatility (%)</label>
                    <input type="number" id="in_iv" value="35" step="0.5" class="mt-1 block w-full rounded-md border-gray-300 shadow-sm p-2 border">
                </div>
            </div>
        </div>

        <!-- Greeks Table -->
        <div class="mb-10">
            <h3 class="text-2xl font-bold mb-6 text-gray-800 border-b pb-2">Position Greeks (Net of Contract x Quantity)</h3>
            <div class="overflow-x-auto shadow-sm rounded-lg border">
                <table class="min-w-full bg-white">
                    <thead class="bg-slate-800 text-white">
                        <tr>
                            <th class="py-3 px-4 text-left font-semibold">Net Delta</th>
                            <th class="py-3 px-4 text-left font-semibold">Net Gamma</th>
                            <th class="py-3 px-4 text-left font-semibold bg-red-900">Net Theta (Daily Bleed)</th>
                            <th class="py-3 px-4 text-left font-semibold">Net Vega</th>
                            <th class="py-3 px-4 text-left font-semibold bg-red-900">Max Capital at Risk ($)</th>
                        </tr>
                    </thead>
                    <tbody class="divide-y divide-gray-200">
                        <tr class="hover:bg-gray-50">
                            <td id="out_delta" class="py-4 px-4 font-mono text-lg font-bold text-gray-700">0.00</td>
                            <td id="out_gamma" class="py-4 px-4 font-mono text-lg font-bold text-gray-700">0.00</td>
                            <td id="out_theta" class="py-4 px-4 font-mono text-lg font-black text-red-600">0.00</td>
                            <td id="out_vega" class="py-4 px-4 font-mono text-lg font-bold text-blue-600">0.00</td>
                            <td id="out_margin" class="py-4 px-4 font-mono text-lg font-black text-red-600">0.00</td>
                        </tr>
                    </tbody>
                </table>
            </div>
        </div>

        <!-- Educational Footer (For the Buyer) -->
        <div class="bg-red-50 border border-red-200 rounded-xl p-6 text-sm text-red-900">
            <h4 class="font-bold text-lg mb-3 uppercase tracking-wide">The Buyer's Guide: Why Most Long Calls Lose Money</h4>
            <div class="grid grid-cols-1 md:grid-cols-2 gap-6">
                <div>
                    <p class="mb-2"><strong class="text-red-700 bg-red-100 px-1 rounded">Delta (Direction):</strong> As a buyer, you need the stock to move aggressively in your direction. If HAL stays exactly at $61, you don't break even—you lose your entire $800 premium because of time decay.</p>
                    <p><strong class="text-red-700 bg-red-100 px-1 rounded">Break-Even Point:</strong> You paid $8.00 for the $60 strike. Your true break-even is $68.00 at expiration. The stock must rise 11% just for you to get your money back.</p>
                </div>
                <div>
                    <p class="mb-2"><strong class="text-red-700 bg-red-100 px-1 rounded">Theta (The Silent Killer):</strong> Because you *bought* the option, Theta is negative. This is the amount of cash bleeding out of your contract every single day. If the stock chops sideways, Theta eats your investment down to zero.</p>
                    <p><strong class="text-red-700 bg-red-100 px-1 rounded">Vega (Volatility Risk):</strong> You bought when the war in Iran caused panic (high IV). If the war resolves, IV will "crush". Even if the stock goes up to $65, a drop in Vega can cause your option to lose value. You are fighting both Time and Fear.</p>
                </div>
            </div>
        </div>

    </div>

    <script>
        // Black-Scholes Math Engine for CALLS
        function normCDF(x) {
            let t = 1 / (1 + 0.2316419 * Math.abs(x));
            let d = 0.3989423 * Math.exp(-x * x / 2);
            let prob = d * t * (0.3193815 + t * (-0.3565638 + t * (1.781478 + t * (-1.821256 + t * 1.330274))));
            return x > 0 ? 1 - prob : prob;
        }
        function normPDF(x) { return Math.exp(-0.5 * x * x) / Math.sqrt(2 * Math.PI); }
        
        function getCallGreeks(S, K, T, r, v) {
            if (T <= 0.0001) {
                let p = Math.max(S - K, 0);
                return { price: p, delta: S > K ? 1 : 0, gamma: 0, vega: 0, theta: 0 };
            }
            let d1 = (Math.log(S/K) + (r + v*v/2)*T) / (v * Math.sqrt(T));
            let d2 = d1 - v * Math.sqrt(T);
            
            let price = S * normCDF(d1) - K * Math.exp(-r*T) * normCDF(d2);
            let delta = normCDF(d1);
            let gamma = normPDF(d1) / (S * v * Math.sqrt(T));
            let vega = (S * normPDF(d1) * Math.sqrt(T)) / 100;
            let theta = (- (S * v * normPDF(d1)) / (2 * Math.sqrt(T)) - r * K * Math.exp(-r*T) * normCDF(d2)) / 365;
            
            return { price, delta, gamma, vega, theta };
        }

        function updateDashboard() {
            // Fetch Inputs
            let S = parseFloat(document.getElementById('in_price').value);
            let K = parseFloat(document.getElementById('in_strike').value);
            let init_dte = parseFloat(document.getElementById('in_initial_dte').value);
            let curr_dte = parseFloat(document.getElementById('in_current_dte').value);
            let qty = parseFloat(document.getElementById('in_qty').value);
            let prem_paid = parseFloat(document.getElementById('in_prem').value);
            let iv = parseFloat(document.getElementById('in_iv').value) / 100;
            let r = 0.045; // 4.5% Risk Free
            
            let T_init = init_dte / 365;
            let T_curr = curr_dte / 365;

            // Calculate Current Greeks
            let callOpt = getCallGreeks(S, K, T_curr, r, iv);

            // Long Call Math
            let currentCallPrice = callOpt.price;
            let unrealizedPnL = (currentCallPrice - prem_paid) * qty * 100;
            
            let netDelta = callOpt.delta * qty * 100;
            let netGamma = callOpt.gamma * qty * 100;
            let netTheta = callOpt.theta * qty * 100;
            let netVega =  callOpt.vega * qty * 100;
            let maxLoss = prem_paid * qty * 100; 
            
            // Calculate P&L Percentage (Return on Premium Paid)
            let pnlPercent = (maxLoss > 0) ? (unrealizedPnL / maxLoss) * 100 : 0;

            // Update UI
            document.getElementById('display-option-price').innerText = "Current Contract Value: $" + currentCallPrice.toFixed(2);
            document.getElementById('out_delta').innerText = netDelta.toFixed(2);
            document.getElementById('out_gamma').innerText = netGamma.toFixed(4);
            document.getElementById('out_theta').innerText = "-$" + Math.abs(netTheta).toFixed(2); 
            document.getElementById('out_vega').innerText = "$" + netVega.toFixed(2);
            document.getElementById('out_margin').innerText = "$" + maxLoss.toLocaleString();

            let pnlEl = document.getElementById('display-pnl');
            let pnlPctEl = document.getElementById('display-pnl-pct');
            let bodyEl = document.getElementById('main-body');
            let pnlBox = document.getElementById('pnl-container');
            
            pnlEl.innerText = (unrealizedPnL >= 0 ? "+$" : "-$") + Math.abs(unrealizedPnL).toLocaleString(undefined, {minimumFractionDigits: 2, maximumFractionDigits:2});
            pnlPctEl.innerText = (unrealizedPnL >= 0 ? "(+" : "(-") + Math.abs(pnlPercent).toFixed(2) + "%)";

            if (unrealizedPnL > 0) {
                bodyEl.className = "profit-bg text-gray-800 font-sans p-4 md:p-8";
                pnlEl.className = "text-6xl font-black mt-2 text-green-600";
                pnlPctEl.className = "text-2xl font-bold mt-1 text-green-600";
                pnlBox.className = "mt-6 p-6 rounded-xl border-2 border-green-400 bg-green-50 inline-block min-w-[300px] shadow-sm";
            } else if (unrealizedPnL < 0) {
                bodyEl.className = "loss-bg text-gray-800 font-sans p-4 md:p-8";
                pnlEl.className = "text-6xl font-black mt-2 text-red-600";
                pnlPctEl.className = "text-2xl font-bold mt-1 text-red-600";
                pnlBox.className = "mt-6 p-6 rounded-xl border-2 border-red-400 bg-red-50 inline-block min-w-[300px] shadow-sm";
            } else {
                bodyEl.className = "neutral-bg text-gray-800 font-sans p-4 md:p-8";
                pnlEl.className = "text-6xl font-black mt-2 text-gray-700";
                pnlPctEl.className = "text-2xl font-bold mt-1 text-gray-700";
                pnlBox.className = "mt-6 p-6 rounded-xl border-2 border-gray-300 bg-gray-100 inline-block min-w-[300px] shadow-sm";
            }

            // ==========================================
            // BUILD 2D CHART
            // ==========================================
            let x_vals = [], y_init = [], y_curr =[], y_exp =[];
            let min_plot = K * 0.7; 
            let max_plot = K * 1.5; 
            
            for(let p = min_plot; p <= max_plot; p += 0.5) {
                x_vals.push(p);
                y_exp.push((Math.max(p - K, 0) - prem_paid) * qty * 100);
                
                let init_c = getCallGreeks(p, K, T_init, r, iv);
                y_init.push((init_c.price - prem_paid) * qty * 100);

                let curr_c = getCallGreeks(p, K, T_curr, r, iv);
                y_curr.push((curr_c.price - prem_paid) * qty * 100);
            }

            let trace_exp = { x: x_vals, y: y_exp, type: 'scatter', mode: 'lines', name: 'Expiration', line: {color: 'gray', dash: 'dash'} };
            let trace_init = { x: x_vals, y: y_init, type: 'scatter', mode: 'lines', name: 'T-Initial (Entry Day)', line: {color: 'orange', width: 2, dash: 'dot'} };
            let trace_curr = { x: x_vals, y: y_curr, type: 'scatter', mode: 'lines', name: 'T+0 (Today)', line: {color: 'blue', width: 3} };
            let trace_dot = { x: [S], y:[unrealizedPnL], type: 'scatter', mode: 'markers', name: 'Current Price', marker: {color: 'black', size: 10} };

            Plotly.react('plotly-2d',[trace_exp, trace_init, trace_curr, trace_dot], {
                title: '2D Profile: The Theta Bleed (Long Call)', xaxis: {title: 'Underlying Stock Price ($)'}, yaxis: {title: 'P&L ($)'},
                margin: {l: 50, r: 20, t: 40, b: 40}, paper_bgcolor: 'rgba(0,0,0,0)', plot_bgcolor: 'rgba(0,0,0,0)',
                shapes:[{type: 'line', x0: min_plot, x1: max_plot, y0: 0, y1: 0, line:{color: 'black', width: 1}}],
                legend: { orientation: 'h', y: -0.2 }
            }, {responsive: true});

            // ==========================================
            // BUILD 3D CHART
            // ==========================================
            let x_3d =[]; let y_3d =[]; let z_3d =[];
            for(let d = init_dte; d >= 0; d -= Math.max(1, Math.floor(init_dte/15))) {
                y_3d.push(d);
                let z_row =[];
                let T = d / 365;
                for(let p = min_plot; p <= max_plot; p += 1) {
                    if (y_3d.length === 1) x_3d.push(p);
                    if (T <= 0.0001) {
                        z_row.push((Math.max(p - K, 0) - prem_paid) * qty * 100);
                    } else {
                        let t0_c = getCallGreeks(p, K, T, r, iv);
                        z_row.push((t0_c.price - prem_paid) * qty * 100);
                    }
                }
                z_3d.push(z_row);
            }

            let trace_surface = {
                z: z_3d, x: x_3d, y: y_3d, type: 'surface',
                colorscale: [[0, '#b91c1c'], [0.5, 'white'],[1, '#15803d']],
                cmin: -prem_paid * qty * 100, cmax: (max_plot - K - prem_paid) * qty * 100,
                colorbar: {title: 'P&L ($)', thickness: 15}
            };
            let trace_marker_3d = {
                x: [S], y: [curr_dte], z:[unrealizedPnL],
                mode: 'markers', type: 'scatter3d',
                marker: {color: 'black', size: 6, symbol: 'circle'}, name: 'Current'
            };

            Plotly.react('plotly-3d',[trace_surface, trace_marker_3d], {
                title: '3D P&L Topography: The Valley of Decay',
                scene: {
                    xaxis: {title: 'Price'}, yaxis: {title: 'DTE', autorange: 'reversed'}, zaxis: {title: 'P&L'},
                    camera: {eye: {x: -1.6, y: -1.6, z: 0.5}}
                },
                margin: {l: 0, r: 0, b: 0, t: 40}, paper_bgcolor: 'rgba(0,0,0,0)', plot_bgcolor: 'rgba(0,0,0,0)'
            }, {responsive: true});
        }

        document.querySelectorAll('input').forEach(input => { input.addEventListener('input', updateDashboard); });
        updateDashboard();
    </script>
</body>
</html>
"""

try:
    with open(full_file_path, "w", encoding="utf-8") as f:
        f.write(html_content)
    print("====================================================================")
    print(f"SUCCESS! Long Call Buyer Visualizer created.")
    print(f"Path: {full_file_path}")
    print("Double-click the file to open the dashboard.")
    print("====================================================================")
except Exception as e:
    print(f"Error: {e}")