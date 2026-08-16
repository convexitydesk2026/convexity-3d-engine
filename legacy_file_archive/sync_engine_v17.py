"""
=============================================================================
Script Name: sync_engine_v17.py
Purpose: Phase 3 of the Local-First Estate Architecture.
         - NEW: Live FX normalization. Detects non-USD assets (SEK, EUR, GBP) 
           and dynamically converts their local market values, costs, and PnL
           into base USD using TWS live exchange rates to prevent GAAP inflation.
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
    print("   ESTATE SYNC ENGINE v17 - LIVE FX NORMALIZATION")
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

        net_liq_base, total_cash_base, accrued_cash_base = None, None, None
        net_liq_usd, total_cash_usd, accrued_cash_usd = 0.0, 0.0, 0.0
        
        # --- NEW: Build a Live FX Dictionary from TWS ---
        fx_rates = {'USD': 1.0, 'BASE': 1.0}
        for v in values:
            if v.tag == 'ExchangeRate':
                fx_rates[v.currency] = float(v.value)
        
        for v in values:
            if v.tag in ['NetLiquidation', 'NetLiquidationByCurrency']:
                if v.currency == 'BASE': net_liq_base = float(v.value)
                elif v.currency == 'USD': net_liq_usd = float(v.value)
            elif v.tag in ['TotalCashBalance', 'CashBalance']:
                if v.currency == 'BASE': total_cash_base = float(v.value)
                elif v.currency == 'USD': total_cash_usd = float(v.value)
            elif v.tag in ['AccruedCash', 'AccruedDividend']:
                if v.currency == 'BASE': accrued_cash_base = float(v.value)
                elif v.currency == 'USD': accrued_cash_usd = float(v.value)
                
        net_liq = net_liq_base if net_liq_base is not None else net_liq_usd
        total_cash = total_cash_base if total_cash_base is not None else total_cash_usd
        accrued_cash = accrued_cash_base if accrued_cash_base is not None else accrued_cash_usd
        
        cursor.execute('''INSERT INTO daily_balances 
                          (date, account, currency, net_liquidation, total_cash)
                          VALUES (?, ?, ?, ?, ?)''', (today_str, acc, 'USD', net_liq, 0.0))

        cursor.execute('''INSERT INTO daily_positions
                          (date, account, symbol, sec_type, position, market_price, market_value, avg_cost, unrealized_pnl, realized_pnl)
                          VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
                       (today_str, acc, 'USD CASH', 'CASH', total_cash, 1.0, total_cash, total_cash, 0.0, 0.0))

        if accrued_cash != 0:
            cursor.execute('''INSERT INTO daily_positions
                              (date, account, symbol, sec_type, position, market_price, market_value, avg_cost, unrealized_pnl, realized_pnl)
                              VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
                           (today_str, acc, 'ACCRUED INTEREST/CFD FEES', 'CASH', accrued_cash, 1.0, accrued_cash, accrued_cash, 0.0, 0.0))

        for item in portfolio_items:
            contract = item.contract
            
            # --- NEW: Apply FX Multiplier ---
            c_curr = contract.currency if contract.currency else 'USD'
            fx = fx_rates.get(c_curr, 1.0)
            
            mkt_price_usd = float(item.marketPrice) * fx
            mkt_val_usd = float(item.marketValue) * fx
            avg_cost_usd = float(item.averageCost) * fx
            unrealized_usd = float(item.unrealizedPNL) * fx
            realized_usd = float(item.realizedPNL) * fx

            if contract.secType == 'OPT':
                symbol = f"{contract.symbol}_{contract.lastTradeDateOrContractMonth}_{contract.strike}_{contract.right}"
            else: symbol = contract.localSymbol if contract.localSymbol else contract.symbol
            
            cursor.execute('''INSERT INTO daily_positions
                              (date, account, symbol, sec_type, position, market_price, market_value, avg_cost, unrealized_pnl, realized_pnl)
                              VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
                           (today_str, acc, symbol, contract.secType, item.position, mkt_price_usd, mkt_val_usd, avg_cost_usd, unrealized_usd, realized_usd))

    conn.commit()
    conn.close()
    print(f"[+] Sync Complete. FX normalized for international assets. DB Patched.")

if __name__ == '__main__':
    sync_tws()