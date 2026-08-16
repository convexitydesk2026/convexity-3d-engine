r"""
=============================================================================
Script Name: Estate_Orchestrator_v6.py
File Path: C:\Users\donca\Desktop\Desktop HP Envy x360 al 22Abr24\Docs Manuel\IBKR_Options\Estate_Orchestrator_v6.py
Purpose: The Zero-Touch Automation Engine for the Family Office.
         V6 UPGRADES:
         - Added Local Fallback Mode: If the API fails (1001), it automatically 
           reads a manual 'Estate_Master_Feed.csv' file if present.
         - Built the "Account Welder": Automatically strips the "F" suffix from 
           UK CFD accounts and sums their NAV/Cash with the main US account.
         - Robust dual-parser handles both API XML and Manual CSV formats.
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
    """ v6 CHANGE: Robust parser that handles both API and Manual CSV downloads """
    lines = csv_text.strip().split('\n')
    nav_data =[]
    pos_data =[]
    
    mode = None
    for line in lines:
        if not line.strip(): continue
        parts = [p.strip(' "\r') for p in line.split(',')]
        
        # Detect API format rows
        if len(parts) > 2 and parts[1] == 'Data':
            actual_parts = parts[2:]
            section = parts[0]
            if section == 'Change in NAV':
                nav_data.append(actual_parts)
            elif section == 'Open Positions':
                pos_data.append(actual_parts)
        
        # Detect Manual format rows
        else:
            if 'FromDate' in parts and 'EndingValue' in parts:
                mode = 'NAV'
                continue
            elif 'Symbol' in parts and 'PositionValue' in parts:
                mode = 'POS'
                continue
            elif 'EndingCash' in parts:
                mode = 'CASH'
                continue
            
            if mode == 'NAV' and len(parts) >= 6 and parts[0].isdigit():
                nav_data.append([parts[0], parts[1], parts[2], parts[3], parts[4], parts[5]])
            elif mode == 'POS' and len(parts) >= 8 and parts[0] != 'CurrencyPrimary':
                pos_data.append(parts)
                
    nav_df = pd.DataFrame(nav_data, columns=['FromDate', 'ToDate', 'StartingValue', 'DepositsWithdrawals', 'EndingValue', 'Account ID']) if nav_data else None
    pos_df = pd.DataFrame(pos_data, columns=['CurrencyPrimary', 'Quantity', 'FXRateToBase', 'MarkPrice', 'AssetClass', 'Symbol', 'PositionValue', 'Account ID']) if pos_data else None
    
    return {'Change in NAV': nav_df, 'Open Positions': pos_df}

def process_ibkr_data(sections):
    """ v6 CHANGE: Extracted processing logic to be used by both API and Local Fallback """
    nav_df = sections.get('Change in NAV')
    if nav_df is not None:
        nav_df['Date'] = pd.to_datetime(nav_df['ToDate']).dt.strftime('%Y%m%d')
        
        # v6 CHANGE: The "Account Welder" - Strips the 'F' off CFD accounts
        nav_df['AccountID'] = nav_df['Account ID'].str.replace('F', '', regex=False)
        nav_df['NAV'] = nav_df['EndingValue'].astype(float)
        nav_df['CashFlow'] = nav_df['DepositsWithdrawals'].astype(float)
        
        # v6 CHANGE: Sums the NAV and CashFlow of the US and UK(F) accounts together!
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

    pos_df = sections.get('Open Positions')
    silo_d_list =[]
    if pos_df is not None:
        # v6 CHANGE: Strip 'F' from positions to safely capture Silo D UK CFDs
        pos_df['Account ID'] = pos_df['Account ID'].str.replace('F', '', regex=False)
        d_pos = pos_df[pos_df['Account ID'] == 'U25218481']
        
        for _, row in d_pos.iterrows():
            sym = row.get('Symbol', '')
            if sym == 'USD' or sym == '': continue
            val = float(row.get('PositionValue', 0))
            fx = float(row.get('FXRateToBase', 1)) if row.get('FXRateToBase', '') != '' else 1.0
            silo_d_list.append({'ticker': sym, 'value': round(val * fx, 2)})
            
    silo_d_list = sorted(silo_d_list, key=lambda x: x['value'], reverse=True)[:10]
    json_path = os.path.join(TARGET_DIR, 'Silo_D_Holdings.json')
    with open(json_path, 'w') as f:
        json.dump(silo_d_list, f)
    print("[OK] Silo D Holdings Exported.")

def update_ibkr_data():
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
        print(f"[ERROR] API Failure: {e}")

    # v6 CHANGE: Local Fallback Mechanism
    if not api_success:
        print("\n   [!] Attempting Local File Fallback...")
        local_csv = os.path.join(TARGET_DIR, 'Estate_Master_Feed.csv')
        if os.path.exists(local_csv):
            print("   [OK] Found manual Estate_Master_Feed.csv. Processing local file...")
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
    print("     ESTATE ORCHESTRATOR v6 - INITIALIZING SYNC...      ")
    print("========================================================")
    
    update_ibkr_data()
    update_yfinance_data()
    
    print("\n3. Generating Dashboard HTML...")
    os.system('python Generate_Estate_Dashboard_v50.py')
    
    html_path = os.path.join(TARGET_DIR, "Family_Estate_Dashboard_v50.html")
    if os.path.exists(html_path):
        webbrowser.open(f'file:///{html_path}')
        
    print("\n[PROCESS COMPLETE] The Family Office is fully updated.")