import sqlite3
import os

DB_PATH = r"C:\Users\donca\Desktop\Desktop HP Envy x360 al 22Abr24\Docs Manuel\IBKR_Options\estate_data.db"

def revert_rxt():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    
    c.execute("""
        UPDATE alpha_campaigns 
        SET status='Pending Settlement ⏳', 
            close_date=NULL, 
            total_pnl=0.0, 
            r_multiple=0.0, 
            grade=NULL 
        WHERE symbol='RXT' AND status='Closed'
    """)
    
    conn.commit()
    print(f"[+] Success! Reverted {c.rowcount} RXT campaign(s) back to Pending Settlement.")
    conn.close()

if __name__ == '__main__':
    revert_rxt()