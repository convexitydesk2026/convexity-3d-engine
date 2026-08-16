"""
=============================================================================
Script Name: audit_daily_drift.py
Purpose: Diagnostic tool to generate a chronological daily log of PnL,
         Cash Flows, and Drift to pinpoint the May 2026 anomaly.
=============================================================================
"""
import sqlite3
import pandas as pd

DB_PATH = "estate_data.db"

def run_daily_audit():
    print("========================================================")
    print("   ESTATE P&L DAILY DRIFT AUDIT")
    print("========================================================")
    
    conn = sqlite3.connect(DB_PATH)
    
    # 1. Fetch Balances
    balances = pd.read_sql_query("SELECT * FROM daily_balances", conn)
    balances.rename(columns={'net_liquidation': 'nav', 'total_cash': 'legacy_flow'}, inplace=True)
    balances['date'] = pd.to_datetime(balances['date']).dt.normalize()
    
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
    
    # 2. Fetch Positions
    positions = pd.read_sql_query("SELECT * FROM daily_positions", conn)
    positions['date'] = pd.to_datetime(positions['date']).dt.normalize()
    positions['unrealized_pnl'] = positions['unrealized_pnl'].fillna(0.0)
    positions['realized_pnl'] = positions['realized_pnl'].fillna(0.0)

    dates = sorted(balances['date'].unique())
    date_to_idx = {d: i for i, d in enumerate(dates)}
    positions['date_idx'] = positions['date'].map(date_to_idx)
    positions['prev_date_idx'] = positions.groupby(['account', 'symbol'])['date_idx'].shift(1)
    positions['is_continuous'] = positions['prev_date_idx'] == (positions['date_idx'] - 1)
    
    positions['cum_pnl'] = positions['unrealized_pnl'] + positions['realized_pnl']
    positions['prev_cum_pnl'] = positions.groupby(['account', 'symbol'])['cum_pnl'].shift(1)
    positions.loc[~positions['is_continuous'], 'prev_cum_pnl'] = 0.0
    positions['active_daily_pnl'] = positions['cum_pnl'] - positions['prev_cum_pnl']
    
    positions.loc[positions['date'] == dates[0], 'active_daily_pnl'] = 0.0

    # 3. Aggregate Daily Data
    audit_records = []
    
    for i in range(1, len(dates)):
        curr_date = dates[i]
        prev_date = dates[i-1]
        
        day_bals = balances[balances['date'] == curr_date]
        day_true_pnl = day_bals['true_daily_pnl'].sum()
        day_legacy_flow = day_bals['legacy_flow'].sum()
        day_new_flow = day_bals['new_flow'].sum()
        
        pos_T = positions[positions['date'] == curr_date]
        pos_T_minus_1 = positions[positions['date'] == prev_date]
        day_tracked_pnl = pos_T['active_daily_pnl'].sum()
        
        drift = day_true_pnl - day_tracked_pnl
        
        vanished = set(pos_T_minus_1['symbol']) - set(pos_T['symbol'])
        
        audit_records.append({
            'Date': curr_date.strftime('%Y-%m-%d'),
            'True_Daily_PnL': round(day_true_pnl, 2),
            'Tracked_Positions_PnL': round(day_tracked_pnl, 2),
            'Drift_Mismatch': round(drift, 2),
            'Legacy_Flow_Total_Cash': round(day_legacy_flow, 2),
            'New_Flow_UI_Ledger': round(day_new_flow, 2),
            'Vanished_Symbols': " | ".join(vanished) if vanished else "None"
        })

    audit_df = pd.DataFrame(audit_records)
    audit_df.to_csv("daily_drift_log.csv", index=False)
    
    print("[+] Audit Complete. Generated 'daily_drift_log.csv'.")
    print("[!] Please open 'daily_drift_log.csv' and look at May 2026.")
    print("[!] Find the row(s) where 'Drift_Mismatch' is a massive number (~$19,000).")
    print("[!] Paste that specific row's data here so we can see the exact cause.")
    print("========================================================")

if __name__ == '__main__':
    run_daily_audit()