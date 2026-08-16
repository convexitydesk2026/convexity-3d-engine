"""
=============================================================================
Script Name: attribution_engine.py
Purpose: Calculates daily PnL split across 5 strategic buckets and appends
         it to the daily_attribution table. 
         (Phase 8: Strict Daily Delta Ledger)
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
    print("   ESTATE P&L ATTRIBUTION ENGINE (PHASE 8)")
    print("   Strict Daily Delta Ledger")
    print("========================================================")
    
    conn = sqlite3.connect(DB_PATH)
    
    # 1. Fetch Balances & Calculate True Daily PnL
    try:
        balances = pd.read_sql_query("SELECT * FROM daily_balances", conn)
        if balances.empty: return
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
    balances['true_daily_pnl'] = balances['nav'] - balances['net_flow'] - balances['prev_nav'].fillna(balances['nav'] - balances['net_flow'])

    # Aggregate True Daily PnL globally per date
    global_true_pnl = balances.groupby('date')['true_daily_pnl'].sum().to_dict()

    # 2. Fetch Positions
    try:
        positions = pd.read_sql_query("SELECT * FROM daily_positions", conn)
        positions['date'] = pd.to_datetime(positions['date']).dt.normalize()
        positions['bucket'] = positions.apply(lambda r: get_bucket(r['symbol'], r['sec_type']), axis=1)
        positions['unrealized_pnl'] = positions['unrealized_pnl'].fillna(0.0)
        positions['realized_pnl'] = positions['realized_pnl'].fillna(0.0)
    except Exception as e:
        print("[!] Database error reading daily_positions:", e)
        return

    dates = sorted(balances['date'].unique())
    attribution_records = []

    # 3. Process Strict Daily Delta
    for i in range(len(dates)):
        curr_date = dates[i]
        
        # Day 0 baseline
        if i == 0:
            alloc_dict = {b: 0.0 for b in ['a1_yield', 'a2_beta', 'a3_vrp', 'a4_alpha', 'a5_fees']}
            alloc_dict['date'] = curr_date.strftime('%Y-%m-%d')
            attribution_records.append(alloc_dict)
            continue

        prev_date = dates[i-1]
        pos_T = positions[positions['date'] == curr_date]
        pos_T_minus_1 = positions[positions['date'] == prev_date]

        # Build precise lookup for T-1: (account, symbol) -> (unrealized, realized)
        prev_lookup = {}
        for _, r in pos_T_minus_1.iterrows():
            key = (r['account'], r['symbol'])
            prev_lookup[key] = (r['unrealized_pnl'], r['realized_pnl'])

        alloc = {b: 0.0 for b in ['a1_yield', 'a2_beta', 'a3_vrp', 'a4_alpha', 'a5_fees']}

        for _, r in pos_T.iterrows():
            key = (r['account'], r['symbol'])
            bkt = r['bucket']
            
            # If asset existed yesterday, calculate strictly differenced daily delta
            if key in prev_lookup:
                prev_U, prev_R = prev_lookup[key]
                dU = r['unrealized_pnl'] - prev_U
                dR = r['realized_pnl'] - prev_R
                delta = dU + dR
            else:
                # New asset appearance. Ignore legacy YTD Realized PnL to prevent spikes,
                # UNLESS the position is 0, indicating a 1-day trade lifecycle.
                delta = r['unrealized_pnl']
                if abs(r['position']) < 0.0001: 
                    delta += r['realized_pnl']
                    
            alloc[bkt] += delta

        # Reconcile exact tracking vs True NAV Cash changes
        true_daily = global_true_pnl.get(curr_date, 0.0)
        tracked_daily = sum(alloc.values())
        drift = true_daily - tracked_daily

        # Only true cash/margin interest noise remains. Route safely.
        if drift > 0:
            alloc['a1_yield'] += drift
        elif drift < 0:
            alloc['a5_fees'] += drift

        alloc['date'] = curr_date.strftime('%Y-%m-%d')
        attribution_records.append(alloc)

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
    print("[+] Phase 8: Strict Daily Delta Ledger applied. Compounding eliminated.")

if __name__ == '__main__':
    run_attribution()