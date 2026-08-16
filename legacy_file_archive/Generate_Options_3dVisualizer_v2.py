r"""
=============================================================================
Script Name: Generate_Options_3dVisualizer_v2.py
Purpose: Generates a unified, interactive HTML dashboard combining both 
         2D Theta Decay and 3D Surface visualization for Put Credit Spreads.
         VERSION 2: Now includes dynamic Unrealized P&L Percentage (Return on Margin).
Author: Chief Investment Officer AI Advisor
Date: April 2026

How to Run:
1. Ensure Python is installed on your PC.
2. Save this script as 'Generate_Options_3dVisualizer_v2.py'.
3. Run it via terminal or your Python IDE:
   python Generate_Options_3dVisualizer_v2.py
4. Navigate to your folder and open 'Master_Options_Dashboard_v2.html'.

Target Path: C:\Users\donca\Desktop\Desktop HP Envy x360 al 22Abr24\Docs Manuel\IBKR_Options
=============================================================================
"""

import os

# Define the exact path using a raw string
target_directory = r"C:\Users\donca\Desktop\Desktop HP Envy x360 al 22Abr24\Docs Manuel\IBKR_Options"
file_name = "Master_Options_Dashboard_v2.html"
full_file_path = os.path.join(target_directory, file_name)

# Create the directory if it does not exist
if not os.path.exists(target_directory):
    os.makedirs(target_directory)

# The Unified HTML, CSS, and JS payload
html_content = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Family Office Master Options Dashboard v2</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <script src="https://cdn.plot.ly/plotly-2.24.1.min.js"></script>
    <style>
        body { transition: background-color 0.5s ease; }
        .profit-bg { background-color: #f0fdf4; } /* Light Green */
        .loss-bg { background-color: #fef2f2; }   /* Light Red */
        .neutral-bg { background-color: #f8fafc; }/* Slate */
    </style>
</head>
<body id="main-body" class="neutral-bg text-gray-800 font-sans p-4 md:p-8">

    <div class="max-w-[1400px] mx-auto bg-white rounded-xl shadow-xl p-6 md:p-8 border border-gray-200">
        
        <!-- Header & P&L Display -->
        <div class="text-center mb-8">
            <h1 class="text-4xl font-extrabold text-gray-900 tracking-tight">Put Credit Spread Master Visualizer</h1>
            <p class="text-gray-500 mt-2 font-medium">Real-Time 2D Decay & 3D Topography</p>
            
            <div class="mt-6 p-6 rounded-xl border-2 inline-block min-w-[300px]" id="pnl-container">
                <h2 class="text-lg font-bold text-gray-500 uppercase tracking-wider">Unrealized P&L</h2>
                <p id="display-pnl" class="text-6xl font-black mt-2">$0.00</p>
                <p id="display-pnl-pct" class="text-2xl font-bold mt-1">(0.00%)</p>
                <p id="display-spread-price" class="text-gray-600 mt-3 font-medium">Current Spread Value: $0.00</p>
            </div>
        </div>

        <!-- Charts Grid (Side by Side on Large Screens) -->
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
            <h3 class="text-2xl font-bold mb-6 text-gray-800 border-b pb-2">Manual Inputs</h3>
            <div class="grid grid-cols-2 md:grid-cols-4 gap-6">
                <div>
                    <label class="block text-sm font-bold text-gray-700">Ticker</label>
                    <input type="text" id="in_ticker" value="XSP" class="mt-1 block w-full rounded-md border-gray-300 shadow-sm p-2 border focus:ring-blue-500 focus:border-blue-500">
                </div>
                <div>
                    <label class="block text-sm font-bold text-gray-700">Current Price ($)</label>
                    <input type="number" id="in_price" value="650" step="0.5" class="mt-1 block w-full rounded-md border-gray-300 shadow-sm p-2 border">
                </div>
                <div>
                    <label class="block text-sm font-bold text-gray-700">Short Strike ($)</label>
                    <input type="number" id="in_short" value="615" step="1" class="mt-1 block w-full rounded-md border-gray-300 shadow-sm p-2 border">
                </div>
                <div>
                    <label class="block text-sm font-bold text-gray-700">Long Strike ($)</label>
                    <input type="number" id="in_long" value="590" step="1" class="mt-1 block w-full rounded-md border-gray-300 shadow-sm p-2 border">
                </div>
                <div>
                    <label class="block text-sm font-bold text-gray-700">Quantity</label>
                    <input type="number" id="in_qty" value="14" step="1" class="mt-1 block w-full rounded-md border-gray-300 shadow-sm p-2 border">
                </div>
                <div>
                    <label class="block text-sm font-bold text-gray-700">Premium Collected ($)</label>
                    <input type="number" id="in_prem" value="2.67" step="0.01" class="mt-1 block w-full rounded-md border-gray-300 shadow-sm p-2 border">
                </div>
                <div>
                    <label class="block text-sm font-bold text-gray-700">Initial DTE (Entry)</label>
                    <input type="number" id="in_initial_dte" value="44" step="1" class="mt-1 block w-full rounded-md border-gray-300 shadow-sm p-2 border">
                </div>
                <div>
                    <label class="block text-sm font-bold text-gray-700">Current DTE (Today)</label>
                    <input type="number" id="in_current_dte" value="43" step="1" class="mt-1 block w-full rounded-md border-gray-300 shadow-sm p-2 border">
                </div>
                <div>
                    <label class="block text-sm font-bold text-gray-700">Implied Volatility (%)</label>
                    <input type="number" id="in_iv" value="19.3" step="0.1" class="mt-1 block w-full rounded-md border-gray-300 shadow-sm p-2 border">
                </div>
            </div>
        </div>

        <!-- Restored Greeks Table -->
        <div class="mb-10">
            <h3 class="text-2xl font-bold mb-6 text-gray-800 border-b pb-2">Position Greeks & Metrics (Net of Spread x Quantity)</h3>
            <div class="overflow-x-auto shadow-sm rounded-lg border">
                <table class="min-w-full bg-white">
                    <thead class="bg-slate-800 text-white">
                        <tr>
                            <th class="py-3 px-4 text-left font-semibold">Net Delta</th>
                            <th class="py-3 px-4 text-left font-semibold">Net Gamma</th>
                            <th class="py-3 px-4 text-left font-semibold">Net Theta</th>
                            <th class="py-3 px-4 text-left font-semibold">Net Vega</th>
                            <th class="py-3 px-4 text-left font-semibold bg-red-900">Margin Locked ($)</th>
                        </tr>
                    </thead>
                    <tbody class="divide-y divide-gray-200">
                        <tr class="hover:bg-gray-50">
                            <td id="out_delta" class="py-4 px-4 font-mono text-lg font-bold text-gray-700">0.00</td>
                            <td id="out_gamma" class="py-4 px-4 font-mono text-lg font-bold text-gray-700">0.00</td>
                            <td id="out_theta" class="py-4 px-4 font-mono text-lg font-bold text-green-600">0.00</td>
                            <td id="out_vega" class="py-4 px-4 font-mono text-lg font-bold text-blue-600">0.00</td>
                            <td id="out_margin" class="py-4 px-4 font-mono text-lg font-black text-red-600">0.00</td>
                        </tr>
                    </tbody>
                </table>
            </div>
        </div>

        <!-- Educational Footer -->
        <div class="bg-blue-50 border border-blue-200 rounded-xl p-6 text-sm text-blue-900">
            <h4 class="font-bold text-lg mb-3 uppercase tracking-wide">CIO Reference Guide: The Greeks Explained</h4>
            <div class="grid grid-cols-1 md:grid-cols-2 gap-6">
                <div>
                    <p class="mb-2"><strong class="text-blue-700 bg-blue-100 px-1 rounded">Delta (Direction):</strong> Measures directional exposure. A Net Delta of 15 means your position gains $15 if the index goes up 1 point. In credit spreads, Delta also acts as your probability gauge (e.g., selling a 20 Delta strike equates to an 80% chance of success).</p>
                    <p><strong class="text-blue-700 bg-blue-100 px-1 rounded">Gamma (Acceleration):</strong> Measures the rate of change of Delta. High Gamma means your risk is accelerating uncontrollably (which peaks near expiration). This is exactly why we mechanically close trades at 21 DTE—to avoid Gamma explosions.</p>
                </div>
                <div>
                    <p class="mb-2"><strong class="text-blue-700 bg-blue-100 px-1 rounded">Theta (Time Decay):</strong> Your daily salary. This positive number represents the dollar amount deposited into your unrealized P&L simply because one day passed, assuming all other market conditions remain totally flat.</p>
                    <p><strong class="text-blue-700 bg-blue-100 px-1 rounded">Vega (Fear Premium):</strong> Measures sensitivity to Implied Volatility (VIX). Because you sold insurance, your Net Vega is negative. This means if Implied Volatility drops by 1%, your portfolio instantly gains that dollar amount in profit (Volatility Crush).</p>
                </div>
            </div>
        </div>

    </div>

    <script>
        // Black-Scholes Math Engine
        function normCDF(x) {
            let t = 1 / (1 + 0.2316419 * Math.abs(x));
            let d = 0.3989423 * Math.exp(-x * x / 2);
            let prob = d * t * (0.3193815 + t * (-0.3565638 + t * (1.781478 + t * (-1.821256 + t * 1.330274))));
            return x > 0 ? 1 - prob : prob;
        }
        function normPDF(x) { return Math.exp(-0.5 * x * x) / Math.sqrt(2 * Math.PI); }
        
        function getPutGreeks(S, K, T, r, v) {
            if (T <= 0.0001) T = 0.0001; 
            let d1 = (Math.log(S/K) + (r + v*v/2)*T) / (v * Math.sqrt(T));
            let d2 = d1 - v * Math.sqrt(T);
            
            let price = K * Math.exp(-r*T) * normCDF(-d2) - S * normCDF(-d1);
            let delta = normCDF(d1) - 1;
            let gamma = normPDF(d1) / (S * v * Math.sqrt(T));
            let vega = (S * normPDF(d1) * Math.sqrt(T)) / 100;
            let theta = (- (S * v * normPDF(d1)) / (2 * Math.sqrt(T)) + r * K * Math.exp(-r*T) * normCDF(-d2)) / 365;
            
            return { price, delta, gamma, vega, theta };
        }

        function updateDashboard() {
            // Fetch Inputs
            let S = parseFloat(document.getElementById('in_price').value);
            let K_s = parseFloat(document.getElementById('in_short').value);
            let K_l = parseFloat(document.getElementById('in_long').value);
            let init_dte = parseFloat(document.getElementById('in_initial_dte').value);
            let curr_dte = parseFloat(document.getElementById('in_current_dte').value);
            let qty = parseFloat(document.getElementById('in_qty').value);
            let prem = parseFloat(document.getElementById('in_prem').value);
            let iv = parseFloat(document.getElementById('in_iv').value) / 100;
            let r = 0.045; // 4.5% Risk Free
            
            let T_init = init_dte / 365;
            let T_curr = curr_dte / 365;

            // Calculate Current Greeks
            let shortPut = getPutGreeks(S, K_s, T_curr, r, iv);
            let longPut = getPutGreeks(S, K_l, T_curr, r, iv);

            // Sell Short, Buy Long Math
            let currentSpreadPrice = shortPut.price - longPut.price;
            let unrealizedPnL = (prem - currentSpreadPrice) * qty * 100;
            
            let netDelta = (longPut.delta - shortPut.delta) * qty * 100;
            let netGamma = (longPut.gamma - shortPut.gamma) * qty * 100;
            let netTheta = (longPut.theta - shortPut.theta) * qty * 100;
            let netVega =  (longPut.vega - shortPut.vega) * qty * 100;
            let marginReq = (K_s - K_l) * 100 * qty;

            // Calculate P&L Percentage (Return on Margin)
            let pnlPercent = (marginReq > 0) ? (unrealizedPnL / marginReq) * 100 : 0;

            // Update UI Data Elements
            document.getElementById('display-spread-price').innerText = "Current Spread Value: $" + currentSpreadPrice.toFixed(2);
            document.getElementById('out_delta').innerText = netDelta.toFixed(2);
            document.getElementById('out_gamma').innerText = netGamma.toFixed(4);
            document.getElementById('out_theta').innerText = "$" + netTheta.toFixed(2);
            document.getElementById('out_vega').innerText = "$" + netVega.toFixed(2);
            document.getElementById('out_margin').innerText = "$" + marginReq.toLocaleString();

            // Update P&L Headers & Colors
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
            let min_plot = K_l - 30; let max_plot = K_s + 40;
            
            for(let p = min_plot; p <= max_plot; p += 0.5) {
                x_vals.push(p);
                y_exp.push((prem - (Math.max(K_s - p, 0) - Math.max(K_l - p, 0))) * qty * 100);
                
                let init_s = getPutGreeks(p, K_s, T_init, r, iv);
                let init_l = getPutGreeks(p, K_l, T_init, r, iv);
                y_init.push((prem - (init_s.price - init_l.price)) * qty * 100);

                let curr_s = getPutGreeks(p, K_s, T_curr, r, iv);
                let curr_l = getPutGreeks(p, K_l, T_curr, r, iv);
                y_curr.push((prem - (curr_s.price - curr_l.price)) * qty * 100);
            }

            let trace_exp = { x: x_vals, y: y_exp, type: 'scatter', mode: 'lines', name: 'Expiration', line: {color: 'gray', dash: 'dash'} };
            let trace_init = { x: x_vals, y: y_init, type: 'scatter', mode: 'lines', name: 'T-Initial (Entry Day)', line: {color: 'orange', width: 2, dash: 'dot'} };
            let trace_curr = { x: x_vals, y: y_curr, type: 'scatter', mode: 'lines', name: 'T+0 (Today)', line: {color: 'blue', width: 3} };
            let trace_dot = { x: [S], y: [unrealizedPnL], type: 'scatter', mode: 'markers', name: 'Current Price', marker: {color: 'black', size: 10} };

            Plotly.react('plotly-2d',[trace_exp, trace_init, trace_curr, trace_dot], {
                title: '2D Decay Profile', xaxis: {title: 'Underlying Price ($)'}, yaxis: {title: 'P&L ($)'},
                margin: {l: 50, r: 20, t: 40, b: 40}, paper_bgcolor: 'rgba(0,0,0,0)', plot_bgcolor: 'rgba(0,0,0,0)',
                shapes:[{type: 'line', x0: min_plot, x1: max_plot, y0: 0, y1: 0, line:{color: 'black', width: 1}}],
                legend: { orientation: 'h', y: -0.2 }
            }, {responsive: true});

            // ==========================================
            // BUILD 3D CHART
            // ==========================================
            let x_3d =[]; let y_3d = []; let z_3d =[];
            for(let d = init_dte; d >= 0; d -= Math.max(1, Math.floor(init_dte/15))) {
                y_3d.push(d);
                let z_row =[];
                let T = d / 365;
                for(let p = min_plot; p <= max_plot; p += 1) {
                    if (y_3d.length === 1) x_3d.push(p);
                    if (T <= 0.0001) {
                        z_row.push((prem - (Math.max(K_s - p, 0) - Math.max(K_l - p, 0))) * qty * 100);
                    } else {
                        let t0_s = getPutGreeks(p, K_s, T, r, iv);
                        let t0_l = getPutGreeks(p, K_l, T, r, iv);
                        z_row.push((prem - (t0_s.price - t0_l.price)) * qty * 100);
                    }
                }
                z_3d.push(z_row);
            }

            let trace_surface = {
                z: z_3d, x: x_3d, y: y_3d, type: 'surface',
                colorscale: [[0, '#fef2f2'],[0.2, '#fca5a5'], [0.5, 'white'],[0.8, '#86efac'],[1, '#f0fdf4']],
                cmin: - (K_s - K_l)*qty*100, cmax: prem*qty*100,
                colorbar: {title: 'P&L ($)', thickness: 15}
            };
            let trace_marker_3d = {
                x: [S], y: [curr_dte], z:[unrealizedPnL],
                mode: 'markers', type: 'scatter3d',
                marker: {color: 'black', size: 6, symbol: 'circle'}, name: 'Current'
            };

            Plotly.react('plotly-3d',[trace_surface, trace_marker_3d], {
                title: '3D P&L Topography (Time vs Price)',
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
    print(f"SUCCESS! Master Options Dashboard (v2) created.")
    print(f"Path: {full_file_path}")
    print("Double-click the file to open your unified 2D/3D interface.")
    print("====================================================================")
except Exception as e:
    print(f"Error: {e}")