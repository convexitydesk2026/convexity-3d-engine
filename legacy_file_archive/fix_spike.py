import sqlite3

conn = sqlite3.connect("estate_data.db")
c = conn.cursor()

# Delete the corrupted backfill data from May 7th onward
c.execute("DELETE FROM daily_attribution WHERE date >= '2026-05-07'")
conn.commit()
conn.close()

print("Corrupted spike removed! You can now re-run the attribution engine.")