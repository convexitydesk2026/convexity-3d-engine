r"""
=============================================================================
Script Name: Estate_Orchestrator_v17.py
Purpose: The Zero-Touch Automation Engine for the Family Office.
         v17 UPGRADES:
         - PnL Attribution Ledger: Day-by-day extraction of a1 (Yield), 
           a3 (VRP), a4 (Alpha), a5 (Fees), with a2 (Beta) as the math plug.
         - Progressive Exposure Advisor: Evaluates Silo B/D merit against 
           the tier matrix and exports suggestions to JSON.
         - Ticker Routing Overrides: Asian/Crypto ETFs routed to Active Alpha.
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
import datetime

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
# HELPER FUNCTIONS
# -------------------------------------------------------------------
def get_col(df, possible_names):
    lower_cols = {c.strip().lower(): c for c in df.columns}
    for n in possible_names:
        if n.lower() in lower_cols:
            return lower_cols[n.lower()]
    return df.columns[0]

def parse_ibkr_universal(csv_text):
    lines = csv_text.strip().split('\n')
    nav_list, pos_list, cash_list, pnl_list = [], [], [], []
    current_mode, current_headers = None,[]
    
    for line in lines:
        if not line.strip(): continue
        parts =[p.strip(' "\r') for p in line.split(',')]
        
        p0_lower = parts[0].lower()
        is_pnl = 'realized' in p0_lower and 'unrealized' in p0_lower and 'performance' in p0_lower
        
        if parts[0] in ['Change in NAV', 'Open Positions', 'Cash Report'] or is_pnl:
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
        elif 'Symbol' in parts and ('Total Realized and Unrealized P/L' in parts or 'TotalMTM' in parts or 'TotalFifoPnl' in parts):
            current_mode = 'PNL'; current_headers = parts; continue

        # Handle rows without standard headers (Fallback parsing)
        if current_mode == 'NAV' and len(parts) > 2 and parts[0].isdigit():
            current_date = parts[1] # Extract the ToDate
            nav_list.append(dict(zip(current_headers, parts)))
        elif current_mode == 'POS' and len(parts) > 2 and parts[0] != 'CurrencyPrimary' and parts[0] != 'Currency':
            row = dict(zip(current_headers, parts))
            pos_list.append(row)
        elif current_mode == 'CASH' and len(parts) >= 2 and parts[0] != 'CurrencyPrimary' and parts[0] != 'Currency':
            row = dict(zip(current_headers, parts))
            cash_list.append(row)
        elif current_mode == 'PNL' and len(parts) >= 2 and parts[0] != 'ClientAccountID':
            row = dict(zip(current_headers, parts))
            pnl_list.append(row)

    return {
        'Change in NAV': pd.DataFrame(nav_list) if nav_list else None, 
        'Open Positions': pd.DataFrame(pos_list) if pos_list else None, 
        'Cash Report': pd.DataFrame(cash_list) if cash_list else None,
        'PnL_Data': pd.DataFrame(pnl_list) if pnl_list else None
    }

def calculate_progressive_exposure(profit):
    tiers =[
        {"tier": "Base", "threshold": 0, "base": 30000},
        {"tier": "Tier 1", "threshold": 3000, "base": 30000},
        {"tier": "Tier 2", "threshold": 4000, "base": 40000},
        {"tier": "Tier 3", "threshold": 7000, "base": 50000},
        {"tier": "Tier 4", "threshold": 11000, "base": 60000},
        {"tier": "Tier 5", "threshold": 18000, "base": 70000},
        {"tier": "Tier 6", "threshold": 29000, "base": 80000},
        {"tier": "Tier 7", "threshold": 47000, "base": 90000},
        {"tier": "Tier 8", "threshold": 76000, "base": 100000}
    ]
    
    current_tier = tiers[0]
    next_tier = tiers[1]
    
    for i, t in enumerate(tiers):
        if profit >= t["threshold"]:
            current_tier = t
            next_tier = tiers[i+1] if (i + 1) < len(tiers) else None
        else:
            break
            
    return {
        "profit": round(profit, 2),
        "current_tier": current_tier["tier"],
        "suggested_base": current_tier["base"],
        "next_threshold": next_tier["threshold"] if next_tier else "MAX",
        "distance_to_next": round(next_tier["threshold"] - profit, 2) if next_tier else 0
    }

# -------------------------------------------------------------------
# MASTER PROCESSING ENGINE
# -------------------------------------------------------------------
def process_ibkr_data(sections):
    print("   [PROCESSING] Executing Core Engine Math...")
    
    # 1. Update Daily NAV
    nav_df = sections.get('Change in NAV')
    current_pull_date = datetime.datetime.now().strftime('%Y%m%d')
    
    if nav_df is not None:
        acc_col = get_col(nav_df, ['AccountID', 'Account ID', 'ClientAccountID'])
        date_col = get_col(nav_df,['ToDate', 'To Date', 'Date', 'ReportDate'])
        nav_col = get_col(nav_df,['EndingValue', 'Ending Value', 'NAV'])
        flow_col = get_col(nav_df,['DepositsWithdrawals', 'Deposits/Withdrawals', 'CashFlow'])

        nav_df['Date'] = pd.to_datetime(nav_df[date_col]).dt.strftime('%Y%m%d')
        current_pull_date = nav_df['Date'].max() # Standardize to IBKR report date
        
        nav_df['AccountID'] = nav_df[acc_col].astype(str).str.replace('F', '', regex=False)
        nav_df['NAV'] = pd.to_numeric(nav_df[nav_col], errors='coerce').fillna(0)
        nav_df['CashFlow'] = pd.to_numeric(nav_df[flow_col], errors='coerce').fillna(0)
        
        new_nav = nav_df.groupby(['AccountID', 'Date']).agg({'NAV': 'max', 'CashFlow': 'sum'}).reset_index()
        
        csv_path = os.path.join(TARGET_DIR, 'IBKR_Daily_Data.csv')
        if os.path.exists(csv_path):
            old_nav = pd.read_csv(csv_path)
            old_nav['Date'] = old_nav['Date'].astype(str)
            combined = pd.concat([old_nav, new_nav]).drop_duplicates(subset=['AccountID', 'Date'], keep='last')
        else:
            combined = new_nav
            
        combined.sort_values(by=['AccountID', 'Date'], inplace=True)
        combined.to_csv(csv_path, index=False)
        print("   [OK] IBKR_Daily_Data.csv Appended & Deduplicated.")
    else:
        csv_path = os.path.join(TARGET_DIR, 'IBKR_Daily_Data.csv')
        if os.path.exists(csv_path): combined = pd.read_csv(csv_path)
        else: combined = pd.DataFrame()

    # 2. Daily PnL Attribution Engine (a1 - a5)
    daily_attr_path = os.path.join(TARGET_DIR, 'Daily_PnL_Attribution.csv')
    attr_list =[]
    
    if os.path.exists(daily_attr_path):
        attr_df = pd.read_csv(daily_attr_path)
        attr_list = attr_df.to_dict('records')
    
    # Process Options Journal (a3 mapping)
    options_daily = {}
    journal_path = os.path.join(TARGET_DIR, 'XSP_XND_Options_Journal_v5.xlsx')
    velocity_data = {"win_rate": 0, "avg_days": 0}
    try:
        if os.path.exists(journal_path):
            j_df = pd.read_excel(journal_path, sheet_name="Options Ledger v5")
            closed = j_df[j_df['Close Date'].notna() & (j_df['Close Date'] != '')].copy()
            if not closed.empty:
                closed['Close Date'] = pd.to_datetime(closed['Close Date']).dt.strftime('%Y%m%d')
                closed['Total P&L (USD)'] = pd.to_numeric(closed['Total P&L (USD)'], errors='coerce').fillna(0)
                options_daily = closed.groupby('Close Date')['Total P&L (USD)'].sum().to_dict()
                
                win_rate = (len(closed[closed['Total P&L (USD)'] > 0]) / len(closed)) * 100
                avg_days = pd.to_numeric(closed['Days in Trade'], errors='coerce').mean()
                velocity_data = {"win_rate": round(win_rate, 1), "avg_days": round(avg_days, 1)}
    except Exception as e:
        print(f"   [WARNING] Options Journal Parse Error: {e}")

    with open(os.path.join(TARGET_DIR, 'Velocity_Metrics.json'), 'w') as f:
        json.dump(velocity_data, f)

    # Reconstruct/Append Daily PnL Math
    if not combined.empty:
        combined['Date'] = combined['Date'].astype(str)
        dates = sorted(combined['Date'].unique())
        
        # Calculate daily step for the entire history to guarantee accuracy
        for dt in dates:
            day_data = combined[combined['Date'] == dt]
            
            # Global NAV Math
            global_nav = day_data['NAV'].sum()
            global_cf = day_data['CashFlow'].sum()
            
            # Silo B and D base PnL Math
            silo_b_data = day_data[day_data['AccountID'] == 'U23139264']
            silo_d_data = day_data[day_data['AccountID'] == 'U25218481']
            
            nav_b = silo_b_data['NAV'].sum() if not silo_b_data.empty else 0
            cf_b = silo_b_data['CashFlow'].sum() if not silo_b_data.empty else 0
            nav_d = silo_d_data['NAV'].sum() if not silo_d_data.empty else 0
            cf_d = silo_d_data['CashFlow'].sum() if not silo_d_data.empty else 0
            
            # Find previous day to calculate Delta NAV
            prev_dt = combined[combined['Date'] < dt]['Date'].max()
            if pd.isna(prev_dt):
                prev_global_nav = global_nav - global_cf
                prev_nav_b = nav_b - cf_b
                prev_nav_d = nav_d - cf_d
            else:
                prev_data = combined[combined['Date'] == prev_dt]
                prev_global_nav = prev_data['NAV'].sum()
                prev_b_data = prev_data[prev_data['AccountID'] == 'U23139264']
                prev_d_data = prev_data[prev_data['AccountID'] == 'U25218481']
                prev_nav_b = prev_b_data['NAV'].sum() if not prev_b_data.empty else 0
                prev_nav_d = prev_d_data['NAV'].sum() if not prev_d_data.empty else 0

            global_pnl = global_nav - prev_global_nav - global_cf
            pnl_b = nav_b - prev_nav_b - cf_b
            pnl_d = nav_d - prev_nav_d - cf_d
            
            # Base variables
            a3_vrp = options_daily.get(dt, 0.0)
            a4_alpha = pnl_b + pnl_d
            a5_fees = 0.0
            a1_yield = 0.0
            override_alpha = 0.0
            
            # Overrides for the Current Pull Date (Using the new Flex Query Extractions)
            if dt == current_pull_date:
                # Extract a5 Fees
                cash_df = sections.get('Cash Report')
                if cash_df is not None:
                    try:
                        comm_col = get_col(cash_df, ['Commissions'])
                        a5_fees = pd.to_numeric(cash_df[comm_col], errors='coerce').sum()
                    except: pass

                # Extract Ticker Routing Overrides
                pnl_df = sections.get('PnL_Data')
                if pnl_df is not None:
                    try:
                        sym_col = get_col(pnl_df, ['Symbol'])
                        asset_col = get_col(pnl_df,['AssetClass', 'Asset Class'])
                        total_pnl_col = get_col(pnl_df,['Total Realized and Unrealized P/L', 'TotalFifoPnl', 'TotalMTM'])
                        
                        for _, row in pnl_df.iterrows():
                            sym = str(row.get(sym_col, '')).upper()
                            asset = str(row.get(asset_col, '')).upper()
                            val = float(row.get(total_pnl_col, 0))
                            
                            if 'IB01' in sym or asset == 'CASH':
                                a1_yield += val
                            elif any(t in sym for t in['ITWN', 'CSKR', 'CNYA', 'BTC', 'ETH']):
                                override_alpha += val
                    except: pass
                    
            # Finalize Attribution logic
            a4_alpha += override_alpha
            a2_beta = global_pnl - (a1_yield + a3_vrp + a4_alpha + a5_fees)
            
            # Update or append to ledger
            existing_row = next((r for r in attr_list if r['Date'] == dt), None)
            if existing_row:
                # If we are reprocessing today, update it. Otherwise keep historical intact.
                if dt == current_pull_date:
                    existing_row.update({'a1_Yield': a1_yield, 'a2_Beta': a2_beta, 'a3_VRP': a3_vrp, 'a4_Alpha': a4_alpha, 'a5_Fees': a5_fees})
            else:
                attr_list.append({
                    'Date': dt, 'a1_Yield': a1_yield, 'a2_Beta': a2_beta, 
                    'a3_VRP': a3_vrp, 'a4_Alpha': a4_alpha, 'a5_Fees': a5_fees
                })

    pd.DataFrame(attr_list).to_csv(daily_attr_path, index=False)
    print("   [OK] Daily PnL Attribution Ledger Updated.")

    # 3. Progressive Exposure Advisor (Suggestion JSON)
    b_cum_cf = combined[combined['AccountID'] == 'U23139264']['CashFlow'].sum() if not combined.empty else 0
    b_curr_nav = combined[(combined['AccountID'] == 'U23139264') & (combined['Date'] == current_pull_date)]['NAV'].sum() if not combined.empty else 0
    b_profit = b_curr_nav - b_cum_cf
    
    d_cum_cf = combined[combined['AccountID'] == 'U25218481']['CashFlow'].sum() if not combined.empty else 0
    d_curr_nav = combined[(combined['AccountID'] == 'U25218481') & (combined['Date'] == current_pull_date)]['NAV'].sum() if not combined.empty else 0
    d_profit = d_curr_nav - d_cum_cf

    exposure_data = {
        "Silo_B": calculate_progressive_exposure(b_profit),
        "Silo_D": calculate_progressive_exposure(d_profit)
    }
    
    with open(os.path.join(TARGET_DIR, 'Progressive_Exposure.json'), 'w') as f:
        json.dump(exposure_data, f)
    print("   [OK] Progressive Exposure Advisor Exported.")

    # 4. Live Allocations & Opt Margin (Unchanged)
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
        pos_acc_col = get_col(pos_df,['ClientAccountID', 'Account ID', 'AccountId'])                
        pos_df[pos_acc_col] = pos_df[pos_acc_col].astype(str).str.replace('F', '', regex=False)
        
        for _, row in pos_df.iterrows():
            raw_acc = str(row.get(pos_acc_col, '')).strip()
            if raw_acc not in acc_map: continue
            
            silo = acc_map[raw_acc]
            sym = str(row.get(get_col(pos_df, ['Symbol']), '')).upper()
            asset = str(row.get(get_col(pos_df, ['AssetClass', 'Asset Class']), ''))
            curr = str(row.get(get_col(pos_df, ['CurrencyPrimary', 'Currency']), 'USD'))
            
            val_col = get_col(pos_df, ['PositionValue', 'Position Value', 'Value'])
            fx_col = get_col(pos_df,['FXRateToBase', 'FX Rate To Base'])
            qty_col = get_col(pos_df, ['Quantity', 'Position'])
            
            try: val = float(row.get(val_col, 0))
            except: val = 0.0
            
            try: fx = float(row.get(fx_col, 1)) if str(row.get(fx_col, '')) != '' else 1.0
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
                
    cash_df = sections.get('Cash Report')
    if cash_df is not None:
        cash_acc_col = get_col(cash_df,['ClientAccountID', 'Account ID', 'AccountId'])
        end_cash_col = get_col(cash_df,['EndingCash', 'Ending Cash'])
        curr_col = get_col(cash_df,['CurrencyPrimary', 'Currency'])
        
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

# -------------------------------------------------------------------
# ORCHESTRATION TRIGGERS
# -------------------------------------------------------------------
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
        close_data = data['Close'].ffill() if 'Close' in data.columns else data.ffill()
        open_data = data['Open'].ffill() if 'Open' in data.columns else data.ffill()
        
        spy_sma10 = close_data['SPY'].rolling(10).mean()
        spy_sma20 = close_data['SPY'].rolling(20).mean()

        new_rows =[]
        for date, row in close_data.iterrows():
            if date.tz_localize(None) > max_date.tz_localize(None):
                s10, s20 = spy_sma10[date], spy_sma20[date]
                if pd.isna(s10) or pd.isna(s20): continue
                
                price = row['SPY']
                vix_price = row['^VIX']

                if s10 > s20 and price > s10: status, min_tor, max_tor = 'Green', 3, 5
                elif s10 < s20 and price < s20: status, min_tor, max_tor = 'Red', 0, 1
                else: status, min_tor, max_tor = 'Yellow', 1, 3

                if status == 'Green': tor = 5 if vix_price < 15 else (4 if vix_price <= 20 else 3)
                elif status == 'Yellow': tor = 3 if vix_price < 20 else (2 if vix_price <= 25 else 1)
                elif status == 'Red': tor = 1 if vix_price < 25 else 0
                    
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
    print("     ESTATE ORCHESTRATOR v17 - INITIALIZING SYNC...      ")
    print("========================================================")
    
    update_ibkr_api_or_fallback()
    update_yfinance_data()
    
    print("\n3. Generating Dashboard HTML...")
    os.system('python Generate_Estate_Dashboard_v65.py')
    
    html_path = os.path.join(TARGET_DIR, "Family_Estate_Dashboard_v65.html")
    if os.path.exists(html_path): webbrowser.open(f'file:///{html_path}')
        
    print("\n[PROCESS COMPLETE] The Family Office is fully updated.")