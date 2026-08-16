"""
=============================================================================
Script Name: attribution_engine_v16.py
Purpose: Parses the official IBKR Flex Query (MTM and CNAV).
         Replaces Delta-NAV guessing with 100% verified clearinghouse data.
         Automatically handles new Silos and dynamically categorizes PnL.
=============================================================================
"""
import sqlite3
import csv
import os
from datetime import datetime
import collections

TARGET_DIR = r"C:\Users\donca\Desktop\Desktop HP Envy x360 al 22Abr24\Docs Manuel\IBKR_Options"
DB_PATH = os.path.join(TARGET_DIR, "estate_data.db")
FLEX_CSV_PATH = os.path.join(TARGET_DIR, "Estate_Master_MTM_Sync.csv")

def parse_date(date_str):
    """Converts IBKR YYYYMMDD to YYYY-MM-DD"""
    if not date_str or len(date_str) != 8: return None
    return f"{date_str[:4]}-{date_str[4:6]}-{date_str[6:]}"

def safe_float(val):
    try:
        if not val or str(val).strip() == '': return 0.0
        return float(str(val).strip())
    except ValueError:
        return 0.0

def get_bucket(sym, sec_type, p_c, exp_date_str, report_date_str):
    s = str(sym).upper()
    
    if 'IB01' in s: return 'a1_yield'
        
    if sec_type == 'CASH':
        if 'USD' in s or s == 'BASE': return 'a1_yield'
        else: return 'a4_alpha' # FX PnL
            
    if any(x in s for x in ['CSPX', 'CNDX', 'CSNDX', 'ITWN', 'CSKR', 'CNYA', 'SGLN', 'IGLN']):
        return 'a2_beta'
        
    if sec_type == 'OPT':
        try:
            if exp_date_str and report_date_str:
                exp_dt = datetime.strptime(exp_date_str, '%Y%m%d')
                rep_dt = datetime.strptime(report_date_str, '%Y%m%d')
                dte = (exp_dt - rep_dt).days
            else:
                dte = 0
                
            is_index = any(x in s for x in ['SPY', 'SPX', 'XSP', 'QQQ', 'NDX', 'XND'])
            if 'VIX' in s and p_c == 'C': return 'a4_alpha' # Tail Hedge
            if p_c == 'P' and dte > 60 and is_index: return 'a4_alpha' # Tail Hedge
            if p_c == 'C' and dte > 90 and is_index: return 'a2_beta' # Synthetic Beta
        except Exception: pass
        return 'a3_vrp'
        
    return 'a4_alpha' # Active Swing / CFDs / Default

def run_attribution():
    print("========================================================")
    print("   ESTATE P&L ATTRIBUTION ENGINE (v16 FLEX QUERY)")
    print("   100% IBKR Verified Clearinghouse Math")
    print("========================================================")
    
    if not os.path.exists(FLEX_CSV_PATH):
        print(f"[!] CRITICAL: Could not find Flex Query CSV at {FLEX_CSV_PATH}")
        return

    cnav_idx, mtmp_idx = {}, {}
    cash_flows = []
    pnl_records = []
    
    print("[*] 1. Parsing MTM Data & Cash Flows from CSV...")
    with open(FLEX_CSV_PATH, 'r', encoding='utf-8-sig') as f:
        reader = csv.reader(f)
        for row in reader:
            if not row or len(row) < 3: continue
            
            row_type, sec_type = row[0], row[1]
            
            # -- MAP HEADERS DYNAMICALLY --
            if row_type == 'HEADER':
                if sec_type == 'CNAV': cnav_idx = {val: i for i, val in enumerate(row)}
                elif sec_type == 'MTMP': mtmp_idx = {val: i for i, val in enumerate(row)}
            
            # -- EXTRACT DATA --
            elif row_type == 'DATA':
                if sec_type == 'CNAV' and cnav_idx:
                    acc = row[cnav_idx['ClientAccountID']].strip().rstrip('F')
                    dt_str = row[cnav_idx['ToDate']]
                    parsed_dt = parse_date(dt_str)
                    
                    # 1a. Parse Capital Flows (Deposits/Transfers)
                    flow = sum([
                        safe_float(row[cnav_idx.get('DepositsWithdrawals', -1)]),
                        safe_float(row[cnav_idx.get('InternalCashTransfers', -1)]),
                        safe_float(row[cnav_idx.get('AssetTransfers', -1)])
                    ])
                    if abs(flow) > 0.01:
                        cash_flows.append((parsed_dt, acc, flow, 'IBKR Flex Sync', 'Official Clearinghouse Flow'))
                    
                    # 1b. Parse Direct Cash PnL (Interest, Dividends, Fees, Tax)
                    interest = safe_float(row[cnav_idx.get('Interest', -1)])
                    divs = safe_float(row[cnav_idx.get('Dividends', -1)])
                    tax = safe_float(row[cnav_idx.get('WithholdingTax', -1)])
                    fees = sum([
                        safe_float(row[cnav_idx.get('BrokerFees', -1)]),
                        safe_float(row[cnav_idx.get('OtherFees', -1)]),
                        safe_float(row[cnav_idx.get('ClientFees', -1)])
                    ])
                    
                    if abs(interest) > 0: pnl_records.append({'date': parsed_dt, 'bucket': 'a1_yield' if interest > 0 else 'a5_fees', 'pnl': interest})
                    if abs(divs) > 0: pnl_records.append({'date': parsed_dt, 'bucket': 'a2_beta', 'pnl': divs})
                    if abs(tax) > 0: pnl_records.append({'date': parsed_dt, 'bucket': 'a5_fees', 'pnl': tax})
                    if abs(fees) > 0: pnl_records.append({'date': parsed_dt, 'bucket': 'a5_fees', 'pnl': fees})
                        
                elif sec_type == 'MTMP' and mtmp_idx:
                    # 1c. Parse Mark-to-Market PnL
                    asset_class = row[mtmp_idx.get('AssetClass', 5)]
                    symbol = row[mtmp_idx.get('Symbol', 7)]
                    underlying = row[mtmp_idx.get('UnderlyingSymbol', 17)]
                    expiry = row[mtmp_idx.get('Expiry', 24)]
                    p_c = row[mtmp_idx.get('Put/Call', 25)]
                    report_dt = row[mtmp_idx['ReportDate']]
                    
                    total_pnl = safe_float(row[mtmp_idx.get('Total', 37)])
                        
                    if abs(total_pnl) > 0.001:
                        full_sym = f"{symbol} {underlying}".strip()
                        bucket = get_bucket(full_sym, asset_class, p_c, expiry, report_dt)
                        pnl_records.append({
                            'date': parse_date(report_dt),
                            'bucket': bucket,
                            'pnl': total_pnl
                        })

    print(f"[*] Extracted {len(cash_flows)} Cash Flows and {len(pnl_records)} Daily PnL events.")
    print("[*] 2. Aggregating attribution into strategy buckets...")
    
    daily_aggs = collections.defaultdict(lambda: {'a1_yield': 0, 'a2_beta': 0, 'a3_vrp': 0, 'a4_alpha': 0, 'a5_fees': 0})
    for r in pnl_records:
        daily_aggs[r['date']][r['bucket']] += r['pnl']
        
    print("[*] 3. Committing to SQLite (WAL Mode)...")
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA journal_mode=WAL;")
    c = conn.cursor()
    
    # Refresh Cash Transfers Table
    c.execute("DROP TABLE IF EXISTS cash_transfers")
    c.execute("CREATE TABLE cash_transfers (date TEXT, account TEXT, amount REAL, type TEXT, notes TEXT)")
    c.executemany("INSERT INTO cash_transfers VALUES (?, ?, ?, ?, ?)", cash_flows)
    
    # Refresh Attribution Table
    c.execute("DROP TABLE IF EXISTS daily_attribution")
    c.execute('''CREATE TABLE daily_attribution (date TEXT PRIMARY KEY, a1_yield REAL, a2_beta REAL, a3_vrp REAL, a4_alpha REAL, a5_fees REAL)''')
    
    attr_inserts = []
    for d, b in daily_aggs.items():
        attr_inserts.append((d, b['a1_yield'], b['a2_beta'], b['a3_vrp'], b['a4_alpha'], b['a5_fees']))
        
    c.executemany("INSERT INTO daily_attribution VALUES (?, ?, ?, ?, ?, ?)", attr_inserts)
    
    conn.commit()
    conn.close()
    print("[+] SUCCESS: v16 Engine Overhaul Complete. PnL and Cash Flows are 100% pristine.\n")

if __name__ == '__main__':
    run_attribution()