"""
=============================================================================
Script Name: attribution_engine.py
Purpose: Calculates daily PnL split across 5 strategic buckets and appends
         it to the daily_attribution table. Unfreezes the dashboard charts.
=============================================================================
"""
import sqlite3
import pandas as pd

DB_PATH = "estate_data.db"

def get_bucket(sym, sec_type):
    s = str(sym).upper()
    if 'IB01' in s or (sec_type == 'CASH' and 'ACCRUED' not in s and 'FEE' not in s):
        return 'a1_yield'
    if 'CSPX' in s or 'CNDX' in s or 'CSNDX' in s:
        return 'a2_beta'
    if sec_type == 'OPT':
        return 'a3_vrp'
    if 'ACCRUED' in s or 'FEE' in s:
        return 'a5_fees'
    return 'a4_alpha'

def run_attribution():
    print("========================================================")
    print("   ESTATE P&L ATTRIBUTION ENGINE (BACKFILL & SYNC)")
    print("========================================================")
    
    conn = sqlite3.connect(DB_PATH)
    
    # 1. Pull Historical Positions
    try:
        df = pd.read_sql_query("SELECT * FROM daily_positions", conn)
        df['date'] = pd.to_datetime(df['date'])
    except Exception as e:
        print("Database error:", e)
        return
    
    # 2. Assign each position to a strategic bucket
    df['bucket'] = df.apply(lambda r: get_bucket(r['symbol'], r['sec_type']), axis=1)
    
    # 3. Calculate Cumulative PnL per bucket per day
    df['total_pnl'] = df['unrealized_pnl'].fillna(0) + df['realized_pnl'].fillna(0)
    daily_cum = df.groupby(['date', 'bucket'])['total_pnl'].sum().unstack(fill_value=0).reset_index()
    
    # Ensure all columns exist
    for col in ['a1_yield', 'a2_beta', 'a3_vrp', 'a4_alpha', 'a5_fees']:
        if col not in daily_cum.columns:
            daily_cum[col] = 0.0
            
    daily_cum = daily_cum.sort_values('date')
    
    # 4. Calculate Daily Change (Today's PnL - Yesterday's PnL)
    daily_pnl = daily_cum.set_index('date').diff().fillna(0).reset_index()
    
    # 5. Create table if missing and inject data
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS daily_attribution (
                    date TEXT PRIMARY KEY, a1_yield REAL, a2_beta REAL, 
                    a3_vrp REAL, a4_alpha REAL, a5_fees REAL)''')
    
    # Find missing dates
    existing = pd.read_sql_query("SELECT date FROM daily_attribution", conn)
    missing_dates = daily_pnl[~daily_pnl['date'].dt.strftime('%Y-%m-%d').isin(existing['date'])]
    
    count = 0
    for _, row in missing_dates.iterrows():
        dt_str = row['date'].strftime('%Y-%m-%d')
        c.execute('''INSERT OR REPLACE INTO daily_attribution 
                     (date, a1_yield, a2_beta, a3_vrp, a4_alpha, a5_fees) 
                     VALUES (?, ?, ?, ?, ?, ?)''',
                  (dt_str, row['a1_yield'], row['a2_beta'], row['a3_vrp'], row['a4_alpha'], row['a5_fees']))
        count += 1
        print(f"[*] Calculated and saved attribution for: {dt_str}")
        
    conn.commit()
    conn.close()
    print(f"[+] Complete. {count} days backfilled to database.")

if __name__ == '__main__':
    run_attribution()