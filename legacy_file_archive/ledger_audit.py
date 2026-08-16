import sqlite3
import pandas as pd
import os

TARGET_DIR = r"C:\Users\donca\Desktop\Desktop HP Envy x360 al 22Abr24\Docs Manuel\IBKR_Options"
DB_PATH = os.path.join(TARGET_DIR, "estate_data.db")

def run_audit():
    print("\n========================================================")
    print("   ESTATE FORENSIC LEDGER AUDIT")
    print("========================================================")
    
    conn = sqlite3.connect(DB_PATH)
    
    # 1. Audit True MTM PnL (The Bar Chart)
    try:
        attr_df = pd.read_sql_query("SELECT * FROM daily_attribution", conn)
        attr_df['Total_MTM'] = attr_df[['a1_yield', 'a2_beta', 'a3_vrp', 'a4_alpha', 'a5_fees']].sum(axis=1)
        true_mtm = attr_df['Total_MTM'].sum()
        print(f"[*] 1. True Clearinghouse MTM PnL (from CSV): ${true_mtm:,.2f}")
    except Exception as e:
        print(f"[*] 1. Failed to read daily_attribution: {e}")

    # 2. Audit Cash Flows (Looking for the A -> B Internal Transfer)
    try:
        cf_df = pd.read_sql_query("SELECT * FROM cash_transfers ORDER BY date ASC", conn)
        print("\n[*] 2. Raw Cash Flow Ledger:")
        if not cf_df.empty:
            for _, row in cf_df.iterrows():
                print(f"       [{row['date']}] {row['account']} | {row['type']} | ${row['amount']:,.2f}")
            
            print("\n       -> SUM BY ACCOUNT:")
            cf_grouped = cf_df.groupby('account')['amount'].sum().reset_index()
            for _, row in cf_grouped.iterrows():
                print(f"          - {row['account']}: ${row['amount']:,.2f}")
            print(f"       -> TOTAL ESTATE NET FLOW: ${cf_df['amount'].sum():,.2f}")
        else:
            print("       - NO CASH FLOWS FOUND IN DATABASE.")
    except Exception as e:
        print(f"[*] 2. Failed to read cash_transfers: {e}")

    # 3. Audit Delta-NAV per Silo (The Dashboard's Silo Math)
    try:
        bal_df = pd.read_sql_query("SELECT date, account, net_liquidation, total_cash FROM daily_balances ORDER BY date ASC", conn)
        print("\n[*] 3. Delta-NAV Calculation per Silo (Dashboard Logic):")
        
        global_start_nav = 0
        global_end_nav = 0
        global_total_flow = 0
        
        for acc in bal_df['account'].unique():
            acc_df = bal_df[bal_df['account'] == acc].copy()
            if acc_df.empty: continue
            
            start_nav = acc_df['net_liquidation'].iloc[0]
            end_nav = acc_df['net_liquidation'].iloc[-1]
            
            acc_flow = cf_df[cf_df['account'] == acc]['amount'].sum() if not cf_df.empty else 0
            legacy_flow = acc_df['total_cash'].sum() 
            
            total_acc_flow = acc_flow + legacy_flow
            delta_pnl = end_nav - start_nav - total_acc_flow
            
            global_start_nav += start_nav
            global_end_nav += end_nav
            global_total_flow += total_acc_flow
            
            print(f"       - {acc}: End NAV (${end_nav:,.0f}) - Start NAV (${start_nav:,.0f}) - Flows (${total_acc_flow:,.0f}) = PnL: ${delta_pnl:,.2f}")
            
        global_delta_pnl = global_end_nav - global_start_nav - global_total_flow
        print(f"\n[*] 4. GLOBAL DELTA-NAV PNL: ${global_delta_pnl:,.2f}")
            
    except Exception as e:
        print(f"[*] 3. Failed to calculate Delta-NAV: {e}")

    conn.close()
    print("========================================================\n")

if __name__ == "__main__":
    run_audit()