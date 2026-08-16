"""
Script: db_scrubber.py
Purpose: Purges corrupted cash flows and attribution history while preserving live positions and the options journal.
"""
import sqlite3
import shutil
import os

TARGET_DIR = r"C:\Users\donca\Desktop\Desktop HP Envy x360 al 22Abr24\Docs Manuel\IBKR_Options"
DB_PATH = os.path.join(TARGET_DIR, "estate_data.db")
BACKUP_PATH = os.path.join(TARGET_DIR, "estate_data_backup.db")

def scrub_database():
    print("\n===========================================")
    print("   ESTATE DATABASE SCRUBBER (CLEAN SLATE)")
    print("===========================================")
    
    if not os.path.exists(DB_PATH):
        print(f"[!] Database not found at {DB_PATH}")
        return

    print("[*] 1. Creating fail-safe database backup...")
    shutil.copy2(DB_PATH, BACKUP_PATH)
    print(f"    -> Backup saved to: estate_data_backup.db")

    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    print("[*] 2. Purging manual cash transfer injections (Transitioning to IBKR Flex)...")
    c.execute("DROP TABLE IF EXISTS cash_transfers")
    
    print("[*] 3. Purging flawed PnL Attribution ledger...")
    c.execute("DROP TABLE IF EXISTS daily_attribution")

    # We intentionally leave daily_balances, daily_positions, open_orders, and options_journal intact.
    
    conn.commit()
    
    print("[*] 4. Vacuuming database to reclaim sector space...")
    c.execute("VACUUM")
    
    conn.close()
    print("\n[+] SUCCESS: Database scrubbed successfully. The Estate is ready for the Flex Query injection.\n")

if __name__ == "__main__":
    scrub_database()