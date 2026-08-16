import sqlite3
conn = sqlite3.connect("estate_data.db")
conn.execute("DELETE FROM license_cache")
conn.commit()
print("Cache cleared! The paywall is re-armed.")