"""
=============================================================================
Script Name: db_surgeon.py
Purpose: Surgically removes corrupted data from specific dates to heal 
         the dashboard's historical charting and Monte Carlo simulator.
=============================================================================
"""

import sqlite3
import os

TARGET_DIR = r"C:\Users\donca\Desktop\Desktop HP Envy x360 al 22Abr24\Docs Manuel\IBKR_Options"
DB_PATH = os.path.join(TARGET_DIR, "estate_data.db")

def perform_surgery():
    print("========================================================")
    print("   ESTATE DATABASE SURGEON")
    print("========================================================")
    
    if not os.path.exists(DB_PATH):
        print(f"[!] Error: Database not found at {DB_PATH}")
        return

    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    
    # The specific dates containing the corrupted USD-only and zero-balance data
    bad_dates = ['2026-06-23', '2026-06-24']
    
    tables_to_clean = [
        'daily_balances', 
        'daily_positions', 
        'open_orders', 
        'daily_attribution', 
        'cash_transfers'
    ]
    
    for date in bad_dates:
        print(f"\n[*] Purging corrupted data for: {date}")
        for table in tables_to_clean:
            try:
                # Target and delete records matching the exact bad dates
                c.execute(f"DELETE FROM {table} WHERE date = ?", (date,))
                deleted_rows = c.rowcount
                print(f"    - Removed {deleted_rows} rows from {table}")
            except sqlite3.OperationalError as e:
                # Failsafe just in case a table doesn't exist yet
                print(f"    - Skipped {table} (Not found or error: {e})")
                
    conn.commit()
    conn.close()
    
    print("\n[+] Surgery Complete. The poisoned data has been successfully amputated.")

if __name__ == "__main__":
    perform_surgery()