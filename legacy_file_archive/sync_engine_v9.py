"""
=============================================================================
Script Name: sync_engine_v9.py
Purpose: Phase 1 of the Local-First Estate Architecture.
         Bypasses TWS Anti-Spam filters with Smart Verification & Retries.
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
    print("     ESTATE SYNC ENGINE v9 - ANTI-SPAM & RETRY LOGIC")
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
        
        success = False
        attempts = 0
        
        while not success and attempts < 3:
            attempts += 1
            if attempts > 1:
                print(f"[*] [Retry {attempts}/3] TWS throttled the request. Waiting 3s to bypass spam filter...")
                ib.sleep(3.0)

            print("[*] Opening data stream...")
            ib.client.reqAccountUpdates(True, acc)
            
            # Wait up to 10 seconds for the first position to appear
            for _ in range(10):
                ib.sleep(1.0)
                if len(ib.portfolio(acc)) > 0:
                    break
            
            # Wait 2 extra seconds for any straggling data packets
            ib.sleep(2.0)
            
            # Read the cache
            values = ib.accountValues(acc)
            portfolio_items = ib.portfolio(acc)
            
            # Close the stream immediately to free up the pipeline
            ib.client.reqAccountUpdates(False, acc)
            
            # Extract Balances
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
            
            pos_count = len(portfolio_items)
            
            # VERIFICATION LOGIC: If TWS returns 0 positions but Net Liq > 10,000, it's a blocked request.
            if pos_count == 0 and net_liq > 10000:
                print(f"[!] Verification Failed: Account has ${net_liq:,.0f} but returned 0 positions.")
                ib.client.reqAccountUpdates(False, acc)
                continue # Loop restarts
            else:
                success = True # Data is valid, break the loop
                
        # --- SAVE VERIFIED DATA TO SQLITE ---
        cursor.execute('''INSERT INTO daily_balances 
                          (date, account, currency, net_liquidation, total_cash)
                          VALUES (?, ?, ?, ?, ?)''', 
                       (today_str, acc, 'USD', net_liq, total_cash))
        print(f"[+] Saved Balances -> Net Liq: ${net_liq:,.2f} | Cash: ${total_cash:,.2f}")

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
            total_positions += pos_count
        
        print(f"[+] Saved {pos_count} live positions for {acc}.")
        
        # Mandatory cool-down before the next account
        ib.sleep(2.0)

    conn.commit()
    conn.close()
    ib.disconnect()
    
    print("\n========================================================")
    print(f"[+] TOTAL SYNC COMPLETE! {total_positions} overall positions saved.")
    print(f"[+] Database updated: {DB_PATH}")
    print("========================================================")

if __name__ == '__main__':
    sync_tws()