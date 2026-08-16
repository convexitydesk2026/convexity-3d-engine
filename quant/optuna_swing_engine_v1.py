# ==============================================================================
# File: C:/Users/donca/Desktop/Desktop HP Envy x360 al 22Abr24/Docs Manuel/IBKR_Options/quant/optuna_swing_engine_v1.py
# Version: 1.0
# Date: June 2026
# Role: Lead Quantitative Financial Engineer
#
# Description:
#   Hyper-Optimized Vectorized Swing Trading Optuna Engine (7.5x ATR Core).
#   This script is the core offline backtester that leverages PostgreSQL
#   to load 1-minute and daily data into a massive RAM dictionary. It simulates
#   a path-dependent, capital-constrained portfolio ($1M starting cash, max 15
#   positions) holding swing trades over multiple days. 
#
# Key Features / Architecture:
#   - Memory-Mapped Data Layer: Daily arrays and 1-min arrays stored in RAM cache.
#   - Deadzone Filter: Rejects "barcode" charts with <2% rolling 5-day variance.
#   - Gap-Down Logic: True gap-down execution simulation at market open.
#   - Ratchet Rule: Trailing stop ratchets upward, preserving MAX(Initial_Stop, SMA).
#   - Multi-threading: n_jobs=10 Optuna optimization hitting local Postgres DB.
#
# Dependencies:
#   pip install optuna pandas numpy sqlalchemy psycopg2-binary
#
# Usage:
#   Update DB_URL with your PostgreSQL credentials, then execute:
#   python optuna_swing_engine_v1.py
# ==============================================================================

import os
import optuna
import pandas as pd
import numpy as np
from sqlalchemy import create_engine
import datetime
import logging

# --- DIRECTORY SETUP ---
PROJECT_DIR = r"C:\Users\donca\Desktop\Desktop HP Envy x360 al 22Abr24\Docs Manuel\IBKR_Options\quant"
LOG_DIR = os.path.join(PROJECT_DIR, "Logs")
os.makedirs(LOG_DIR, exist_ok=True)

# --- CONFIGURATION ---
DB_URL = "postgresql+psycopg2://YOUR_USER:YOUR_PASSWORD@localhost:5432/orb20_db" 
STUDY_NAME = "ORB20-ADAPT_Champion_Swing_v1"
N_TRIALS = 500
N_JOBS = 10 
START_AUM = 1_000_000.0
RISK_PCT = 0.001 # 0.1% Global NAV
MAX_POSITIONS = 15

# Date Range
START_DATE = '2016-12-01'
END_DATE = '2025-11-26' 

log_file = os.path.join(LOG_DIR, f"optuna_run_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.log")
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s",
                    handlers=[logging.FileHandler(log_file), logging.StreamHandler()])

class VectorizedSwingEngine:
    def __init__(self):
        self.engine = create_engine(DB_URL)
        self.daily_data = None
        self.minute_cache = {} 
        self.trading_dates = []

    def load_data(self):
        logging.info("Step 1: Calculating Daily Metrics, SMAs & Deadzone Filter...")
        query_daily = f"""
        SELECT 
            trading_date, symbol,
            (array_agg(open ORDER BY "timestamp" ASC))[1] as d_open,
            MAX(high) as d_high,
            MIN(low) as d_low,
            (array_agg(close ORDER BY "timestamp" DESC))[1] as d_close
        FROM public.stock_datum
        WHERE trading_date BETWEEN '{START_DATE}' AND '{END_DATE}'
        GROUP BY trading_date, symbol
        """
        df = pd.read_sql(query_daily, self.engine, parse_dates=['trading_date'])
        df.sort_values(['symbol', 'trading_date'], inplace=True)
        
        # Calculate True Range & ATR
        df['prev_close'] = df.groupby('symbol')['d_close'].shift(1)
        df['tr1'] = df['d_high'] - df['d_low']
        df['tr2'] = abs(df['d_high'] - df['prev_close'])
        df['tr3'] = abs(df['d_low'] - df['prev_close'])
        df['true_range'] = df[['tr1', 'tr2', 'tr3']].max(axis=1)
        df['atr_14'] = df.groupby('symbol')['true_range'].transform(lambda x: x.rolling(14).mean())
        
        # Calculate SMAs
        df['sma_10'] = df.groupby('symbol')['d_close'].transform(lambda x: x.rolling(10).mean())
        df['sma_20'] = df.groupby('symbol')['d_close'].transform(lambda x: x.rolling(20).mean())
        df['sma_50'] = df.groupby('symbol')['d_close'].transform(lambda x: x.rolling(50).mean())
        
        # Calculate Deadzone (5-Day Range)
        df['5d_high'] = df.groupby('symbol')['d_high'].transform(lambda x: x.rolling(5).max())
        df['5d_low'] = df.groupby('symbol')['d_low'].transform(lambda x: x.rolling(5).min())
        df['5d_range_pct'] = (df['5d_high'] - df['5d_low']) / df['5d_low']
        
        # Shift values to T-1 for signals to prevent Look-Ahead bias
        for col in ['d_close', 'atr_14', 'sma_10', 'sma_20', 'sma_50', '5d_range_pct']:
            df[f'{col}_prev'] = df.groupby('symbol')[col].shift(1)
            
        df.dropna(subset=['sma_50_prev', 'atr_14_prev'], inplace=True) # Honors the 50-day blind runway
        
        # Signal Generation
        df['ratio'] = ((df['d_close_prev'] - df['sma_50_prev']) / df['sma_50_prev']) / (df['atr_14_prev'] / df['d_close_prev'])
        df['vol_cond'] = (100 * (df['atr_14_prev'] / df['d_close_prev'])) > 0.5
        df['deadzone_pass'] = df['5d_range_pct_prev'] >= 0.02
        
        self.daily_data = df.set_index(['trading_date', 'symbol'])
        df_candidates = df[(df['ratio'] >= 5.0) & df['vol_cond'] & df['deadzone_pass']].copy()
        
        logging.info(f"Identified {len(df_candidates)} setup candidate days. Fetching Entry 1-Min Bars...")
        df_candidates[['trading_date', 'symbol']].to_sql('temp_optuna_candidates', self.engine, if_exists='replace', index=False)
        
        query_1min = """
        SELECT s.trading_date, s.symbol,
               s."timestamp" AT TIME ZONE 'America/New_York' AS time_et,
               s.open, s.high, s.low, s.close
        FROM public.stock_datum s
        JOIN temp_optuna_candidates t ON s.trading_date = t.trading_date AND s.symbol = t.symbol
        WHERE CAST(s."timestamp" AT TIME ZONE 'America/New_York' AS time) BETWEEN '09:30:00' AND '15:59:00'
        ORDER BY s.trading_date, s.symbol, s."timestamp"
        """
        df_1min = pd.read_sql(query_1min, self.engine, parse_dates=['trading_date', 'time_et'])
        df_1min['min_from_open'] = df_1min['time_et'].dt.hour * 60 + df_1min['time_et'].dt.minute - 570 
        
        for (date, sym), group in df_1min.groupby(['trading_date', 'symbol']):
            self.minute_cache[(date, sym)] = group[['min_from_open', 'open', 'high', 'low', 'close']].values
            
        self.trading_dates = sorted(df.trading_date.unique())
        with self.engine.connect() as conn:
            conn.execute(pd.io.sql.text("DROP TABLE temp_optuna_candidates;"))
            conn.commit()
            
        logging.info("Data mapped. Engine ready for Optuna.")

    def objective(self, trial):
        # Hyperparameters
        p_entry = trial.suggest_categorical('entry_time', [15, 30, 45]) # Mins from open (09:45, 10:00, 10:15)
        p_target = trial.suggest_float('atr_target', 5.0, 10.0, step=0.5)
        p_r_mult = trial.suggest_categorical('transition_r', [1.0, 1.5, 2.0])
        p_sma = trial.suggest_categorical('trailing_sma', ['sma_10_prev', 'sma_20_prev', 'sma_50_prev'])
        
        cash = START_AUM
        open_positions = {}
        daily_nav_curve = []
        
        for date in self.trading_dates:
            # 1. Update BOD NAV
            bod_nav = cash
            for sym, pos in open_positions.items():
                if (date, sym) in self.daily_data.index:
                    bod_nav += pos['shares'] * self.daily_data.loc[(date, sym), 'd_close_prev']
            daily_nav_curve.append(bod_nav)
            target_risk = bod_nav * RISK_PCT
            
            # 2. Manage Existing Positions
            closed_syms = []
            for sym, pos in open_positions.items():
                if (date, sym) not in self.daily_data.index: continue
                
                day_bar = self.daily_data.loc[(date, sym)]
                d_O, d_H, d_L, d_C = day_bar['d_open'], day_bar['d_high'], day_bar['d_low'], day_bar['d_close']
                sma_val = day_bar[p_sma]
                
                if pos['state'] == 'waiting_target':
                    if d_O <= pos['active_stop']: # Gap Down
                        cash += pos['shares'] * (d_O - 0.005)
                        closed_syms.append(sym)
                    elif d_L <= pos['active_stop']: # Intraday Stop Hit
                        cash += pos['shares'] * (pos['active_stop'] - 0.005)
                        closed_syms.append(sym)
                    elif d_H >= pos['target_price']: # Target Hit
                        pos['state'] = 'trailing'
                        pos['active_stop'] = max(pos['initial_stop'], sma_val) # Ratchet Rule
                
                elif pos['state'] == 'trailing':
                    pos['active_stop'] = max(pos['active_stop'], sma_val) # Ratchet Rule
                    if d_O <= pos['active_stop']:
                        cash += pos['shares'] * (d_O - 0.005)
                        closed_syms.append(sym)
                    elif d_L <= pos['active_stop']:
                        cash += pos['shares'] * (pos['active_stop'] - 0.005)
                        closed_syms.append(sym)
                        
            for sym in closed_syms:
                del open_positions[sym]
                
            # 3. New Entries
            if date in self.daily_data.index.get_level_values(0):
                day_data = self.daily_data.xs(date, level='trading_date')
                candidates = day_data[(day_data['ratio'] >= p_target) & day_data['vol_cond'] & day_data['deadzone_pass']].sort_values('ratio', ascending=False)
                
                for sym, row in candidates.iterrows():
                    if len(open_positions) >= MAX_POSITIONS or cash < 100: break
                    if (date, sym) not in self.minute_cache: continue
                    
                    bars = self.minute_cache[(date, sym)]
                    entry_idx = np.where(bars[:, 0] == p_entry)[0]
                    if len(entry_idx) == 0: continue
                    idx = entry_idx[0]
                    
                    lod = np.min(bars[:idx+1, 3])
                    entry_px = bars[idx, 4]
                    if entry_px <= lod: continue
                    
                    risk_per_share = entry_px - lod
                    shares = np.floor(target_risk / risk_per_share)
                    cost = shares * entry_px
                    
                    if cost > cash:
                        shares = np.floor(cash / entry_px)
                        cost = shares * entry_px
                        
                    if shares <= 0: continue
                    
                    cash -= (cost + (shares * 0.005)) # Buy + Comm/Slip
                    target = entry_px + (p_r_mult * risk_per_share)
                    
                    # Day 1 Remainder Simulation
                    day1_exit = False
                    for i in range(idx+1, len(bars)):
                        if bars[i, 3] <= lod:
                            cash += shares * (min(lod, bars[i, 1]) - 0.005)
                            day1_exit = True
                            break
                        if bars[i, 2] >= target:
                            # Target hit on Day 1. Transition to trailing immediately
                            active_stop = max(lod, row[p_sma])
                            # Check trailing stop for rest of day
                            for j in range(i+1, len(bars)):
                                if bars[j, 3] <= active_stop:
                                    cash += shares * (min(active_stop, bars[j, 1]) - 0.005)
                                    day1_exit = True
                                    break
                            break
                            
                    if not day1_exit:
                        open_positions[sym] = {
                            'shares': shares,
                            'initial_stop': lod,
                            'active_stop': lod,
                            'target_price': target,
                            'state': 'trailing' if np.max(bars[idx+1:, 2]) >= target else 'waiting_target'
                        }
        
        # Scoring
        equity_array = np.array(daily_nav_curve)
        if len(equity_array) < 100 or equity_array[-1] <= START_AUM: return -999.0
            
        peak_array = np.maximum.accumulate(equity_array)
        drawdowns = (equity_array - peak_array) / peak_array
        max_dd = abs(np.min(drawdowns))
        if max_dd == 0: return 0.0
            
        years = len(self.trading_dates) / 252.0
        cagr = (equity_array[-1] / START_AUM) ** (1 / years) - 1.0
        return cagr / max_dd

if __name__ == "__main__":
    engine = VectorizedSwingEngine()
    engine.load_data()
    
    optuna_db = DB_URL.replace("orb20_db", "optuna_studies")
    study = optuna.create_study(study_name=STUDY_NAME, storage=optuna_db, direction="maximize", load_if_exists=True)
    
    logging.info(f"Starting {N_JOBS}-Threaded Optuna Sweep...")
    study.optimize(engine.objective, n_trials=N_TRIALS, n_jobs=N_JOBS)
    logging.info(f"Best Calmar: {study.best_trial.value:.4f} | Params: {study.best_trial.params}")