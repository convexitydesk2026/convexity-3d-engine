"""
===============================================================================
PROJECT: LoteCalc DR (B2B PropTech SaaS)
FILE: usage_logger.py
VERSION: 1.0
DATE: August 02, 2026
AUTHOR: P1 (Lead PropTech Developer)

LOCAL PATH: 
C:\\Users\\donca\\Desktop\\Desktop HP Envy x360 al 22Abr24\\Docs Manuel\\IBKR_Options\\lotecalc\\usage_logger.py

DESCRIPTION:
Logs report generation events to the SQLite database for analytics and billing.
===============================================================================
"""
import os
import sqlite3

BASE_DIR = r"C:\Users\donca\Desktop\Desktop HP Envy x360 al 22Abr24\Docs Manuel\IBKR_Options\lotecalc"
DB_PATH = os.path.join(BASE_DIR, 'zoning_dr.db')

def log_report_generation(user_id, sector_id, report_type):
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO usage_logs (user_id, sector_id, report_type) VALUES (?, ?, ?)",
            (user_id, sector_id, report_type)
        )
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"Logging failed: {e}") # Fails silently so it doesn't crash the user's app