"""
=============================================================================
Script Name: audit_anomaly.py
Purpose: Scans the CSV to find the exact asset reporting the fake $63k PnL.
=============================================================================
"""

import csv
import os
import collections

TARGET_DIR = r"C:\Users\donca\Desktop\Desktop HP Envy x360 al 22Abr24\Docs Manuel\IBKR_Options"
FLEX_CSV_PATH = os.path.join(TARGET_DIR, "Estate_Master_MTM_Sync.csv")

def safe_float(val):
    try:
        if not val or str(val).strip() == '': return 0.0
        return float(str(val).strip())
    except ValueError:
        return 0.0

def run_anomaly_hunt():
    print("========================================================")
    print("   HUNTING THE $63K PHANTOM PNL ANOMALY")
    print("========================================================")

    if not os.path.exists(FLEX_CSV_PATH):
        print(f"[!] ERROR: Could not find {FLEX_CSV_PATH}")
        return

    mtmp_idx = {}
    cnav_idx = {}
    
    symbol_pnl = collections.defaultdict(float)
    cnav_pnl = collections.defaultdict(float)

    with open(FLEX_CSV_PATH, 'r', encoding='utf-8-sig') as f:
        reader = csv.reader(f)
        for row in reader:
            if not row or len(row) < 3: continue
            
            row_type, sec_type = row[0], row[1]

            if row_type == 'HEADER':
                if sec_type == 'MTMP':
                    mtmp_idx = {val.replace(' ', '').replace('/', '').replace('_', ''): i for i, val in enumerate(row)}
                elif sec_type == 'CNAV':
                    cnav_idx = {val.replace(' ', '').replace('/', '').replace('_', ''): i for i, val in enumerate(row)}

            elif row_type == 'DATA':
                if sec_type == 'MTMP' and mtmp_idx:
                    sym = str(row[mtmp_idx.get('Symbol', 7)]).strip()
                    ac_str = str(row[mtmp_idx.get('AssetClass', 5)]).strip().lower()
                    
                    if not sym or 'cash' in ac_str or 'fx' in ac_str:
                        continue
                        
                    pnl = safe_float(row[mtmp_idx.get('Total', 37)])
                    symbol_pnl[sym] += pnl
                    
                elif sec_type == 'CNAV' and cnav_idx:
                    cnav_pnl['Interest'] += safe_float(row[cnav_idx.get('Interest', -1)])
                    cnav_pnl['Dividends'] += safe_float(row[cnav_idx.get('Dividends', -1)])
                    cnav_pnl['Fees & Tax'] += safe_float(row[cnav_idx.get('BrokerFees', -1)]) + safe_float(row[cnav_idx.get('WithholdingTax', -1)])
                    cnav_pnl['FxTranslation'] += safe_float(row[cnav_idx.get('FxTranslation', -1)])
                    cnav_pnl['NetFxTrading'] += safe_float(row[cnav_idx.get('NetFxTrading', -1)])

    print("\n[*] TOP 10 ASSETS BY REPORTED PNL (MTMP):")
    sorted_syms = sorted(symbol_pnl.items(), key=lambda x: x[1], reverse=True)
    for sym, pnl in sorted_syms[:10]:
        print(f"    - {sym}: ${pnl:,.2f}")

    print("\n[*] BOTTOM 5 ASSETS BY REPORTED PNL (MTMP):")
    for sym, pnl in sorted_syms[-5:]:
        print(f"    - {sym}: ${pnl:,.2f}")

    print("\n[*] ACCOUNT-LEVEL PNL (CNAV):")
    for k, v in cnav_pnl.items():
        print(f"    - {k}: ${v:,.2f}")
        
    total_csv_pnl = sum(symbol_pnl.values()) + sum(cnav_pnl.values())
    print("\n--------------------------------------------------------")
    print(f"TOTAL CSV PNL CLAIMED BY IBKR: ${total_csv_pnl:,.2f}")
    print("--------------------------------------------------------\n")

if __name__ == "__main__":
    run_anomaly_hunt()