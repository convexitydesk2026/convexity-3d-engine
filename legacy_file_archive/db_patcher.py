import sqlite3
import os

DB_PATH = r"C:\Users\donca\Desktop\Desktop HP Envy x360 al 22Abr24\Docs Manuel\IBKR_Options\estate_data.db"

def patch_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    # Grab the healthy NAV from May 5
    c.execute("SELECT net_liquidation FROM daily_balances WHERE account='U23139264' AND date='2026-05-05'")
    healthy_nav = c.fetchone()[0]
    
    # Overwrite the corrupted May 6 row
    c.execute("UPDATE daily_balances SET net_liquidation = ? WHERE account='U23139264' AND date='2026-05-06'", (healthy_nav,))
    conn.commit()
    conn.close()
    print("[+] DB Patched! The May 6th glitch is smoothed over.")

if __name__ == '__main__':
    patch_db()