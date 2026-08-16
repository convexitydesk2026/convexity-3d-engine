# ==============================================================================
# File: C:/Users/donca/Desktop/Desktop HP Envy x360 al 22Abr24/Docs Manuel/IBKR_Options/quant/optuna_swing_engine_v2.py
# Version: 2.0
# Date: June 2026
# Role: Lead Quantitative Financial Engineer
#
# Description:
#   Vectorized Swing Trading Optuna Engine (7.5x ATR Core).
#   v2 introduces dynamic INI configuration parsing for both Database Credentials
#   and Optuna Hyperparameters, completely decoupling logic from parameters.
#
# Dependencies:
#   pip install optuna pandas numpy sqlalchemy psycopg2-binary
# ==============================================================================

import os
import re
import configparser
import optuna
import pandas as pd
import numpy as np
from sqlalchemy import create_engine
import datetime
import logging

# --- DIRECTORY & CONFIG SETUP ---
PROJECT_DIR = r"C:\Users\donca\Desktop\Desktop HP Envy x360 al 22Abr24\Docs Manuel\IBKR_Options\quant"
LOG_DIR = os.path.join(PROJECT_DIR, "Logs")
os.makedirs(LOG_DIR, exist_ok=True)

# File Paths
DB_CONFIG_PATH = r"C:\ORB20\Scripts\Py_scripts\DB_upload_config.ini"
OPTUNA_CONFIG_PATH = os.path.join(PROJECT_DIR, "optimizer_config_7_5x_ATR.ini")

log_file = os.path.join(LOG_DIR, f"optuna_run_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.log")
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s",
                    handlers=[logging.FileHandler(log_file), logging.StreamHandler()])

class VectorizedSwingEngine:
    def __init__(self):
        # 1. Load DB Credentials
        db_config = configparser.ConfigParser()
        db_config.read(DB_CONFIG_PATH)
        db_creds = db_config['database']
        
        self.db_url = f"postgresql+psycopg2://{db_creds['username']}:{db_creds['password']}@{db_creds['host']}:{db_creds['port']}/{db_creds['dbname']}"
        self.optuna_url = f"postgresql+psycopg2://{db_creds['username']}:{db_creds['password']}@{db_creds['host']}:{db_creds['port']}/optuna_studies"
        self.engine = create_engine(self.db_url)
        
        # 2. Load Optuna Study Configurations
        self.opt_config = configparser.ConfigParser()
        self.opt_config.read(OPTUNA_CONFIG_PATH)
        
        self.start_date = self.opt_config.get('Fixed_Parameters', 'start_date')
        self.end_date = self.opt_config.get('Fixed_Parameters', 'end_date')
        self.start_aum = self.opt_config.getfloat('Fixed_Parameters', 'initial_aum')
        self.risk_pct = self.opt_config.getfloat('Fixed_Parameters', 'risk_pct')
        self.max_positions = self.opt_config.getint('Fixed_Parameters', 'max_positions')
        
        self.daily_data = None
        self.minute_cache = {} 
        self.trading_dates = []

    def load_data(self):
        logging.info("Step 1: Calculating Daily Metrics, SMAs & Deadzone Filter...")
        query_daily = f"""
        SELECT 
            trading_date, symbol,
            MAX(daily_open) as d_open,
            MAX(daily_high) as d_high,
            MAX(daily_low) as d_low,
            MAX(daily_close) as d_close
        FROM public.stock_datum
        WHERE trading_date BETWEEN '{self.start_date}' AND '{self.end_date}'
        GROUP BY trading_date, symbol
        """
        df = pd.read_sql(query_daily, self.engine, parse_dates=['trading_date'])
        df.sort_values(['symbol', 'trading_date'], inplace=True)
        
        df['prev_close'] = df.groupby('symbol')['d_close'].shift(1)
        df['tr1'] = df['d_high'] - df['d_low']
        df['tr2'] = abs(df['d_high'] - df['prev_close'])
        df['tr3'] = abs(df['d_low'] - df['prev_close'])
        df['true_range'] = df[['tr1', 'tr2', 'tr3']].max(axis=1)
        df['atr_14'] = df.groupby('symbol')['true_range'].transform(lambda x: x.rolling(14).mean())
        
        df['sma_10'] = df.groupby('symbol')['d_close'].transform(lambda x: x.rolling(10).mean())
        df['sma_20'] = df.groupby('symbol')['d_close'].transform(lambda x: x.rolling(20).mean())
        df['sma_50'] = df.groupby('symbol')['d_close'].transform(lambda x: x.rolling(50).mean())
        
        df['5d_high'] = df.groupby('symbol')['d_high'].transform(lambda x: x.rolling(5).max())
        df['5d_low'] = df.groupby('symbol')['d_low'].transform(lambda x: x.rolling(5).min())
        df['5d_range_pct'] = (df['5d_high'] - df['5d_low']) / df['5d_low']
        
        for col in ['d_close', 'atr_14', 'sma_10', 'sma_20', 'sma_50', '5d_range_pct']:
            df[f'{col}_prev'] = df.groupby('symbol')[col].shift(1)
            
        df.dropna(subset=['sma_50_prev', 'atr_14_prev'], inplace=True) 
        
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
        # Dynamic INI Parameter Parsing
        params = {}
        space = self.opt_config['Hyperparameter_Space']
        
        for key, value in space.items():
            value_str = value.strip()
            categorical_match = re.match(r'categorical\((.*?)\)', value_str)
            if categorical_match:
                params[key] = trial.suggest_categorical(key, [c.strip() for c in categorical_match.group(1).split(',')])
                continue
            parts = [p.strip() for p in value_str.split(',')]
            if all('.' not in p for p in parts):
                p_int = [int(p) for p in parts]
                params[key] = trial.suggest_int(key, p_int[0], p_int[1], step=p_int[2] if len(p_int) > 2 else 1)
            else:
                p_float = [float(p) for p in parts]
                params[key] = trial.suggest_float(key, p_float[0], p_float[1], step=p_float[2] if len(p_float) > 2 else None)
        
        # Explicit type casting for logic operations
        p_entry = int(params['entry_time'])
        p_target = float(params['atr_target'])
        p_r_mult = float(params['transition_r'])
        p_sma = str(params['trailing_sma'])
        
        cash = self.start_aum
        open_positions = {}
        daily_nav_curve = []
        
        for date in self.trading_dates:
            bod_nav = cash
            for sym, pos in open_positions.items():
                if (date, sym) in self.daily_data.index:
                    bod_nav += pos['shares'] * self.daily_data.loc[(date, sym), 'd_close_prev']
            daily_nav_curve.append(bod_nav)
            target_risk = bod_nav * self.risk_pct
            
            closed_syms = []
            for sym, pos in open_positions.items():
                if (date, sym) not in self.daily_data.index: continue
                
                day_bar = self.daily_data.loc[(date, sym)]
                d_O, d_H, d_L = day_bar['d_open'], day_bar['d_high'], day_bar['d_low']
                sma_val = day_bar[p_sma]
                
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
                
            if date in self.daily_data.index.get_level_values(0):
                day_data = self.daily_data.xs(date, level='trading_date')
                candidates = day_data[(day_data['ratio'] >= p_target) & day_data['vol_cond'] & day_data['deadzone_pass']].sort_values('ratio', ascending=False)
                
                for sym, row in candidates.iterrows():
                    if len(open_positions) >= self.max_positions or cash < 100: break
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
                    
                    cash -= (cost + (shares * 0.005)) 
                    target = entry_px + (p_r_mult * risk_per_share)
                    
                    day1_exit = False
                    for i in range(idx+1, len(bars)):
                        if bars[i, 3] <= lod:
                            cash += shares * (min(lod, bars[i, 1]) - 0.005)
                            day1_exit = True
                            break
                        if bars[i, 2] >= target:
                            active_stop = max(lod, row[p_sma])
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
        
        equity_array = np.array(daily_nav_curve)
        if len(equity_array) < 100 or equity_array[-1] <= self.start_aum: return -999.0
            
        peak_array = np.maximum.accumulate(equity_array)
        drawdowns = (equity_array - peak_array) / peak_array
        max_dd = abs(np.min(drawdowns))
        if max_dd == 0: return 0.0
            
        years = len(self.trading_dates) / 252.0
        cagr = (equity_array[-1] / self.start_aum) ** (1 / years) - 1.0
        return cagr / max_dd

if __name__ == "__main__":
    engine = VectorizedSwingEngine()
    
    study_name = engine.opt_config.get('Study', 'name')
    n_trials = engine.opt_config.getint('Study', 'n_trials')
    n_jobs = engine.opt_config.getint('Study', 'n_jobs')
    
    engine.load_data()
    study = optuna.create_study(study_name=study_name, storage=engine.optuna_url, direction="maximize", load_if_exists=True)
    
    logging.info(f"Starting {n_jobs}-Threaded Optuna Sweep for Study: {study_name}...")
    study.optimize(engine.objective, n_trials=n_trials, n_jobs=n_jobs)
    logging.info(f"Best Calmar: {study.best_trial.value:.4f} | Params: {study.best_trial.params}")