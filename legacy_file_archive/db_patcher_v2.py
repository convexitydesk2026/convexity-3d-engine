import sqlite3
import pandas as pd
import os

DB_PATH = r"C:\Users\donca\Desktop\Desktop HP Envy x360 al 22Abr24\Docs Manuel\IBKR_Options\estate_data.db"

def patch_attribution():
    conn = sqlite3.connect(DB_PATH)
    
    # Load raw balances to extract the exact truth
    df_bal = pd.read_sql_query("SELECT * FROM daily_balances ORDER BY date", conn)
    df_attr = pd.read_sql_query("SELECT * FROM daily_attribution ORDER BY date", conn)

    # 1. Calculate Global PnL
    global_df = df_bal.groupby('date').agg({'net_liquidation':'sum', 'total_cash':'sum'}).reset_index()
    global_df['prev_nav'] = global_df['net_liquidation'].shift(1)
    global_df['global_pnl'] = global_df['net_liquidation'] - global_df['total_cash'] - global_df['prev_nav'].fillna(global_df['net_liquidation'] - global_df['total_cash'])

    # 2. Calculate Silo B's Exact PnL (The true Alpha definition)
    silo_b = df_bal[df_bal['account'] == 'U23139264'].sort_values('date').copy()
    silo_b['prev_nav'] = silo_b['net_liquidation'].shift(1)
    silo_b['silo_b_pnl'] = silo_b['net_liquidation'] - silo_b['total_cash'] - silo_b['prev_nav'].fillna(silo_b['net_liquidation'] - silo_b['total_cash'])

    # 3. Merge and Remap
    merged = pd.merge(df_attr, global_df[['date', 'global_pnl']], on='date', how='left')
    merged = pd.merge(merged, silo_b[['date', 'silo_b_pnl']], on='date', how='left').fillna(0)
    
    c = conn.cursor()
    print("[*] Rebalancing historical Attribution Math...")
    
    for idx, row in merged.iterrows():
        d = row['date']
        
        # New a4 is STRICTLY Silo B's PnL
        new_a4 = row['silo_b_pnl']
        
        # New a2 takes the remainder of the equity PnL (absorbing the regional ETFs)
        new_a2 = row['global_pnl'] - (row['a1_yield'] + row['a3_vrp'] + new_a4 + row['a5_fees'])
        
        c.execute('''UPDATE daily_attribution 
                     SET a2_beta = ?, a4_alpha = ? 
                     WHERE date = ?''', (new_a2, new_a4, d))
                     
    conn.commit()
    conn.close()
    print("[+] DB Patched! ETFs moved from a4 to a2 successfully.")

if __name__ == '__main__':
    patch_attribution()