"""
=============================================================================
Script Name: audit_forensic_nbis.py
Purpose: Performs a day-by-day X-Ray on the MTMP data for NBIS to 
         prove exactly when and how IBKR is reporting the $68k profit.
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

def run_forensic():
    print("=======================================================================")
    print("   FORENSIC X-RAY: NBIS (DAY-BY-DAY IBKR MTMP LEDGER)")
    print("=======================================================================")

    if not os.path.exists(FLEX_CSV_PATH):
        print(f"[!] ERROR: Could not find {FLEX_CSV_PATH}")
        return

    mtmp_idx = {}
    nbis_records = []
    
    with open(FLEX_CSV_PATH, 'r', encoding='utf-8-sig') as f:
        reader = csv.reader(f)
        for row in reader:
            if not row or len(row) < 3: continue
            
            row_type, sec_type = row[0], row[1]

            if row_type == 'HEADER' and sec_type == 'MTMP':
                mtmp_idx = {val.replace(' ', '').replace('/', '').replace('_', ''): i for i, val in enumerate(row)}
                
            elif row_type == 'DATA' and sec_type == 'MTMP' and mtmp_idx:
                sym = str(row[mtmp_idx.get('Symbol', '')]).strip().upper()
                
                if sym == 'NBIS':
                    date_str = str(row[mtmp_idx.get('ReportDate', '')])
                    qty = str(row[mtmp_idx.get('CloseQuantity', '')])
                    prev_px = str(row[mtmp_idx.get('PrevClosePrice', '')])
                    close_px = str(row[mtmp_idx.get('ClosePrice', '')])
                    pnl = safe_float(row[mtmp_idx.get('Total', 37)])
                    
                    if abs(pnl) > 0.001:
                        nbis_records.append({
                            'date': date_str,
                            'qty': qty,
                            'prev_px': prev_px,
                            'close_px': close_px,
                            'pnl': pnl
                        })

    # Sort chronologically
    nbis_records = sorted(nbis_records, key=lambda x: x['date'])

    print(f"{'DATE':<12} | {'QTY':<10} | {'PREV PRICE':<12} | {'CLOSE PRICE':<12} | {'DAILY PNL CLAIMED'}")
    print("-" * 75)
    
    total_pnl = 0.0
    for r in nbis_records:
        # Format the date nicely if possible
        dt = f"{r['date'][:4]}-{r['date'][4:6]}-{r['date'][6:]}" if len(r['date']) == 8 else r['date']
        
        print(f"{dt:<12} | {r['qty']:<10} | ${r['prev_px']:<11} | ${r['close_px']:<11} | ${r['pnl']:,.2f}")
        total_pnl += r['pnl']
        
    print("-" * 75)
    print(f"TOTAL NBIS PNL CLAIMED BY IBKR IN CSV: ${total_pnl:,.2f}")
    print("=======================================================================\n")

if __name__ == "__main__":
    run_forensic()