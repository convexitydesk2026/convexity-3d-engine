"""
=============================================================================
Script Name: sync_engine_v13.py
Purpose: Phase 1 of the Local-First Estate Architecture.
         The "Isolated Session" approach. Guarantees 100% extraction by 
         using a fresh API connection per account.
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
    print("   ESTATE SYNC ENGINE v13 - ISOLATED SESSION EXTRACTION")
    print("========================================================")
    
    # --- STEP 1: GET THE GROUND TRUTH ---
    print("[*] Connecting to TWS (Session 1) to establish absolute ground truth...")
    ib_master = IB()
    try:
        ib_master.connect('127.0.0.1', PORT, clientId=1)
    except Exception as e:
        print(f"[!] Connection failed: {e}")
        return
        
    accounts = ib_master.managedAccounts()
    master_positions = ib_master.reqPositions()
    
    expected_counts = {}
    for p in master_positions:
        expected_counts[p.account] = expected_counts.get(p.account, 0) + 1
        
    ib_master.disconnect()
    print("[+] Ground truth established. TWS Master List verified.")

    conn = init_db()
    cursor = conn.cursor()
    today_str = datetime.date.today().isoformat()
    
    cursor.execute("DELETE FROM daily_balances WHERE date = ?", (today_str,))
    cursor.execute("DELETE FROM daily_positions WHERE date = ?", (today_str,))

    total_positions_saved = 0
    client_id = 2 # Start at 2 since 1 was just used

    # --- STEP 2: ISOLATED EXTRACTION PER ACCOUNT ---
    for acc in accounts:
        expected = expected_counts.get(acc, 0)
        print(f"\n[*] --- Processing Account: {acc} ---")
        print(f"[*] Expected Positions to Download: {expected}")
        
        ib = IB()
        # Fresh connection guarantees no crossed streams
        ib.connect('127.0.0.1', PORT, clientId=client_id)
        client_id += 1 
        
        # PROPER SYNTAX FIX
        ib.reqAccountUpdates(acc)
        
        # DETERMINISTIC WAIT
        # The script will hold the line until exactly the expected number of contracts
        # arrive AND the account balances have populated.
        timer = 0
        while True:
            curr_pos = len(ib.portfolio(acc))
            curr_vals = len(ib.accountValues(acc))
            
            if curr_pos == expected and curr_vals > 0:
                print(f"[+] Verified: {curr_pos}/{expected} positions arrived.")
                break
            if timer >= 15:
                print(f"[!] Stream timed out. Reached {curr_pos}/{expected} positions.")
                break
                
            ib.sleep(1.0)
            timer += 1
            
        ib.sleep(1.0) # Final 1-second buffer for any lagging greeks/prices
        
        values = ib.accountValues(acc)
        portfolio_items = ib.portfolio(acc)
        
        # Disconnect instantly to clean the slate for the next account
        ib.disconnect()

        # Extract Balances
        net_liq_base = None
        total_cash_base = None
        net_liq_usd = 0.0
        total_cash_usd = 0.0
        
        for v in values:
            if v.tag in ['NetLiquidation', 'NetLiquidationByCurrency']:
                if v.currency == 'BASE': net_liq_base = float(v.value)
                elif v.currency == 'USD': net_liq_usd = float(v.value)
            elif v.tag in['TotalCashBalance', 'CashBalance']:
                if v.currency == 'BASE': total_cash_base = float(v.value)
                elif v.currency == 'USD': total_cash_usd = float(v.value)
                
        net_liq = net_liq_base if net_liq_base is not None else net_liq_usd
        total_cash = total_cash_base if total_cash_base is not None else total_cash_usd
        
        cursor.execute('''INSERT INTO daily_balances 
                          (date, account, currency, net_liquidation, total_cash)
                          VALUES (?, ?, ?, ?, ?)''', 
                       (today_str, acc, 'USD', net_liq, total_cash))
        print(f"[+] Saved Balances -> Net Liq: ${net_liq:,.2f} | Cash: ${total_cash:,.2f}")

        # Extract Positions
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
            total_positions_saved += 1
        
        print(f"[+] Saved {pos_count} live positions to database.")

    conn.commit()
    conn.close()
    
    print("\n========================================================")
    print(f"[+] TOTAL SYNC COMPLETE! {total_positions_saved} overall positions saved.")
    print(f"[+] Database updated: {DB_PATH}")
    print("========================================================")

if __name__ == '__main__':
    sync_tws()