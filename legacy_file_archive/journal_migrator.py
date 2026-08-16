"""
=============================================================================
Script Name: journal_migrator.py
Purpose: One-time migration script.
         Extracts the complete history from XSP_XND_Options_Journal_v5.xlsx 
         and permanently seeds it into the SQLite estate_data.db.
=============================================================================
"""

import pandas as pd
import sqlite3
import os

# Define Paths
TARGET_DIR = r"C:\Users\donca\Desktop\Desktop HP Envy x360 al 22Abr24\Docs Manuel\IBKR_Options"
DB_PATH = os.path.join(TARGET_DIR, "estate_data.db")
EXCEL_PATH = os.path.join(TARGET_DIR, "XSP_XND_Options_Journal_v5.xlsx")

def run_migration():
    print("========================================================")
    print("   ESTATE OPTIONS JOURNAL MIGRATOR")
    print("========================================================")
    
    if not os.path.exists(EXCEL_PATH):
        print(f"[-] ERROR: Cannot find the Excel file at:\n    {EXCEL_PATH}")
        return

    print("[*] Reading Excel file...")
    try:
        # Read Excel (pandas automatically reads the cached values of formulas)
        df = pd.read_excel(EXCEL_PATH, engine='openpyxl')
        
        # Drop any empty rows trailing at the bottom
        df = df.dropna(subset=['Tranche ID'])
        
        # Clean Date formatting to standard SQL YYYY-MM-DD
        if 'Open Date' in df.columns:
            df['Open Date'] = pd.to_datetime(df['Open Date']).dt.strftime('%Y-%m-%d')
        if 'Close Date' in df.columns:
            # Using errors='coerce' turns empty cells (open trades) into NaT (Not a Time), then leaves them blank
            df['Close Date'] = pd.to_datetime(df['Close Date'], errors='coerce').dt.strftime('%Y-%m-%d')

        print(f"[+] Successfully extracted {len(df)} option trades.")
        
    except Exception as e:
        print(f"[-] ERROR reading Excel file: {e}")
        return

    print("[*] Connecting to SQLite database...")
    try:
        conn = sqlite3.connect(DB_PATH)
        
        # Write the dataframe to the database
        # if_exists='replace' ensures if you run this twice, it overwrites cleanly instead of duplicating
        df.to_sql('options_journal', conn, if_exists='replace', index=False)
        
        conn.commit()
        conn.close()
        print("[+] SUCCESS! Excel data injected into 'options_journal' table.")
        print("[!] You may now safely archive or delete the .xlsx file.")
        print("========================================================")
        
    except Exception as e:
        print(f"[-] ERROR writing to database: {e}")

if __name__ == '__main__':
    run_migration()