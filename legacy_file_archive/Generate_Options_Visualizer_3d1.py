r"""
=============================================================================
Script Name: Generate_Options_Visualizer_3d1.py
Purpose: Generates a standalone HTML dashboard featuring an interactive 
         3D Surface Plot of a Put Credit Spread. Visualizes the impact of 
         Underlying Price (X-axis) and Time Decay (Y-axis) on Profit (Z-axis).
=============================================================================
"""

import os

target_directory = r"C:\Users\donca\Desktop\Desktop HP Envy x360 al 22Abr24\Docs Manuel\IBKR_Options"
file_name = "Options_Visualizer_3d1.html"
full_file_path = os.path.join(target_directory, file_name)

if not os.path.exists(target_directory):
    os.makedirs(target_directory)

html_content = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Family Office 3D Options Visualizer</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <script src="https://cdn.plot.ly/plotly-2.24.1.min.js"></script>
    <style>
        body { background-color: #f8fafc; }
        .profit-text { color: #15803d; }
        .loss-text { color: #b91c1c; }
    </style>
</head>
<body class="text-gray-800 font-sans p-6">

    <div class="max-w-7xl mx-auto bg-white rounded-xl shadow-lg p-6">
        
        <div class="text-center mb-4">
            <h1 class="text-3xl font-bold text-gray-900">3D Options Surface Map</h1>
            <p class="text-gray-500 mt-2">Rotate the chart to view how Time and Price dynamically alter Profitability</p>
            <h2 class="text-2xl font-bold mt-4">Current Unrealized P&L: <span id="display-pnl">0.00 USD</span></h2>
        </div>

        <div id="plotly-3d" class="w-full h-[600px] mb-8 border rounded-lg bg-gray-50"></div>

        <div>
            <h3 class="text-xl font-bold mb-4 border-b pb-2">Simulation Parameters</h3>
            <div class="grid grid-cols-2 md:grid-cols-4 gap-4">
                <div><label class="block text-sm font-medium text-gray-700">Current Price (USD)</label><input type="number" id="in_price" value="650" step="0.5" class="mt-1 block w-full rounded-md border-gray-300 shadow-sm p-2 border"></div>
                <div><label class="block text-sm font-medium text-gray-700">Short Strike (USD)</label><input type="number" id="in_short" value="620" step="1" class="mt-1 block w-full rounded-md border-gray-300 shadow-sm p-2 border"></div>
                <div><label class="block text-sm font-medium text-gray-700">Long Strike (USD)</label><input type="number" id="in_long" value="595" step="1" class="mt-1 block w-full rounded-md border-gray-300 shadow-sm p-2 border"></div>
                <div><label class="block text-sm font-medium text-gray-700">Quantity</label><input type="number" id="in_qty" value="10" step="1" class="mt-1 block w-full rounded-md border-gray-300 shadow-sm p-2 border"></div>
                <div><label class="block text-sm font-medium text-gray-700">Premium Collected (USD)</label><input type="number" id="in_prem" value="3.00" step="0.01" class="mt-1 block w-full rounded-md border-gray-300 shadow-sm p-2 border"></div>
                <div><label class="block text-sm font-medium text-gray-700">Initial DTE</label><input type="number" id="in_initial_dte" value="45" step="1" class="mt-1 block w-full rounded-md border-gray-300 shadow-sm p-2 border"></div>
                <div><label class="block text-sm font-medium text-gray-700">Current DTE</label><input type="number" id="in_current_dte" value="30" step="1" class="mt-1 block w-full rounded-md border-gray-300 shadow-sm p-2 border"></div>
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
        function getPutPrice(S, K, T, r, v) {
            if (T <= 0.0001) return Math.max(K - S, 0);
            let d1 = (Math.log(S/K) + (r + v*v/2)*T) / (v * Math.sqrt(T));
            let d2 = d1 - v * Math.sqrt(T);
            return K * Math.exp(-r*T) * normCDF(-d2) - S * normCDF(-d1);
        }

        function update3D() {
            let S = parseFloat(document.getElementById('in_price').value);
            let K_s = parseFloat(document.getElementById('in_short').value);
            let K_l = parseFloat(document.getElementById('in_long').value);
            let init_dte = parseFloat(document.getElementById('in_initial_dte').value);
            let curr_dte = parseFloat(document.getElementById('in_current_dte').value);
            let qty = parseFloat(document.getElementById('in_qty').value);
            let prem = parseFloat(document.getElementById('in_prem').value);
            let iv = parseFloat(document.getElementById('in_iv').value) / 100;
            let r = 0.045;

            // Current P&L calculation
            let T_curr = curr_dte / 365;
            let currPrice = getPutPrice(S, K_s, T_curr, r, iv) - getPutPrice(S, K_l, T_curr, r, iv);
            let unrealizedPnL = (prem - currPrice) * qty * 100;
            
            let pnlText = document.getElementById('display-pnl');
            pnlText.innerText = (unrealizedPnL >= 0 ? "+" : "") + unrealizedPnL.toFixed(2) + " USD";
            pnlText.className = unrealizedPnL >= 0 ? "profit-text" : "loss-text";

            // Generate 3D Grid Data
            let x_price = [];
            let y_dte = [];
            let z_pnl =[];

            let min_plot = K_l - 30;
            let max_plot = K_s + 40;

            // Y-Axis: Time (from Entry Day down to Expiration 0)
            for(let d = init_dte; d >= 0; d -= Math.max(1, Math.floor(init_dte/20))) {
                y_dte.push(d);
                let z_row =[];
                let T = d / 365;
                for(let p = min_plot; p <= max_plot; p += 1) {
                    if (y_dte.length === 1) x_price.push(p);
                    
                    if (T <= 0.0001) {
                        let val = (prem - (Math.max(K_s - p, 0) - Math.max(K_l - p, 0))) * qty * 100;
                        z_row.push(val);
                    } else {
                        let val = (prem - (getPutPrice(p, K_s, T, r, iv) - getPutPrice(p, K_l, T, r, iv))) * qty * 100;
                        z_row.push(val);
                    }
                }
                z_pnl.push(z_row);
            }

            let trace_surface = {
                z: z_pnl, x: x_price, y: y_dte, type: 'surface',
                colorscale: [[0, 'red'], [0.5, 'white'], [1, 'green']],
                cmin: - (K_s - K_l)*qty*100, cmax: prem*qty*100,
                colorbar: {title: 'P&L (USD)'}
            };

            let trace_marker = {
                x: [S], y: [curr_dte], z:[unrealizedPnL],
                mode: 'markers', type: 'scatter3d',
                marker: {color: 'black', size: 8, symbol: 'circle'},
                name: 'Current Position'
            };

            let layout = {
                scene: {
                    xaxis: {title: 'Underlying Price'},
                    yaxis: {title: 'Days to Expiration', autorange: 'reversed'},
                    zaxis: {title: 'Profit & Loss (USD)'},
                    camera: {eye: {x: 1.5, y: -1.5, z: 0.5}}
                },
                margin: {l: 0, r: 0, b: 0, t: 0}
            };

            Plotly.react('plotly-3d', [trace_surface, trace_marker], layout, {responsive: true});
        }

        document.querySelectorAll('input').forEach(input => { input.addEventListener('input', update3D); });
        update3D();
    </script>
</body>
</html>"""

try:
    with open(full_file_path, "w", encoding="utf-8") as f:
        f.write(html_content)
    print(f"SUCCESS! 3D Options Visualizer created at: {full_file_path}")
except Exception as e:
    print(f"Error: {e}")