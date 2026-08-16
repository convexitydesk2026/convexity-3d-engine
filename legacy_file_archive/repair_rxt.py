import sqlite3
import os

DB_PATH = os.path.join(r"C:\Users\donca\Desktop\Desktop HP Envy x360 al 22Abr24\Docs Manuel\IBKR_Options", "estate_data.db")

conn = sqlite3.connect(DB_PATH)
c = conn.cursor()

# Revert the RXT trade back to 'Open' and erase the incorrect grading
c.execute("""
    UPDATE alpha_campaigns 
    SET status='Open', close_date=NULL, total_pnl=0.0, r_multiple=0.0, grade='' 
    WHERE symbol='RXT' AND status='Closed'
""")

conn.commit()
conn.close()

print("[+] SUCCESS: RXT Campaign has been unlocked and reverted to 'Open'.")