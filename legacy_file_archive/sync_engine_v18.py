"""
=============================================================================
Script Name: sync_engine_v18.py
Purpose: Phase 4 of the Local-First Estate Architecture.
         - NEW: Extracts 'AvailableFunds' to monitor PDT Margin Locks.
         - NEW: Queries reqAllOpenOrders() and saves resting OCO brackets
           into the SQLite DB to power the Naked Options alerting system.
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
    
    # 1. Balances Table
    c.execute('''CREATE TABLE IF NOT EXISTS daily_balances (
                    date TEXT, account TEXT, currency TEXT, 
                    net_liquidation REAL, total_cash REAL,
                    PRIMARY KEY (date, account, currency)
                 )''')
    
    # Schema Migration: Safely add available_funds if it doesn't exist
    c.execute("PRAGMA table_info(daily_balances)")
    cols = [row[1] for row in c.fetchall()]
    if 'available_funds' not in cols:
        c.execute("ALTER TABLE daily_balances ADD COLUMN available_funds REAL DEFAULT 0.0")

    # 2. Positions Table
    c.execute('''CREATE TABLE IF NOT EXISTS daily_positions (
                    date TEXT, account TEXT, symbol TEXT, sec_type TEXT, 
                    position REAL, market_price REAL, market_value REAL, 
                    avg_cost REAL, unrealized_pnl REAL, realized_pnl REAL,
                    PRIMARY KEY (date, account, symbol, sec_type)
                 )''')
                 
    # 3. NEW: Open Orders Table (OCO Traps)
    c.execute('''CREATE TABLE IF NOT EXISTS open_orders (
                    date TEXT, account TEXT, symbol TEXT, sec_type TEXT,
                    action TEXT, total_quantity REAL, order_type TEXT,
                    lmt_price REAL, aux_price REAL,
                    PRIMARY KEY (date, account, symbol, sec_type, action, order_type)
                 )''')
                 
    conn.commit()
    return conn

def sync_tws():
    print("========================================================")
    print("   ESTATE SYNC ENGINE v18 - STRUCTURAL SAFEGUARDS")
    print("========================================================")
    
    ib_master = IB()
    try: 
        ib_master.connect('127.0.0.1', PORT, clientId=1)
    except Exception as e: 
        print(f"[!] Could not connect to TWS. Is it running? Error: {e}")
        return
        
    accounts = ib_master.managedAccounts()
    master_positions = ib_master.reqPositions()
    expected_counts = {}
    for p in master_positions:
        if p.position != 0: expected_counts[p.account] = expected_counts.get(p.account, 0) + 1
        
    # --- NEW: Fetch Open Orders for Naked Options Alert ---
    print("[*] Fetching global Open Orders (OCO Brackets)...")
    ib_master.reqAllOpenOrders()
    ib_master.sleep(2.0) # Give TWS time to return the order list
    open_trades = ib_master.openTrades()
    
    ib_master.disconnect()

    conn = init_db()
    cursor = conn.cursor()
    today_str = datetime.date.today().isoformat()
    
    # Clear today's data to prevent duplicates upon multiple daily syncs
    cursor.execute("DELETE FROM daily_balances WHERE date = ?", (today_str,))
    cursor.execute("DELETE FROM daily_positions WHERE date = ?", (today_str,))
    cursor.execute("DELETE FROM open_orders WHERE date = ?", (today_str,))
    
    # --- Process Open Orders ---
    for trade in open_trades:
        contract = trade.contract
        order = trade.order
        acc = order.account
        
        if contract.secType == 'OPT':
            symbol = f"{contract.symbol}_{contract.lastTradeDateOrContractMonth}_{contract.strike}_{contract.right}"
        else: 
            symbol = contract.localSymbol if contract.localSymbol else contract.symbol
            
        lmt_val = float(order.lmtPrice) if order.lmtPrice else 0.0
        aux_val = float(order.auxPrice) if order.auxPrice else 0.0
            
        cursor.execute('''INSERT OR REPLACE INTO open_orders
                          (date, account, symbol, sec_type, action, total_quantity, order_type, lmt_price, aux_price)
                          VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)''',
                       (today_str, acc, symbol, contract.secType, order.action, float(order.totalQuantity), order.orderType, lmt_val, aux_val))

    client_id = 2
    for acc in accounts:
        expected = expected_counts.get(acc, 0)
        print(f"[*] Processing Portfolio Data for {acc}...")
        
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

        net_liq_base, total_cash_base, accrued_cash_base, avail_funds_base = None, None, None, None
        net_liq_usd, total_cash_usd, accrued_cash_usd, avail_funds_usd = 0.0, 0.0, 0.0, 0.0
        
        # --- Build Live FX Dictionary from TWS ---
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
            # --- NEW: Extract AvailableFunds for PDT Tracking ---
            elif v.tag == 'AvailableFunds':
                if v.currency == 'BASE': avail_funds_base = float(v.value)
                elif v.currency == 'USD': avail_funds_usd = float(v.value)
                
        net_liq = net_liq_base if net_liq_base is not None else net_liq_usd
        total_cash = total_cash_base if total_cash_base is not None else total_cash_usd
        accrued_cash = accrued_cash_base if accrued_cash_base is not None else accrued_cash_usd
        avail_funds = avail_funds_base if avail_funds_base is not None else avail_funds_usd
        
        cursor.execute('''INSERT INTO daily_balances 
                          (date, account, currency, net_liquidation, total_cash, available_funds)
                          VALUES (?, ?, ?, ?, ?, ?)''', (today_str, acc, 'USD', net_liq, 0.0, avail_funds))

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
    print(f"[+] Sync Complete. Margin and OCO traps registered. DB Patched.")

if __name__ == '__main__':
    sync_tws()