r"""
=============================================================================
Script Name: Estate_Orchestrator_v13.py
File Path: C:\Users\donca\Desktop\Desktop HP Envy x360 al 22Abr24\Docs Manuel\IBKR_Options\Estate_Orchestrator_v13.py
Purpose: The Zero-Touch Automation Engine for the Family Office.
         v13 UPGRADES:
         - Added Manual CSV Fallback Parser for "TotalFifoPnl".
Author: Chief Investment Officer AI Advisor
Date: May 2026
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

def get_col(df, possible_names):
    """ Resilient column finder to prevent KeyErrors """
    lower_cols = {c.strip().lower(): c for c in df.columns}
    for n in possible_names:
        if n.lower() in lower_cols:
            return lower_cols[n.lower()]
    return df.columns[0]

def parse_ibkr_universal(csv_text):
    lines = csv_text.strip().split('\n')
    nav_list, pos_list, cash_list, pnl_list = [], [],[], []
    current_mode, current_headers = None,[]
    
    for line in lines:
        if not line.strip(): continue
        parts =[p.strip(' "\r') for p in line.split(',')]
        
        # v62 Patch: Fuzzy catch for PnL section name
        is_pnl = parts[0].startswith('Realized and Unrealized Performance Summary')
        
        if parts[0] in['Change in NAV', 'Open Positions', 'Cash Report'] or is_pnl:
            if len(parts) > 1 and parts[1] == 'Header': current_headers = parts[2:]
            elif len(parts) > 1 and parts[1] == 'Data':
                row_dict = dict(zip(current_headers, parts[2:]))
                if parts[0] == 'Change in NAV': nav_list.append(row_dict)
                elif parts[0] == 'Open Positions': pos_list.append(row_dict)
                elif parts[0] == 'Cash Report': cash_list.append(row_dict)
                elif is_pnl: pnl_list.append(row_dict)
            continue

        if 'FromDate' in parts and ('EndingValue' in parts or 'Ending Value' in parts):
            current_mode = 'NAV'; current_headers = parts; continue
        elif 'Symbol' in parts and ('PositionValue' in parts or 'Position Value' in parts):
            current_mode = 'POS'; current_headers = parts; continue
        elif 'EndingCash' in parts and ('CurrencyPrimary' in parts or 'Currency' in parts):
            current_mode = 'CASH'; current_headers = parts; continue
        elif 'Symbol' in parts and ('TotalFifoPnl' in parts or 'TotalMTM' in parts):
            current_mode = 'PNL'; current_headers = parts; continue
            
        if current_mode == 'NAV' and len(parts) > 2 and parts[0].isdigit():
            nav_list.append(dict(zip(current_headers, parts)))
        elif current_mode == 'POS' and len(parts) > 2 and parts[0] != 'CurrencyPrimary' and parts[0] != 'Currency':
            pos_list.append(dict(zip(current_headers, parts)))
        elif current_mode == 'CASH' and len(parts) >= 2 and parts[0] != 'CurrencyPrimary' and parts[0] != 'Currency':
            cash_list.append(dict(zip(current_headers, parts)))
        elif current_mode == 'PNL' and len(parts) >= 2 and parts[0] != 'ClientAccountID':
            pnl_list.append(dict(zip(current_headers, parts)))

    return {
        'Change in NAV': pd.DataFrame(nav_list) if nav_list else None, 
        'Open Positions': pd.DataFrame(pos_list) if pos_list else None, 
        'Cash Report': pd.DataFrame(cash_list) if cash_list else None,
        'PnL_Data': pd.DataFrame(pnl_list) if pnl_list else None
    }

def process_ibkr_data(sections):
    # ---------------------------------------------------------
    # 1. Update Daily NAV (.agg instead of .sum)
    # ---------------------------------------------------------
    nav_df = sections.get('Change in NAV')
    if nav_df is not None:
        acc_col = get_col(nav_df,['AccountID', 'Account ID', 'ClientAccountID'])
        date_col = get_col(nav_df,['ToDate', 'To Date', 'Date', 'ReportDate'])
        nav_col = get_col(nav_df, ['EndingValue', 'Ending Value', 'NAV'])
        flow_col = get_col(nav_df, ['DepositsWithdrawals', 'Deposits/Withdrawals', 'CashFlow'])

        nav_df['Date'] = pd.to_datetime(nav_df[date_col]).dt.strftime('%Y%m%d')
        nav_df['AccountID'] = nav_df[acc_col].astype(str).str.replace('F', '', regex=False)
        nav_df['NAV'] = pd.to_numeric(nav_df[nav_col], errors='coerce').fillna(0)
        nav_df['CashFlow'] = pd.to_numeric(nav_df[flow_col], errors='coerce').fillna(0)
        
        # Used .agg('last', 'sum') to prevent duplicate line explosions
        new_nav = nav_df.groupby(['AccountID', 'Date']).agg({'NAV': 'max', 'CashFlow': 'sum'}).reset_index()
        
        csv_path = os.path.join(TARGET_DIR, 'IBKR_Daily_Data.csv')
        if os.path.exists(csv_path):
            old_nav = pd.read_csv(csv_path)
            old_nav['Date'] = old_nav['Date'].astype(str)
            combined = pd.concat([old_nav, new_nav]).drop_duplicates(subset=['AccountID', 'Date'], keep='last')
        else:
            combined = new_nav
            
        combined.to_csv(csv_path, index=False)
        print("   [OK] IBKR_Daily_Data.csv Appended & Deduplicated.")

    # ---------------------------------------------------------
    # 2. Extract Live Allocations & Opt Margin 
    # ---------------------------------------------------------
    live_pos = {
        'A': {'IB01': 0, 'CSPX': 0, 'CNDX': 0, 'ITWN': 0, 'CSKR': 0, 'CNYA': 0, 'CRYPTO': 0, 'CASH': 0, 'OPT_LIAB': 0, 'OPT_MARGIN': 0},
        'B': {'CASH': 0, 'CFD': 0, 'INTL': 0},
        'C': {'IB01': 0, 'CSPX': 0, 'CNDX': 0, 'ITWN': 0, 'CSKR': 0, 'CNYA': 0, 'CRYPTO': 0, 'CASH': 0, 'OPT_LIAB': 0, 'OPT_MARGIN': 0},
        'D': {'CASH': 0}
    }
    acc_map = {'U23144948': 'A', 'U23139264': 'B', 'U23154199': 'C', 'U25218481': 'D'}

    pos_df = sections.get('Open Positions')
    silo_d_list =[]
    
    if pos_df is not None:
        pos_acc_col = get_col(pos_df, ['ClientAccountID', 'Account ID', 'AccountId'])
        pos_df[pos_acc_col] = pos_df[pos_acc_col].astype(str).str.replace('F', '', regex=False)
        
        for _, row in pos_df.iterrows():
            raw_acc = str(row.get(pos_acc_col, '')).strip()
            if raw_acc not in acc_map: continue
            
            silo = acc_map[raw_acc]
            sym = str(row.get(get_col(pos_df, ['Symbol']), '')).upper()
            asset = str(row.get(get_col(pos_df,['AssetClass', 'Asset Class']), ''))
            curr = str(row.get(get_col(pos_df, ['CurrencyPrimary', 'Currency']), 'USD'))
            
            val_col = get_col(pos_df, ['PositionValue', 'Position Value', 'Value'])
            fx_col = get_col(pos_df, ['FXRateToBase', 'FX Rate To Base'])
            qty_col = get_col(pos_df, ['Quantity', 'Position'])
            
            try: val = float(row.get(val_col, 0))
            except: val = 0.0
            
            try: fx = float(row.get(fx_col, 1)) if row.get(fx_col, '') != '' else 1.0
            except: fx = 1.0
            
            try: qty = float(row.get(qty_col, 0))
            except: qty = 0.0
            
            usd_val = val * fx
            
            if silo == 'D':
                if sym != 'USD' and sym != '':
                    silo_d_list.append({'ticker': sym, 'value': round(usd_val, 2)})
            elif silo in ['A', 'C']:
                if 'IB01' in sym: live_pos[silo]['IB01'] += usd_val
                elif 'CSPX' in sym: live_pos[silo]['CSPX'] += usd_val
                elif 'CNDX' in sym or 'CSNDX' in sym: live_pos[silo]['CNDX'] += usd_val
                elif 'ITWN' in sym: live_pos[silo]['ITWN'] += usd_val
                elif 'CSKR' in sym: live_pos[silo]['CSKR'] += usd_val
                elif 'CNYA' in sym: live_pos[silo]['CNYA'] += usd_val
                elif 'ETH' in sym or 'BTC' in sym: live_pos[silo]['CRYPTO'] += usd_val
                elif asset == 'OPT': 
                    live_pos[silo]['OPT_LIAB'] += usd_val
                    # Automate Opt Margin based on negative quantity
                    if qty < 0:
                        if 'XSP' in sym: live_pos[silo]['OPT_MARGIN'] += (abs(qty) * 2500)
                        elif 'XND' in sym: live_pos[silo]['OPT_MARGIN'] += (abs(qty) * 1000)
                        
            elif silo == 'B':
                if asset == 'CFD': live_pos[silo]['CFD'] += usd_val
                elif asset == 'STK':
                    if curr == 'USD': live_pos[silo]['CFD'] += usd_val
                    else: live_pos[silo]['INTL'] += usd_val

    silo_d_list = sorted(silo_d_list, key=lambda x: x['value'], reverse=True)[:10]
    with open(os.path.join(TARGET_DIR, 'Silo_D_Holdings.json'), 'w') as f:
        json.dump(silo_d_list, f)
    print("   [OK] Silo D Holdings Exported.")

    # ---------------------------------------------------------
    # 3. Extract Cash Balances
    # ---------------------------------------------------------
    cash_df = sections.get('Cash Report')
    if cash_df is not None:
        cash_acc_col = get_col(cash_df, ['ClientAccountID', 'Account ID', 'AccountId'])
        end_cash_col = get_col(cash_df, ['EndingCash', 'Ending Cash'])
        curr_col = get_col(cash_df, ['CurrencyPrimary', 'Currency'])
        
        cash_df[cash_acc_col] = cash_df[cash_acc_col].astype(str).str.replace('F', '', regex=False)
        for _, row in cash_df.iterrows():
            raw_acc = str(row.get(cash_acc_col, '')).strip()
            if raw_acc in acc_map:
                curr = str(row.get(curr_col, '')).strip()
                if curr == 'BASE_SUMMARY':
                    silo = acc_map[raw_acc]
                    try: cash_val = float(row.get(end_cash_col, 0))
                    except: cash_val = 0.0
                    live_pos[silo]['CASH'] += cash_val

    for silo in live_pos:
        for k, v in live_pos[silo].items():
            if isinstance(v, list): continue
            live_pos[silo][k] = round(v, 2)

    with open(os.path.join(TARGET_DIR, 'Live_Allocations.json'), 'w') as f:
        json.dump(live_pos, f)
    print("   [OK] Live Portfolio Allocations Exported.")

    # ---------------------------------------------------------
    # 4. Extract PnL Attribution
    # ---------------------------------------------------------
    pnl_df = sections.get('PnL_Data')
    attr_data = {"Risk-Free Yield": 0.0, "VRP Engine": 0.0, "Active Alpha": 0.0, "Core Beta": 0.0}
    if pnl_df is not None:
        pnl_acc_col = get_col(pnl_df,['ClientAccountID', 'Account ID', 'AccountId'])
        sym_col = get_col(pnl_df, ['Symbol'])
        asset_col = get_col(pnl_df, ['AssetClass', 'Asset Class'])
        total_pnl_col = get_col(pnl_df,['Total', 'TotalMTM', 'RealizedTotal', 'TotalFifoPnl'])
        
        for _, row in pnl_df.iterrows():
            raw_acc = str(row.get(pnl_acc_col, '')).strip().replace('F', '')
            sym = str(row.get(sym_col, '')).upper()
            asset = str(row.get(asset_col, '')).upper()
            try: pnl_val = float(row.get(total_pnl_col, 0))
            except: pnl_val = 0.0
            
            silo = acc_map.get(raw_acc, '')
            if asset == 'CASH' or 'IB01' in sym: attr_data["Risk-Free Yield"] += pnl_val
            elif asset == 'OPT': attr_data["VRP Engine"] += pnl_val
            elif silo in ['B', 'D']: attr_data["Active Alpha"] += pnl_val
            elif silo in ['A', 'C']: attr_data["Core Beta"] += pnl_val

    with open(os.path.join(TARGET_DIR, 'PnL_Attribution.json'), 'w') as f:
        json.dump(attr_data, f)
    print("   [OK] PnL Attribution Exported.")

    # ---------------------------------------------------------
    # 5. Extract Capital Velocity (from Excel Journal)
    # ---------------------------------------------------------
    journal_path = os.path.join(TARGET_DIR, 'XSP_XND_Options_Journal_v5.xlsx')
    velocity_data = {"win_rate": 0, "avg_days": 0}
    try:
        if os.path.exists(journal_path):
            j_df = pd.read_excel(journal_path, sheet_name="Options Ledger v5")    
            closed_trades = j_df[j_df['Close Date'].notna() & (j_df['Close Date'] != '')]
            if not closed_trades.empty:
                winning_trades = closed_trades[pd.to_numeric(closed_trades['Total P&L (USD)'], errors='coerce') > 0]
                win_rate = (len(winning_trades) / len(closed_trades)) * 100
                avg_days = pd.to_numeric(closed_trades['Days in Trade'], errors='coerce').mean()
                velocity_data = {"win_rate": round(win_rate, 1), "avg_days": round(avg_days, 1)}
    except Exception as e:
        print(f"   [ERROR] Parsing Options Journal: {e}")
        
    with open(os.path.join(TARGET_DIR, 'Velocity_Metrics.json'), 'w') as f:
        json.dump(velocity_data, f)
    print("   [OK] Capital Velocity Exported.")

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
                process_ibkr_data(parse_ibkr_universal(csv_data))
                api_success = True
            else: print("   [ERROR] Timeout waiting for IBKR to compile.")
        else: print(f"   [ERROR] IBKR API Rejected: {root.find('ErrorCode').text} - {root.find('ErrorMessage').text}")
    except Exception as e:
        print(f"   [ERROR] API Failure: {e}")

    if not api_success:
        print("\n   [!] Attempting Local File Fallback...")
        local_csv = os.path.join(TARGET_DIR, 'Estate_Master_Feed.csv')
        if os.path.exists(local_csv):
            print("   [OK] Found manual Estate_Master_Feed.csv. Processing local file...")
            with open(local_csv, 'r') as f: local_data = f.read()
            process_ibkr_data(parse_ibkr_universal(local_data))
        else: print("   [!] No local Estate_Master_Feed.csv found. Skipping IBKR update.")

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
        
        # Extract closing data safely
        close_data = data['Close'].ffill() if 'Close' in data.columns else data.ffill()
        open_data = data['Open'].ffill() if 'Open' in data.columns else data.ffill()
        
        spy_open = open_data['SPY']
        spy_close = close_data['SPY']
        vix_close = close_data['^VIX']
        
        # Inject VIX into the CIO Audit Proof
        proof_df = pd.DataFrame({'Open': spy_open, 'Close': spy_close, 'VIX': vix_close.round(2)})
        proof_df['10SMA'] = proof_df['Close'].rolling(10).mean().round(2)
        proof_df['20SMA'] = proof_df['Close'].rolling(20).mean().round(2)
        proof_df['50SMA'] = proof_df['Close'].rolling(50).mean().round(2)
        proof_df['200SMA'] = proof_df['Close'].rolling(200).mean().round(2)
        
        proof_df_clean = proof_df.dropna().reset_index()
        proof_df_clean['Date'] = proof_df_clean['Date'].dt.strftime('%Y-%m-%d')
        proof_df_clean.to_csv(os.path.join(TARGET_DIR, 'SPY_Technical_Proof.csv'), index=False)

        spy_sma10 = close_data['SPY'].rolling(10).mean()
        spy_sma20 = close_data['SPY'].rolling(20).mean()

        new_rows =[]
        for date, row in close_data.iterrows():
            if date.tz_localize(None) > max_date.tz_localize(None):
                s10, s20 = spy_sma10[date], spy_sma20[date]
                if pd.isna(s10) or pd.isna(s20): continue
                
                price = row['SPY']
                vix_price = row['^VIX']

                # 1. Determine Regime (Status)
                if s10 > s20 and price > s10:
                    status, min_tor, max_tor = 'Green', 3, 5
                elif s10 < s20 and price < s20:
                    status, min_tor, max_tor = 'Red', 0, 1
                else:
                    status, min_tor, max_tor = 'Yellow', 1, 3

                # 2. Determine Exact TOR based on VIX Tier
                if status == 'Green':
                    if vix_price < 15: tor = 5
                    elif vix_price <= 20: tor = 4
                    else: tor = 3
                elif status == 'Yellow':
                    if vix_price < 20: tor = 3
                    elif vix_price <= 25: tor = 2
                    else: tor = 1
                elif status == 'Red':
                    if vix_price < 25: tor = 1
                    else: tor = 0
                    
                new_rows.append({
                    'Date': date.strftime('%d-%b-%y'), 'SPY Close': round(row['SPY'], 2), 
                    'QQQ Close': round(row['QQQ'], 2), 'Status': status, 
                    'Min TOR': min_tor, 'Max TOR': max_tor, 'Set TOR': tor
                })

        if new_rows:
            new_df = pd.DataFrame(new_rows)
            old_bench = pd.concat([old_bench.drop(columns=['Date_obj']), new_df]) if not old_bench.empty else new_df
            old_bench.to_csv(spy_csv_path, index=False)
            print(f"   [OK] Rebuilt benchmark file with {len(new_rows)} new days of pure mathematical TOR.")
        else: print("   [OK] Market data is already up to date.")
            
    except Exception as e: print(f"   [ERROR] YFinance Failure: {e}")

if __name__ == "__main__":
    print("========================================================")
    print("     ESTATE ORCHESTRATOR v13 - INITIALIZING SYNC...      ")
    print("========================================================")
    
    update_ibkr_api_or_fallback()
    update_yfinance_data()
    
    print("\n3. Generating Dashboard HTML...")
    os.system('python Generate_Estate_Dashboard_v62.py')
    
    html_path = os.path.join(TARGET_DIR, "Family_Estate_Dashboard_v62.html")
    if os.path.exists(html_path): webbrowser.open(f'file:///{html_path}')
        
    print("\n[PROCESS COMPLETE] The Family Office is fully updated.")