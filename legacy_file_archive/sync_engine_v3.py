"""
=============================================================================
Script Name: sync_engine_v3.py
Purpose: Phase 1 of the Local-First Estate Architecture.
         Connects to live TWS, extracts real-time balances and positions,
         and securely stores them in a local SQLite database.
=============================================================================
"""

from ib_insync import *
import sqlite3
import datetime
import os

# --- CONFIGURATION ---
PORT = 7496
DB_NAME = "estate_data.db"

# Explicit path for team/family context
TARGET_DIR = r"C:\Users\donca\Desktop\Desktop HP Envy x360 al 22Abr24\Docs Manuel\IBKR_Options"
DB_PATH = os.path.join(TARGET_DIR, DB_NAME)

def init_db():
    """Creates the SQLite database and tables if they don't exist."""
    if not os.path.exists(TARGET_DIR):
        os.makedirs(TARGET_DIR)
        
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    
    # Table 1: Daily Account Balances
    c.execute('''CREATE TABLE IF NOT EXISTS daily_balances (
                    date TEXT, 
                    account TEXT, 
                    currency TEXT, 
                    net_liquidation REAL, 
                    total_cash REAL,
                    PRIMARY KEY (date, account, currency)
                 )''')
                 
    # Table 2: Daily Portfolio Positions
    c.execute('''CREATE TABLE IF NOT EXISTS daily_positions (
                    date TEXT, 
                    account TEXT, 
                    symbol TEXT, 
                    sec_type TEXT, 
                    position REAL, 
                    market_price REAL, 
                    market_value REAL, 
                    avg_cost REAL,
                    unrealized_pnl REAL, 
                    realized_pnl REAL,
                    PRIMARY KEY (date, account, symbol, sec_type)
                 )''')
    conn.commit()
    return conn

def sync_tws():
    print("========================================================")
    print("     ESTATE SYNC ENGINE v3 - LIVE TWS CONNECTION")
    print("========================================================")
    
    # 1. Connect to IBKR
    ib = IB()
    print(f"[*] Attempting to connect to TWS on port {PORT}...")
    try:
        ib.connect('127.0.0.1', PORT, clientId=1)
        print("[+] Successfully connected to TWS API!")
    except Exception as e:
        print(f"[!] Connection failed: {e}")
        print("[!] ACTION REQUIRED: Ensure TWS is open, logged in, and API is enabled.")
        return

    # 2. Connect to Database & Clear Today's Previous Runs
    conn = init_db()
    cursor = conn.cursor()
    today_str = datetime.date.today().isoformat()
    
    print(f"[*] Preparing database snapshot for {today_str}...")
    cursor.execute("DELETE FROM daily_balances WHERE date = ?", (today_str,))
    cursor.execute("DELETE FROM daily_positions WHERE date = ?", (today_str,))

    accounts = ib.managedAccounts()
    print(f"[*] Found {len(accounts)} managed accounts: {', '.join(accounts)}")

    # 3. WARM THE CACHE
    print("[*] Waking up TWS data streams (this takes 2 seconds)...")
    for acc in accounts:
        # Calling these triggers the background subscription automatically
        ib.accountValues(acc)
        ib.portfolio(acc)
    
    # Give TWS 2 full seconds to push the data over the local network into the wrapper
    ib.sleep(2.0)

    # 4. Fetch Balances
    print("[*] Fetching live account balances...")
    for acc in accounts:
        values = ib.accountValues(acc)
        net_liq = 0.0
        total_cash = 0.0
        
        for v in values:
            if v.tag == 'NetLiquidation' and v.currency == 'BASE':
                net_liq = float(v.value)
            elif v.tag == 'TotalCashBalance' and v.currency == 'BASE':
                total_cash = float(v.value)
        
        cursor.execute('''INSERT INTO daily_balances 
                          (date, account, currency, net_liquidation, total_cash)
                          VALUES (?, ?, ?, ?, ?)''', 
                       (today_str, acc, 'USD', net_liq, total_cash))

    # 5. Fetch Positions
    print("[*] Fetching live portfolio positions (eradicating ghost contracts)...")
    total_positions = 0
    for acc in accounts:
        portfolio_items = ib.portfolio(acc)
        for item in portfolio_items:
            contract = item.contract
            
            # Format Options nicely (e.g., SPX_20260515_5000_P)
            if contract.secType == 'OPT':
                symbol = f"{contract.symbol}_{contract.lastTradeDateOrContractMonth}_{contract.strike}_{contract.right}"
            else:
                symbol = contract.localSymbol if contract.localSymbol else contract.symbol
            
            cursor.execute('''INSERT INTO daily_positions
                              (date, account, symbol, sec_type, position, market_price, market_value, avg_cost, unrealized_pnl, realized_pnl)
                              VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
                           (today_str, acc, symbol, contract.secType, 
                            item.position, item.marketPrice, item.marketValue, item.averageCost,
                            item.unrealizedPNL, item.realizedPNL))
            total_positions += 1

    # 6. Commit and Clean Up
    conn.commit()
    conn.close()
    ib.disconnect()
    
    print(f"[+] Sync complete! {total_positions} live positions saved safely.")
    print(f"[+] Database updated: {DB_PATH}")
    print("========================================================")

if __name__ == '__main__':
    sync_tws()