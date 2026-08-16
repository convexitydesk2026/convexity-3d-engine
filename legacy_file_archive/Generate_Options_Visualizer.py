r"""
=============================================================================
Script Name: Generate_Options_Visualizer.py
Purpose: Generates a standalone, interactive HTML dashboard to visualize 
         Put Credit Spreads. Features real-time Black-Scholes calculations, 
         Greeks, T+0 vs Expiration payoff charts, and dynamic P&L color mapping.
Author: Chief Investment Officer AI Advisor
Date: April 2026

How to Run:
1. Ensure Python is installed on your PC.
2. Save this script anywhere on your computer and run it via terminal or IDE:
   python Generate_Options_Visualizer.py
3. The script will automatically create the HTML file at the path specified below.
4. Navigate to the folder, double-click 'Options_Visualizer.html', and explore!

Target Path: C:\Users\donca\Desktop\Desktop HP Envy x360 al 22Abr24\Docs Manuel\IBKR_Options
=============================================================================
"""

import os

# Define the exact path
target_directory = r"C:\Users\donca\Desktop\Desktop HP Envy x360 al 22Abr24\Docs Manuel\IBKR_Options"
file_name = "Options_Visualizer.html"
full_file_path = os.path.join(target_directory, file_name)

# Create the directory if it does not exist
if not os.path.exists(target_directory):
    os.makedirs(target_directory)

# The HTML, CSS (Tailwind), and JavaScript (Plotly & Black-Scholes) string
html_content = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Family Office Options Visualizer</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <script src="https://cdn.plot.ly/plotly-2.24.1.min.js"></script>
    <style>
        body { transition: background-color 0.5s ease; }
        .profit-bg { background-color: #e6ffe6; } /* Light Green */
        .loss-bg { background-color: #ffe6e6; } /* Light Red */
        .neutral-bg { background-color: #f3f4f6; } /* Light Gray */
    </style>
</head>
<body id="main-body" class="neutral-bg text-gray-800 font-sans p-6">

    <div class="max-w-6xl mx-auto bg-white rounded-xl shadow-lg p-6">
        
        <!-- Header & P&L Display -->
        <div class="text-center mb-6">
            <h1 class="text-3xl font-bold text-gray-900">Put Credit Spread Simulator</h1>
            <p class="text-gray-500 mt-2">Adjust parameters below to recalculate T+0 curves and Greeks</p>
            
            <div class="mt-6 p-4 rounded-lg border-2" id="pnl-container">
                <h2 class="text-xl font-semibold">Unrealized P&L</h2>
                <p id="display-pnl" class="text-5xl font-black mt-2">$0.00</p>
                <p id="display-spread-price" class="text-gray-600 mt-2">Current Spread Value: $0.00</p>
            </div>
        </div>

        <!-- Chart Section -->
        <div id="plotly-chart" class="w-full h-96 mb-8"></div>

        <!-- Inputs Table -->
        <div class="mb-8">
            <h3 class="text-xl font-bold mb-4 border-b pb-2">Manual Inputs</h3>
            <div class="grid grid-cols-2 md:grid-cols-4 gap-4">
                <div>
                    <label class="block text-sm font-medium text-gray-700">Ticker</label>
                    <input type="text" id="in_ticker" value="XSP" class="mt-1 block w-full rounded-md border-gray-300 shadow-sm p-2 border focus:border-blue-500">
                </div>
                <div>
                    <label class="block text-sm font-medium text-gray-700">Current Price ($)</label>
                    <input type="number" id="in_price" value="650" step="0.5" class="mt-1 block w-full rounded-md border-gray-300 shadow-sm p-2 border">
                </div>
                <div>
                    <label class="block text-sm font-medium text-gray-700">Short Strike ($)</label>
                    <input type="number" id="in_short" value="620" step="1" class="mt-1 block w-full rounded-md border-gray-300 shadow-sm p-2 border">
                </div>
                <div>
                    <label class="block text-sm font-medium text-gray-700">Long Strike ($)</label>
                    <input type="number" id="in_long" value="595" step="1" class="mt-1 block w-full rounded-md border-gray-300 shadow-sm p-2 border">
                </div>
                <div>
                    <label class="block text-sm font-medium text-gray-700">Quantity</label>
                    <input type="number" id="in_qty" value="10" step="1" class="mt-1 block w-full rounded-md border-gray-300 shadow-sm p-2 border">
                </div>
                <div>
                    <label class="block text-sm font-medium text-gray-700">Premium Collected ($)</label>
                    <input type="number" id="in_prem" value="3.00" step="0.01" class="mt-1 block w-full rounded-md border-gray-300 shadow-sm p-2 border">
                </div>
                <div>
                    <label class="block text-sm font-medium text-gray-700">Days to Expiration (DTE)</label>
                    <input type="number" id="in_dte" value="45" step="1" class="mt-1 block w-full rounded-md border-gray-300 shadow-sm p-2 border">
                </div>
                <div>
                    <label class="block text-sm font-medium text-gray-700">Implied Volatility (%)</label>
                    <input type="number" id="in_iv" value="20" step="0.5" class="mt-1 block w-full rounded-md border-gray-300 shadow-sm p-2 border">
                </div>
            </div>
        </div>

        <!-- Greeks Table -->
        <div>
            <h3 class="text-xl font-bold mb-4 border-b pb-2">Position Greeks (Net of Spread x Quantity)</h3>
            <div class="overflow-x-auto">
                <table class="min-w-full bg-white border border-gray-200">
                    <thead class="bg-gray-50">
                        <tr>
                            <th class="py-2 px-4 border-b text-left">Net Delta</th>
                            <th class="py-2 px-4 border-b text-left">Net Gamma</th>
                            <th class="py-2 px-4 border-b text-left">Net Theta</th>
                            <th class="py-2 px-4 border-b text-left">Net Vega</th>
                            <th class="py-2 px-4 border-b text-left">Margin Required ($)</th>
                        </tr>
                    </thead>
                    <tbody>
                        <tr>
                            <td id="out_delta" class="py-2 px-4 border-b font-mono">0.00</td>
                            <td id="out_gamma" class="py-2 px-4 border-b font-mono">0.00</td>
                            <td id="out_theta" class="py-2 px-4 border-b font-mono">0.00</td>
                            <td id="out_vega" class="py-2 px-4 border-b font-mono">0.00</td>
                            <td id="out_margin" class="py-2 px-4 border-b font-mono font-bold text-red-600">0.00</td>
                        </tr>
                    </tbody>
                </table>
            </div>
        </div>
    </div>

    <script>
        // Black-Scholes Math Functions
        function normCDF(x) {
            let t = 1 / (1 + 0.2316419 * Math.abs(x));
            let d = 0.3989423 * Math.exp(-x * x / 2);
            let prob = d * t * (0.3193815 + t * (-0.3565638 + t * (1.781478 + t * (-1.821256 + t * 1.330274))));
            return x > 0 ? 1 - prob : prob;
        }
        function normPDF(x) {
            return Math.exp(-0.5 * x * x) / Math.sqrt(2 * Math.PI);
        }

        function getPutGreeks(S, K, T, r, v) {
            if (T <= 0.0001) T = 0.0001; // prevent division by zero
            let d1 = (Math.log(S/K) + (r + v*v/2)*T) / (v * Math.sqrt(T));
            let d2 = d1 - v * Math.sqrt(T);
            
            let price = K * Math.exp(-r*T) * normCDF(-d2) - S * normCDF(-d1);
            let delta = normCDF(d1) - 1;
            let gamma = normPDF(d1) / (S * v * Math.sqrt(T));
            let vega = (S * normPDF(d1) * Math.sqrt(T)) / 100;
            let theta = (- (S * v * normPDF(d1)) / (2 * Math.sqrt(T)) + r * K * Math.exp(-r*T) * normCDF(-d2)) / 365;
            
            return { price, delta, gamma, vega, theta };
        }

        function updateAll() {
            // Get inputs
            let S = parseFloat(document.getElementById('in_price').value);
            let K_short = parseFloat(document.getElementById('in_short').value);
            let K_long = parseFloat(document.getElementById('in_long').value);
            let DTE = parseFloat(document.getElementById('in_dte').value);
            let qty = parseFloat(document.getElementById('in_qty').value);
            let prem = parseFloat(document.getElementById('in_prem').value);
            let iv = parseFloat(document.getElementById('in_iv').value) / 100;
            let r = 0.045; // 4.5% Risk Free Rate assumption
            let T = DTE / 365;

            // Calculate current Greeks (Short Put - Long Put)
            let shortPut = getPutGreeks(S, K_short, T, r, iv);
            let longPut = getPutGreeks(S, K_long, T, r, iv);

            // We SELL the short, BUY the long
            let currentSpreadPrice = shortPut.price - longPut.price;
            let netDelta = (longPut.delta - shortPut.delta) * qty * 100;
            let netGamma = (longPut.gamma - shortPut.gamma) * qty * 100;
            let netTheta = (longPut.theta - shortPut.theta) * qty * 100;
            let netVega =  (longPut.vega - shortPut.vega) * qty * 100;
            let marginReq = (K_short - K_long) * 100 * qty;

            // Calculate P&L
            let unrealizedPnL = (prem - currentSpreadPrice) * qty * 100;

            // Update UI Elements
            document.getElementById('display-spread-price').innerText = "Current Spread Value: $" + currentSpreadPrice.toFixed(2);
            document.getElementById('out_delta').innerText = netDelta.toFixed(2);
            document.getElementById('out_gamma').innerText = netGamma.toFixed(4);
            document.getElementById('out_theta').innerText = "$" + netTheta.toFixed(2);
            document.getElementById('out_vega').innerText = "$" + netVega.toFixed(2);
            document.getElementById('out_margin').innerText = "$" + marginReq.toLocaleString();

            let pnlEl = document.getElementById('display-pnl');
            let bodyEl = document.getElementById('main-body');
            let pnlBox = document.getElementById('pnl-container');
            
            pnlEl.innerText = (unrealizedPnL >= 0 ? "+$" : "-$") + Math.abs(unrealizedPnL).toLocaleString(undefined, {minimumFractionDigits: 2, maximumFractionDigits:2});

            if (unrealizedPnL > 0) {
                bodyEl.className = "profit-bg text-gray-800 font-sans p-6";
                pnlEl.className = "text-5xl font-black mt-2 text-green-700";
                pnlBox.className = "mt-6 p-4 rounded-lg border-2 border-green-400 bg-green-50";
            } else if (unrealizedPnL < 0) {
                bodyEl.className = "loss-bg text-gray-800 font-sans p-6";
                pnlEl.className = "text-5xl font-black mt-2 text-red-700";
                pnlBox.className = "mt-6 p-4 rounded-lg border-2 border-red-400 bg-red-50";
            } else {
                bodyEl.className = "neutral-bg text-gray-800 font-sans p-6";
                pnlEl.className = "text-5xl font-black mt-2 text-gray-700";
                pnlBox.className = "mt-6 p-4 rounded-lg border-2 border-gray-300 bg-gray-100";
            }

            // Draw Chart
            let x_vals = [];
            let y_t0 =[];
            let y_exp =[];
            
            let min_plot = K_long - 30;
            let max_plot = K_short + 30;
            
            for(let p = min_plot; p <= max_plot; p += 0.5) {
                x_vals.push(p);
                // Expiration Payoff
                let exp_short = Math.max(K_short - p, 0);
                let exp_long = Math.max(K_long - p, 0);
                let exp_val = (prem - (exp_short - exp_long)) * qty * 100;
                y_exp.push(exp_val);
                
                // T+0 Payoff
                let t0_s = getPutGreeks(p, K_short, T, r, iv);
                let t0_l = getPutGreeks(p, K_long, T, r, iv);
                let t0_val = (prem - (t0_s.price - t0_l.price)) * qty * 100;
                y_t0.push(t0_val);
            }

            let trace_exp = {
                x: x_vals, y: y_exp, type: 'scatter', mode: 'lines',
                name: 'Expiration', line: {color: 'gray', dash: 'dash'}
            };
            let trace_t0 = {
                x: x_vals, y: y_t0, type: 'scatter', mode: 'lines',
                name: 'T+0 (Today)', line: {color: 'blue', width: 3}
            };
            let trace_current = {
                x: [S], y: [unrealizedPnL], type: 'scatter', mode: 'markers',
                name: 'Current Price', marker: {color: 'black', size: 10}
            };

            let layout = {
                title: 'Payoff Diagram (P&L vs Underlying Price)',
                xaxis: {title: 'Underlying Price ($)'},
                yaxis: {title: 'P&L ($)'},
                margin: {l: 50, r: 20, t: 40, b: 40},
                paper_bgcolor: 'rgba(0,0,0,0)',
                plot_bgcolor: 'rgba(0,0,0,0)',
                shapes:[{type: 'line', x0: min_plot, x1: max_plot, y0: 0, y1: 0, line:{color: 'black', width: 1}}]
            };

            Plotly.react('plotly-chart', [trace_exp, trace_t0, trace_current], layout, {responsive: true});
        }

        // Attach event listeners to all inputs
        document.querySelectorAll('input').forEach(input => {
            input.addEventListener('input', updateAll);
        });

        // Initial Load
        updateAll();
    </script>
</body>
</html>
"""

# Write the HTML file
try:
    with open(full_file_path, "w", encoding="utf-8") as f:
        f.write(html_content)
    print("====================================================================")
    print(f"SUCCESS! Options Visualizer HTML created.")
    print(f"Path: {full_file_path}")
    print("Double-click the file to open it in your web browser.")
    print("====================================================================")
except Exception as e:
    print(f"An error occurred: {e}")