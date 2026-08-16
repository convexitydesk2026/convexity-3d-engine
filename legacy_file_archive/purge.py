import sqlite3

DB_PATH = r"C:\Users\donca\Desktop\Desktop HP Envy x360 al 22Abr24\Docs Manuel\IBKR_Options\estate_data.db"
conn = sqlite3.connect(DB_PATH)
c = conn.cursor()

# Surgically delete ONLY the ghost campaigns (where the system failed to log a stop-loss or entry price)
c.execute("DELETE FROM alpha_campaigns WHERE status LIKE '%Pending%' AND (entry_price = 0 OR initial_stop = 0 OR entry_price IS NULL OR initial_stop IS NULL)")
deleted = c.rowcount
conn.commit()
conn.close()

print(f"SUCCESS: {deleted} ghost campaigns permanently purged from the database.")