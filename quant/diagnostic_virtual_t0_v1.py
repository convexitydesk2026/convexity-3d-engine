# ==============================================================================
# File: C:/Users/donca/Desktop/Desktop HP Envy x360 al 22Abr24/Docs Manuel/IBKR_Options/quant/diagnostic_virtual_t0_v1.py
# Version: 1.0
# Date: June 2026
# Description:
#   Diagnostic tool to verify the "Micro-Stop" LOD bug against TC2000.
#   It treats a historical date as "Today" (T-0), calculates the T-1 signals,
#   identifies the Top 100 candidates, and calculates the exact unpadded
#   Low of Day (LOD) and Entry Price for the 09:45, 10:00, and 10:15 time slots.
#
# Dependencies: pandas, sqlalchemy, psycopg2-binary
# Usage: python diagnostic_virtual_t0_v1.py
# ==============================================================================

import os
import pandas as pd
import numpy as np
from sqlalchemy import create_engine
import configparser
import logging

PROJECT_DIR = r"C:\Users\donca\Desktop\Desktop HP Envy x360 al 22Abr24\Docs Manuel\IBKR_Options\quant"
DB_CONFIG_PATH = r"C:\ORB20\Scripts\Py_scripts\DB_upload_config.ini"

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

# --- VIRTUAL T-0 CONFIGURATION ---
VIRTUAL_T0 = '2025-11-14'
LOOKBACK_START = '2025-06-01' # 5+ months of runway for the 50 SMA
MIN_OPEN_PRICE = 4.0

def run_diagnostics():
    logging.info(f"Starting Virtual T-0 Diagnostic for {VIRTUAL_T0}...")
    
    # 1. Connect to Database
    config = configparser.ConfigParser()
    config.read(DB_CONFIG_PATH)
    creds = config['database']
    db_url = f"postgresql+psycopg2://{creds['username']}:{creds['password']}@{creds['host']}:{creds['port']}/{creds['dbname']}"
    engine = create_engine(db_url)
    
    # 2. Fetch Daily Data & Calculate T-1 Signals
    logging.info("Fetching Daily Data and calculating T-1 indicators...")
    query_daily = f"""
    SELECT trading_date, symbol, d_open, d_high, d_low, d_close
    FROM public.daily_ohlc_cache
    WHERE trading_date BETWEEN '{LOOKBACK_START}' AND '{VIRTUAL_T0}'
    """
    df = pd.read_sql(query_daily, engine, parse_dates=['trading_date'])
    df = df[df['symbol'].str.isalpha()]
    df.sort_values(['symbol', 'trading_date'], inplace=True)
    
    df['prev_close'] = df.groupby('symbol')['d_close'].shift(1)
    df['tr1'] = df['d_high'] - df['d_low']
    df['tr2'] = abs(df['d_high'] - df['prev_close'])
    df['tr3'] = abs(df['d_low'] - df['prev_close'])
    df['true_range'] = df[['tr1', 'tr2', 'tr3']].max(axis=1)
    df['atr_14'] = df.groupby('symbol')['true_range'].transform(lambda x: x.rolling(14).mean())
    df['sma_50'] = df.groupby('symbol')['d_close'].transform(lambda x: x.rolling(50).mean())
    df['5d_high'] = df.groupby('symbol')['d_high'].transform(lambda x: x.rolling(5).max())
    df['5d_low'] = df.groupby('symbol')['d_low'].transform(lambda x: x.rolling(5).min())
    df['5d_range_pct'] = (df['5d_high'] - df['5d_low']) / df['5d_low']
    
    for col in ['d_close', 'atr_14', 'sma_50', '5d_range_pct']:
        df[f'{col}_prev'] = df.groupby('symbol')[col].shift(1)
        
    df.dropna(subset=['sma_50_prev', 'atr_14_prev'], inplace=True) 
    
    df['ratio'] = ((df['d_close_prev'] - df['sma_50_prev']) / df['sma_50_prev']) / (df['atr_14_prev'] / df['d_close_prev'])
    df['vol_cond'] = (100 * (df['atr_14_prev'] / df['d_close_prev'])) > 0.5
    df['deadzone_pass'] = df['5d_range_pct_prev'] >= 0.02
    df['price_pass'] = df['d_close_prev'] >= MIN_OPEN_PRICE
    
    # 3. Isolate the Virtual T-0 Date
    df_t0 = df[df['trading_date'] == VIRTUAL_T0].copy()
    df_candidates = df_t0[(df_t0['ratio'] >= 5.0) & df_t0['vol_cond'] & df_t0['deadzone_pass'] & df_t0['price_pass']]
    df_top_100 = df_candidates.sort_values('ratio', ascending=False).head(100)
    
    symbols_list = tuple(df_top_100['symbol'].tolist())
    logging.info(f"Identified {len(symbols_list)} valid candidates for {VIRTUAL_T0}.")
    
    # 4. Fetch 1-Minute Data strictly for T-0 Morning
    logging.info("Fetching 1-minute morning bars for candidates...")
    query_1min = f"""
    SELECT symbol, 
           CAST("timestamp" AT TIME ZONE 'America/New_York' AS time) as time_et,
           low, close
    FROM public.stock_datum
    WHERE trading_date = '{VIRTUAL_T0}' 
      AND symbol IN {symbols_list}
      AND CAST("timestamp" AT TIME ZONE 'America/New_York' AS time) BETWEEN '09:30:00' AND '10:15:00'
    ORDER BY symbol, time_et
    """
    df_1m = pd.read_sql(query_1min, engine)
    
    # 5. Calculate strict unpadded LODs and Entries
    results = []
    
    for sym in symbols_list:
        bars = df_1m[df_1m['symbol'] == sym]
        if bars.empty: continue
        
        ratio = df_top_100[df_top_100['symbol'] == sym]['ratio'].values[0]
        row_data = {'Symbol': sym, 'T-1_Ratio': round(ratio, 2)}
        
        # Test all 3 time slots
        for target_time in ['09:45:00', '10:00:00', '10:15:00']:
            # Filter bars up to the target time
            slice_bars = bars[bars['time_et'] <= pd.to_datetime(target_time).time()]
            
            if slice_bars.empty:
                row_data[f'Entry_{target_time[:5]}'] = "No Data"
                row_data[f'LOD_{target_time[:5]}'] = "No Data"
                row_data[f'Risk_Dist_{target_time[:5]}'] = "No Data"
                continue
            
            # Entry Price is the close of the exact target minute (or the closest prior minute if halted/low vol)
            entry_price = slice_bars.iloc[-1]['close']
            # LOD is the absolute minimum low from 09:30 up to the target minute
            lod = slice_bars['low'].min()
            
            row_data[f'Entry_{target_time[:5]}'] = entry_price
            row_data[f'LOD_{target_time[:5]}'] = lod
            row_data[f'Risk_Dist_{target_time[:5]}'] = round(entry_price - lod, 4)
            
        results.append(row_data)
        
    # 6. Output to CSV
    df_results = pd.DataFrame(results)
    out_file = os.path.join(PROJECT_DIR, f"virtual_t0_diagnostics_{VIRTUAL_T0}.csv")
    df_results.to_csv(out_file, index=False)
    
    logging.info(f"Done! Diagnostic CSV saved to: {out_file}")

if __name__ == "__main__":
    run_diagnostics()