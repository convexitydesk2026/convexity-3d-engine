"""
===============================================================================
PROJECT: LoteCalc DR (B2B PropTech SaaS)
FILE: db_builder.py
VERSION: 1.1 (Updated for CSV Ingestion)
DATE: August 02, 2026
AUTHOR: P1 (Lead PropTech Developer)

LOCAL PATH: 
C:\\Users\\donca\\Desktop\\Desktop HP Envy x360 al 22Abr24\\Docs Manuel\\IBKR_Options\\lotecalc\\db_builder.py

DESCRIPTION:
Reads the 'poligono_central_master.csv' file managed by the admin and 
converts it into the secure local SQLite database (zoning_dr.db).
===============================================================================
"""
import os
import sqlite3
import pandas as pd

BASE_DIR = r"C:\Users\donca\Desktop\Desktop HP Envy x360 al 22Abr24\Docs Manuel\IBKR_Options\lotecalc"
DB_PATH = os.path.join(BASE_DIR, 'zoning_dr.db')
CSV_PATH = os.path.join(BASE_DIR, 'poligono_central_master.csv')

def build_database():
    print(f"Reading CSV from: {CSV_PATH}")
    if not os.path.exists(CSV_PATH):
        print("ERROR: CSV file not found. Please create poligono_central_master.csv first.")
        return

    df = pd.read_csv(CSV_PATH)
    conn = sqlite3.connect(DB_PATH)
    df.to_sql('zoning_parameters', conn, if_exists='replace', index=False)
    
    # Create Usage Logs Table while we are connected
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS usage_logs (
            log_id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
            user_id TEXT,
            sector_id TEXT,
            report_type TEXT
        )
    ''')
    
    print("Database built successfully! Zoning and Logging tables created.")
    conn.close()

if __name__ == "__main__":
    build_database()