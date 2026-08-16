r"""
=============================================================================
Script Name: Estate_Orchestrator_v7.py
File Path: C:\Users\donca\Desktop\Desktop HP Envy x360 al 22Abr24\Docs Manuel\IBKR_Options\Estate_Orchestrator_v7.py
Purpose: The Zero-Touch Automation Engine for the Family Office.
         V7 UPGRADES:
         - Fully Restored: The complete "Auto-Injector" logic that categorizes
           live positions into JSON for the v51 Dashboard.
         - Robust Headers: Safely handles both 'Account ID' (API) and 
           'ClientAccountID' (Manual CSV) column names.
         - Triggers Generate_Estate_Dashboard_v51.py.
Author: Chief Investment Officer AI Advisor
Date: April 2026
=============================================================================
"""

import os
import sys
import time
import json
import requests
import urllib3
import pandas as pd
import yfinance as yf
import xml.etree.ElementTree as ET
import webbrowser
import configparser

# Disable SSL warnings for older IBKR API endpoints
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# ==============================================================================
# SECURE CONFIGURATION LOADING
# ==============================================================================
TARGET_DIR = r"C:\Users\donca\Desktop\Desktop HP Envy x360 al 22Abr24\Docs Manuel\IBKR_Options"
config_path = os.path.join(TARGET_DIR, 'estate_config.ini')

if not os.path.exists(config_path):
    print(f"[FATAL ERROR] Cannot find {config_path}")
    print("Please create estate_config.ini with [IBKR] section containing TOKEN and QUERY_ID.")
    sys.exit()

config = configparser.ConfigParser()
config.read(config_path)
TOKEN = config['IBKR']['TOKEN']
QUERY_ID = config['IBKR']['QUERY_ID']
# ==============================================================================

def parse_ibkr_universal(csv_text):
    """ v7 CHANGE: Robust parser that handles both API and Manual CSV downloads """
    lines = csv_text.strip().split('\n')
    nav_data, pos_data, cash_data = [], [],[]
    mode = None
    headers_nav, headers_pos, headers_cash = [], [],[]
    
    for line in lines:
        if not line.strip(): continue
        parts =[p.strip(' "\r') for p in line.split(',')]
        
        # API Format
        if len(parts) > 2 and parts[1] == 'Data':
            actual_parts = parts[2:]
            section = parts[0]
            if section == 'Change in NAV': nav_data.append(actual_parts)
            elif section == 'Open Positions': pos_data.append(actual_parts)
            elif section == 'Cash Report': cash_data.append(actual_parts)
            
        # Manual CSV Format
        else:
            if 'FromDate' in parts and ('EndingValue' in parts or 'Ending Value' in parts): 
                mode = 'NAV'
                headers_nav = parts
                continue
            elif 'Symbol' in parts and ('PositionValue' in parts or 'Position Value' in parts): 
                mode = 'POS'
                headers_pos = parts
                continue
            elif 'EndingCash' in parts and 'CurrencyPrimary' in parts: 
                mode = 'CASH'
                headers_cash = parts
                continue
            
            if mode == 'NAV' and len(parts) >= 6 and parts[0].isdigit():
                nav_data.append(parts)
            elif mode == 'POS' and len(parts) >= 8 and parts[0] != 'CurrencyPrimary':
                pos_data.append(parts)
            elif mode == 'CASH' and len(parts) >= 5 and parts[0] != 'CurrencyPrimary':
                cash_data.append(parts)
                
    # v7 CHANGE: Safely assign headers based on format type
    nav_df = pd.DataFrame(nav_data, columns=headers_nav if headers_nav else['FromDate', 'ToDate', 'StartingValue', 'DepositsWithdrawals', 'EndingValue', 'Account ID']) if nav_data else None
    pos_df = pd.DataFrame(pos_data, columns=headers_pos if headers_pos else['CurrencyPrimary', 'Quantity', 'FXRateToBase', 'MarkPrice', 'AssetClass', 'Symbol', 'PositionValue', 'Account ID']) if pos_data else None
    cash_df = pd.DataFrame(cash_data, columns=headers_cash if headers_cash else['CurrencyPrimary', 'EndingCash', 'EndingCashSecurities', 'EndingCashCommodities', 'Account ID']) if cash_data else None
    
    return {'Change in NAV': nav_df, 'Open Positions': pos_df, 'Cash Report': cash_df}

def process_ibkr_data(sections):
    # ---------------------------------------------------------
    # 1. Update Daily NAV (IBKR_Daily_Data.csv)
    # ---------------------------------------------------------
    nav_df = sections.get('Change in NAV')
    if nav_df is not None:
        # Standardize column names between API and Manual CSV
        date_col = 'ToDate' if 'ToDate' in nav_df.columns else ('To Date' if 'To Date' in nav_df.columns else nav_df.columns[1])
        acc_col = 'ClientAccountID' if 'ClientAccountID' in nav_df.columns else 'Account ID'
        end_val_col = 'EndingValue' if 'EndingValue' in nav_df.columns else 'Ending Value'
        flow_col = 'DepositsWithdrawals' if 'DepositsWithdrawals' in nav_df.columns else 'Deposits/Withdrawals'

        nav_df['Date'] = pd.to_datetime(nav_df[date_col]).dt.strftime('%Y%m%d')
        nav_df['AccountID'] = nav_df[acc_col].str.replace('F', '', regex=False)
        nav_df['NAV'] = nav_df[end_val_col].astype(float)
        nav_df['CashFlow'] = nav_df[flow_col].astype(float)
        
        # Weld 'F' (UK CFD) accounts to main US accounts
        new_nav = nav_df.groupby(['AccountID', 'Date'])[['NAV', 'CashFlow']].sum().reset_index()
        
        csv_path = os.path.join(TARGET_DIR, 'IBKR_Daily_Data.csv')
        if os.path.exists(csv_path):
            old_nav = pd.read_csv(csv_path)
            old_nav['Date'] = old_nav['Date'].astype(str)
            combined = pd.concat([old_nav, new_nav]).drop_duplicates(subset=['AccountID', 'Date'], keep='last')
        else:
            combined = new_nav
            
        combined.to_csv(csv_path, index=False)
        print("[OK] IBKR_Daily_Data.csv Appended, Welded & Deduplicated.")
    else:
        print("   [INFO] No NAV changes found.")

    # ---------------------------------------------------------
    # 2. Extract Live Allocations for Panel 2 Auto-Fill (v7 RESTORED)
    # ---------------------------------------------------------
    live_pos = {
        'A': {'IB01': 0, 'CSPX': 0, 'CNDX': 0, 'ITWN': 0, 'CSKR': 0, 'CNYA': 0, 'CRYPTO': 0, 'CASH': 0, 'OPT_LIAB': 0},
        'B': {'CASH': 0, 'CFD': 0, 'INTL': 0},
        'C': {'IB01': 0, 'CSPX': 0, 'CNDX': 0, 'ITWN': 0, 'CSKR': 0, 'CNYA': 0, 'CRYPTO': 0, 'CASH': 0, 'OPT_LIAB': 0},
        'D': {'CASH': 0}
    }
    
    # Internal mapping for U-Numbers
    acc_map = {'U23144948': 'A', 'U23139264': 'B', 'U23154199': 'C', 'U25218481': 'D'}

    pos_df = sections.get('Open Positions')
    silo_d_list =[]
    
    if pos_df is not None:
        pos_acc_col = 'ClientAccountID' if 'ClientAccountID' in pos_df.columns else 'Account ID'
        pos_df[pos_acc_col] = pos_df[pos_acc_col].str.replace('F', '', regex=False)
        
        for _, row in pos_df.iterrows():
            raw_acc = row.get(pos_acc_col, '')
            if raw_acc not in acc_map: continue
            
            silo = acc_map[raw_acc]
            sym = row.get('Symbol', '').upper()
            asset = row.get('AssetClass', '')
            curr = row.get('CurrencyPrimary', row.get('Currency', 'USD'))
            
            val_col = 'PositionValue' if 'PositionValue' in row else 'Position Value'
            fx_col = 'FXRateToBase' if 'FXRateToBase' in row else 'FX Rate To Base'
            
            val = float(row.get(val_col, 0))
            fx_str = row.get(fx_col, '')
            fx = float(fx_str) if fx_str != '' else 1.0
            usd_val = val * fx
            
            # Silo D specific 13F Extraction
            if silo == 'D':
                if sym != 'USD' and sym != '':
                    silo_d_list.append({'ticker': sym, 'value': round(usd_val, 2)})
            
            # Silos A & C Allocation Routing
            elif silo in ['A', 'C']:
                if 'IB01' in sym: live_pos[silo]['IB01'] += usd_val
                elif 'CSPX' in sym: live_pos[silo]['CSPX'] += usd_val
                elif 'CNDX' in sym or 'CSNDX' in sym: live_pos[silo]['CNDX'] += usd_val
                elif 'ITWN' in sym: live_pos[silo]['ITWN'] += usd_val
                elif 'CSKR' in sym: live_pos[silo]['CSKR'] += usd_val
                elif 'CNYA' in sym: live_pos[silo]['CNYA'] += usd_val
                elif 'ETH' in sym or 'BTC' in sym: live_pos[silo]['CRYPTO'] += usd_val
                elif asset == 'OPT': live_pos[silo]['OPT_LIAB'] += usd_val
                
            # Silo B Allocation Routing
            elif silo == 'B':
                if asset == 'CFD': 
                    live_pos[silo]['CFD'] += usd_val
                elif asset == 'STK':
                    if curr == 'USD': live_pos[silo]['CFD'] += usd_val
                    else: live_pos[silo]['INTL'] += usd_val

    # Silo D Export
    silo_d_list = sorted(silo_d_list, key=lambda x: x['value'], reverse=True)[:10]
    json_path_d = os.path.join(TARGET_DIR, 'Silo_D_Holdings.json')
    with open(json_path_d, 'w') as f:
        json.dump(silo_d_list, f)
    print("   [OK] Silo D Holdings Exported.")

    # ---------------------------------------------------------
    # 3. Extract Cash Balances
    # ---------------------------------------------------------
    cash_df = sections.get('Cash Report')
    if cash_df is not None:
        cash_acc_col = 'ClientAccountID' if 'ClientAccountID' in cash_df.columns else 'Account ID'
        cash_df[cash_acc_col] = cash_df[cash_acc_col].str.replace('F', '', regex=False)
        
        for _, row in cash_df.iterrows():
            raw_acc = row.get(cash_acc_col, '')
            curr = row.get('CurrencyPrimary', row.get('Currency', ''))
            
            if raw_acc in acc_map and curr == 'BASE_SUMMARY':
                silo = acc_map[raw_acc]
                end_cash_col = 'EndingCash' if 'EndingCash' in row else 'Ending Cash'
                live_pos[silo]['CASH'] += float(row.get(end_cash_col, 0))

    # Round all values for clean HTML injection
    for silo in live_pos:
        for k, v in live_pos[silo].items():
            if isinstance(v, list): continue
            live_pos[silo][k] = round(v, 2)

    json_path_alloc = os.path.join(TARGET_DIR, 'Live_Allocations.json')
    with open(json_path_alloc, 'w') as f:
        json.dump(live_pos, f)
    print("   [OK] Live Portfolio Allocations Exported.")

def update_ibkr_api_or_fallback():
    print("\n1. Pinging IBKR Flex Web Service securely...")
    url = f"https://gdcdyn.interactivebrokers.com/Universal/servlet/FlexStatementService.SendRequest?t={TOKEN}&q={QUERY_ID}&v=3"
    
    api_success = False
    try:
        res = requests.get(url, verify=False)
        root = ET.fromstring(res.text)
        status = root.find('Status').text
        
        if status == 'Success':
            ref_code = root.find('ReferenceCode').text
            print(f"   Success! Ref Code: {ref_code}. Waiting for IBKR to compile data...")
            fetch_url = f"https://gdcdyn.interactivebrokers.com/Universal/servlet/FlexStatementService.GetStatement?t={TOKEN}&q={ref_code}&v=3"
            csv_data = None
            
            for _ in range(12):
                time.sleep(5)
                data_res = requests.get(fetch_url, verify=False)
                if data_res.status_code == 200 and not data_res.text.startswith('<'):
                    csv_data = data_res.text
                    break
            
            if csv_data:
                print("   Data Downloaded via API. Processing ledgers...")
                sections = parse_ibkr_universal(csv_data)
                process_ibkr_data(sections)
                api_success = True
            else:
                print("   [ERROR] Timeout waiting for IBKR to compile.")
        else:
            err = root.find('ErrorCode').text
            msg = root.find('ErrorMessage').text
            print(f"   [ERROR] IBKR API Rejected: {err} - {msg}")
            
    except Exception as e:
        print(f"   [ERROR] API Failure: {e}")

    # v7 CHANGE: Local Fallback Mechanism
    if not api_success:
        print("\n   [!] Attempting Local File Fallback...")
        local_csv = os.path.join(TARGET_DIR, 'Estate_Master_Feed.csv')
        if os.path.exists(local_csv):
            print("[OK] Found manual Estate_Master_Feed.csv. Processing local file...")
            with open(local_csv, 'r') as f:
                local_data = f.read()
            sections = parse_ibkr_universal(local_data)
            process_ibkr_data(sections)
        else:
            print("   [!] No local Estate_Master_Feed.csv found. Skipping IBKR update.")

def update_yfinance_data():
    print("\n2. Generating Pure Script-Sourced Benchmark Data (2-Year Lookback)...")
    spy_csv_path = os.path.join(TARGET_DIR, 'SPY_QQQ_Close.csv')
    
    try:
        if os.path.exists(spy_csv_path):
            old_bench = pd.read_csv(spy_csv_path)
            old_bench['Date_obj'] = pd.to_datetime(old_bench['Date'], format='%d-%b-%y')
            max_date = old_bench['Date_obj'].max()
        else:
            old_bench = pd.DataFrame()
            max_date = pd.to_datetime('2000-01-01')

        # v7 CHANGE: Download SPY, QQQ, VIX safely
        data = yf.download(["SPY", "QQQ", "^VIX"], period="2y", progress=False, auto_adjust=False)
        
        print("   -> Exporting SPY_Technical_Proof.csv for CIO Audit...")
        spy_open = data['Open']['SPY']
        spy_close = data['Close']['SPY']
        
        proof_df = pd.DataFrame({'Open': spy_open, 'Close': spy_close})
        proof_df['10SMA'] = proof_df['Close'].rolling(10).mean().round(2)
        proof_df['20SMA'] = proof_df['Close'].rolling(20).mean().round(2)
        proof_df['50SMA'] = proof_df['Close'].rolling(50).mean().round(2)
        proof_df['200SMA'] = proof_df['Close'].rolling(200).mean().round(2)
        
        proof_df_clean = proof_df.dropna().reset_index()
        proof_df_clean['Date'] = proof_df_clean['Date'].dt.strftime('%Y-%m-%d')
        
        proof_path = os.path.join(TARGET_DIR, 'SPY_Technical_Proof.csv')
        proof_df_clean.to_csv(proof_path, index=False)
        print(f"   [OK] Generated SPY_Technical_Proof.csv with {len(proof_df_clean)} days of data.")

        if 'Close' in data.columns:
            close_data = data['Close'].ffill() 
        else:
            close_data = data.ffill()

        spy_sma10 = close_data['SPY'].rolling(10).mean()
        spy_sma20 = close_data['SPY'].rolling(20).mean()

        new_rows =[]
        for date, row in close_data.iterrows():
            if date.tz_localize(None) > max_date.tz_localize(None):
                s10 = spy_sma10[date]
                s20 = spy_sma20[date]
                spy_price = row['SPY']
                qqq_price = row['QQQ']
                vix_price = row['^VIX']
                
                if pd.isna(s10) or pd.isna(s20): continue
                
                if s10 > s20:
                    status = 'Green'
                    min_tor, max_tor = 3, 5
                    if vix_price < 15: tor = 5
                    elif vix_price <= 20: tor = 4
                    else: tor = 3
                elif s10 < s20:
                    status = 'Red'
                    min_tor, max_tor = 0, 1
                    if vix_price > 25: tor = 0
                    else: tor = 1
                else:
                    status = 'Yellow'
                    min_tor, max_tor = 1, 3
                    tor = 2
                    
                d_str = date.strftime('%d-%b-%y')
                
                new_rows.append({
                    'Date': d_str, 
                    'SPY Close': round(spy_price, 2), 
                    'QQQ Close': round(qqq_price, 2),
                    'Status': status, 
                    'Min TOR': min_tor, 
                    'Max TOR': max_tor, 
                    'Set TOR': tor
                })

        if new_rows:
            new_df = pd.DataFrame(new_rows)
            if not old_bench.empty:
                old_bench = pd.concat([old_bench.drop(columns=['Date_obj']), new_df])
            else:
                old_bench = new_df
            old_bench.to_csv(spy_csv_path, index=False)
            print(f"   [OK] Rebuilt benchmark file with {len(new_rows)} new days of pure mathematical TOR.")
        else:
            print("   [OK] Market data is already up to date.")
            
    except Exception as e:
        print(f"   [ERROR] YFinance Failure: {e}")

if __name__ == "__main__":
    print("========================================================")
    print("     ESTATE ORCHESTRATOR v7 - INITIALIZING SYNC...      ")
    print("========================================================")
    
    update_ibkr_api_or_fallback()
    update_yfinance_data()
    
    print("\n3. Generating Dashboard HTML...")
    # Calls v51 script seamlessly
    os.system('python Generate_Estate_Dashboard_v51.py')
    
    html_path = os.path.join(TARGET_DIR, "Family_Estate_Dashboard_v51.html")
    if os.path.exists(html_path):
        webbrowser.open(f'file:///{html_path}')
        
    print("\n[PROCESS COMPLETE] The Family Office is fully updated.")