"""
=============================================================================
Script Name: audit_pnl.py
Purpose: Diagnostic tool to export a CSV of Daily NAV PnL vs Position PnL
         to expose the exact source of the mathematical drift.
=============================================================================
"""
import sqlite3
import pandas as pd

DB_PATH = "estate_data.db"

def run_audit():
    print("========================================================")
    print("   ESTATE P&L AUDIT TOOL")
    print("========================================================")
    
    conn = sqlite3.connect(DB_PATH)
    
    # 1. Fetch Balances
    balances = pd.read_sql_query("SELECT * FROM daily_balances", conn)
    balances.rename(columns={'net_liquidation': 'nav', 'total_cash': 'legacy_flow'}, inplace=True)
    balances['date'] = pd.to_datetime(balances['date']).dt.normalize()
    
    # Safely handle cash_transfers if the table doesn't exist yet
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
    
    true_pnl_df = balances.groupby('date')['true_daily_pnl'].sum().reset_index()

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
    
    # Drop Day 0 inception spikes for active tracking
    day_0 = dates[0]
    positions.loc[positions['date'] == day_0, 'active_daily_pnl'] = 0.0
    
    tracked_pnl_df = positions.groupby('date')['active_daily_pnl'].sum().reset_index()

    # 3. Merge and Compare
    audit_df = pd.merge(true_pnl_df, tracked_pnl_df, on='date', how='left').fillna(0.0)
    audit_df.rename(columns={'active_daily_pnl': 'tracked_position_pnl'}, inplace=True)
    audit_df['drift_mismatch'] = audit_df['true_daily_pnl'] - audit_df['tracked_position_pnl']
    
    audit_df['cum_true_pnl'] = audit_df['true_daily_pnl'].cumsum()
    audit_df['cum_tracked_pnl'] = audit_df['tracked_position_pnl'].cumsum()
    audit_df['cum_drift'] = audit_df['drift_mismatch'].cumsum()

    # Format Date for CSV
    audit_df['date'] = audit_df['date'].dt.strftime('%Y-%m-%d')
    
    audit_df.to_csv("pnl_audit_report.csv", index=False)
    conn.close()
    
    print("[+] Audit Complete. Generated 'pnl_audit_report.csv'.")
    print(f"[*] Total True Estate PnL: ${audit_df['cum_true_pnl'].iloc[-1]:,.2f}")
    print(f"[*] Total Tracked Positions PnL: ${audit_df['cum_tracked_pnl'].iloc[-1]:,.2f}")
    print(f"[*] Total Cumulative Drift (Missing Closed Trades): ${audit_df['cum_drift'].iloc[-1]:,.2f}")
    print("========================================================")

if __name__ == '__main__':
    run_audit()