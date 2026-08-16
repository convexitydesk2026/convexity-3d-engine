"""
=============================================================================
Script Name: history_migrator_v1.py
Purpose: Phase 1.5 - One-Time Historical Migration.
         Reads your old IBKR_Daily_Data.csv and securely injects the 
         historical Net Liquidation and Cash Flows into the new SQLite DB.
=============================================================================
"""

import pandas as pd
import sqlite3
import os

DB_NAME = "estate_data.db"
TARGET_DIR = r"C:\Users\donca\Desktop\Desktop HP Envy x360 al 22Abr24\Docs Manuel\IBKR_Options"
DB_PATH = os.path.join(TARGET_DIR, DB_NAME)
CSV_PATH = os.path.join(TARGET_DIR, "IBKR_Daily_Data.csv")

def migrate_history():
    print("========================================================")
    print("   ESTATE MIGRATOR v1 - HISTORICAL DATA RESCUE")
    print("========================================================")
    
    if not os.path.exists(CSV_PATH):
        print(f"[!] ERROR: Cannot find {CSV_PATH}")
        return
        
    print(f"[*] Reading historical data from: {CSV_PATH}")
    df = pd.read_csv(CSV_PATH)
    
    # Ensure date is formatted as YYYY-MM-DD
    df['Date'] = pd.to_datetime(df['Date'].astype(str)).dt.strftime('%Y-%m-%d')
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    records_inserted = 0
    records_skipped = 0
    
    print("[*] Injecting history into SQLite database...")
    for index, row in df.iterrows():
        acc = str(row['AccountID']).strip()
        date_str = row['Date']
        nav = float(row['NAV']) if pd.notna(row['NAV']) else 0.0
        
        # We check if a record already exists for this date/account
        cursor.execute("SELECT 1 FROM daily_balances WHERE date = ? AND account = ?", (date_str, acc))
        exists = cursor.fetchone()
        
        if not exists:
            # We insert historical NAVs. We use 'total_cash' to temporarily store 'CashFlow' 
            # for historical PnL calculations later.
            cursor.execute('''INSERT INTO daily_balances 
                              (date, account, currency, net_liquidation, total_cash)
                              VALUES (?, ?, ?, ?, ?)''', 
                           (date_str, acc, 'USD', nav, float(row['CashFlow'])))
            records_inserted += 1
        else:
            records_skipped += 1
            
    conn.commit()
    conn.close()
    
    print(f"[+] Migration Complete!")
    print(f"[+] Successfully rescued {records_inserted} historical daily snapshots.")
    print(f"[-] Skipped {records_skipped} records (already existed).")
    print("========================================================")

if __name__ == '__main__':
    migrate_history()