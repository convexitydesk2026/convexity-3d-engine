"""
=============================================================================
Script Name: sync_engine_v23.py
Purpose: Phase 7 of the Local-First Estate Architecture.
         - NEW: Extracts native `currency` tags from IBKR contracts.
         - NEW: Upgrades database schema to store `currency` in both 
           daily_positions and open_orders, enabling dynamic FX conversions
           for international Total Open Risk (TOR) tracking.
         - INCLUDES: Phase 6 BAG/Combo unpacker.
=============================================================================
"""
from ib_insync import *
import sqlite3
import datetime
import os
import time
import random
import yfinance as yf

PORT = 7496
DB_NAME = "estate_data.db"
TARGET_DIR = r"C:\Users\donca\Desktop\Desktop HP Envy x360 al 22Abr24\Docs Manuel\IBKR_Options"
DB_PATH = os.path.join(TARGET_DIR, DB_NAME)

def init_db():
    if not os.path.exists(TARGET_DIR): os.makedirs(TARGET_DIR)
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    
    # 1. Update daily_balances
    c.execute('''CREATE TABLE IF NOT EXISTS daily_balances (date TEXT, account TEXT, currency TEXT, net_liquidation REAL, total_cash REAL, PRIMARY KEY (date, account, currency))''')
    c.execute("PRAGMA table_info(daily_balances)")
    cols = [row[1] for row in c.fetchall()]
    if 'available_funds' not in cols: c.execute("ALTER TABLE daily_balances ADD COLUMN available_funds REAL DEFAULT 0.0")
    
    # 2. Update daily_positions (Adding currency column)
    c.execute('''CREATE TABLE IF NOT EXISTS daily_positions (date TEXT, account TEXT, symbol TEXT, sec_type TEXT, position REAL, market_price REAL, market_value REAL, avg_cost REAL, unrealized_pnl REAL, realized_pnl REAL, PRIMARY KEY (date, account, symbol, sec_type))''')
    c.execute("PRAGMA table_info(daily_positions)")
    pos_cols = [row[1] for row in c.fetchall()]
    if 'currency' not in pos_cols: c.execute("ALTER TABLE daily_positions ADD COLUMN currency TEXT DEFAULT 'USD'")
    
    # 3. Update open_orders (Adding currency column)
    c.execute('''CREATE TABLE IF NOT EXISTS open_orders (date TEXT, account TEXT, symbol TEXT, sec_type TEXT, action TEXT, total_quantity REAL, order_type TEXT, lmt_price REAL, aux_price REAL, PRIMARY KEY (date, account, symbol, sec_type, action, order_type))''')
    c.execute("PRAGMA table_info(open_orders)")
    ord_cols = [row[1] for row in c.fetchall()]
    if 'currency' not in ord_cols: c.execute("ALTER TABLE open_orders ADD COLUMN currency TEXT DEFAULT 'USD'")
    
    conn.commit()
    return conn

def fetch_fx_rates():
    rates = {'USD': 1.0}
    # Yahoo direct pairs
    direct = {'EUR': 'EURUSD=X', 'GBP': 'GBPUSD=X', 'AUD': 'AUDUSD=X', 'NZD': 'NZDUSD=X'}
    # Yahoo inverted pairs (USD to CURR)
    inverted = {
        'KRW': 'KRW=X', 'SEK': 'SEK=X', 'CAD': 'CAD=X', 'CHF': 'CHF=X', 
        'JPY': 'JPY=X', 'TWD': 'TWD=X', 'HKD': 'HKD=X', 'SGD': 'SGD=X'
    }
    
    for curr, pair in direct.items():
        try: rates[curr] = float(yf.Ticker(pair).history(period='1d')['Close'].iloc[-1])
        except: rates[curr] = 1.0
        
    for curr, pair in inverted.items():
        try: 
            rate = float(yf.Ticker(pair).history(period='1d')['Close'].iloc[-1])
            rates[curr] = 1.0 / rate if rate > 0 else 1.0
        except: rates[curr] = 1.0
        
    return rates

def sync_tws():
    print("========================================================")
    print("   ESTATE SYNC ENGINE v23 - YFINANCE FX ENGINE")
    print("========================================================")    
    
    ib_master = IB()
    try: 
        # Connect to Master Client ID to capture manual GUI orders
        ib_master.connect('127.0.0.1', PORT, clientId=0)
    except Exception as e: 
        print(f"[!] Could not connect to TWS. Is it running? Error: {e}")
        return
        
    accounts = ib_master.managedAccounts()
    master_positions = ib_master.reqPositions()
    expected_counts = {}
    for p in master_positions:
        if p.position != 0: expected_counts[p.account] = expected_counts.get(p.account, 0) + 1
        
    print("[*] Fetching global Open Orders (OCO Brackets)...")
    ib_master.reqAllOpenOrders()
    ib_master.sleep(2.0)
    open_trades = ib_master.openTrades()
    
    expanded_orders = []
    
    # --- Unpack BAG (Combo) Contracts and Native Leg Currencies ---
    for trade in open_trades:
        contract = trade.contract
        order = trade.order
        acc = order.account
        
        if contract.secType == 'BAG':
            for leg in contract.comboLegs:
                leg_contract = Contract(conId=leg.conId)
                ib_master.qualifyContracts(leg_contract) # Resolve missing data (Strike/Right/Currency)
                
                if leg_contract.secType == 'OPT':
                    symbol = f"{leg_contract.symbol}_{leg_contract.lastTradeDateOrContractMonth}_{leg_contract.strike}_{leg_contract.right}"
                else: 
                    symbol = leg_contract.localSymbol if leg_contract.localSymbol else leg_contract.symbol
                
                # Double-Negative Combo Math: Invert the leg action if the master order is a SELL
                leg_action = leg.action
                if order.action == 'SELL':
                    leg_action = 'BUY' if leg.action == 'SELL' else 'SELL'
                    
                expanded_orders.append({
                    'acc': acc, 'symbol': symbol, 'secType': leg_contract.secType,
                    'action': leg_action, 'qty': float(order.totalQuantity) * leg.ratio,
                    'orderType': order.orderType,
                    'lmtPrice': float(order.lmtPrice) if order.lmtPrice else 0.0,
                    'auxPrice': float(order.auxPrice) if order.auxPrice else 0.0,
                    'currency': leg_contract.currency if leg_contract.currency else 'USD'
                })
        else:
            if contract.secType == 'OPT':
                symbol = f"{contract.symbol}_{contract.lastTradeDateOrContractMonth}_{contract.strike}_{contract.right}"
            else: 
                symbol = contract.localSymbol if contract.localSymbol else contract.symbol
                
            expanded_orders.append({
                'acc': acc, 'symbol': symbol, 'secType': contract.secType,
                'action': order.action, 'qty': float(order.totalQuantity),
                'orderType': order.orderType,
                'lmtPrice': float(order.lmtPrice) if order.lmtPrice else 0.0,
                'auxPrice': float(order.auxPrice) if order.auxPrice else 0.0,
                'currency': contract.currency if contract.currency else 'USD'
            })
            
    ib_master.disconnect()

    conn = init_db()
    cursor = conn.cursor()
    today_str = datetime.date.today().isoformat()
    
    cursor.execute("DELETE FROM daily_balances WHERE date = ?", (today_str,))
    cursor.execute("DELETE FROM daily_positions WHERE date = ?", (today_str,))
    cursor.execute("DELETE FROM open_orders WHERE date = ?", (today_str,))
    
    # Save the expanded orders directly, now including currency        
    for t in expanded_orders:
        cursor.execute('''INSERT OR REPLACE INTO open_orders
                          (date, account, symbol, sec_type, action, total_quantity, order_type, lmt_price, aux_price, currency)
                          VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
                       (today_str, t['acc'], t['symbol'], t['secType'], t['action'], t['qty'], t['orderType'], t['lmtPrice'], t['auxPrice'], t['currency']))
        
    client_id = random.randint(100, 9999)  # <--- RANDOMIZE ID TO PREVENT ZOMBIE LOCKS
    for acc in accounts:        
        
        expected = expected_counts.get(acc, 0)
        print(f"[*] Processing Portfolio Data for {acc}...")
        
        time.sleep(1.5)  # Gives TWS API time to close the previous socket
                
        ib = IB()
        ib.RequestTimeout = 10  # STRICT TIMEOUT: Prevents infinite hanging on unfunded accounts
        
        try:
            ib.connect('127.0.0.1', PORT, clientId=client_id)
            client_id += 1 
            
            # This try/except catches TWS ignoring unfunded accounts (Silo D)
            try:
                ib.reqAccountUpdates(acc)
            except Exception:
                print(f"[!] Warning: {acc} timed out (Likely unfunded/dormant). Assigning $0.")
                
            timer = 0
            while True:
                if len(ib.portfolio(acc)) == expected and len(ib.accountValues(acc)) > 0: break
                if timer >= 10: break # Reduced wait time for empty accounts
                ib.sleep(1.0); timer += 1
                
            values = ib.accountValues(acc)
            portfolio_items = ib.portfolio(acc)
            ib.disconnect()
            
        except Exception as e:
            print(f"[!] Error processing {acc}: {e}. Skipping.")
            values = []
            portfolio_items = []
            if ib.isConnected(): ib.disconnect()        
        
        net_liq_base, total_cash_base, accrued_cash_base, avail_funds_base = None, None, None, None
        net_liq_usd, total_cash_usd, accrued_cash_usd, avail_funds_usd = 0.0, 0.0, 0.0, 0.0
        
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
            elif v.tag == 'AvailableFunds':
                if v.currency == 'BASE': avail_funds_base = float(v.value)
                elif v.currency == 'USD': avail_funds_usd = float(v.value)
                
        net_liq = net_liq_base if net_liq_base is not None else net_liq_usd
        total_cash = total_cash_base if total_cash_base is not None else total_cash_usd
        accrued_cash = accrued_cash_base if accrued_cash_base is not None else accrued_cash_usd
        avail_funds = avail_funds_base if avail_funds_base is not None else avail_funds_usd
        
        cursor.execute("INSERT INTO daily_balances VALUES (?, ?, ?, ?, ?, ?)", (today_str, acc, 'USD', net_liq, 0.0, avail_funds))
        
        # Explicit column mapping needed now that we added 'currency' to the schema
        cursor.execute("INSERT INTO daily_positions (date, account, symbol, sec_type, position, market_price, market_value, avg_cost, unrealized_pnl, realized_pnl, currency) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", 
                       (today_str, acc, 'USD CASH', 'CASH', total_cash, 1.0, total_cash, total_cash, 0.0, 0.0, 'USD'))

        if accrued_cash != 0: 
            cursor.execute("INSERT INTO daily_positions (date, account, symbol, sec_type, position, market_price, market_value, avg_cost, unrealized_pnl, realized_pnl, currency) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", 
                           (today_str, acc, 'ACCRUED INTEREST/CFD FEES', 'CASH', accrued_cash, 1.0, accrued_cash, accrued_cash, 0.0, 0.0, 'USD'))

        real_fx_rates = fetch_fx_rates()

        for item in portfolio_items:
            c_curr = item.contract.currency if item.contract.currency else 'USD'
            fx = real_fx_rates.get(c_curr, 1.0)

            # ib_insync normalizes LSE cost basis to Pounds automatically, so we just apply standard FX
            mkt_price_usd = float(item.marketPrice) * fx
            mkt_val_usd = float(item.marketValue) * fx
            avg_cost_usd = float(item.averageCost) * fx
            unrealized_usd = float(item.unrealizedPNL) * fx
            realized_usd = float(item.realizedPNL) * fx

            if item.contract.secType == 'OPT':        
                symbol = f"{item.contract.symbol}_{item.contract.lastTradeDateOrContractMonth}_{item.contract.strike}_{item.contract.right}"
            else: 
                symbol = item.contract.localSymbol if item.contract.localSymbol else item.contract.symbol
                
            cursor.execute("INSERT INTO daily_positions (date, account, symbol, sec_type, position, market_price, market_value, avg_cost, unrealized_pnl, realized_pnl, currency) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", 
                           (today_str, acc, symbol, item.contract.secType, item.position, mkt_price_usd, mkt_val_usd, avg_cost_usd, unrealized_usd, realized_usd, c_curr))

    conn.commit()
    conn.close()
    print(f"[+] Sync Complete. True option legs resolved and DB Patched.")

if __name__ == '__main__':
    sync_tws()