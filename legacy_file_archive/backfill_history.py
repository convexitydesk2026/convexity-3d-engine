"""
=============================================================================
Script Name: backfill_history.py
Purpose: Parses the interleaved IBKR Flex Query CSV and surgically injects 
         the missing historical NAV, Cash Flows, and MTM PnL directly 
         into the local SQLite database.
=============================================================================
"""
import os
import csv
import sqlite3
import pandas as pd

def clean_date(d_str):
    d_str = d_str.strip().replace('-', '')
    if len(d_str) == 8:
        return f"{d_str[:4]}-{d_str[4:6]}-{d_str[6:]}"
    return d_str

def run_backfill():
    print("========================================================")
    print("   ESTATE MASTER: HISTORICAL DATA INJECTION TOOL")
    print("========================================================")

    csv_path = "ibkr_flex_history.csv"
    db_path = "estate_data.db"

    if not os.path.exists(csv_path):
        print(f"[!] Error: '{csv_path}' not found in the current directory.")
        return

    mtm_data = []
    nav_data = []
    current_section = None
    mtm_headers = []
    nav_headers = []

    print("[*] Parsing interleaved IBKR Flex Query CSV...")
    with open(csv_path, 'r', encoding='utf-8-sig') as f:
        reader = csv.reader(f)
        for row in reader:
            if not row: continue
            
            if row[0] == 'ClientAccountID':
                if len(row) > 3 and row[3] == 'CurrencyPrimary':
                    current_section = 'NAV'
                    nav_headers = [c.strip() for c in row]
                elif len(row) > 3 and row[3] == 'AssetClass':
                    current_section = 'MTM'
                    mtm_headers = [c.strip() for c in row]
                continue

            if current_section == 'NAV':
                row_dict = dict(zip(nav_headers, row))
                if row_dict.get('ClientAccountID', '').startswith('U') and row_dict.get('CurrencyPrimary') == 'USD':
                    nav_data.append(row_dict)
                    
            elif current_section == 'MTM':
                row_dict = dict(zip(mtm_headers, row))
                if row_dict.get('ClientAccountID', '').startswith('U') and row_dict.get('AssetClass') != '':
                    mtm_data.append(row_dict)

    print(f"[*] Extracted {len(nav_data)} NAV records and {len(mtm_data)} MTM records.")

    if len(nav_data) == 0 or len(mtm_data) == 0:
        print("[!] Critical: Missing MTM or NAV data. Could not parse format.")
        return

    # --- 1. PROCESS NAV DATA ---
    df_nav = pd.DataFrame(nav_data)
    df_nav['date'] = df_nav.apply(lambda r: clean_date(r.get('ToDate', r.get('ReportDate', ''))), axis=1)
    df_nav['account'] = df_nav['ClientAccountID'].str.rstrip('F').str.rstrip('S')
    
    df_nav['EndingValue'] = pd.to_numeric(df_nav['EndingValue'], errors='coerce').fillna(0)
    df_nav['Flows'] = pd.to_numeric(df_nav['DepositsWithdrawals'], errors='coerce').fillna(0) + \
                      pd.to_numeric(df_nav.get('InternalCashTransfers', 0), errors='coerce').fillna(0)

    df_nav_grouped = df_nav.groupby(['date', 'account']).agg({'EndingValue': 'sum', 'Flows': 'sum'}).reset_index()

    balances_to_insert = []
    transfers_to_insert = []
    for _, r in df_nav_grouped.iterrows():
        balances_to_insert.append((r['date'], r['account'], 'USD', r['EndingValue'], 0.0, r['EndingValue']))
        if r['Flows'] != 0:
            transfers_to_insert.append((r['date'], r['account'], r['Flows'], 'Flex Backfill', 'IBKR Flex Query'))

    # --- 2. PROCESS MTM DATA ---
    df_mtm = pd.DataFrame(mtm_data)
    df_mtm['date'] = df_mtm['ReportDate'].apply(clean_date)
    df_mtm['account'] = df_mtm['ClientAccountID'].str.rstrip('F').str.rstrip('S')
    df_mtm['daily_pnl'] = pd.to_numeric(df_mtm['Total'], errors='coerce').fillna(0)

    def map_symbol(row):
        ac = row.get('AssetClass', '')
        if ac == 'OPT':
            strike = float(row.get('Strike', 0) or 0)
            return f"{row.get('UnderlyingSymbol')}_{row.get('Expiry')}_{strike}_{row.get('Put/Call')}"
        elif ac == 'CASH':
            return f"{row.get('Symbol')} CASH"
        else:
            return row.get('Symbol', 'UNKNOWN')

    df_mtm['symbol'] = df_mtm.apply(map_symbol, axis=1)
    df_mtm['sec_type'] = df_mtm['AssetClass']

    df_mtm_grouped = df_mtm.groupby(['date', 'account', 'symbol', 'sec_type'])['daily_pnl'].sum().reset_index()

    df_mtm_grouped = df_mtm_grouped.sort_values(['account', 'symbol', 'date'])
    df_mtm_grouped['cum_pnl'] = df_mtm_grouped.groupby(['account', 'symbol'])['daily_pnl'].cumsum()

    positions_to_insert = []
    for _, r in df_mtm_grouped.iterrows():
        positions_to_insert.append((
            r['date'], r['account'], r['symbol'], r['sec_type'],
            1.0, 0.0, 0.0, 0.0, r['cum_pnl'], 0.0
        ))

    min_date = df_mtm_grouped['date'].min()
    max_date = df_mtm_grouped['date'].max()

    print(f"[*] Injecting seamless history into SQLite (Period: {min_date} to {max_date})...")

    conn = sqlite3.connect(db_path)
    c = conn.cursor()

    # Clear window
    c.execute("DELETE FROM daily_balances WHERE date BETWEEN ? AND ?", (min_date, max_date))
    c.execute("DELETE FROM daily_positions WHERE date BETWEEN ? AND ?", (min_date, max_date))
    c.execute("CREATE TABLE IF NOT EXISTS cash_transfers (date TEXT, account TEXT, amount REAL, type TEXT, notes TEXT)")
    c.execute("DELETE FROM cash_transfers WHERE date BETWEEN ? AND ? AND type = 'Flex Backfill'", (min_date, max_date))

    # --- THE FIX: INSERT OR REPLACE ---
    c.executemany('''INSERT OR REPLACE INTO daily_balances 
                     (date, account, currency, net_liquidation, total_cash, available_funds) 
                     VALUES (?, ?, ?, ?, ?, ?)''', balances_to_insert)

    c.executemany('''INSERT OR REPLACE INTO cash_transfers 
                     (date, account, amount, type, notes) 
                     VALUES (?, ?, ?, ?, ?)''', transfers_to_insert)

    c.executemany('''INSERT OR REPLACE INTO daily_positions 
                     (date, account, symbol, sec_type, position, market_price, market_value, avg_cost, unrealized_pnl, realized_pnl) 
                     VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''', positions_to_insert)

    conn.commit()
    conn.close()

    print("[+] Historical Data Injection Complete!")
    print("[+] ACTION REQUIRED: You must now re-run 'Run_Estate_Sync.bat' one final time.")
    print("========================================================")

if __name__ == '__main__':
    run_backfill()