import sqlite3
import pandas as pd

conn = sqlite3.connect("estate_data.db")
try:
    df = pd.read_sql_query("SELECT date, COUNT(symbol) as position_count FROM daily_positions GROUP BY date", conn)
    df['date'] = pd.to_datetime(df['date'])
    df['month'] = df['date'].dt.to_period('M')
    print("\n--- POSITIONS RECORDED PER MONTH ---")
    print(df.groupby('month')['position_count'].sum())
except Exception as e:
    print("Error:", e)
conn.close()