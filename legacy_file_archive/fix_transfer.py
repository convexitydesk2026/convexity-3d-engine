import sqlite3

db_path = "estate_data.db"
conn = sqlite3.connect(db_path)
c = conn.cursor()

# Log Withdrawal for Silo A
c.execute("UPDATE daily_balances SET total_cash = -10000 WHERE date = '2026-05-11' AND account = 'U23144948'")

# Log Deposit for Silo B
c.execute("UPDATE daily_balances SET total_cash = 10000 WHERE date = '2026-05-11' AND account = 'U23139264'")

conn.commit()
conn.close()
print("Cash flows successfully registered! Refresh your dashboard.")