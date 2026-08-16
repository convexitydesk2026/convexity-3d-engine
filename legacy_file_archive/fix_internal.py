import sqlite3

DB_PATH = "estate_data.db"

def fix_internal_transfers():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    
    # The 5 deposits that went into Silo B
    internal_flows = [
        ('2025-12-04', 100.0),
        ('2025-12-05', 210000.0),
        ('2025-12-05', 105000.0),
        ('2025-12-11', 51000.0),
        ('2025-12-11', 153363.0)
    ]
    
    inserts = 0
    for date_str, amount in internal_flows:
        neg_amt = -amount
        # Check if already injected
        c.execute("SELECT * FROM cash_transfers WHERE date=? AND account='U23144948' AND amount=?", (date_str, neg_amt))
        if not c.fetchone():
            c.execute("INSERT INTO cash_transfers VALUES (?, ?, ?, ?, ?)", 
                      (date_str, 'U23144948', neg_amt, "Internal Transfer Out", "Balancing Silo B Funding"))
            inserts += 1
            
    conn.commit()
    conn.close()
    print(f"[+] Fixed {inserts} Internal Transfers out of Silo A.")

if __name__ == '__main__':
    fix_internal_transfers()