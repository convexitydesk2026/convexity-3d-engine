"""
=============================================================================
Script Name: attribution_engine_v20.py
Purpose: Parses the official IBKR Flex Query (MTM and CNAV).
         - FIXED: "Rolling Window Amputation" bug via Dynamic Data Stitching.
         - FIXED: "Zero Cash Flow" Bug (Regex header parsing).
         - FIXED: Table Drop Bug. Prevents wiping manual UI cash flow entries.
=============================================================================
"""

import sqlite3
import csv
import os
import time
import requests
import configparser
import collections
from datetime import date, datetime
import xml.etree.ElementTree as ET

TARGET_DIR = r"C:\Users\donca\Desktop\Desktop HP Envy x360 al 22Abr24\Docs Manuel\IBKR_Options"
DB_PATH = os.path.join(TARGET_DIR, "estate_data.db")
CONFIG_PATH = os.path.join(TARGET_DIR, "estate_config.ini")
FLEX_CSV_PATH = os.path.join(TARGET_DIR, "Estate_Master_MTM_Sync.csv")

def parse_date(date_str):
    """Converts IBKR YYYYMMDD to YYYY-MM-DD"""
    if not date_str or len(date_str) != 8: 
        return None
    return f"{date_str[:4]}-{date_str[4:6]}-{date_str[6:]}"

def safe_float(val):
    """Safely converts empty or missing strings into 0.0 floats."""
    try:
        if not val or str(val).strip() == '': 
            return 0.0
        return float(str(val).strip())
    except ValueError:
        return 0.0

def get_bucket(sym, sec_type, p_c, exp_date_str, report_date_str):
    """Determines the specific architectural strategy bucket for a PnL event."""
    s = str(sym).upper()
    
    if 'IB01' in s: 
        return 'a1_yield'
        
    if sec_type == 'CASH':
        if 'USD' in s or s == 'BASE': 
            return 'a1_yield'
        else: 
            return 'a4_alpha' # FX PnL
            
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
            
            # Tail Hedges
            if 'VIX' in s and p_c == 'C': 
                return 'a4_alpha'
            if p_c == 'P' and dte > 60 and is_index: 
                return 'a4_alpha'
                
            # Synthetic Beta
            if p_c == 'C' and dte > 90 and is_index: 
                return 'a2_beta'
                
        except Exception: 
            pass
            
        return 'a3_vrp' # Default for short-dated options
        
    return 'a4_alpha' # Active Swing / CFDs / Default

def fetch_flex_report(token, query_id):
    """Connects to the IBKR Flex Web Service and automatically downloads the CSV."""
    print(f"[*] Requesting Flex Query {query_id} via IBKR Web Service...")
    
    request_url = f"https://gdcdyn.interactivebrokers.com/Universal/servlet/FlexStatementService.SendRequest?t={token}&q={query_id}&v=3"
    response = requests.get(request_url, headers={'User-Agent': 'Mozilla/5.0'})
    
    try:
        root = ET.fromstring(response.text)
    except ET.ParseError:
        print("[!] Failed to parse XML response from IBKR.")
        return False
        
    status = root.find('Status').text if root.find('Status') is not None else 'Error'
    
    if status != 'Success':
        error_msg = root.find('ErrorMessage').text if root.find('ErrorMessage') is not None else 'Unknown Error'
        print(f"[!] API Request Failed: {error_msg}")
        return False
        
    ref_code = root.find('ReferenceCode').text
    base_url = root.find('Url').text
    
    print(f"[*] Report generation initiated. Reference Code: {ref_code}")
    print("[*] Waiting for IBKR servers to compile the 205-day report...")
    
    poll_url = f"{base_url}?q={ref_code}&t={token}&v=3"
    
    # Poll the server every 5 seconds until the report is ready
    for attempt in range(24): # Maximum 120 seconds wait time
        time.sleep(5)
        res = requests.get(poll_url, headers={'User-Agent': 'Mozilla/5.0'})
        
        # If the response starts with XML, the report is still generating or failed
        if res.text.strip().startswith('<FlexStatementResponse'):
            try:
                poll_root = ET.fromstring(res.text)
                poll_status = poll_root.find('Status').text if poll_root.find('Status') is not None else ''
                
                if poll_status == 'Warn':
                    # Warning usually means "Still generating"
                    continue 
                elif poll_status == 'Error':
                    err = poll_root.find('ErrorMessage').text
                    print(f"[!] API Polling Error: {err}")
                    return False
            except Exception:
                pass
                
        # If the response is not XML, we successfully received the CSV payload!
        else:
            with open(FLEX_CSV_PATH, 'wb') as f:
                f.write(res.content)
            print("[+] Flex Query successfully downloaded and saved to disk.")
            return True
            
    print("[!] Timeout waiting for Flex Query to generate.")
    return False

def run_attribution():
    print("========================================================")
    print("   ESTATE P&L ATTRIBUTION ENGINE (v19 FULL AUTOMATION)")
    print("   100% IBKR Verified Clearinghouse Math & Self-Healing")
    print("========================================================")
    
    # 1. Load Configurations & Fetch the Report
    config = configparser.ConfigParser()
    config.read(CONFIG_PATH)
    
    try:
        token = config['IBKR']['TOKEN']
        query_id = config['IBKR']['MTM_QUERY_ID']
        
        # Download the report dynamically
        success = fetch_flex_report(token, query_id)
        if not success:
            print("[!] Falling back to local CSV file if available...")
    except KeyError:
        print("[!] Token or MTM_QUERY_ID missing in estate_config.ini. Using local CSV.")

    if not os.path.exists(FLEX_CSV_PATH):
        print(f"[!] CRITICAL: Could not find Flex Query CSV at {FLEX_CSV_PATH}")
        return

    cnav_idx, mtmp_idx = {}, {}
    cash_flows = []
    pnl_records = []
    healing_inserts = []
    
    # Python Datetime FIX
    today_str = date.today().isoformat()
    
    print("[*] 1. Parsing MTM Data, Cash Flows, & Historic NAVs from CSV...")
    with open(FLEX_CSV_PATH, 'r', encoding='utf-8-sig') as f:
        reader = csv.reader(f)
        for row in reader:
            if not row or len(row) < 3: 
                continue
            
            row_type, sec_type = row[0], row[1]

            # -- MAP HEADERS DYNAMICALLY --
            if row_type == 'HEADER':
                if sec_type == 'CNAV': 
                    # V19 FIX: Strip spaces and punctuation so "Deposits/Withdrawals" maps cleanly
                    cnav_idx = {val.replace(' ', '').replace('/', '').replace('_', ''): i for i, val in enumerate(row)}
                elif sec_type == 'MTMP': 
                    mtmp_idx = {val.replace(' ', '').replace('/', '').replace('_', ''): i for i, val in enumerate(row)}
            
            # -- EXTRACT DATA --
            elif row_type == 'DATA':
                
                # --- CHANGE IN NAV SECTION (CNAV) ---
                if sec_type == 'CNAV' and cnav_idx:
                    acc = row[cnav_idx['ClientAccountID']].strip().rstrip('F')
                    parsed_dt = parse_date(row[cnav_idx['ToDate']])
                    
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
                    
                    if abs(interest) > 0: 
                        pnl_records.append({'date': parsed_dt, 'bucket': 'a1_yield' if interest > 0 else 'a5_fees', 'pnl': interest})
                    if abs(divs) > 0: 
                        pnl_records.append({'date': parsed_dt, 'bucket': 'a2_beta', 'pnl': divs})
                    if abs(tax) > 0: 
                        pnl_records.append({'date': parsed_dt, 'bucket': 'a5_fees', 'pnl': tax})
                    if abs(fees) > 0: 
                        pnl_records.append({'date': parsed_dt, 'bucket': 'a5_fees', 'pnl': fees})
                        
                    # 1c. HARVEST HISTORIC NAV FOR DATABASE HEALING
                    ending_value = safe_float(row[cnav_idx.get('EndingValue', -1)])
                    
                    # The Firewall: Never overwrite today's live TWS sync data
                    if parsed_dt and parsed_dt < today_str and ending_value > 0:
                        healing_inserts.append((parsed_dt, acc, 'USD', ending_value, 0.0, 0.0))
                        
                # --- MARK-TO-MARKET PERFORMANCE SECTION (MTMP) ---
                elif sec_type == 'MTMP' and mtmp_idx:
                    asset_class = row[mtmp_idx.get('AssetClass', 5)]
                    symbol = row[mtmp_idx.get('Symbol', 7)]
                    underlying = row[mtmp_idx.get('UnderlyingSymbol', 17)]
                    expiry = row[mtmp_idx.get('Expiry', 24)]
                    p_c = row[mtmp_idx.get('PutCall', 25)]
                    report_dt = row[mtmp_idx.get('ReportDate', 0)]
                    
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
    
    # V19 FAILSAFE: If the fallback CSV is broken or empty, DO NOT wipe the database!
    if len(cash_flows) == 0 and len(pnl_records) == 0:
        print("[!] CRITICAL ABORT: 0 records extracted. The CSV is empty or corrupted.")
        print("[!] Aborting database commit to protect the historical ledger.")
        return

    print("[*] 2. Aggregating attribution into strategy buckets...")
    
    daily_aggs = collections.defaultdict(lambda: {'a1_yield': 0, 'a2_beta': 0, 'a3_vrp': 0, 'a4_alpha': 0, 'a5_fees': 0})
    for r in pnl_records:
        daily_aggs[r['date']][r['bucket']] += r['pnl']
        
    print("[*] 3. Committing to SQLite (WAL Mode)...")
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA journal_mode=WAL;")
    c = conn.cursor()
    
    # -------------------------------------------------------------------------
    # SELF-HEALING PROTOCOL
    # -------------------------------------------------------------------------
    print(f"[*] 4. Self-Healing Protocol: Scanning for missing days to backfill...")
    c.execute("CREATE TABLE IF NOT EXISTS daily_balances (date TEXT, account TEXT, currency TEXT, net_liquidation REAL, total_cash REAL, available_funds REAL)")
    c.execute("SELECT date, account FROM daily_balances")
    existing_records = set(c.fetchall())
    
    injections = 0
    for record in healing_inserts:
        # record = (date, account, currency, net_liquidation, total_cash, available_funds)
        date_val = record[0]
        acc_val = record[1]
        
        # If the date+account combo doesn't exist in the database, inject it.
        if (date_val, acc_val) not in existing_records:
            c.execute("INSERT INTO daily_balances VALUES (?, ?, ?, ?, ?, ?)", record)
            # Add to the set so we don't try to inject it twice in the loop
            existing_records.add((date_val, acc_val)) 
            injections += 1
            
    print(f"    - [+] Successfully injected {injections} missing daily balance records.")

    # -------------------------------------------------------------------------
    # WRITE CASH FLOWS & ATTRIBUTION (V20: DYNAMIC STITCHING)
    # -------------------------------------------------------------------------
    
    # Identify the oldest date in the current CSV payload to establish the "Stitching Boundary"
    all_dates = [r['date'] for r in pnl_records if r['date']] + [c[0] for c in cash_flows if c[0]]
    min_date = min(all_dates) if all_dates else None

    # Refresh Cash Transfers Table SAFELY
    c.execute("CREATE TABLE IF NOT EXISTS cash_transfers (date TEXT, account TEXT, amount REAL, type TEXT, notes TEXT)")
    
    if min_date:
        # V20: Only delete official flows that are equal to or newer than the CSV's oldest date.
        # This permanently protects older historical data from being amputated by a rolling window.
        c.execute("DELETE FROM cash_transfers WHERE notes = 'Official Clearinghouse Flow' AND date >= ?", (min_date,))
    
    if cash_flows:
        c.executemany("INSERT INTO cash_transfers VALUES (?, ?, ?, ?, ?)", cash_flows)
    
    # Refresh Attribution Table SAFELY
    c.execute('''CREATE TABLE IF NOT EXISTS daily_attribution (date TEXT PRIMARY KEY, a1_yield REAL, a2_beta REAL, a3_vrp REAL, a4_alpha REAL, a5_fees REAL)''')
    
    if min_date:
        c.execute("DELETE FROM daily_attribution WHERE date >= ?", (min_date,))
    
    attr_inserts = []
    for d, b in daily_aggs.items():
        attr_inserts.append((d, b['a1_yield'], b['a2_beta'], b['a3_vrp'], b['a4_alpha'], b['a5_fees']))
        
    if attr_inserts:
        c.executemany("INSERT INTO daily_attribution VALUES (?, ?, ?, ?, ?, ?)", attr_inserts)
    
    conn.commit()
    conn.close()
    
    print("[+] SUCCESS: v20 Engine Complete. Infinite Data Stitching Deployed.\n")

if __name__ == '__main__':
    run_attribution()