import sqlite3
import os

TARGET_DIR = r"C:\Users\donca\Desktop\Desktop HP Envy x360 al 22Abr24\Docs Manuel\IBKR_Options"
DB_PATH = os.path.join(TARGET_DIR, "estate_data.db")

conn = sqlite3.connect(DB_PATH)
c = conn.cursor()
c.execute("DELETE FROM daily_balances WHERE net_liquidation < 100")
print(f"Database Healed! Removed {c.rowcount} corrupted zero-balance records.")
conn.commit()
conn.close()