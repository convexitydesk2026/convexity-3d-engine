import sqlite3
import os

DB_PATH = r"C:\Users\donca\Desktop\Desktop HP Envy x360 al 22Abr24\Docs Manuel\IBKR_Options\estate_data.db"

def heal_dates():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    
    c.execute("SELECT rowid, close_date FROM champion_closed_trades")
    rows = c.fetchall()
    
    fixed_count = 0
    for rowid, old_date in rows:
        if old_date and len(old_date) == 8 and '-' not in old_date:
            new_date = f"{old_date[:4]}-{old_date[4:6]}-{old_date[6:]}"
            c.execute("UPDATE champion_closed_trades SET close_date=? WHERE rowid=?", (new_date, rowid))
            fixed_count += 1
            
    conn.commit()
    print(f"[+] Successfully healed {fixed_count} historical dates in the ledger.")
    conn.close()

if __name__ == '__main__':
    heal_dates()