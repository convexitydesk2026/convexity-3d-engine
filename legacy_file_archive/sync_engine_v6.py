"""
=============================================================================
Script Name: sync_engine_v6.py
Purpose: Phase 1 of the Local-First Estate Architecture.
         Uses RAW SOCKET commands to prevent API hangs.
=============================================================================
"""

from ib_insync import *
import sqlite3
import datetime
import os

PORT = 7496
DB_NAME = "estate_data.db"
TARGET_DIR = r"C:\Users\donca\Desktop\Desktop HP Envy x360 al 22Abr24\Docs Manuel\IBKR_Options"
DB_PATH = os.path.join(TARGET_DIR, DB_NAME)

def init_db():
    if not os.path.exists(TARGET_DIR):
        os.makedirs(TARGET_DIR)
        
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS daily_balances (
                    date TEXT, account TEXT, currency TEXT, 
                    net_liquidation REAL, total_cash REAL,
                    PRIMARY KEY (date, account, currency)
                 )''')
    c.execute('''CREATE TABLE IF NOT EXISTS daily_positions (
                    date TEXT, account TEXT, symbol TEXT, sec_type TEXT, 
                    position REAL, market_price REAL, market_value REAL, 
                    avg_cost REAL, unrealized_pnl REAL, realized_pnl REAL,
                    PRIMARY KEY (date, account, symbol, sec_type)
                 )''')
    conn.commit()
    return conn

def sync_tws():
    print("========================================================")
    print("     ESTATE SYNC ENGINE v6 - RAW SOCKET SYNC")
    print("========================================================")
    
    ib = IB()
    print(f"[*] Attempting to connect to TWS on port {PORT}...")
    try:
        ib.connect('127.0.0.1', PORT, clientId=1)
        print("[+] Successfully connected to TWS API!")
    except Exception as e:
        print(f"[!] Connection failed: {e}")
        return

    conn = init_db()
    cursor = conn.cursor()
    today_str = datetime.date.today().isoformat()
    
    cursor.execute("DELETE FROM daily_balances WHERE date = ?", (today_str,))
    cursor.execute("DELETE FROM daily_positions WHERE date = ?", (today_str,))

    accounts = ib.managedAccounts()
    print(f"[*] Found {len(accounts)} managed accounts: {', '.join(accounts)}")
    total_positions = 0

    for acc in accounts:
        print(f"\n[*] --- Processing Account: {acc} ---")
        print("[*] Opening raw socket stream (waiting 3 seconds for packets)...")
        
        # RAW API COMMAND: Open the faucet without blocking the script
        ib.client.reqAccountUpdates(True, acc)
        ib.sleep(3.0) 
        
        # Read the now-populated cache
        values = ib.accountValues(acc)
        portfolio_items = ib.portfolio(acc)
        
        # RAW API COMMAND: Close the faucet immediately to prevent choking
        ib.client.reqAccountUpdates(False, acc)
        ib.sleep(0.5)

        # 1. Extract Balances
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
        print(f"[+] Saved Balances -> Net Liq: ${net_liq:,.2f} | Cash: ${total_cash:,.2f}")

        # 2. Extract Positions
        pos_count = 0
        for item in portfolio_items:
            contract = item.contract
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
            pos_count += 1
            total_positions += 1
        
        print(f"[+] Saved {pos_count} live positions for {acc}.")

    conn.commit()
    conn.close()
    ib.disconnect()
    
    print("\n========================================================")
    print(f"[+] TOTAL SYNC COMPLETE! {total_positions} overall positions saved.")
    print(f"[+] Database updated: {DB_PATH}")
    print("========================================================")

if __name__ == '__main__':
    sync_tws()