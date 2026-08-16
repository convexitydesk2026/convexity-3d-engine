import pandas as pd
import sqlite3
import os

DB_PATH = "estate_data.db"
CSV_PATH = "Estate_Cash_Flows_20260616.csv"

def inject_historical_cash():
    print("========================================================")
    print("   HISTORICAL CASH FLOW INJECTOR")
    print("========================================================")
    
    if not os.path.exists(CSV_PATH):
        print(f"[!] Error: Could not find {CSV_PATH} in the directory.")
        return

    # 1. Load the CSV
    df = pd.read_csv(CSV_PATH, dtype=str)
    
    # 2. Filter strictly for Bank Deposits and Withdrawals
    deposits_df = df[df['Type'] == 'Deposits/Withdrawals'].copy()
    
    if deposits_df.empty:
        print("[!] No 'Deposits/Withdrawals' found in the CSV.")
        return
        
    # 3. Format the data to match the UI's cash_transfers table schema
    # SettleDate format in CSV is 'YYYYMMDD'. Convert to 'YYYY-MM-DD'
    deposits_df['formatted_date'] = pd.to_datetime(deposits_df['SettleDate'], format='%Y%m%d').dt.strftime('%Y-%m-%d')
    deposits_df['amount'] = pd.to_numeric(deposits_df['Amount'], errors='coerce')
    
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    
    # Ensure the table exists (just in case)
    c.execute("CREATE TABLE IF NOT EXISTS cash_transfers (date TEXT, account TEXT, amount REAL, type TEXT, notes TEXT)")
    
    inserts = 0
    skips = 0
    
    # 4. Inject into the Database safely
    for _, row in deposits_df.iterrows():
        acct = str(row['ClientAccountID'])
        amt = float(row['amount'])
        date_str = str(row['formatted_date'])
        flow_type = "External Deposit" if amt > 0 else "External Withdrawal"
        notes = "Historical IBKR Flex Query"
        
        # Check for duplicates to prevent double-counting if script is run twice
        c.execute("SELECT * FROM cash_transfers WHERE date=? AND account=? AND amount=? AND type=?", 
                  (date_str, acct, amt, flow_type))
        if not c.fetchone():
            c.execute("INSERT INTO cash_transfers VALUES (?, ?, ?, ?, ?)", 
                      (date_str, acct, amt, flow_type, notes))
            inserts += 1
            print(f"[+] Injected: {date_str} | {acct} | ${amt:,.2f}")
        else:
            skips += 1
            
    conn.commit()
    conn.close()
    
    print(f"\n[OK] Injection Complete! Added {inserts} new transfers. Skipped {skips} existing.")
    print("[*] Next Step: Run 'Run_Estate_Sync.bat' to recalculate the PnL history.")

if __name__ == '__main__':
    inject_historical_cash()