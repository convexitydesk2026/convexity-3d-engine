"""
=============================================================================
Script Name: sync_engine_v15.py
Purpose: Phase 1 of the Local-First Estate Architecture.
         Fixes the PnL Math Glitch. Separates Uninvested Cash from Daily 
         Deposits/Withdrawals to preserve perfectly accurate historical math.
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
    if not os.path.exists(TARGET_DIR): os.makedirs(TARGET_DIR)
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
    print("   ESTATE SYNC ENGINE v15 - MATH PRESERVATION FIX")
    print("========================================================")
    
    ib_master = IB()
    try: ib_master.connect('127.0.0.1', PORT, clientId=1)
    except: return
        
    accounts = ib_master.managedAccounts()
    master_positions = ib_master.reqPositions()
    expected_counts = {}
    for p in master_positions:
        if p.position != 0: expected_counts[p.account] = expected_counts.get(p.account, 0) + 1
    ib_master.disconnect()

    conn = init_db()
    cursor = conn.cursor()
    today_str = datetime.date.today().isoformat()
    
    cursor.execute("DELETE FROM daily_balances WHERE date = ?", (today_str,))
    cursor.execute("DELETE FROM daily_positions WHERE date = ?", (today_str,))

    client_id = 2
    for acc in accounts:
        expected = expected_counts.get(acc, 0)
        print(f"[*] Processing {acc}...")
        
        ib = IB()
        ib.connect('127.0.0.1', PORT, clientId=client_id)
        client_id += 1 
        ib.reqAccountUpdates(acc)
        
        timer = 0
        while True:
            curr_pos = len(ib.portfolio(acc))
            curr_vals = len(ib.accountValues(acc))
            if curr_pos == expected and curr_vals > 0: break
            if timer >= 15: break
            ib.sleep(1.0); timer += 1
            
        ib.sleep(1.0) 
        values = ib.accountValues(acc)
        portfolio_items = ib.portfolio(acc)
        ib.disconnect()

        net_liq_base, total_cash_base = None, None
        net_liq_usd, total_cash_usd = 0.0, 0.0
        
        for v in values:
            if v.tag in ['NetLiquidation', 'NetLiquidationByCurrency']:
                if v.currency == 'BASE': net_liq_base = float(v.value)
                elif v.currency == 'USD': net_liq_usd = float(v.value)
            elif v.tag in['TotalCashBalance', 'CashBalance']:
                if v.currency == 'BASE': total_cash_base = float(v.value)
                elif v.currency == 'USD': total_cash_usd = float(v.value)
                
        net_liq = net_liq_base if net_liq_base is not None else net_liq_usd
        total_cash = total_cash_base if total_cash_base is not None else total_cash_usd
        
        # FIX: We insert 0.0 for daily deposits to preserve historical math
        cursor.execute('''INSERT INTO daily_balances 
                          (date, account, currency, net_liquidation, total_cash)
                          VALUES (?, ?, ?, ?, ?)''', (today_str, acc, 'USD', net_liq, 0.0))

        # FIX: We save the Uninvested Cash directly as a portfolio position!
        cursor.execute('''INSERT INTO daily_positions
                          (date, account, symbol, sec_type, position, market_price, market_value, avg_cost, unrealized_pnl, realized_pnl)
                          VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
                       (today_str, acc, 'USD CASH', 'CASH', total_cash, 1.0, total_cash, total_cash, 0.0, 0.0))

        for item in portfolio_items:
            contract = item.contract
            if contract.secType == 'OPT':
                symbol = f"{contract.symbol}_{contract.lastTradeDateOrContractMonth}_{contract.strike}_{contract.right}"
            else: symbol = contract.localSymbol if contract.localSymbol else contract.symbol
            
            cursor.execute('''INSERT INTO daily_positions
                              (date, account, symbol, sec_type, position, market_price, market_value, avg_cost, unrealized_pnl, realized_pnl)
                              VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
                           (today_str, acc, symbol, contract.secType, item.position, item.marketPrice, item.marketValue, item.averageCost, item.unrealizedPNL, item.realizedPNL))

    conn.commit()
    conn.close()
    print(f"[+] Sync Complete. DB Patched.")

if __name__ == '__main__':
    sync_tws()