"""
=============================================================================
Script Name: audit_local_csv.py
Purpose: Parses the local Estate_Master_MTM_Sync.csv to find the exact 
         amount of external cash injected into the Estate since inception.
=============================================================================
"""

import csv
import os

TARGET_DIR = r"C:\Users\donca\Desktop\Desktop HP Envy x360 al 22Abr24\Docs Manuel\IBKR_Options"
FLEX_CSV_PATH = os.path.join(TARGET_DIR, "Estate_Master_MTM_Sync.csv")

def safe_float(val):
    try:
        if not val or str(val).strip() == '': return 0.0
        return float(str(val).strip())
    except ValueError:
        return 0.0

def run_local_audit():
    print("========================================================")
    print("   LOCAL CSV GROUND TRUTH CASH FLOW AUDIT")
    print("========================================================")

    if not os.path.exists(FLEX_CSV_PATH):
        print(f"[!] ERROR: Could not find {FLEX_CSV_PATH}")
        return

    cnav_idx = {}
    total_deposits = 0.0
    total_internal = 0.0
    total_asset = 0.0
    
    account_flows = {}

    print(f"[*] Reading {FLEX_CSV_PATH}...")
    
    with open(FLEX_CSV_PATH, 'r', encoding='utf-8-sig') as f:
        reader = csv.reader(f)
        for row in reader:
            if not row or len(row) < 3: 
                continue
            
            row_type, sec_type = row[0], row[1]

            if row_type == 'HEADER' and sec_type == 'CNAV':
                cnav_idx = {val.replace(' ', '').replace('/', '').replace('_', ''): i for i, val in enumerate(row)}
                
            elif row_type == 'DATA' and sec_type == 'CNAV' and cnav_idx:
                acc = row[cnav_idx['ClientAccountID']].strip().rstrip('F')
                
                # Exclude summary rows to avoid double counting
                if not acc or 'total' in acc.lower():
                    continue
                    
                dep_with = safe_float(row[cnav_idx.get('DepositsWithdrawals', -1)])
                int_trans = safe_float(row[cnav_idx.get('InternalCashTransfers', -1)])
                ast_trans = safe_float(row[cnav_idx.get('AssetTransfers', -1)])
                
                total_deposits += dep_with
                total_internal += int_trans
                total_asset += ast_trans
                
                if acc not in account_flows:
                    account_flows[acc] = 0.0
                account_flows[acc] += (dep_with + int_trans + ast_trans)

    # Note: Internal transfers should mathematically sum to $0 globally.
    global_cash_injected = total_deposits + total_asset

    print("\n--------------------------------------------------------")
    print("   EVIDENCE: IBKR CLEARINGHOUSE TOTALS (CSV)")
    print("--------------------------------------------------------")
    print(f"External Deposits/Withdrawals:   ${total_deposits:,.2f}")
    print(f"Internal Cash Transfers (Net):   ${total_internal:,.2f} (Should be ~$0)")
    print(f"Asset Transfers:                 ${total_asset:,.2f}")
    print("--------------------------------------------------------")
    print(f"TRUE NET CASH INJECTED (GLOBAL): ${global_cash_injected:,.2f}")
    print("--------------------------------------------------------")
    
    print("\n[*] Net Flows By Silo:")
    for acc, flow in account_flows.items():
        print(f"    - {acc}: ${flow:,.2f}")

    current_nav = 1002687.0
    true_pnl = current_nav - global_cash_injected
    
    print("\n--------------------------------------------------------")
    print("   THE FINAL MATHEMATICAL VERDICT")
    print("--------------------------------------------------------")
    print(f"Current Global NAV:              ${current_nav:,.2f}")
    print(f"Less True Cash Injected:        -${global_cash_injected:,.2f}")
    print("--------------------------------------------------------")
    print(f"UNDENIABLE TRUE GLOBAL PNL:      ${true_pnl:,.2f}")
    print("========================================================\n")

if __name__ == "__main__":
    run_local_audit()