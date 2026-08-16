r"""
=============================================================================
Script Name: Generate_Options_Visualizer_v1.py
Purpose: Generates a 2D HTML dashboard to visualize Put Credit Spreads. 
         UPDATED: Now includes 'Initial DTE' to visualize the Theta decay gap 
         between trade entry and the current day.
=============================================================================
"""

import os

target_directory = r"C:\Users\donca\Desktop\Desktop HP Envy x360 al 22Abr24\Docs Manuel\IBKR_Options"
file_name = "Options_Visualizer_v1.html"
full_file_path = os.path.join(target_directory, file_name)

if not os.path.exists(target_directory):
    os.makedirs(target_directory)

html_content = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Family Office 2D Options Visualizer v1</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <script src="https://cdn.plot.ly/plotly-2.24.1.min.js"></script>
    <style>
        body { transition: background-color 0.5s ease; }
        .profit-bg { background-color: #e6ffe6; }
        .loss-bg { background-color: #ffe6e6; }
        .neutral-bg { background-color: #f3f4f6; }
    </style>
</head>
<body id="main-body" class="neutral-bg text-gray-800 font-sans p-6">

    <div class="max-w-6xl mx-auto bg-white rounded-xl shadow-lg p-6">
        <div class="text-center mb-6">
            <h1 class="text-3xl font-bold text-gray-900">Put Credit Spread 2D Simulator (with Theta Decay)</h1>
            <div class="mt-6 p-4 rounded-lg border-2" id="pnl-container">
                <h2 class="text-xl font-semibold">Unrealized P&L</h2>
                <p id="display-pnl" class="text-5xl font-black mt-2">0.00 USD</p>
                <p id="display-spread-price" class="text-gray-600 mt-2">Current Spread Value: 0.00 USD</p>
            </div>
        </div>

        <div id="plotly-chart" class="w-full h-96 mb-8"></div>

        <div class="mb-8">
            <h3 class="text-xl font-bold mb-4 border-b pb-2">Manual Inputs</h3>
            <div class="grid grid-cols-2 md:grid-cols-4 gap-4">
                <div><label class="block text-sm font-medium text-gray-700">Current Price (USD)</label><input type="number" id="in_price" value="650" step="0.5" class="mt-1 block w-full rounded-md border-gray-300 shadow-sm p-2 border"></div>
                <div><label class="block text-sm font-medium text-gray-700">Short Strike (USD)</label><input type="number" id="in_short" value="620" step="1" class="mt-1 block w-full rounded-md border-gray-300 shadow-sm p-2 border"></div>
                <div><label class="block text-sm font-medium text-gray-700">Long Strike (USD)</label><input type="number" id="in_long" value="595" step="1" class="mt-1 block w-full rounded-md border-gray-300 shadow-sm p-2 border"></div>
                <div><label class="block text-sm font-medium text-gray-700">Quantity</label><input type="number" id="in_qty" value="10" step="1" class="mt-1 block w-full rounded-md border-gray-300 shadow-sm p-2 border"></div>
                <div><label class="block text-sm font-medium text-gray-700">Premium Collected (USD)</label><input type="number" id="in_prem" value="3.00" step="0.01" class="mt-1 block w-full rounded-md border-gray-300 shadow-sm p-2 border"></div>
                <div><label class="block text-sm font-medium text-gray-700">Initial DTE (Entry Day)</label><input type="number" id="in_initial_dte" value="45" step="1" class="mt-1 block w-full rounded-md border-gray-300 shadow-sm p-2 border"></div>
                <div><label class="block text-sm font-medium text-gray-700">Current DTE (Today)</label><input type="number" id="in_current_dte" value="38" step="1" class="mt-1 block w-full rounded-md border-gray-300 shadow-sm p-2 border"></div>
                <div><label class="block text-sm font-medium text-gray-700">Implied Volatility (%)</label><input type="number" id="in_iv" value="20" step="0.5" class="mt-1 block w-full rounded-md border-gray-300 shadow-sm p-2 border"></div>
            </div>
        </div>
    </div>

    <script>
        function normCDF(x) {
            let t = 1 / (1 + 0.2316419 * Math.abs(x));
            let d = 0.3989423 * Math.exp(-x * x / 2);
            let prob = d * t * (0.3193815 + t * (-0.3565638 + t * (1.781478 + t * (-1.821256 + t * 1.330274))));
            return x > 0 ? 1 - prob : prob;
        }
        function normPDF(x) { return Math.exp(-0.5 * x * x) / Math.sqrt(2 * Math.PI); }
        function getPutPrice(S, K, T, r, v) {
            if (T <= 0.0001) return Math.max(K - S, 0);
            let d1 = (Math.log(S/K) + (r + v*v/2)*T) / (v * Math.sqrt(T));
            let d2 = d1 - v * Math.sqrt(T);
            return K * Math.exp(-r*T) * normCDF(-d2) - S * normCDF(-d1);
        }

        function updateAll() {
            let S = parseFloat(document.getElementById('in_price').value);
            let K_short = parseFloat(document.getElementById('in_short').value);
            let K_long = parseFloat(document.getElementById('in_long').value);
            let initial_dte = parseFloat(document.getElementById('in_initial_dte').value);
            let current_dte = parseFloat(document.getElementById('in_current_dte').value);
            let qty = parseFloat(document.getElementById('in_qty').value);
            let prem = parseFloat(document.getElementById('in_prem').value);
            let iv = parseFloat(document.getElementById('in_iv').value) / 100;
            let r = 0.045; 
            
            let T_init = initial_dte / 365;
            let T_curr = current_dte / 365;

            let currentSpreadPrice = getPutPrice(S, K_short, T_curr, r, iv) - getPutPrice(S, K_long, T_curr, r, iv);
            let unrealizedPnL = (prem - currentSpreadPrice) * qty * 100;

            document.getElementById('display-spread-price').innerText = "Current Spread Value: " + currentSpreadPrice.toFixed(2) + " USD";
            let pnlEl = document.getElementById('display-pnl');
            let bodyEl = document.getElementById('main-body');
            let pnlBox = document.getElementById('pnl-container');
            
            pnlEl.innerText = (unrealizedPnL >= 0 ? "+" : "-") + Math.abs(unrealizedPnL).toLocaleString(undefined, {minimumFractionDigits: 2, maximumFractionDigits:2}) + " USD";

            if (unrealizedPnL > 0) {
                bodyEl.className = "profit-bg text-gray-800 font-sans p-6";
                pnlEl.className = "text-5xl font-black mt-2 text-green-700";
                pnlBox.className = "mt-6 p-4 rounded-lg border-2 border-green-400 bg-green-50";
            } else if (unrealizedPnL < 0) {
                bodyEl.className = "loss-bg text-gray-800 font-sans p-6";
                pnlEl.className = "text-5xl font-black mt-2 text-red-700";
                pnlBox.className = "mt-6 p-4 rounded-lg border-2 border-red-400 bg-red-50";
            }

            let x_vals = [], y_init = [], y_curr = [], y_exp =[];
            let min_plot = K_long - 30; let max_plot = K_short + 40;
            
            for(let p = min_plot; p <= max_plot; p += 0.5) {
                x_vals.push(p);
                y_exp.push((prem - (Math.max(K_short - p, 0) - Math.max(K_long - p, 0))) * qty * 100);
                y_init.push((prem - (getPutPrice(p, K_short, T_init, r, iv) - getPutPrice(p, K_long, T_init, r, iv))) * qty * 100);
                y_curr.push((prem - (getPutPrice(p, K_short, T_curr, r, iv) - getPutPrice(p, K_long, T_curr, r, iv))) * qty * 100);
            }

            let trace_exp = { x: x_vals, y: y_exp, type: 'scatter', mode: 'lines', name: 'Expiration', line: {color: 'gray', dash: 'dash'} };
            let trace_init = { x: x_vals, y: y_init, type: 'scatter', mode: 'lines', name: 'T-Initial (Entry Day)', line: {color: 'orange', width: 2, dash: 'dot'} };
            let trace_curr = { x: x_vals, y: y_curr, type: 'scatter', mode: 'lines', name: 'T+0 (Today)', line: {color: 'blue', width: 3} };
            let trace_dot = { x: [S], y: [unrealizedPnL], type: 'scatter', mode: 'markers', name: 'Current Price', marker: {color: 'black', size: 10} };

            Plotly.react('plotly-chart', [trace_exp, trace_init, trace_curr, trace_dot], {
                title: 'Payoff Diagram showing Theta Decay Gap', xaxis: {title: 'Underlying Price (USD)'}, yaxis: {title: 'P&L (USD)'},
                margin: {l: 50, r: 20, t: 40, b: 40}, paper_bgcolor: 'rgba(0,0,0,0)', plot_bgcolor: 'rgba(0,0,0,0)',
                shapes:[{type: 'line', x0: min_plot, x1: max_plot, y0: 0, y1: 0, line:{color: 'black', width: 1}}]
            }, {responsive: true});
        }
        document.querySelectorAll('input').forEach(input => { input.addEventListener('input', updateAll); });
        updateAll();
    </script>
</body>
</html>"""

try:
    with open(full_file_path, "w", encoding="utf-8") as f:
        f.write(html_content)
    print(f"SUCCESS! Created {file_name}")
except Exception as e:
    print(f"Error: {e}")