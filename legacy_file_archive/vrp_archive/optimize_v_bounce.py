#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import sys
import optuna
import logging
from datetime import datetime
import pandas as pd

# Add the strategy_executor directory to the Python path to import the executor
sys.path.append(r'C:\ORB20\Scripts\Py_scripts\strategy_executor')
from v_bounce_executor import run_backtest, prepare_daily_data

# Basic Logging Setup
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s', stream=sys.stdout)

# Database for Optuna Studies
OPTUNA_DB = 'postgresql://postgres:iD9nqV7$YW$T$z8@localhost:5432/optuna_studies'
STUDY_NAME = 'v_bounce_statistical_hunt_v2'

# 10-Year Dataset for massive validation run
START_DATE = '2014-01-01'
END_DATE = '2024-01-01'

def create_objective(daily_df, spy_regime, output_dir):
    def objective(trial):
        # 1. Broad Filters
        min_price = trial.suggest_float('min_price', 5.0, 200.0, step=1.0)
        # Suggest min dollar volume (proxy for Market Cap) between 500k and 10M
        min_dollar_volume = 50000000 # Estate AI Directive (Hardcoded $50M)
        
        # 2. V-Bounce Severity Criteria
        drop_threshold_pct = trial.suggest_float('drop_threshold_pct', 0.15, 0.60, step=0.01)
        volume_multiplier = trial.suggest_float('volume_multiplier', 1.0, 5.0, step=0.5)
        
        # 3. Time Constraints
        watchlist_days = trial.suggest_int('watchlist_days', 3, 15)
        
        # 4. Trigger Condition
        strict_trigger = trial.suggest_categorical('strict_trigger', [True, False])
        min_trigger_body_pct = trial.suggest_float('min_trigger_body_pct', 0.0, 0.05, step=0.01)
        
        # 5. Risk Management / Exits
        entry_gap_abort_pct = trial.suggest_float('entry_gap_abort_pct', 0.005, 0.05, step=0.005)
        
        # Add a toggle for whether or not to use trailing stops
        use_trailing_stop = trial.suggest_categorical('use_trailing_stop', [True, False])
        if use_trailing_stop:
            trailing_stop_pct = trial.suggest_float('trailing_stop_pct', 0.02, 0.20, step=0.01)
        else:
            trailing_stop_pct = 9.99 # Effectively disables trailing stop (needs 999% drop)
            
        take_profit_pct = trial.suggest_float('take_profit_pct', 0.10, 0.50, step=0.01)
        max_hold_days = trial.suggest_int('max_hold_days', 2, 10)
        
        # 6. Regime Filters
        require_stock_uptrend = trial.suggest_categorical('require_stock_uptrend', [True, False])
        
        params = {
            'min_price': min_price,
            'min_dollar_volume': min_dollar_volume,
            'drop_threshold_pct': drop_threshold_pct,
            'volume_multiplier': volume_multiplier,
            'watchlist_days': watchlist_days,
            'strict_trigger': strict_trigger,
            'min_trigger_body_pct': min_trigger_body_pct,
            'entry_gap_abort_pct': entry_gap_abort_pct,
            'trailing_stop_pct': trailing_stop_pct,
            'take_profit_pct': take_profit_pct,
            'max_hold_days': max_hold_days,
            'require_stock_uptrend': require_stock_uptrend
        }
        
        logging.info(f"Trial {trial.number} started with params: {params}")
        
        try:
            # Run the backtest using the FAST in-memory approximation method
            results_df = run_backtest(params, daily_df, spy_regime, use_minute_data=False)
            
            if results_df.empty:
                return -100.0 # Punish parameter sets that produce no trades
                
            # Save the results to CSV for this trial
            output_file = os.path.join(output_dir, f'trial_{trial.number}_trades.csv')
            results_df.to_csv(output_file, index=False)
                
            num_trades = len(results_df)
            
            if num_trades < 5:
                return -50.0 
                
            # Our primary optimization metric: The Average PnL per trade
            # We want to maximize the statistical expectancy of the bounce.
            avg_pnl = results_df['pnl_pct'].mean()
            
            # Alternatively, we could maximize (Win Rate * Avg PnL), but average PnL natively accounts for both.
            # Adding a tiny bonus for high trade count to break ties between similar strategies
            score = avg_pnl + (num_trades * 0.00001)
            
            return score
            
        except Exception as e:
            logging.error(f"Trial {trial.number} failed: {str(e)}")
            return -100.0
            
    return objective

if __name__ == "__main__":
    logging.info(f"Initializing Optuna Study: {STUDY_NAME}")
    
    # 1. Prepare Data ONCE
    logging.info("Preparing data globally for all trials...")
    daily_df, spy_regime = prepare_daily_data(START_DATE, END_DATE)
    
    # 2. Setup output directory for trial CSVs
    output_dir = r'C:\ORB20\Scripts\Py_scripts\Optuna\trial_stock_lists'
    os.makedirs(output_dir, exist_ok=True)
    
    # Create or load the study from the PostgreSQL database
    study = optuna.create_study(
        study_name=STUDY_NAME,
        storage=OPTUNA_DB,
        direction='maximize',
        load_if_exists=True
    )
    
    # HARDWARE OPTIMIZATION: 
    # Your i7-1260P has 16 logical threads and 64GB RAM.
    # We will use 10 parallel workers (n_jobs=10). 
    # This leaves 6 threads completely free for you to use the PC without lag.
    logging.info("Starting optimization with 10 parallel workers...")
    
    # Run 500 trials sequentially for the massive 10-year search
    study.optimize(create_objective(daily_df, spy_regime, output_dir), n_trials=500, n_jobs=10)
    
    logging.info("Optimization Completed!")
    logging.info(f"Best Trial: {study.best_trial.number}")
    logging.info(f"Best Score (Avg PnL): {study.best_value:.4%}")
    logging.info("Best Parameters:")
    for key, value in study.best_trial.params.items():
        logging.info(f"  {key}: {value}")
