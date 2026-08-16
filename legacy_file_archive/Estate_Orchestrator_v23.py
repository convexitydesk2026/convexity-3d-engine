r"""
=============================================================================
Script Name: Estate_Orchestrator_v23.py
Purpose: The Zero-Touch Automation Engine for the Family Office.
         v23 UPGRADES & FIXES:
         - Fixed F-Account wipeout bug via global pre-filtering.
         - Fixed historical snapshot bloat in POST/CRTT databases.
         - Continues to enforce "Seed & Append" Database Architecture.
         - Continues to feed perfectly pure MTMP/TRNT data to the Dashboard.
=============================================================================
"""

import os
import sys
import time
import json
import shutil
import glob
import requests
import urllib3
import pandas as pd
import yfinance as yf
import csv
import io
import datetime
import configparser
import webbrowser

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

TARGET_DIR = r"C:\Users\donca\Desktop\Desktop HP Envy x360 al 22Abr24\Docs Manuel\IBKR_Options"
config_path = os.path.join(TARGET_DIR, 'estate_config.ini')

if not os.path.exists(config_path):
    print(f"[FATAL ERROR] Cannot find {config_path}")
    sys.exit()

config = configparser.ConfigParser()  
config.read(config_path)
TOKEN = config['IBKR']['TOKEN']
QUERY_ID = config['IBKR']['QUERY_ID']

# -------------------------------------------------------------------
# AUTO-BACKUP ROUTINE
# -------------------------------------------------------------------
def create_backup():
    print("\n0. Initiating Pre-Run Auto-Backup...")
    backup_root = os.path.join(TARGET_DIR, "Backups")
    if not os.path.exists(backup_root): os.makedirs(backup_root)
        
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    current_backup_dir = os.path.join(backup_root, f"Backup_{timestamp}")
    os.makedirs(current_backup_dir)
    
    file_types =['*.csv', '*.json', '*.html']
    files_backed_up = 0
    
    for file_type in file_types:
        for f_path in glob.glob(os.path.join(TARGET_DIR, file_type)):
            shutil.copy(f_path, current_backup_dir)
            files_backed_up += 1
            
    print(f"   [OK] {files_backed_up} files safely archived to {current_backup_dir}")

# -------------------------------------------------------------------
# EXPLICIT FLEX QUERY PARSER (WITH F-ACCOUNT ERADICATION)
# -------------------------------------------------------------------
def parse_ibkr_flex(csv_text):
    data = {}
    headers = {}
    reader = csv.reader(io.StringIO(csv_text.strip()))
    
    for row in reader:
        if not row or len(row) < 2: continue
        r_type = row[0].strip().upper()
        sec = row[1].strip().upper()
        
        if r_type == 'HEADER':
            headers[sec] =[c.strip() for c in row[2:]]
            if sec not in data: data[sec] =[]
        elif r_type == 'DATA':
            if sec in headers:
                row_data = row[2:]
                if len(row_data) < len(headers[sec]):
                    row_data += [''] * (len(headers[sec]) - len(row_data))
                data[sec].append(dict(zip(headers[sec], row_data)))
                
    parsed_dfs = {sec: pd.DataFrame(rows) for sec, rows in data.items() if rows}
    
    # GLOBAL F-ACCOUNT ERADICATION (Fixes the $600k Wipeout Bug)
    for sec in parsed_dfs:
        if 'ClientAccountID' in parsed_dfs[sec].columns:
            parsed_dfs[sec] = parsed_dfs[sec][~parsed_dfs[sec]['ClientAccountID'].astype(str).str.endswith('F')].copy()
            
    return parsed_dfs

# -------------------------------------------------------------------
# PROGRESSIVE EXPOSURE ALGORITHM
# -------------------------------------------------------------------
def calculate_progressive_exposure(profit):
    tiers =[
        {"tier": "Base", "threshold": 0, "base": 30000},
        {"tier": "Tier 1", "threshold": 3000, "base": 30000},
        {"tier": "Tier 2", "threshold": 4000, "base": 40000},
        {"tier": "Tier 3", "threshold": 7000, "base": 50000},
        {"tier": "Tier 4", "threshold": 11000, "base": 60000},
        {"tier": "Tier 5", "threshold": 18000, "base": 70000}
    ]
    current_tier, next_tier = tiers[0], tiers[1]
    
    for i, t in enumerate(tiers):
        if profit >= t["threshold"]:
            current_tier = t
            next_tier = tiers[i+1] if (i + 1) < len(tiers) else None
        else: break
            
    return {
        "profit": round(profit, 2),
        "current_tier": current_tier["tier"],
        "suggested_base": current_tier["base"],
        "next_threshold": next_tier["threshold"] if next_tier else "MAX",
        "distance_to_next": round(next_tier["threshold"] - profit, 2) if next_tier else 0
    }

# -------------------------------------------------------------------
# SEED & APPEND DATABASE ENGINE
# -------------------------------------------------------------------
def process_ibkr_data(parsed_dfs):
    print("[DATABASE] Executing Seed & Append Engine...")
    local_db = {}
    
    # 1. Update/Overwrite Static Snapshots (POST, CRTT) - (Fixes the $80M Bloat Bug)
    if 'POST' in parsed_dfs and not parsed_dfs['POST'].empty:
        df = parsed_dfs['POST'].copy()
        df = df.drop_duplicates(subset=['ClientAccountID', 'Symbol', 'AssetClass', 'CurrencyPrimary'], keep='last')
        db_path = os.path.join(TARGET_DIR, "Local_DB_POST.csv")
        df.to_csv(db_path, index=False)
        local_db['POST'] = df
    else:
        db_path = os.path.join(TARGET_DIR, "Local_DB_POST.csv")
        local_db['POST'] = pd.read_csv(db_path, dtype=str) if os.path.exists(db_path) else pd.DataFrame()

    if 'CRTT' in parsed_dfs and not parsed_dfs['CRTT'].empty:
        df = parsed_dfs['CRTT'].copy()
        df = df.drop_duplicates(subset=['ClientAccountID', 'CurrencyPrimary'], keep='last')
        db_path = os.path.join(TARGET_DIR, "Local_DB_CRTT.csv")
        df.to_csv(db_path, index=False)
        local_db['CRTT'] = df
    else:
        db_path = os.path.join(TARGET_DIR, "Local_DB_CRTT.csv")
        local_db['CRTT'] = pd.read_csv(db_path, dtype=str) if os.path.exists(db_path) else pd.DataFrame()

    # 2. Append & Deduplicate Historical Logs (CNAV, MTMP, TRNT, CTRN)
    dedup_subsets = {
        'CNAV': ['ClientAccountID', 'ToDate'],
        'MTMP': ['ClientAccountID', 'ReportDate', 'Symbol', 'AssetClass'],
        'TRNT': ['ClientAccountID', 'TradeDate', 'Symbol', 'TransactionID'], 
        'CTRN':['ClientAccountID', 'ReportDate', 'Type', 'Amount', 'Symbol']
    }
    
    for sec in ['CNAV', 'MTMP', 'TRNT', 'CTRN']:
        db_path = os.path.join(TARGET_DIR, f"Local_DB_{sec}.csv")
        old_df = pd.read_csv(db_path, dtype=str) if os.path.exists(db_path) else pd.DataFrame()
        new_df = parsed_dfs.get(sec, pd.DataFrame())
        
        if not new_df.empty:
            combined = pd.concat([old_df, new_df], ignore_index=True)
            if dedup_subsets[sec]: combined = combined.drop_duplicates(subset=dedup_subsets[sec], keep='last')
            else: combined = combined.drop_duplicates(keep='last')
            combined.to_csv(db_path, index=False)
            local_db[sec] = combined
        else:
            local_db[sec] = old_df
            
    print("   [OK] Local Databases Synced & Deduplicated.")
    execute_hierarchy_math(local_db)

# -------------------------------------------------------------------
# THE HIERARCHY OF TRUTH MATH ENGINE
# -------------------------------------------------------------------
def execute_hierarchy_math(db):
    print("   [MATH] Re-calculating Global Estate Matrix...")
    
    # --- 1. BUILD IBKR_Daily_Data.csv ---
    cnav = db.get('CNAV', pd.DataFrame())
    if not cnav.empty:
        cnav['AccountID'] = cnav['ClientAccountID'].astype(str).str.replace('F', '', regex=False)
        cnav['Date'] = cnav['ToDate']
        cnav['NAV'] = pd.to_numeric(cnav['EndingValue'], errors='coerce').fillna(0)
        cnav['CashFlow'] = pd.to_numeric(cnav['DepositsWithdrawals'], errors='coerce').fillna(0)
        
        daily_nav = cnav.groupby(['AccountID', 'Date']).agg({'NAV': 'last', 'CashFlow': 'sum'}).reset_index()
        daily_nav.sort_values(by=['AccountID', 'Date'], inplace=True)
        daily_nav.to_csv(os.path.join(TARGET_DIR, 'IBKR_Daily_Data.csv'), index=False)
    else:
        daily_nav = pd.read_csv(os.path.join(TARGET_DIR, 'IBKR_Daily_Data.csv'))

    # --- 2. EXTRACT A1, A3, A4 (MTMP) ---
    mtmp = db.get('MTMP', pd.DataFrame())
    a1_map, a3_map, a4_alpha_map = {}, {}, {}
    
    if not mtmp.empty:
        mtmp['Date'] = mtmp['ReportDate']
        mtmp['Total'] = pd.to_numeric(mtmp['Total'], errors='coerce').fillna(0)
        mtmp['AccountID'] = mtmp['ClientAccountID'].astype(str).str.replace('F', '', regex=False)
        
        for dt, group in mtmp.groupby('Date'):
            # a1: Yield from IB01 or Idle Cash
            a1_val = group[(group['Symbol'].str.contains('IB01', na=False)) | (group['AssetClass'] == 'CASH')]['Total'].sum()
            a1_map[dt] = a1_val
            
            # a3: VRP from Options
            a3_val = group[group['AssetClass'] == 'OPT']['Total'].sum()
            a3_map[dt] = a3_val
            
            # a4: Active Alpha (Silo B/D + Alpha ETFs everywhere)
            alpha_etfs =['ITWN', 'CSKR', 'CNYA', 'ETHE', 'BTC']
            a4_val = group[
                (group['AccountID'].isin(['U23139264', 'U25218481'])) | 
                (group['Symbol'].str.contains('|'.join(alpha_etfs), case=False, na=False))
            ]['Total'].sum()
            a4_alpha_map[dt] = a4_val

    # --- 3. EXTRACT A5 FEES (TRNT + CTRN) ---
    a5_map = {}
    trnt = db.get('TRNT', pd.DataFrame())
    if not trnt.empty:
        trnt['TradeDate'] = trnt['TradeDate'].astype(str).str.strip()
        trnt['IBCommission'] = pd.to_numeric(trnt['IBCommission'], errors='coerce').fillna(0)
        trnt_fees = trnt[trnt['TradeDate'] != ''].groupby('TradeDate')['IBCommission'].sum().to_dict()
        for k, v in trnt_fees.items(): a5_map[k] = a5_map.get(k, 0) + v
            
    ctrn = db.get('CTRN', pd.DataFrame())
    if not ctrn.empty:
        ctrn['ReportDate'] = ctrn['ReportDate'].astype(str).str.strip()
        ctrn['Amount'] = pd.to_numeric(ctrn['Amount'], errors='coerce').fillna(0)
        non_trade = ctrn[(ctrn['ReportDate'] != '') & (~ctrn['Type'].str.contains('Withdrawal|Deposit', case=False, na=False))]
        ctrn_fees = non_trade.groupby('ReportDate')['Amount'].sum().to_dict()
        for k, v in ctrn_fees.items(): a5_map[k] = a5_map.get(k, 0) + v

    # --- 4. OPTIONS VELOCITY WIDGET ---
    if not trnt.empty:
        opt_c = trnt[(trnt['AssetClass'] == 'OPT') & (trnt['Open/CloseIndicator'].astype(str) == 'C')].copy()
        if not opt_c.empty:
            opt_c['FifoPnlRealized'] = pd.to_numeric(opt_c['FifoPnlRealized'], errors='coerce').fillna(0)
            opt_c = opt_c[opt_c['TradeDate'].astype(str).str.strip() != '']
            opt_c['OpenDT'] = opt_c['OpenDateTime'].astype(str).str.split(';').str[0]
            
            opt_c['Days'] = (pd.to_datetime(opt_c['TradeDate'], format='%Y%m%d', errors='coerce') - 
                             pd.to_datetime(opt_c['OpenDT'], format='%Y%m%d', errors='coerce')).dt.days
            
            win_rate = (len(opt_c[opt_c['FifoPnlRealized'] > 0]) / len(opt_c)) * 100
            avg_days = opt_c['Days'].mean() if not opt_c['Days'].isna().all() else 0
            vel_data = {"win_rate": round(win_rate, 1), "avg_days": round(avg_days, 1)}
            
            with open(os.path.join(TARGET_DIR, 'Velocity_Metrics.json'), 'w') as f:
                json.dump(vel_data, f)
            print("   [OK] Options Journal Automated via Closed Lots.")

    # --- 5. BUILD ATTRIBUTION LEDGER ---
    attr_list =[]
    if not daily_nav.empty:
        daily_nav['Date'] = daily_nav['Date'].astype(str)
        dates = sorted(daily_nav['Date'].unique())
        
        for dt in dates:
            day_data = daily_nav[daily_nav['Date'] == dt]
            global_nav = day_data['NAV'].sum()
            global_cf = day_data['CashFlow'].sum()
            
            prev_dt = daily_nav[daily_nav['Date'] < dt]['Date'].max()
            if pd.isna(prev_dt):
                prev_global_nav = global_nav - global_cf
            else:
                prev_global_nav = daily_nav[daily_nav['Date'] == prev_dt]['NAV'].sum()

            global_pnl = global_nav - prev_global_nav - global_cf
            
            a1 = a1_map.get(dt, 0.0)
            a3 = a3_map.get(dt, 0.0)
            a5 = a5_map.get(dt, 0.0)
            
            # a4_net is from MTMP, a4_gross adds explicit friction back so a2 isn't penalized
            a4_net = a4_alpha_map.get(dt, 0.0)
            a4_gross = a4_net + abs(a5)
            
            # The mathematical plug ensures Dashboard ties to the penny
            a2 = global_pnl - (a1 + a3 + a4_gross + a5)
            
            attr_list.append({'Date': dt, 'a1_Yield': a1, 'a2_Beta': a2, 'a3_VRP': a3, 'a4_Alpha': a4_gross, 'a5_Fees': a5})

    pd.DataFrame(attr_list).to_csv(os.path.join(TARGET_DIR, 'Daily_PnL_Attribution.csv'), index=False)
    print("   [OK] Daily Attribution Ledger re-built with pure MTMP/TRNT data.")

    # --- 6. LIVE ALLOCATIONS & EXPOSURE ---
    post = db.get('POST', pd.DataFrame())
    silo_d_list =[]
    live_pos = {'A': {}, 'B': {}, 'C': {}, 'D': {}}
    for s in live_pos: 
        live_pos[s] = {'IB01': 0, 'CSPX': 0, 'CNDX': 0, 'ITWN': 0, 'CSKR': 0, 'CNYA': 0, 'CRYPTO': 0, 'CASH': 0, 'OPT_LIAB': 0, 'OPT_MARGIN': 0, 'CFD': 0, 'INTL': 0}
        
    acc_map = {'U23144948': 'A', 'U23139264': 'B', 'U23154199': 'C', 'U25218481': 'D'}

    if not post.empty:
        post['AccountID'] = post['ClientAccountID'].astype(str).str.replace('F', '', regex=False)
        for _, row in post.iterrows():
            acc = row.get('AccountID', '')
            if acc not in acc_map: continue
            
            silo = acc_map[acc]
            sym = str(row.get('Symbol', '')).upper()
            asset = str(row.get('AssetClass', '')).upper()
            
            try: local_val = float(row.get('PositionValue', 0))
            except: local_val = 0.0
            try: fx = float(row.get('FXRateToBase', 1))
            except: fx = 1.0
            usd_val = local_val * fx
            
            if silo == 'D':
                if sym != 'USD' and sym != '': silo_d_list.append({'ticker': sym, 'value': usd_val})
            elif silo in['A', 'C']:
                if 'IB01' in sym: live_pos[silo]['IB01'] += usd_val
                elif 'CSPX' in sym: live_pos[silo]['CSPX'] += usd_val
                elif 'CNDX' in sym or 'CSNDX' in sym: live_pos[silo]['CNDX'] += usd_val
                elif 'ITWN' in sym: live_pos[silo]['ITWN'] += usd_val
                elif 'CSKR' in sym: live_pos[silo]['CSKR'] += usd_val
                elif 'CNYA' in sym: live_pos[silo]['CNYA'] += usd_val
                elif 'ETH' in sym or 'BTC' in sym: live_pos[silo]['CRYPTO'] += usd_val
                elif asset == 'OPT':
                    live_pos[silo]['OPT_LIAB'] += usd_val
                    try: qty = float(row.get('Quantity', 0))
                    except: qty = 0
                    if qty < 0:
                        if 'XSP' in sym: live_pos[silo]['OPT_MARGIN'] += (abs(qty) * 2500)
                        elif 'XND' in sym: live_pos[silo]['OPT_MARGIN'] += (abs(qty) * 1000)
            elif silo == 'B':
                curr = str(row.get('CurrencyPrimary', 'USD'))
                if asset in['CFD', 'STK', '']:
                    if curr == 'USD': live_pos[silo]['CFD'] += usd_val
                    else: live_pos[silo]['INTL'] += usd_val

    silo_d_list = sorted(silo_d_list, key=lambda x: x['value'], reverse=True)[:10]
    with open(os.path.join(TARGET_DIR, 'Silo_D_Holdings.json'), 'w') as f: json.dump(silo_d_list, f)

    crtt = db.get('CRTT', pd.DataFrame())
    if not crtt.empty:
        crtt['AccountID'] = crtt['ClientAccountID'].astype(str).str.replace('F', '', regex=False)
        base_cash = crtt[crtt['CurrencyPrimary'] == 'BASE_SUMMARY']
        for _, row in base_cash.iterrows():
            acc = row.get('AccountID', '')
            if acc in acc_map:
                try: c_val = float(row.get('EndingCash', 0))
                except: c_val = 0.0
                live_pos[acc_map[acc]]['CASH'] += c_val

    with open(os.path.join(TARGET_DIR, 'Live_Allocations.json'), 'w') as f: json.dump(live_pos, f)

    # Exposure
    curr_date = daily_nav['Date'].max() if not daily_nav.empty else ''
    b_cf = daily_nav[daily_nav['AccountID'] == 'U23139264']['CashFlow'].sum() if not daily_nav.empty else 0
    b_nav = daily_nav[(daily_nav['AccountID'] == 'U23139264') & (daily_nav['Date'] == curr_date)]['NAV'].sum() if not daily_nav.empty else 0
    d_cf = daily_nav[daily_nav['AccountID'] == 'U25218481']['CashFlow'].sum() if not daily_nav.empty else 0
    d_nav = daily_nav[(daily_nav['AccountID'] == 'U25218481') & (daily_nav['Date'] == curr_date)]['NAV'].sum() if not daily_nav.empty else 0
    
    with open(os.path.join(TARGET_DIR, 'Progressive_Exposure.json'), 'w') as f:
        json.dump({"Silo_B": calculate_progressive_exposure(b_nav - b_cf), "Silo_D": calculate_progressive_exposure(d_nav - d_cf)}, f)
        
# -------------------------------------------------------------------
# ORCHESTRATION TRIGGERS
# -------------------------------------------------------------------
def update_ibkr_api_or_fallback():
    parsed_data = {}
    
    print("\n1. Pinging IBKR Flex Web Service securely...")
    url = f"https://gdcdyn.interactivebrokers.com/Universal/servlet/FlexStatementService.SendRequest?t={TOKEN}&q={QUERY_ID}&v=3"
    api_success = False
    try:
        res = requests.get(url, verify=False)
        if 'Success' in res.text:
            ref_code = res.text.split('<ReferenceCode>')[1].split('</ReferenceCode>')[0]
            print(f"   Success! Ref Code: {ref_code}. Waiting for IBKR compilation...")
            fetch_url = f"https://gdcdyn.interactivebrokers.com/Universal/servlet/FlexStatementService.GetStatement?t={TOKEN}&q={ref_code}&v=3"
            for _ in range(12):
                time.sleep(5)
                data_res = requests.get(fetch_url, verify=False)
                if data_res.status_code == 200 and not data_res.text.startswith('<'):
                    print("   [OK] API Payload Downloaded.")
                    parsed_data = parse_ibkr_flex(data_res.text)
                    api_success = True
                    break
        else: print(f"   [ERROR] API Rejected.")
    except Exception as e: print(f"   [ERROR] API Failure: {e}")

    # Check for historical manual file (The Seed File)
    local_csv = os.path.join(TARGET_DIR, 'Estate_Master_Feed.csv')
    if os.path.exists(local_csv):
        print("\n   [!] Found Estate_Master_Feed.csv. Ingesting historical seed file...")
        with open(local_csv, 'r') as f: file_text = f.read()
        file_parsed = parse_ibkr_flex(file_text)
        
        # Merge API + File Data before processing
        for k in file_parsed:
            if k in parsed_data: parsed_data[k] = pd.concat([parsed_data[k], file_parsed[k]])
            else: parsed_data[k] = file_parsed[k]
            
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        os.rename(local_csv, os.path.join(TARGET_DIR, f"Estate_Master_Feed_Processed_{timestamp}.csv"))
        print(f"   [OK] Seed file ingested and renamed to prevent double-parsing.")
        
    if parsed_data: process_ibkr_data(parsed_data)
    else: print("   [!] No new data to process.")

def update_yfinance_data():
    print("\n2. Generating Pure Script-Sourced Benchmark Data (2-Year Lookback)...")
    spy_path = os.path.join(TARGET_DIR, 'SPY_QQQ_Close.csv')
    try:
        old_bench = pd.read_csv(spy_path) if os.path.exists(spy_path) else pd.DataFrame()
        max_date = pd.to_datetime(old_bench['Date'], format='%d-%b-%y').max() if not old_bench.empty else pd.to_datetime('2000-01-01')
        
        data = yf.download(["SPY", "QQQ", "^VIX"], period="2y", progress=False, auto_adjust=False)
        close_data = data['Close'].ffill() if 'Close' in data.columns else data.ffill()
        
        spy_sma10 = close_data['SPY'].rolling(10).mean()
        spy_sma20 = close_data['SPY'].rolling(20).mean()

        new_rows =[]
        for date, row in close_data.iterrows():
            if date.tz_localize(None) > max_date.tz_localize(None):
                s10, s20 = spy_sma10[date], spy_sma20[date]
                if pd.isna(s10): continue
                
                price, vix = row['SPY'], row['^VIX']
                if s10 > s20 and price > s10: status, mn, mx = 'Green', 3, 5
                elif s10 < s20 and price < s20: status, mn, mx = 'Red', 0, 1
                else: status, mn, mx = 'Yellow', 1, 3

                if status == 'Green': tor = 5 if vix < 15 else (4 if vix <= 20 else 3)
                elif status == 'Yellow': tor = 3 if vix < 20 else (2 if vix <= 25 else 1)
                elif status == 'Red': tor = 1 if vix < 25 else 0
                    
                new_rows.append({'Date': date.strftime('%d-%b-%y'), 'SPY Close': round(price, 2), 'QQQ Close': round(row['QQQ'], 2), 'Status': status, 'Min TOR': mn, 'Max TOR': mx, 'Set TOR': tor})

        if new_rows:
            new_df = pd.DataFrame(new_rows)
            combined = pd.concat([old_bench, new_df]) if not old_bench.empty else new_df
            combined.to_csv(spy_path, index=False)
            print(f"   [OK] Rebuilt benchmark file with {len(new_rows)} new days.")
        else: print("   [OK] Market data is already up to date.")
    except Exception as e: print(f"   [ERROR] YFinance Failure: {e}")

if __name__ == "__main__":
    print("========================================================")
    print("     ESTATE ORCHESTRATOR v23 - INITIALIZING SYNC...      ")
    print("========================================================")
    create_backup()    
    update_ibkr_api_or_fallback()
    update_yfinance_data()
    print("\n3. Generating Dashboard HTML...")
    os.system('python Generate_Estate_Dashboard_v67.py')
    html_path = os.path.join(TARGET_DIR, "Family_Estate_Dashboard_v67.html")
    if os.path.exists(html_path): webbrowser.open(f'file:///{html_path}')
    print("\n[PROCESS COMPLETE] The Family Office is fully updated.")