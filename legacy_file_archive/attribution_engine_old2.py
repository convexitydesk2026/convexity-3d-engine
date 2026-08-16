"""
=============================================================================
Script Name: attribution_engine.py
Purpose: Calculates daily PnL split across 5 strategic buckets and appends
         it to the daily_attribution table. 
         (Phase 5 Rewrite: True NAV Reconciliation to prevent PnL Amnesia)
=============================================================================
"""
import sqlite3
import pandas as pd
import numpy as np

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
    print("   ESTATE P&L ATTRIBUTION ENGINE (PHASE 5 REWRITE)")
    print("========================================================")
    
    conn = sqlite3.connect(DB_PATH)
    
    # 1. Fetch Balances & Calculate True Daily PnL
    try:
        balances = pd.read_sql_query("SELECT * FROM daily_balances", conn)
        if balances.empty:
            print("No balances found. Exiting.")
            return
        balances.rename(columns={'net_liquidation': 'nav', 'total_cash': 'legacy_flow'}, inplace=True)
        balances['date'] = pd.to_datetime(balances['date']).dt.normalize()
    except Exception as e:
        print("[!] Database error reading daily_balances:", e)
        return

    try:
        transfers_df = pd.read_sql_query("SELECT * FROM cash_transfers", conn)
        transfers_df['date'] = pd.to_datetime(transfers_df['date']).dt.normalize()
        daily_transfers = transfers_df.groupby(['date', 'account'])['amount'].sum().reset_index()
        daily_transfers.rename(columns={'amount': 'new_flow'}, inplace=True)
        balances = pd.merge(balances, daily_transfers, on=['date', 'account'], how='left')
        balances['new_flow'] = balances['new_flow'].fillna(0.0)
    except Exception:
        balances['new_flow'] = 0.0

    balances['legacy_flow'] = balances['legacy_flow'].fillna(0.0)
    balances['net_flow'] = balances['legacy_flow'] + balances['new_flow']

    balances = balances.sort_values(['account', 'date'])
    balances['prev_nav'] = balances.groupby('account')['nav'].shift(1)
    # Reconcile true PnL matching the exact formula in dashboard_v38.py
    balances['true_daily_pnl'] = balances['nav'] - balances['net_flow'] - balances['prev_nav'].fillna(balances['nav'] - balances['net_flow'])

    # 2. Fetch Positions & Calculate Active Daily PnL
    try:
        positions = pd.read_sql_query("SELECT * FROM daily_positions", conn)
        positions['date'] = pd.to_datetime(positions['date']).dt.normalize()
        positions['bucket'] = positions.apply(lambda r: get_bucket(r['symbol'], r['sec_type']), axis=1)
    except Exception as e:
        print("[!] Database error reading daily_positions:", e)
        return

    positions = positions.sort_values(['account', 'symbol', 'date'])
    positions['prev_unrealized'] = positions.groupby(['account', 'symbol'])['unrealized_pnl'].shift(1).fillna(0.0)
    positions['active_daily_pnl'] = positions['unrealized_pnl'] - positions['prev_unrealized'] + positions['realized_pnl'].fillna(0.0)

    # Prevent inception capitalization spikes (Syncs with Dashboard's Day 0 logic)
    balances_subset = balances[['date', 'account', 'prev_nav']]
    positions = pd.merge(positions, balances_subset, on=['date', 'account'], how='left')
    positions.loc[positions['prev_nav'].isna(), 'active_daily_pnl'] = 0.0

    # 3. Process Day-by-Day Global Attribution
    dates = sorted(balances['date'].unique())
    attribution_records = []
    
    for i in range(len(dates)):
        curr_date = dates[i]
        
        if i == 0:
            # Force Day 0 to empty diff matrix to mirror cumsum origin
            alloc_dict = {b: 0.0 for b in ['a1_yield', 'a2_beta', 'a3_vrp', 'a4_alpha', 'a5_fees']}
            alloc_dict['date'] = curr_date.strftime('%Y-%m-%d')
            attribution_records.append(alloc_dict)
            continue
            
        day_balances = balances[balances['date'] == curr_date]
        true_global_pnl = day_balances['true_daily_pnl'].sum()
        
        day_positions = positions[positions['date'] == curr_date]
        day_bucket_pnl = day_positions.groupby('bucket')['active_daily_pnl'].sum().to_dict()
        
        sum_active_pnl = sum(day_bucket_pnl.values())
        diff_pnl = true_global_pnl - sum_active_pnl
        
        # Identity closed/vanished trades since yesterday
        dropped_buckets = set()
        prev_date = dates[i-1]
        prev_pos = positions[positions['date'] == prev_date]
        
        prev_pairs = set(zip(prev_pos['account'], prev_pos['symbol']))
        curr_pairs = set(zip(day_positions['account'], day_positions['symbol']))
        
        dropped_pairs = prev_pairs - curr_pairs
        
        for acc, sym in dropped_pairs:
            b_row = prev_pos[(prev_pos['account'] == acc) & (prev_pos['symbol'] == sym)]
            if not b_row.empty:
                dropped_buckets.add(b_row.iloc[0]['bucket'])
        
        alloc_dict = {b: day_bucket_pnl.get(b, 0.0) for b in ['a1_yield', 'a2_beta', 'a3_vrp', 'a4_alpha', 'a5_fees']}
        
        if abs(diff_pnl) > 0.01:
            if len(dropped_buckets) > 0:
                # Assign the missing closing PnL to the buckets of the closed trades
                share = diff_pnl / len(dropped_buckets)
                for b in dropped_buckets:
                    alloc_dict[b] = alloc_dict.get(b, 0.0) + share
            else:
                # If no trades closed, the drift is FX/Fees/Interest
                alloc_dict['a5_fees'] = alloc_dict.get('a5_fees', 0.0) + diff_pnl
                
        alloc_dict['date'] = curr_date.strftime('%Y-%m-%d')
        attribution_records.append(alloc_dict)

    # 4. Save to Database
    attr_df = pd.DataFrame(attribution_records)
    
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS daily_attribution (
                    date TEXT PRIMARY KEY, a1_yield REAL, a2_beta REAL, 
                    a3_vrp REAL, a4_alpha REAL, a5_fees REAL)''')
    
    count = 0
    for _, row in attr_df.iterrows():
        c.execute('''INSERT OR REPLACE INTO daily_attribution 
                     (date, a1_yield, a2_beta, a3_vrp, a4_alpha, a5_fees) 
                     VALUES (?, ?, ?, ?, ?, ?)''',
                  (row['date'], row['a1_yield'], row['a2_beta'], row['a3_vrp'], row['a4_alpha'], row['a5_fees']))
        count += 1
        
    conn.commit()
    conn.close()
    print(f"[*] Successfully processed and synced attribution for {count} days.")
    print("[+] Engine Rewrite Complete. PnL Amnesia Resolved.")

if __name__ == '__main__':
    run_attribution()