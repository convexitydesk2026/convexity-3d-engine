"""
=============================================================================
Script Name: sync_engine_v11.py
Purpose: Phase 1 of the Local-First Estate Architecture.
         The "Human Simulation" approach. Bypasses all IBKR bot-throttling 
         by letting TWS naturally switch accounts with generous caching delays.
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
    print("   ESTATE SYNC ENGINE v11 - THE STABLE EXTRACTION")
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
    
    # Clean slate for today
    cursor.execute("DELETE FROM daily_balances WHERE date = ?", (today_str,))
    cursor.execute("DELETE FROM daily_positions WHERE date = ?", (today_str,))

    accounts = ib.managedAccounts()
    print(f"[*] Found {len(accounts)} managed accounts: {', '.join(accounts)}")
    
    total_positions_saved = 0

    for acc in accounts:
        print(f"\n[*] --- Processing Account: {acc} ---")
        
        # 1. Switch TWS to this account
        print("[*] Switching TWS stream. Allowing 6 seconds for Options & FX models to calculate...")
        ib.client.reqAccountUpdates(True, acc)
        
        # 2. Let the data flow naturally. No spamming, no timeouts.
        ib.sleep(6.0) 
            
        # 3. Snap the data
        values = ib.accountValues(acc)
        portfolio_items = ib.portfolio(acc)
        
        # WE DO NOT SEND A CLOSE COMMAND. 
        # When we loop to the next account, TWS safely auto-closes this one on its own.

        # 4. Extract Balances
        net_liq_base = None
        total_cash_base = None
        net_liq_usd = 0.0
        total_cash_usd = 0.0
        
        for v in values:
            if v.tag in['NetLiquidation', 'NetLiquidationByCurrency']:
                if v.currency == 'BASE': net_liq_base = float(v.value)
                elif v.currency == 'USD': net_liq_usd = float(v.value)
            elif v.tag in ['TotalCashBalance', 'CashBalance']:
                if v.currency == 'BASE': total_cash_base = float(v.value)
                elif v.currency == 'USD': total_cash_usd = float(v.value)
                
        net_liq = net_liq_base if net_liq_base is not None else net_liq_usd
        total_cash = total_cash_base if total_cash_base is not None else total_cash_usd
        
        cursor.execute('''INSERT INTO daily_balances 
                          (date, account, currency, net_liquidation, total_cash)
                          VALUES (?, ?, ?, ?, ?)''', 
                       (today_str, acc, 'USD', net_liq, total_cash))
        print(f"[+] Saved Balances -> Net Liq: ${net_liq:,.2f} | Cash: ${total_cash:,.2f}")

        # 5. Extract Positions
        pos_count = 0
        for item in portfolio_items:
            contract = item.contract
            
            # Format Options (e.g., XSP_20260618_655_P)
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
            total_positions_saved += 1
        
        print(f"[+] Saved {pos_count} live positions for {acc}.")

    conn.commit()
    conn.close()
    ib.disconnect()
    
    print("\n========================================================")
    print(f"[+] TOTAL SYNC COMPLETE! {total_positions_saved} overall positions saved.")
    print(f"[+] Database updated: {DB_PATH}")
    print("========================================================")

if __name__ == '__main__':
    sync_tws()