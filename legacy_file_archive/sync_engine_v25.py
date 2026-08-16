"""
=============================================================================
Script Name: sync_engine_v25.py
Purpose: Phase 8 of the Local-First Estate Architecture.
         - NEW: Added dynamic Alpha Watchlist IV Scanner (Tick 106).
         - MAINTAINS: SQLite WAL Mode to eliminate "Database is Locked" errors.
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
    conn.execute("PRAGMA journal_mode=WAL;")
    c = conn.cursor()
    
    # 1. Update daily_balances
    c.execute('''CREATE TABLE IF NOT EXISTS daily_balances (date TEXT, account TEXT, currency TEXT, net_liquidation REAL, total_cash REAL, available_funds REAL DEFAULT 0.0, PRIMARY KEY (date, account, currency))''')
    
    # 2. Update daily_positions
    c.execute('''CREATE TABLE IF NOT EXISTS daily_positions (date TEXT, account TEXT, symbol TEXT, sec_type TEXT, position REAL, market_price REAL, market_value REAL, avg_cost REAL, unrealized_pnl REAL, realized_pnl REAL, currency TEXT DEFAULT 'USD', PRIMARY KEY (date, account, symbol, sec_type))''')
    
    # 3. Update open_orders
    c.execute('''CREATE TABLE IF NOT EXISTS open_orders (date TEXT, account TEXT, symbol TEXT, sec_type TEXT, action TEXT, total_quantity REAL, order_type TEXT, lmt_price REAL, aux_price REAL, currency TEXT DEFAULT 'USD', PRIMARY KEY (date, account, symbol, sec_type, action, order_type))''')
    
    # 4. NEW: Alpha Conviction Watchlist for IV Scanning
    c.execute('''CREATE TABLE IF NOT EXISTS alpha_watchlist (symbol TEXT PRIMARY KEY, target_iv REAL, current_iv REAL DEFAULT 0.0)''')
    
    conn.commit()
    return conn

def fetch_fx_rates():
    rates = {'USD': 1.0}
    direct = {'EUR': 'EURUSD=X', 'GBP': 'GBPUSD=X', 'AUD': 'AUDUSD=X', 'NZD': 'NZDUSD=X'}
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
    print("   ESTATE SYNC ENGINE v25 - WAL MODE & IV SCANNER")
    print("========================================================")    
    
    ib_master = IB()
    try: 
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
    
    for trade in open_trades:
        contract = trade.contract
        order = trade.order
        acc = order.account
        
        if contract.secType == 'BAG':
            for leg in contract.comboLegs:
                leg_contract = Contract(conId=leg.conId)
                ib_master.qualifyContracts(leg_contract)
                
                if leg_contract.secType == 'OPT':
                    symbol = f"{leg_contract.symbol}_{leg_contract.lastTradeDateOrContractMonth}_{leg_contract.strike}_{leg_contract.right}"
                else: 
                    symbol = leg_contract.localSymbol if leg_contract.localSymbol else leg_contract.symbol
                
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
    
    for t in expanded_orders:
        cursor.execute('''INSERT OR REPLACE INTO open_orders
                          (date, account, symbol, sec_type, action, total_quantity, order_type, lmt_price, aux_price, currency)
                          VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
                       (today_str, t['acc'], t['symbol'], t['secType'], t['action'], t['qty'], t['orderType'], t['lmtPrice'], t['auxPrice'], t['currency']))
        
    client_id = random.randint(100, 9999) 
    for acc in accounts:        
        
        expected = expected_counts.get(acc, 0)
        print(f"[*] Processing Portfolio Data for {acc}...")
        
        time.sleep(1.5) 
                
        ib = IB()
        ib.RequestTimeout = 10 
        
        try:
            ib.connect('127.0.0.1', PORT, clientId=client_id)
            client_id += 1 
            
            try:
                ib.reqAccountUpdates(acc)
            except Exception:
                print(f"[!] Warning: {acc} timed out (Likely unfunded/dormant). Assigning $0.")
                
            timer = 0
            while True:
                if len(ib.portfolio(acc)) == expected and len(ib.accountValues(acc)) > 0: break
                if timer >= 10: break 
                ib.sleep(1.0); timer += 1
                
            values = ib.accountValues(acc)
            portfolio_items = ib.portfolio(acc)
            
        except Exception as e:
            print(f"[!] Error processing {acc}: {e}. Skipping.")
            values = []
            portfolio_items = []
            
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
        
        cursor.execute("INSERT INTO daily_positions (date, account, symbol, sec_type, position, market_price, market_value, avg_cost, unrealized_pnl, realized_pnl, currency) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", 
                       (today_str, acc, 'USD CASH', 'CASH', total_cash, 1.0, total_cash, total_cash, 0.0, 0.0, 'USD'))

        if accrued_cash != 0: 
            cursor.execute("INSERT INTO daily_positions (date, account, symbol, sec_type, position, market_price, market_value, avg_cost, unrealized_pnl, realized_pnl, currency) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", 
                           (today_str, acc, 'ACCRUED INTEREST/CFD FEES', 'CASH', accrued_cash, 1.0, accrued_cash, accrued_cash, 0.0, 0.0, 'USD'))

        real_fx_rates = fetch_fx_rates()

        for item in portfolio_items:
            c_curr = item.contract.currency if item.contract.currency else 'USD'
            fx = real_fx_rates.get(c_curr, 1.0)

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

        if ib.isConnected(): ib.disconnect()

    # --- NEW FEATURE: ALPHA WATCHLIST IV SCANNER ---
    print("[*] Processing Alpha Conviction Watchlist IVs...")
    cursor.execute("SELECT symbol FROM alpha_watchlist")
    watchlist = cursor.fetchall()
    
    if watchlist:
        ib_scanner = IB()
        try:
            ib_scanner.connect('127.0.0.1', PORT, clientId=client_id + 1)
            for row in watchlist:
                sym = str(row[0]).upper()
                try:
                    contract = Stock(sym, 'SMART', 'USD')
                    ib_scanner.qualifyContracts(contract)
                    # genericTickList='106' explicitly requests Option Implied Volatility for the underlying
                    ticker = ib_scanner.reqMktData(contract, genericTickList='106', snapshot=True)
                    ib_scanner.sleep(1.5) # Wait for IBKR servers to return the snapshot
                    
                    live_iv = 0.0
                    if ticker.impliedVolatility and str(ticker.impliedVolatility).lower() != 'nan':
                        live_iv = float(ticker.impliedVolatility) * 100 # Convert to percentage
                    
                    if live_iv > 0:
                        cursor.execute("UPDATE alpha_watchlist SET current_iv = ? WHERE symbol = ?", (live_iv, sym))
                        print(f"    - {sym} IV Logged: {live_iv:.2f}%")
                    else:
                        print(f"    - {sym} IV Logged: Market Data Unavailable (Assigning 0.0%)")
                        
                except Exception as e:
                    print(f"[!] Failed to fetch IV for {sym}: {e}")
            
            ib_scanner.disconnect()
        except Exception as e:
            print(f"[!] IV Scanner failed to connect to TWS: {e}")

    conn.commit()
    conn.close()
    print(f"[+] Sync Complete. True option legs resolved and DB Patched.")

if __name__ == '__main__':
    sync_tws()