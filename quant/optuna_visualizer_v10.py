# ==============================================================================
# File: C:/Users/donca/Desktop/Desktop HP Envy x360 al 22Abr24/Docs Manuel/IBKR_Options/quant/optuna_visualizer_v10.py
# Version: 10.0
# Description:
#   Visualizer adapted to the V10 Anti-Cash-Leak logic.
# ==============================================================================

import os
import optuna
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import webbrowser
from sqlalchemy import text

# Import from the v10 engine script
from optuna_swing_engine_v10 import VectorizedSwingEngine, PROJECT_DIR

def visualize_champion_run():
    print("Loading Core Engine & Dependencies...")
    engine = VectorizedSwingEngine()
    
    study_name = engine.opt_config.get('Study', 'name')
    study = optuna.load_study(study_name=study_name, storage=engine.optuna_url)
    
    best_params = study.best_trial.params
    print(f"WINNING PARAMETERS FOUND: {best_params}")
    
    p_entry = int(best_params['entry_time'])
    p_target = float(best_params['atr_target'])
    p_r_mult = float(best_params['transition_r'])
    p_sma = str(best_params['trailing_sma'])

    engine.load_data()
    
    cash = engine.start_aum
    open_positions = {}
    daily_nav = []
    daily_pos_count = []
    trade_logs = []
    
    print("Simulating Champion Run...")
    for date in engine.trading_dates:
        bod_nav = cash
        for sym, pos in open_positions.items():
            if (date, sym) in engine.daily_dict:
                bod_nav += pos['shares'] * engine.daily_dict[(date, sym)]['d_close_prev']
                
        daily_nav.append({'Date': date, 'NAV': bod_nav})
        daily_pos_count.append(len(open_positions))
        target_risk = bod_nav * engine.risk_pct
        max_capital_per_trade = bod_nav / engine.max_positions
        
        closed_syms = []
        for sym, pos in open_positions.items():
            if (date, sym) not in engine.daily_dict: continue
            
            day_bar = engine.daily_dict[(date, sym)]
            d_O = day_bar['d_open']
            d_H = day_bar['d_high']
            d_L = day_bar['d_low']
            sma_val = day_bar[p_sma]
            
            exit_price = None
            exit_time_str = "TBD"
            
            if pos['state'] == 'waiting_target':
                if d_O <= pos['active_stop']: 
                    exit_price = d_O
                elif d_L <= pos['active_stop']: 
                    exit_price = pos['active_stop']
                elif d_H >= pos['target_price']: 
                    pos['state'] = 'trailing'
                    pos['active_stop'] = max(pos['initial_stop'], sma_val) 
            elif pos['state'] == 'trailing':
                pos['active_stop'] = max(pos['active_stop'], sma_val)
                if d_O <= pos['active_stop']: 
                    exit_price = d_O
                elif d_L <= pos['active_stop']: 
                    exit_price = pos['active_stop']
            
            if exit_price is not None:
                cash += pos['shares'] * (exit_price - 0.005)
                closed_syms.append(sym)
                
                query = f"""
                SELECT "timestamp" AT TIME ZONE 'America/New_York' as time_et
                FROM stock_datum 
                WHERE symbol = '{sym}' AND trading_date = '{date.strftime('%Y-%m-%d')}'
                  AND low <= {pos['active_stop']}
                ORDER BY "timestamp" ASC LIMIT 1
                """
                with engine.engine.connect() as conn:
                    res = conn.execute(text(query)).fetchone()
                    exit_time_str = str(res[0]) if res else f"{date.strftime('%Y-%m-%d')} 09:30:00 (Gap)"
                
                trade_logs.append({
                    'symbol': sym, 'entry_time': pos['entry_time'], 'exit_time': exit_time_str,
                    'shares': pos['shares'], 'entry_price': pos['entry_price'], 'exit_price': exit_price,
                    'pnl': pos['shares'] * (exit_price - pos['entry_price'] - 0.01)
                })
                    
        for sym in closed_syms: del open_positions[sym]
            
        candidates = engine.candidates_by_date.get(date, [])
        for row in candidates:
            if row['ratio'] < p_target: continue
            sym = row['symbol']
            
            # V10 FIX: THE ANTI BLACK-HOLE CHECK
            if sym in open_positions: continue
            
            if len(open_positions) >= engine.max_positions or cash < 100: break
            if (date, sym) not in engine.minute_cache: continue
            
            bars = engine.minute_cache[(date, sym)]
            idx_arr = np.where(bars[:, 0] == p_entry)[0]
            if len(idx_arr) == 0: continue
            idx = idx_arr[0]
            
            lod = np.min(bars[:idx+1, 3])
            entry_px = bars[idx, 4]
            if entry_px <= lod: continue
            
            min_stop_distance = entry_px * 0.005
            if (entry_px - lod) < min_stop_distance:
                lod = entry_px - min_stop_distance
            
            risk_ps = entry_px - lod
            if risk_ps <= 0: continue 
            
            shares = np.floor(target_risk / risk_ps)
            
            cost_per_share = entry_px + 0.005
            desired_cost = shares * cost_per_share
            
            allowed_cash = min(cash, max_capital_per_trade)
            if desired_cost > allowed_cash:
                shares = np.floor(allowed_cash / cost_per_share)
            
            if shares <= 0: continue
            
            cash -= (shares * cost_per_share)
            target = entry_px + (p_r_mult * risk_ps)
            
            entry_time_str = f"{date.strftime('%Y-%m-%d')} {int(9 + (30+p_entry)//60):02d}:{(30+p_entry)%60:02d}:00"
            
            day1_exit = False
            day1_target_hit = False
            
            for i in range(idx+1, len(bars)):
                if bars[i, 3] <= lod:
                    exit_price = min(lod, bars[i, 1])
                    cash += shares * (exit_price - 0.005)
                    day1_exit = True
                    
                    exit_min_offset = int(bars[i, 0])
                    exit_time_str = f"{date.strftime('%Y-%m-%d')} {int(9 + (30+exit_min_offset)//60):02d}:{(30+exit_min_offset)%60:02d}:00"
                    
                    trade_logs.append({
                        'symbol': sym, 'entry_time': entry_time_str, 'exit_time': exit_time_str,
                        'shares': shares, 'entry_price': entry_px, 'exit_price': exit_price,
                        'pnl': shares * (exit_price - entry_px - 0.01)
                    })
                    break
                if bars[i, 2] >= target:
                    day1_target_hit = True
                    active_stop = max(lod, row[p_sma])
                    for j in range(i+1, len(bars)):
                        if bars[j, 3] <= active_stop:
                            exit_price = min(active_stop, bars[j, 1])
                            cash += shares * (exit_price - 0.005)
                            day1_exit = True
                            
                            exit_min_offset = int(bars[j, 0])
                            exit_time_str = f"{date.strftime('%Y-%m-%d')} {int(9 + (30+exit_min_offset)//60):02d}:{(30+exit_min_offset)%60:02d}:00"
                            
                            trade_logs.append({
                                'symbol': sym, 'entry_time': entry_time_str, 'exit_time': exit_time_str,
                                'shares': shares, 'entry_price': entry_px, 'exit_price': exit_price,
                                'pnl': shares * (exit_price - entry_px - 0.01)
                            })
                            break
                    break
                    
            if not day1_exit:
                open_positions[sym] = {
                    'shares': shares, 'entry_price': entry_px, 'entry_time': entry_time_str,
                    'initial_stop': lod, 
                    'active_stop': max(lod, row[p_sma]) if day1_target_hit else lod, 
                    'target_price': target, 
                    'state': 'trailing' if day1_target_hit else 'waiting_target'
                }

    if trade_logs:
        print("Uploading Trade Logs to Database: champion_trade_log")
        df_logs = pd.DataFrame(trade_logs)
        df_logs.to_sql('champion_trade_log', engine.engine, if_exists='replace', index=False)
    else:
        print("No trades were taken by the champion. Log table skipped.")

    print("Generating HTML chart...")
    df_nav = pd.DataFrame(daily_nav)
    df_nav['HighWaterMark'] = df_nav['NAV'].cummax()
    df_nav['Drawdown'] = (df_nav['NAV'] - df_nav['HighWaterMark']) / df_nav['HighWaterMark']
    
    fig = make_subplots(rows=2, cols=1, shared_xaxes=True, row_heights=[0.7, 0.3], vertical_spacing=0.05)
    fig.add_trace(go.Scatter(x=df_nav['Date'], y=df_nav['NAV'], name="Portfolio NAV", line=dict(color='limegreen')), row=1, col=1)
    fig.add_trace(go.Scatter(x=df_nav['Date'], y=daily_pos_count, name="Active Positions", fill='tozeroy', line=dict(color='royalblue')), row=2, col=1)
    
    subtitle = f"Params: Entry: {p_entry}m | Target: {p_target} | R-Mult: {p_r_mult} | SMA: {p_sma}"
    fig.update_layout(title=f"Champion Equity Curve (7.5x ATR Core)<br><sup>{subtitle}</sup>", template="plotly_dark", height=800)
    
    out_path = os.path.join(PROJECT_DIR, "champion_visualization.html")
    fig.write_html(out_path)
    
    try:
        webbrowser.open(f'file://{os.path.realpath(out_path)}')
    except Exception:
        pass
        
if __name__ == "__main__":
    visualize_champion_run()