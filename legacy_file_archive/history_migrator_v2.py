"""
=============================================================================
Script Name: history_migrator_v2.py
Purpose: Phase 1.5 - Historical Migration (Part 2).
         Rescues the granular PnL Attribution math (Yield, Beta, VRP, Alpha, Fees)
         from the old CSV and injects it into the SQLite Database.
=============================================================================
"""

import pandas as pd
import sqlite3
import os

DB_NAME = "estate_data.db"
TARGET_DIR = r"C:\Users\donca\Desktop\Desktop HP Envy x360 al 22Abr24\Docs Manuel\IBKR_Options"
DB_PATH = os.path.join(TARGET_DIR, DB_NAME)
ATTR_CSV_PATH = os.path.join(TARGET_DIR, "Daily_PnL_Attribution.csv")

def migrate_attribution():
    print("========================================================")
    print("   ESTATE MIGRATOR v2 - PNL ATTRIBUTION RESCUE")
    print("========================================================")
    
    if not os.path.exists(ATTR_CSV_PATH):
        print(f"[!] ERROR: Cannot find {ATTR_CSV_PATH}")
        print("Please ensure Daily_PnL_Attribution.csv is in the folder.")
        return
        
    print(f"[*] Reading attribution data from: {ATTR_CSV_PATH}")
    df = pd.read_csv(ATTR_CSV_PATH)
    
    # Clean the date format
    df['Date'] = pd.to_datetime(df['Date'].astype(str)).dt.strftime('%Y-%m-%d')
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Create the Attribution table
    cursor.execute('''CREATE TABLE IF NOT EXISTS daily_attribution (
                    date TEXT PRIMARY KEY, 
                    a1_yield REAL, 
                    a2_beta REAL, 
                    a3_vrp REAL, 
                    a4_alpha REAL, 
                    a5_fees REAL
                 )''')
    
    records_inserted = 0
    records_skipped = 0
    
    print("[*] Injecting attribution history into SQLite database...")
    for index, row in df.iterrows():
        date_str = row['Date']
        
        cursor.execute("SELECT 1 FROM daily_attribution WHERE date = ?", (date_str,))
        exists = cursor.fetchone()
        
        if not exists:
            cursor.execute('''INSERT INTO daily_attribution 
                              (date, a1_yield, a2_beta, a3_vrp, a4_alpha, a5_fees)
                              VALUES (?, ?, ?, ?, ?, ?)''', 
                           (date_str, 
                            float(row.get('a1_Yield', 0)), 
                            float(row.get('a2_Beta', 0)), 
                            float(row.get('a3_VRP', 0)), 
                            float(row.get('a4_Alpha', 0)), 
                            float(row.get('a5_Fees', 0))))
            records_inserted += 1
        else:
            records_skipped += 1
            
    conn.commit()
    conn.close()
    
    print(f"[+] Migration Complete!")
    print(f"[+] Successfully rescued {records_inserted} days of PnL Attribution math.")
    print(f"[-] Skipped {records_skipped} records (already existed).")
    print("========================================================")

if __name__ == '__main__':
    migrate_attribution()