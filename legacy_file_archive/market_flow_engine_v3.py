#!/usr/bin/env python3
"""
================================================================================
File:        market_flow_engine_v3.py
Location:    C:\\Users\\donca\\Desktop\\Desktop HP Envy x360 al 22Abr24\\Docs Manuel\\IBKR_Options\\
Description: Automated Market Relative Strength & Institutional Flow Dashboard.
             - Unified, Globally Sortable Architecture
             - Frozen Benchmark (RSP) & Sticky Headers
             - Volume Climax Indicators (🔥)
             - Output: market_flow_report.html & market_flow_report.pdf
Launch the UI by running exactly: streamlit run market_flow_engine_v3.py             
Author:      Virtual CFO
Date:        July 2026
Version:     3.0 (Unified Matrix)
================================================================================
"""

import yfinance as yf
import pandas as pd
import numpy as np
import os
from playwright.sync_api import sync_playwright

# ==============================================================================
# CONFIGURATION & CONSTANTS
# ==============================================================================
BENCHMARK = 'RSP'

SECTIONS_MACRO = {
    "Index": ["RSP", "SPY", "QQQ", "QQQE", "IWM", "DIA", "SPMO", "TLT"],
    "Segment": ["IJJ", "IJS", "IJT", "IJR", "IJH", "IJK", "IVE", "IVW", "IVV"],
    "EW Sector": ["RSPF", "RSPH", "RSPN", "RSPU", "RSPS", "RSPC", "RSPR", "RSPM", "RSPD", "RSPG", "RSPT", "SPY"],
    "SPDR Sector": ["XLF", "XLV", "XLI", "XLU", "XLC", "XLB", "XLP", "XLY", "XLRE", "XLE", "SPY", "XLK"]
}

SECTIONS_MICRO = {
    "Tech & Innovation": ["SMH", "IGV", "CIBR", "SKYY", "FDN", "HACK"],
    "Financials & Real Estate": ["KRE", "KCE", "KIE", "VNQ", "REM"],
    "Industrials & Infrastructure": ["IYT", "JETS", "XHB", "ITB", "PAVE", "VIS"],
    "Healthcare": ["XBI", "IHI", "IHF", "PPH"],
    "Consumer Discretionary": ["XRT", "PBJ", "PEJ", "BETZ", "IBUY"],
    "Consumer Staples": ["KXI", "IYK"],
    "Energy (Traditional & Clean)": ["XOP", "OIH", "TAN", "FAN", "CRAK"],
    "Commodities & Mining": ["GDX", "COPX", "URA", "LIT", "SLX", "PICK", "XME"],
    "Communications & Utilities": ["SOCL", "XTL", "UTF", "FIW"]
}

NAMES = {
    "RSP": "S&P 500 Eq Weight", "SPY": "S&P 500", "QQQ": "Nasdaq-100", "QQQE": "Nasdaq-100 Eq Weight",
    "IWM": "Russell 2000", "DIA": "Dow 30", "SPMO": "S&P 500 Momentum", "TLT": "20+ Yr Treasury",
    "IJJ": "MidCap 400 Value", "IJS": "Small-Cap 600 Value", "IJT": "Small-Cap 600 Growth", 
    "IJR": "Small-Cap 600", "IJH": "MidCap 400", "IJK": "MidCap 400 Growth", "IVE": "Large-Cap 500 Value", 
    "IVW": "Large-Cap 500 Growth", "IVV": "S&P 500", "RSPF": "Eq Weight Financials", 
    "RSPH": "Eq Weight Health Care", "RSPN": "Eq Weight Industrial", "RSPU": "Eq Weight Utilities", 
    "RSPS": "Eq Weight Staples", "RSPC": "Eq Weight Communication", "RSPR": "Eq Weight Real Estate", 
    "RSPM": "Eq Weight Material", "RSPD": "Eq Weight Discretionary", "RSPG": "Eq Weight Energy", 
    "RSPT": "Eq Weight Technology", "XLF": "Financials", "XLV": "Health Care", "XLI": "Industrials", 
    "XLU": "Utilities", "XLC": "Communication Services", "XLB": "Materials", "XLP": "Consumer Staples", 
    "XLY": "Consumer Discretionary", "XLRE": "Real Estate", "XLE": "Energy", "XLK": "Technology",
    "SMH": "Semiconductors", "IGV": "Software", "CIBR": "Cybersecurity", "SKYY": "Cloud Computing", 
    "FDN": "Internet", "HACK": "Cyber Security", "KRE": "Regional Banks", "KCE": "Capital Markets", 
    "KIE": "Insurance", "VNQ": "REITs", "REM": "Mortgage REITs", "IYT": "Transportation", 
    "JETS": "Airlines", "XHB": "Homebuilders", "ITB": "Home Construction", "PAVE": "Infrastructure", 
    "XBI": "Biotech", "IHI": "Medical Devices", "IHF": "Healthcare Providers", "PPH": "Pharmaceuticals", 
    "XRT": "Retail", "PBJ": "Food & Beverage", "PEJ": "Leisure & Ent.", "BETZ": "Sports Betting", 
    "XOP": "Oil & Gas E&P", "OIH": "Oil Services", "TAN": "Solar", "FAN": "Wind Energy", 
    "CRAK": "Oil Refining", "GDX": "Gold Miners", "COPX": "Copper Miners", "URA": "Uranium", 
    "LIT": "Lithium & Battery", "SLX": "Steel", "PICK": "Global Mining", "VIS": "Industrials",
    "IBUY": "Online Retail", "KXI": "Global Consumer Def.", "IYK": "US Consumer Goods", 
    "XME": "Metals & Mining", "SOCL": "Social Media", "XTL": "Telecom", "UTF": "Utilities & Infra", "FIW": "Water"
}

# Build flat metadata dictionary: ticker -> {"Class": ..., "Category": ...}
TICKER_META = {}
for category, tickers in SECTIONS_MACRO.items():
    for t in tickers:
        if t not in TICKER_META:  # Keeps the first mapped category
            TICKER_META[t] = {"Class": "Macro", "Category": category}

for category, tickers in SECTIONS_MICRO.items():
    for t in tickers:
        if t not in TICKER_META:
            TICKER_META[t] = {"Class": "Micro", "Category": category}

ALL_TICKERS = list(TICKER_META.keys())
if BENCHMARK not in ALL_TICKERS: 
    ALL_TICKERS.append(BENCHMARK)
    TICKER_META[BENCHMARK] = {"Class": "Macro", "Category": "Index"}

# ==============================================================================
# DATA FETCHING & MATH
# ==============================================================================
print(f"Fetching 1-Year daily data for {len(ALL_TICKERS)} tickers...")
data = yf.download(ALL_TICKERS, period="1y", group_by="ticker", auto_adjust=True, progress=False, ignore_tz=True)

def get_clean_data(ticker):
    try:
        return data.dropna() if len(ALL_TICKERS) == 1 else data[ticker].dropna()
    except KeyError:
        return pd.DataFrame()

def calculate_atr(df, period=14):
    high_low, high_close, low_close = df['High'] - df['Low'], (df['High'] - df['Close'].shift(1)).abs(), (df['Low'] - df['Close'].shift(1)).abs()
    return pd.concat([high_low, high_close, low_close], axis=1).max(axis=1).rolling(period).mean()

bench_df = get_clean_data(BENCHMARK)
bench_atr = calculate_atr(bench_df)
bench_mom = (bench_df['Close'] - bench_df['Close'].shift(1)) / bench_atr

print("Calculating metrics, VARS, RVOL, and RS Velocity...")
results = {}
for ticker in ALL_TICKERS:
    df = get_clean_data(ticker)
    if len(df) < 100: continue 
    
    current, prev_close, today_open = df['Close'].iloc[-1], df['Close'].iloc[-2], df['Open'].iloc[-1]
    price_1m, price_3m, high_52w = df['Close'].iloc[-22], df['Close'].iloc[-64], df['Close'].max()
    
    pct_id, pct_1d = (current - today_open) / today_open, (current - prev_close) / prev_close
    pct_1m, pct_3m, pct_52w = (current - price_1m) / price_1m, (current - price_3m) / price_3m, (current - high_52w) / high_52w

    avg_vol_50d = df['Volume'].rolling(50).mean().iloc[-1]
    rvol = df['Volume'].iloc[-1] / avg_vol_50d if avg_vol_50d > 0 else 0
    
    vars_daily = ((df['Close'] - df['Close'].shift(1)) / calculate_atr(df)) - bench_mom
    vars_line = vars_daily.rolling(50).sum() 
    
    last_25 = vars_line.tail(25).dropna()
    if len(last_25) == 25 and len(vars_line) >= 30:
        rs_1m_pct = (last_25 < last_25.iloc[-1]).mean() 
        rs_vel = rs_1m_pct - (vars_line.iloc[-30:-5] < vars_line.iloc[-30:-5].iloc[-1]).mean()
    else:
        rs_1m_pct, rs_vel = 0, 0
        
    thrust = ((current / price_3m) / (bench_df['Close'].iloc[-1] / bench_df['Close'].iloc[-64])) - 1

    results[ticker] = {
        "Class": TICKER_META[ticker]["Class"],
        "Category": TICKER_META[ticker]["Category"],
        "RVOL": rvol, "Thrust": thrust, "RS_1M": rs_1m_pct, "Velocity": rs_vel,
        "Spark": df['Close'].tail(22).values, "VARS": last_25.values,
        "% Intraday": pct_id, "% 1D": pct_1d, "% 1M": pct_1m, "% 3M": pct_3m, "% Off 52W": pct_52w
    }

# ==============================================================================
# CONTEXT-AWARE DYNAMIC DISCOVERY ENGINE
# ==============================================================================
valid_tickers = [t for t in ALL_TICKERS if t in results and t != BENCHMARK]

def get_insight_html():
    def stat(t, metric): return results[t][metric]
    
    html = f'''<div style="background-color:#fff; border: 1px solid #ddd; padding: 20px; margin-top: 30px; box-shadow: 0 1px 3px rgba(0,0,0,0.1); max-width: 1300px;">
        <h2 style="margin-top:0; color:#1b5e20;">Top Actionable Discoveries (Context-Aware)</h2><ul style="font-size: 13px; line-height: 1.6;">'''
    
    acc_t = max(valid_tickers, key=lambda t: stat(t, 'Velocity') if stat(t, 'RVOL') > 1.0 else -999)
    if stat(acc_t, 'Velocity') > 0.15:
        nm, vel, vol, off52 = NAMES.get(acc_t, acc_t), stat(acc_t, 'Velocity')*100, stat(acc_t, 'RVOL'), stat(acc_t, '% Off 52W')*100
        if off52 < -15:
            html += f"<li><b>🎣 Bottom Fishing (High Volume): {acc_t} ({nm})</b> - Jumped +{vel:.0f} percentiles on {vol:.1f}x volume. However, it is still {off52:.0f}% off its highs. Smart money may be establishing a floor, but it is fighting a macro downtrend.</li>"
        else:
            html += f"<li><b>🔥 Momentum Breakout: {acc_t} ({nm})</b> - Surged +{vel:.0f} percentiles on {vol:.1f}x volume near its highs ({off52:.0f}% off). This confirms aggressive institutional accumulation aligning with macro strength.</li>"

    dist_t = min(valid_tickers, key=lambda t: stat(t, 'Velocity') if stat(t, 'RVOL') > 1.0 else 999)
    if stat(dist_t, 'Velocity') < -0.15:
        nm, vel, vol, off52, thr = NAMES.get(dist_t, dist_t), stat(dist_t, 'Velocity')*100, stat(dist_t, 'RVOL'), stat(dist_t, '% Off 52W')*100, stat(dist_t, 'Thrust')
        if off52 > -8 and thr > 0:
            html += f"<li><b>📉 Routine Consolidation: {dist_t} ({nm})</b> - Lost {abs(vel):.0f} percentiles on {vol:.1f}x volume, but remains only {off52:.0f}% off highs with a positive 3-month trend. This looks like a healthy pause rather than a structural breakdown.</li>"
        else:
            html += f"<li><b>🩸 Institutional Distribution: {dist_t} ({nm})</b> - Collapsed {abs(vel):.0f} percentiles on {vol:.1f}x volume and sits {off52:.0f}% off highs. Institutions are actively reducing exposure.</li>"

    lead_t = max(valid_tickers, key=lambda t: stat(t, 'Thrust') if stat(t, 'RS_1M') >= 0.8 and stat(t, '% Off 52W') >= -0.05 else -999)
    if stat(lead_t, 'Thrust') > 0 and stat(lead_t, 'RS_1M') >= 0.8:
        html += f"<li><b>👑 The Supreme Leader: {lead_t} ({NAMES.get(lead_t, lead_t)})</b> - Outperforming the market by +{stat(lead_t, 'Thrust')*100:.0f}% over 3 months, holding a dominant {stat(lead_t, 'RS_1M')*100:.0f}% short-term RS rank, and sitting near all-time highs. The trend remains pristine.</li>"

    warn_t = max(valid_tickers, key=lambda t: stat(t, 'RS_1M') if stat(t, 'Velocity') < -0.15 and stat(t, 'Thrust') > 0.05 else -999)
    if stat(warn_t, 'RS_1M') >= 0.7 and stat(warn_t, 'Velocity') < -0.15:
        html += f"<li><b>⚠️ Divergence Warning: {warn_t} ({NAMES.get(warn_t, warn_t)})</b> - Holds a high 1-month RS ({stat(warn_t, 'RS_1M')*100:.0f}%), but underlying momentum is silently decelerating (Velocity: {stat(warn_t, 'Velocity')*100:.0f}). Watch closely for a potential top.</li>"
    
    return html + "</ul></div>"

# ==============================================================================
# SVG & CSS UI GENERATION
# ==============================================================================
def make_line_sparkline(prices):
    if len(prices) < 2: return ""
    rng = max(prices) - min(prices) if max(prices) != min(prices) else 1
    pts = [f"{(i/(len(prices)-1))*54+3:.1f},{14-((p-min(prices))/rng)*10+2:.1f}" for i, p in enumerate(prices)]
    mx, my = pts[list(prices).index(max(prices))].split(',')
    return f'<svg width="60" height="18" style="overflow:visible;"><polyline fill="none" stroke="#2e7d32" stroke-width="1.5" points="{" ".join(pts)}"/><circle cx="{mx}" cy="{my}" r="2.5" fill="#1b5e20"/></svg>'

def make_bar_sparkline(v_data):
    if len(v_data) < 2: return ""
    rng = max(v_data) - min(v_data) if max(v_data) != min(v_data) else 1
    rects = [f'<rect x="{i*(60/len(v_data)):.1f}" y="{15-max(((v-min(v_data))/rng)*15, 1):.1f}" width="1.8" height="{max(((v-min(v_data))/rng)*15, 1):.1f}" fill="{"#1b5e20" if v==max(v_data) else "#81c784"}"/>' for i, v in enumerate(v_data)]
    return f'<svg width="60" height="18">{"".join(rects)}</svg>'

def get_color_class(val, metric_type="standard"):
    if metric_type == "rank": return "bg-green-dark" if val >= 0.8 else "bg-green" if val >= 0.5 else "bg-red-dark" if val <= 0.2 else "bg-red"
    elif metric_type == "rvol": return "bg-green-dark" if val >= 1.5 else "bg-green" if val >= 1.2 else "bg-red" if val <= 0.5 else ""
    elif metric_type == "velocity": return "bg-green-dark" if val >= 0.3 else "bg-green" if val >= 0.1 else "bg-red-dark" if val <= -0.3 else "bg-red" if val <= -0.1 else ""
    return "bg-green" if val > 0 else "bg-red" if val < 0 else ""

def build_unified_html_table():
    html_out = f'<h2 style="margin-top:30px; margin-bottom:5px; color:#333;">Master Flow Matrix (Globally Ranked)</h2><table>'
    
    # Generate Sticky Headers
    html_out += '''<thead>
        <tr class="section-header" style="background:#e0e0e0;">
            <th class="left sortable" style="cursor:pointer;" title="Click to sort">Class ↕</th>
            <th class="left sortable" style="cursor:pointer;" title="Click to sort">Category ↕</th>
            <th class="left sortable" style="cursor:pointer;" title="Click to sort">Ticker ↕</th>
            <th class="left sortable" style="cursor:pointer;" title="Click to sort">Index/Name ↕</th>
            <th class="sortable" style="cursor:pointer;" title="Click to sort">RVOL ↕</th>
            <th class="sortable" style="cursor:pointer;" title="Click to sort">3M RS(RSP) ↕</th>
            <th class="sortable" style="cursor:pointer;" title="Click to sort">1-Mth RS % ↕</th>
            <th class="sortable" style="cursor:pointer;" title="Click to sort">RS Vel (5D) ↕</th>
            <th>1-Mth Chart</th><th>1-Mth RS</th>
            <th class="sortable" style="cursor:pointer;" title="Click to sort">% Intraday ↕</th>
            <th class="sortable" style="cursor:pointer;" title="Click to sort">% 1D ↕</th>
            <th class="sortable" style="cursor:pointer;" title="Click to sort">% 1-Mth ↕</th>
            <th class="sortable" style="cursor:pointer;" title="Click to sort">% 3-Mth ↕</th>
            <th class="sortable" style="cursor:pointer;" title="Click to sort">% Off 52W H ↕</th>
        </tr>'''
        
    # Generate Frozen Benchmark Row (Lives inside thead so it stays on top and ignores sorting)
    if BENCHMARK in results:
        t = BENCHMARK
        d = results[t]
        tv_link = f'<a href="https://www.tradingview.com/chart/?symbol={t}" target="_blank" style="text-decoration:none; color:inherit; font-weight:bold;">{t}</a>'
        
        rvol_text = f'{d["RVOL"]:.1f}x'
        if d["RVOL"] > 2.5: rvol_text += " 🔥"
        
        html_out += f'''<tr class="benchmark-row" style="background:#e8f5e9; font-weight:bold;">
            <td class="left" style="color:#2e7d32">{d["Class"]}</td>
            <td class="left" style="color:#2e7d32">{d["Category"]}</td>
            <td class="left" style="color:#2e7d32">{tv_link}</td>
            <td class="left" style="color:#2e7d32">{NAMES.get(t, t)}</td>
            <td class="{get_color_class(d["RVOL"], "rvol")}">{rvol_text}</td>
            <td>benchmark</td><td>-</td><td>-</td>
            <td>{make_line_sparkline(d["Spark"])}</td><td>{make_bar_sparkline(d["VARS"])}</td>
            <td class="{get_color_class(d["% Intraday"])}">{d["% Intraday"]*100:.1f}%</td>
            <td class="{get_color_class(d["% 1D"])}">{d["% 1D"]*100:.1f}%</td>
            <td class="{get_color_class(d["% 1M"])}">{d["% 1M"]*100:.1f}%</td>
            <td class="{get_color_class(d["% 3M"])}">{d["% 3M"]*100:.1f}%</td>
            <td>{d["% Off 52W"]*100:.0f}%</td>
        </tr>'''
    html_out += '</thead><tbody>'

    # Filter out benchmark and sort the remaining by 1-Month RS% (Strongest to Weakest)
    sortable_tickers = [t for t in valid_tickers if t != BENCHMARK]
    sortable_tickers.sort(key=lambda t: results[t]["RS_1M"], reverse=True)
    
    max_drop = min([results[t]["% Off 52W"] for t in sortable_tickers] + [-0.01])
    if max_drop == 0: max_drop = -0.01 

    for t in sortable_tickers:
        d = results[t]
        bw = min(abs(d["% Off 52W"] / max_drop) * 100, 100)
        tv_link = f'<a href="https://www.tradingview.com/chart/?symbol={t}" target="_blank" style="text-decoration:none; color:inherit; font-weight:bold;">{t}</a>'
        
        # Micro gets a faint background color, Macro gets white
        row_class = "row-micro" if d["Class"] == "Micro" else "row-macro"
        
        # Volume Climax Indicator
        rvol_text = f'{d["RVOL"]:.1f}x'
        if d["RVOL"] > 2.5: rvol_text += " 🔥"
        
        html_out += f'<tr class="data-row {row_class}">'
        html_out += f'<td class="left" data-sort="{d["Class"]}">{d["Class"]}</td>'
        html_out += f'<td class="left" data-sort="{d["Category"]}">{d["Category"]}</td>'
        html_out += f'<td class="left" data-sort="{t}">{tv_link}</td>'
        html_out += f'<td class="left" data-sort="{NAMES.get(t, t)}">{NAMES.get(t, t)}</td>'
        html_out += f'<td data-sort="{d["RVOL"]}" class="{get_color_class(d["RVOL"], "rvol")}">{rvol_text}</td>'
        html_out += f'<td data-sort="{d["Thrust"]}" class="{get_color_class(d["Thrust"])}">{d["Thrust"]*100:.0f}%</td>'
        html_out += f'<td data-sort="{d["RS_1M"]}" class="{get_color_class(d["RS_1M"], "rank")}">{d["RS_1M"]*100:.0f}%</td>'
        html_out += f'<td data-sort="{d["Velocity"]}" class="{get_color_class(d["Velocity"], "velocity")}">{f"{d['Velocity']*100:+.0f}" if d['Velocity']!=0 else "0"}</td>'
        html_out += f'<td data-sort="0">{make_line_sparkline(d["Spark"])}</td><td data-sort="0">{make_bar_sparkline(d["VARS"])}</td>'
        
        html_out += f'<td data-sort="{d["% Intraday"]}" class="{get_color_class(d["% Intraday"])}">{d["% Intraday"]*100:.1f}%</td>'
        html_out += f'<td data-sort="{d["% 1D"]}" class="{get_color_class(d["% 1D"])}">{d["% 1D"]*100:.1f}%</td>'
        html_out += f'<td data-sort="{d["% 1M"]}" class="{get_color_class(d["% 1M"])}">{d["% 1M"]*100:.1f}%</td>'
        html_out += f'<td data-sort="{d["% 3M"]}" class="{get_color_class(d["% 3M"])}">{d["% 3M"]*100:.1f}%</td>'
        html_out += f'<td data-sort="{d["% Off 52W"]}" class="bar-cell"><div class="bar-bg" style="width:{bw}%"></div>{d["% Off 52W"]*100:.0f}%</td>'
        html_out += '</tr>'
        
    html_out += '</tbody></table>'
    return html_out

# ==============================================================================
# HTML COMPILATION & PLAYWRIGHT PDF GENERATION
# ==============================================================================
print("Compiling HTML dashboard...")
html = '''<!DOCTYPE html><html><head><meta charset="UTF-8"><title>Institutional Flow Dashboard (v3)</title>
<style>
    body { font-family: Arial, sans-serif; font-size: 11px; margin: 20px; background-color: #f9f9f9;}
    table { border-collapse: collapse; width: 100%; max-width: 1300px; background-color: #fff; box-shadow: 0 1px 3px rgba(0,0,0,0.1); position: relative; }
    th, td { border: 1px solid #ddd; padding: 4px; text-align: center; }
    
    /* Sticky Header Logic */
    th { background: #f2f2f2; font-weight: bold; position: sticky; top: 0; z-index: 10; box-shadow: 0 2px 2px -1px rgba(0, 0, 0, 0.4); }
    .benchmark-row th, .benchmark-row td { position: sticky; top: 25px; z-index: 9; border-bottom: 2px solid #2e7d32; box-shadow: 0 2px 2px -1px rgba(0, 0, 0, 0.4); }
    
    th.sortable:hover { background-color: #ddd; }
    .left { text-align: left; font-weight: bold; }
    .bg-green { background: #c8e6c9; } .bg-green-dark { background: #81c784; }
    .bg-red { background: #ffcdd2; } .bg-red-dark { background: #e57373; }
    
    /* Macro vs Micro Class Styling */
    .row-macro { background-color: #ffffff; }
    .row-micro { background-color: #f8fafc; }
    
    .bar-cell { position: relative; text-align: right; z-index: 1; padding-right: 5px; }
    .bar-bg { position: absolute; right: 0; top: 0; bottom: 0; background: #ff9999; z-index: -1; }
</style></head><body>
'''
html += build_unified_html_table()
html += get_insight_html()

# Javascript to make the table sortable interactively (ignores the thead where benchmark lives)
js_script = '''
<script>
document.addEventListener('DOMContentLoaded', function() {
    document.querySelectorAll('th.sortable').forEach(th => {
        th.addEventListener('click', function() {
            const table = this.closest('table');
            const tbody = table.querySelector('tbody');
            const rows = Array.from(tbody.querySelectorAll('tr.data-row'));
            const colIdx = Array.from(this.parentNode.children).indexOf(this);
            let asc = this.dataset.asc === 'true';
            this.dataset.asc = !asc;
            
            rows.sort((a, b) => {
                let valA = a.children[colIdx].getAttribute('data-sort');
                let valB = b.children[colIdx].getAttribute('data-sort');
                let numA = parseFloat(valA);
                let numB = parseFloat(valB);
                
                if(!isNaN(numA) && !isNaN(numB)) {
                    return asc ? numA - numB : numB - numA;
                } else {
                    return asc ? valA.localeCompare(valB) : valB.localeCompare(valA);
                }
            });
            rows.forEach(tr => tbody.appendChild(tr));
        });
    });
});
</script>
'''
html += js_script
html += '</body></html>'

html_out_path = "market_flow_report.html"
pdf_out_path = "market_flow_report.pdf"

with open(html_out_path, "w", encoding="utf-8") as f: 
    f.write(html)
print(f"Success! HTML saved to {html_out_path}.")

print("Generating PDF snapshot via headless Playwright engine...")
try:
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        abs_path = os.path.abspath(html_out_path)
        page.goto(f"file:///{abs_path.replace(os.sep, '/')}")
        page.wait_for_timeout(1000)
        page.pdf(path=pdf_out_path, format="A3", landscape=True, print_background=True)
        browser.close()
    print(f"Success! High-resolution PDF saved to {pdf_out_path}.")
except Exception as e:
    print(f"Failed to generate PDF. Is Playwright fully installed? Error: {e}")