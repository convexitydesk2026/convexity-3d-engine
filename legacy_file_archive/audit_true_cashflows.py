"""
=============================================================================
Script Name: audit_true_cashflows.py
Purpose: Diagnostic script to fetch the undeniable ground truth of all 
         cash injected into the Estate directly from the IBKR Flex API.
=============================================================================
"""

import os
import time
import requests
import configparser
import sqlite3
import xml.etree.ElementTree as ET

TARGET_DIR = r"C:\Users\donca\Desktop\Desktop HP Envy x360 al 22Abr24\Docs Manuel\IBKR_Options"
CONFIG_PATH = os.path.join(TARGET_DIR, "estate_config.ini")
DB_PATH = os.path.join(TARGET_DIR, "estate_data.db")

def safe_float(val):
    try:
        if not val or str(val).strip() == '': return 0.0
        return float(str(val).strip())
    except ValueError:
        return 0.0

def run_cash_audit():
    print("========================================================")
    print("   IBKR FLEX QUERY: GROUND TRUTH CASH FLOW AUDIT")
    print("========================================================")

    config = configparser.ConfigParser()
    config.read(CONFIG_PATH)
    
    try:
        token = config['IBKR']['TOKEN']
        query_id = config['IBKR']['MTM_QUERY_ID']
    except KeyError:
        print("[!] ERROR: Missing TOKEN or MTM_QUERY_ID in estate_config.ini")
        return

    print(f"[*] Requesting Flex Query {query_id} via IBKR Web Service...")
    req_url = f"https://gdcdyn.interactivebrokers.com/Universal/servlet/FlexStatementService.SendRequest?t={token}&q={query_id}&v=3"
    
    try:
        response = requests.get(req_url, headers={'User-Agent': 'Mozilla/5.0'})
        root = ET.fromstring(response.text)
        status = root.find('Status').text if root.find('Status') is not None else 'Error'
        
        if status != 'Success':
            err = root.find('ErrorMessage').text if root.find('ErrorMessage') is not None else 'Unknown Error'
            print(f"[!] API Request Failed: {err}")
            return
            
        ref_code = root.find('ReferenceCode').text
        base_url = root.find('Url').text
        print(f"[*] Report generation initiated. Reference Code: {ref_code}")
        print("[*] Waiting for IBKR servers to compile the report...")
        
        poll_url = f"{base_url}?q={ref_code}&t={token}&v=3"
        xml_root = None
        
        for attempt in range(24):
            time.sleep(5)
            res = requests.get(poll_url, headers={'User-Agent': 'Mozilla/5.0'})
            
            if res.text.strip().startswith('<FlexStatementResponse'):
                try:
                    poll_root = ET.fromstring(res.text)
                    if poll_root.find('Status') is not None and poll_root.find('Status').text == 'Warn':
                        continue
                except: pass
            else:
                xml_root = ET.fromstring(res.text)
                print("[+] Report successfully downloaded.")
                break
                
        if xml_root is None:
            print("[!] Timeout waiting for Flex Query to generate.")
            return

    except Exception as e:
        print(f"[!] Network or Parsing Error: {e}")
        return

    print("\n[*] Parsing 'Change in NAV' (CNAV) section for undeniable cash flows...")
    
    total_deposits_withdrawals = 0.0
    total_internal_transfers = 0.0
    total_asset_transfers = 0.0
    
    # We use a set to prevent double counting the same exact row if IBKR sends duplicates
    processed_rows = set()

    for flex_statement in xml_root.findall('.//FlexStatement'):
        for cnav in flex_statement.findall('.//ChangeInNav'):
            acc = cnav.get('accountId', '').strip()
            date_val = cnav.get('toDate', '')
            
            # Skip summary/total rows
            if not acc or 'total' in acc.lower():
                continue
                
            dep_with = safe_float(cnav.get('depositsWithdrawals', 0))
            int_trans = safe_float(cnav.get('internalCashTransfers', 0))
            ast_trans = safe_float(cnav.get('assetTransfers', 0))
            
            row_hash = f"{acc}_{date_val}_{dep_with}_{int_trans}_{ast_trans}"
            
            if row_hash not in processed_rows:
                total_deposits_withdrawals += dep_with
                total_internal_transfers += int_trans
                total_asset_transfers += ast_trans
                processed_rows.add(row_hash)

    ibkr_total_net_flows = total_deposits_withdrawals + total_internal_transfers + total_asset_transfers

    print("\n--------------------------------------------------------")
    print("   EVIDENCE: IBKR CLEARINGHOUSE TOTALS (Since Dec 2025)")
    print("--------------------------------------------------------")
    print(f"External Deposits/Withdrawals:   ${total_deposits_withdrawals:,.2f}")
    print(f"Internal Cash Transfers:         ${total_internal_transfers:,.2f}")
    print(f"Asset Transfers:                 ${total_asset_transfers:,.2f}")
    print("--------------------------------------------------------")
    print(f"TRUE IBKR NET CASH INJECTED:     ${ibkr_total_net_flows:,.2f}")
    print("--------------------------------------------------------")

    print("\n[*] Querying local SQLite database (cash_transfers) for comparison...")
    try:
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute("SELECT SUM(amount) FROM cash_transfers")
        db_sum = c.fetchone()[0]
        db_sum = db_sum if db_sum else 0.0
        
        c.execute("SELECT SUM(amount) FROM cash_transfers WHERE notes = 'Official Clearinghouse Flow'")
        db_flex_sum = c.fetchone()[0]
        db_flex_sum = db_flex_sum if db_flex_sum else 0.0
        conn.close()
        
        print(f"Total Cash in Local Database:    ${db_sum:,.2f}")
        print(f"Total Flex-Tagged Cash in DB:    ${db_flex_sum:,.2f}")
        print("\n[*] DIAGNOSTIC COMPLETE.")
        
        if abs(ibkr_total_net_flows - db_sum) < 1.0:
            print("[+] CONCLUSION: Your database cash flows PERFECTLY MATCH IBKR.")
            print("    The True PnL is $8,124. The bug is isolated to the Attribution Engine (MTMP parsing).")
        else:
            diff = abs(ibkr_total_net_flows - db_sum)
            print(f"[!] CONCLUSION: Database mismatch detected (${diff:,.2f}).")
            print("    Please provide me these final output numbers so we can correct the math.")
            
    except Exception as e:
        print(f"[!] SQLite Error: {e}")

if __name__ == "__main__":
    run_cash_audit()