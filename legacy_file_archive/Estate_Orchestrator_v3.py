r"""
=============================================================================
Script Name: Estate_Orchestrator_v3.py
File Path: C:\Users\donca\Desktop\Desktop HP Envy x360 al 22Abr24\Docs Manuel\IBKR_Options\Estate_Orchestrator_v3.py
Purpose: The Zero-Touch Automation Engine for the Family Office.
         V3 UPGRADES:
         - Fixed 'q_close' variable typo in the YFinance module.
         - Silenced 'auto_adjust' FutureWarnings from the yfinance library.
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

def parse_ibkr_flex(csv_data):
    """Custom parser to handle IBKR's multi-section CSV format."""
    lines = csv_data.split('\n')
    sections = {}
    curr_section = None
    headers = []
    data =[]
    for line in lines:
        if not line.strip(): continue
        parts =[p.strip(' "') for p in line.split(',')]
        if len(parts) > 2 and parts[1] == 'Header':
            if curr_section and data:
                sections[curr_section] = pd.DataFrame(data, columns=headers)
            curr_section = parts[0]
            headers = parts[2:]
            data =[]
        elif len(parts) > 2 and parts[1] == 'Data':
            data.append(parts[2:])
    if curr_section and data:
        sections[curr_section] = pd.DataFrame(data, columns=headers)
    return sections

def update_ibkr_data():
    print("\n1. Pinging IBKR Flex Web Service securely...")
    url = f"https://gdcdyn.interactivebrokers.com/Universal/servlet/FlexStatementService.SendRequest?t={TOKEN}&q={QUERY_ID}&v=3"
    
    try:
        res = requests.get(url, verify=False)
        root = ET.fromstring(res.text)
        status = root.find('Status').text
        
        if status == 'Success':
            ref_code = root.find('ReferenceCode').text
            print(f"   Success! Ref Code: {ref_code}. Waiting for IBKR to compile data...")
            
            fetch_url = f"https://gdcdyn.interactivebrokers.com/Universal/servlet/FlexStatementService.GetStatement?t={TOKEN}&q={ref_code}&v=3"
            csv_data = None
            
            # Poll IBKR every 5 seconds
            for _ in range(12):
                time.sleep(5)
                data_res = requests.get(fetch_url, verify=False)
                if data_res.status_code == 200 and not data_res.text.startswith('<'):
                    csv_data = data_res.text
                    break
            
            if csv_data:
                print("   Data Downloaded. Processing ledgers...")
                sections = parse_ibkr_flex(csv_data)
                
                # --- APPEND DAILY NAV CSV ---
                nav_df = sections.get('Change in NAV')
                if nav_df is not None:
                    date_col = 'To Date' if 'To Date' in nav_df.columns else ('Date' if 'Date' in nav_df.columns else nav_df.columns[1])
                    nav_df['Date'] = pd.to_datetime(nav_df[date_col]).dt.strftime('%Y%m%d')
                    nav_df['AccountID'] = nav_df['Account ID']
                    nav_df['NAV'] = nav_df['Ending Value'].astype(float)
                    nav_df['CashFlow'] = nav_df['Deposits/Withdrawals'].astype(float)
                    
                    new_nav = nav_df[['AccountID', 'Date', 'NAV', 'CashFlow']]
                    csv_path = os.path.join(TARGET_DIR, 'IBKR_Daily_Data.csv')
                    
                    if os.path.exists(csv_path):
                        old_nav = pd.read_csv(csv_path)
                        old_nav['Date'] = old_nav['Date'].astype(str)
                        combined = pd.concat([old_nav, new_nav]).drop_duplicates(subset=['AccountID', 'Date'], keep='last')
                    else:
                        combined = new_nav
                        
                    combined.to_csv(csv_path, index=False)
                    print("   [OK] IBKR_Daily_Data.csv Appended & Deduplicated.")
                else:
                    print("   [INFO] No NAV changes found for the requested period.")

                # --- EXTRACT SILO D (SMART MONEY) POSITIONS ---
                pos_df = sections.get('Open Positions')
                silo_d_list =[]
                if pos_df is not None:
                    d_pos = pos_df[pos_df['Account ID'] == 'U25218481']
                    for _, row in d_pos.iterrows():
                        sym = row.get('Symbol', '')
                        if sym == 'USD' or sym == '': continue
                        val = float(row.get('Position Value', 0))
                        fx = float(row.get('FX Rate To Base', 1)) if row.get('FX Rate To Base', '') != '' else 1.0
                        silo_d_list.append({'ticker': sym, 'value': round(val * fx, 2)})
                        
                silo_d_list = sorted(silo_d_list, key=lambda x: x['value'], reverse=True)[:10]
                json_path = os.path.join(TARGET_DIR, 'Silo_D_Holdings.json')
                with open(json_path, 'w') as f:
                    json.dump(silo_d_list, f)
                print("   [OK] Silo D Holdings Exported.")
            else:
                print("   [ERROR] Timeout waiting for IBKR to compile.")
        else:
            err = root.find('ErrorCode').text
            msg = root.find('ErrorMessage').text
            print(f"   [ERROR] IBKR API Rejected: {err} - {msg}")
            
    except Exception as e:
        print(f"   [ERROR] API Failure: {e}")

def update_yfinance_data():
    print("\n2. Generating Pure Script-Sourced Benchmark Data (2-Year Lookback)...")
    spy_csv_path = os.path.join(TARGET_DIR, 'SPY_QQQ_Close.csv')
    
    try:
        if os.path.exists(spy_csv_path):
            old_bench = pd.read_csv(spy_csv_path)
            old_bench['Date_obj'] = pd.to_datetime(old_bench['Date'])
            max_date = old_bench['Date_obj'].max()
        else:
            old_bench = pd.DataFrame()
            max_date = pd.to_datetime('2000-01-01')

        # v3 CHANGE: Explicitly set auto_adjust=False to silence FutureWarnings
        data = yf.download("SPY QQQ ^VIX", period="2y", progress=False, auto_adjust=False)
        
        # yfinance multi-ticker returns a MultiIndex. We isolate 'Close'
        if 'Close' in data.columns:
            close_data = data['Close'].dropna()
        else:
            close_data = data.dropna()

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
                
                # --- THE CIO TOR / VIX MATRIX ---
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
                
                # v3 CHANGE: Corrected the variable name to qqq_price 
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
        print(f"[ERROR] YFinance Failure: {e}")

if __name__ == "__main__":
    print("========================================================")
    print("     ESTATE ORCHESTRATOR v3 - INITIALIZING SYNC...      ")
    print("========================================================")
    
    update_ibkr_data()
    update_yfinance_data()
    
    print("\n3. Generating Dashboard HTML...")
    # Calls the dashboard script seamlessly
    os.system('python Generate_Estate_Dashboard_v50.py')
    
    # Opens the dashboard automatically
    html_path = os.path.join(TARGET_DIR, "Family_Estate_Dashboard_v50.html")
    if os.path.exists(html_path):
        webbrowser.open(f'file:///{html_path}')
        
    print("\n[PROCESS COMPLETE] The Family Office is fully updated.")