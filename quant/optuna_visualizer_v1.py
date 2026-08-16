# ==============================================================================
# File: C:/Users/donca/Desktop/Desktop HP Envy x360 al 22Abr24/Docs Manuel/IBKR_Options/quant/optuna_visualizer_v1.py
# Version: 1.0
# Date: June 2026
# Role: Lead Quantitative Financial Engineer
#
# Description:
#   Standalone visualizer for the 7.5x ATR Swing Trading Engine. 
#   This script imports the core engine, runs a single vectorized backtest 
#   using a specific set of parameters, and outputs an interactive Plotly 
#   HTML dashboard of the Equity Curve and Active Positions over time.
#
# Key Features / Architecture:
#   - Isolated run: Does not trigger the Optuna optimizer.
#   - Interactive HTML: Generates 'backtest_visualization.html' and opens it automatically.
#   - Seamless Integration: Shares the exact mathematical engine state from v1.
#
# Dependencies:
#   pip install pandas numpy plotly
#
# Usage:
#   1. Ensure `optuna_swing_engine_v1.py` is in the same directory.
#   2. Adjust TEST_PARAMS dict within this script if you want to test specific hyperparams.
#   3. Execute: python optuna_visualizer_v1.py
# ==============================================================================

import os
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import webbrowser

# IMPORTANT: Ensure the import correctly points to the v1 engine script
from optuna_swing_engine_v1 import VectorizedSwingEngine, PROJECT_DIR

# --- TEST PARAMETERS ---
# Edit these to the parameters you want to visualize (usually grabbed from your best Optuna trial)
TEST_PARAMS = {
    'entry_time': 30,             # 15=09:45, 30=10:00, 45=10:15
    'atr_target': 7.5,            # 5.0 to 10.0
    'transition_r': 1.5,          # 1.0, 1.5, 2.0
    'trailing_sma': 'sma_20_prev' # sma_10_prev, sma_20_prev, sma_50_prev
}

def visualize_run():
    print("Loading data via VectorizedSwingEngine...")
    engine = VectorizedSwingEngine()
    engine.load_data()
    
    cash = 1_000_000.0
    open_positions = {}
    daily_nav = []
    daily_pos_count = []
    
    print("Simulating single run with TEST_PARAMS...")
    for date in engine.trading_dates:
        bod_nav = cash
        for sym, pos in open_positions.items():
            if (date, sym) in engine.daily_data.index:
                bod_nav += pos['shares'] * engine.daily_data.loc[(date, sym), 'd_close_prev']
                
        daily_nav.append({'Date': date, 'NAV': bod_nav})
        daily_pos_count.append(len(open_positions))
        target_risk = bod_nav * 0.001
        
        closed_syms = []
        for sym, pos in open_positions.items():
            if (date, sym) not in engine.daily_data.index: continue
            day_bar = engine.daily_data.loc[(date, sym)]
            d_O, d_H, d_L = day_bar['d_open'], day_bar['d_high'], day_bar['d_low']
            sma_val = day_bar[TEST_PARAMS['trailing_sma']]
            
            if pos['state'] == 'waiting_target':
                if d_O <= pos['active_stop']: 
                    cash += pos['shares'] * (d_O - 0.005); closed_syms.append(sym)
                elif d_L <= pos['active_stop']: 
                    cash += pos['shares'] * (pos['active_stop'] - 0.005); closed_syms.append(sym)
                elif d_H >= pos['target_price']: 
                    pos['state'] = 'trailing'
                    pos['active_stop'] = max(pos['initial_stop'], sma_val) 
            elif pos['state'] == 'trailing':
                pos['active_stop'] = max(pos['active_stop'], sma_val)
                if d_O <= pos['active_stop']: 
                    cash += pos['shares'] * (d_O - 0.005); closed_syms.append(sym)
                elif d_L <= pos['active_stop']: 
                    cash += pos['shares'] * (pos['active_stop'] - 0.005); closed_syms.append(sym)
                    
        for sym in closed_syms: del open_positions[sym]
            
        if date in engine.daily_data.index.get_level_values(0):
            day_data = engine.daily_data.xs(date, level='trading_date')
            candidates = day_data[(day_data['ratio'] >= TEST_PARAMS['atr_target']) & day_data['vol_cond'] & day_data['deadzone_pass']].sort_values('ratio', ascending=False)
            
            for sym, row in candidates.iterrows():
                if len(open_positions) >= 15 or cash < 100: break
                if (date, sym) not in engine.minute_cache: continue
                
                bars = engine.minute_cache[(date, sym)]
                idx_arr = np.where(bars[:, 0] == TEST_PARAMS['entry_time'])[0]
                if len(idx_arr) == 0: continue
                idx = idx_arr[0]
                
                lod = np.min(bars[:idx+1, 3])
                entry_px = bars[idx, 4]
                if entry_px <= lod: continue
                
                risk_ps = entry_px - lod
                shares = np.floor(target_risk / risk_ps)
                cost = shares * entry_px
                if cost > cash:
                    shares = np.floor(cash / entry_px)
                    cost = shares * entry_px
                if shares <= 0: continue
                
                cash -= (cost + (shares * 0.005))
                target = entry_px + (TEST_PARAMS['transition_r'] * risk_ps)
                
                day1_exit = False
                for i in range(idx+1, len(bars)):
                    if bars[i, 3] <= lod:
                        cash += shares * (min(lod, bars[i, 1]) - 0.005)
                        day1_exit = True
                        break
                    if bars[i, 2] >= target:
                        active_stop = max(lod, row[TEST_PARAMS['trailing_sma']])
                        for j in range(i+1, len(bars)):
                            if bars[j, 3] <= active_stop:
                                cash += shares * (min(active_stop, bars[j, 1]) - 0.005)
                                day1_exit = True
                                break
                        break
                        
                if not day1_exit:
                    open_positions[sym] = {
                        'shares': shares, 'initial_stop': lod, 'active_stop': lod,
                        'target_price': target, 'state': 'trailing' if np.max(bars[idx+1:, 2]) >= target else 'waiting_target'
                    }

    # Plotting
    print("Backtest complete. Generating HTML chart...")
    df_nav = pd.DataFrame(daily_nav)
    df_nav['HighWaterMark'] = df_nav['NAV'].cummax()
    df_nav['Drawdown'] = (df_nav['NAV'] - df_nav['HighWaterMark']) / df_nav['HighWaterMark']
    
    fig = make_subplots(rows=2, cols=1, shared_xaxes=True, row_heights=[0.7, 0.3], vertical_spacing=0.05)
    fig.add_trace(go.Scatter(x=df_nav['Date'], y=df_nav['NAV'], name="Portfolio NAV", line=dict(color='limegreen')), row=1, col=1)
    fig.add_trace(go.Scatter(x=df_nav['Date'], y=daily_pos_count, name="Active Positions", fill='tozeroy', line=dict(color='royalblue')), row=2, col=1)
    
    fig.update_layout(title="Swing Trading Equity Curve (7.5x ATR Core)", template="plotly_dark", height=800)
    
    out_path = os.path.join(PROJECT_DIR, "backtest_visualization.html")
    fig.write_html(out_path)
    print(f"Done! Chart saved to: {out_path}")
    
    try:
        webbrowser.open(f'file://{os.path.realpath(out_path)}')
    except Exception as e:
        print(f"Could not automatically open browser. File is located at: {out_path}")

if __name__ == "__main__":
    visualize_run()