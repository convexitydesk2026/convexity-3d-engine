"""
=============================================================================
Script Name: flex_ledger_engine_v5.py
Purpose: Automated Historical Trade Ingestion via IBKR Flex Query API.
         - v5 FIX: Auto-Healing Mechanism. Detects orphan trades missing from 
           the Accountability Journal and retroactively injects them.
         - v4 FIX: Integrated estate_env.py for dynamic OS-agnostic pathing.
         - v3 FIX: Dynamic Silo Generation. Parses estate_config.ini to map 
           historical trades to user-defined aliases instead of hardcoded strings.
         - v2 FIX: Defeated the ASCII Date Trap by explicitly formatting YYYYMMDD.
=============================================================================
"""
import sqlite3
import pandas as pd
from ib_insync import FlexReport
import configparser
import os
import hashlib
import xml.etree.ElementTree as ET
from estate_env import TARGET_DIR, DB_PATH, CONFIG_PATH

def get_base_nav(symbol, account):
    """Fetches the locked-in Base NAV from when the trade was opened."""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT base_nav FROM champion_state WHERE symbol=? AND account=?", (symbol, account))
    row = c.fetchone()
    conn.close()
    return row[0] if row else 200000.0  # Generic fallback if historical state wasn't tracked

def run_flex_sync():
    print("========================================================")
    print("   ESTATE FLEX QUERY ENGINE v5 - AUTO-HEALING ENABLED")
    print("========================================================")
    
    # 1. Setup Database & Safely add Unique Hash Column (to prevent double counting)
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA journal_mode=WAL;")
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS champion_closed_trades 
                 (close_date TEXT, symbol TEXT, account TEXT, silo TEXT, 
                  r_base REAL, realized_pnl REAL, r_multiple REAL, notes TEXT, tags TEXT)''')
    try:
        # Add the column without the UNIQUE keyword to satisfy SQLite rules
        c.execute("ALTER TABLE champion_closed_trades ADD COLUMN trade_hash TEXT")
    except sqlite3.OperationalError:
        pass # Column already exists
        
    # Enforce uniqueness using an Index instead
    c.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_trade_hash ON champion_closed_trades(trade_hash)")
    conn.commit()

    # 2. Get Token, Query ID, and Dynamic Silo Map
    config = configparser.ConfigParser()
    config.read(CONFIG_PATH)
    try:
        token = config['IBKR']['TOKEN']
        query_id = config['IBKR']['EXEC_QUERY_ID']
    except KeyError as e:
        print(f"[!] Configuration Error: Could not find {e} in estate_config.ini.")
        return

    SILO_MAP = {}
    if 'SILOS' in config:
        for acc, val in config['SILOS'].items():
            parts = val.split('|')
            SILO_MAP[acc.upper()] = parts[0]

    # 3. Pull Data (API or Local Fallback)
    local_xml = os.path.join(TARGET_DIR, "Estate_Execution_Ledger.xml")
    trades = []
    
    if os.path.exists(local_xml):
        print("[*] Local XML file detected. Bypassing API and parsing local file...")
        tree = ET.parse(local_xml)
        root = tree.getroot()
        for trade in root.iter('Trade'):
            trades.append(trade.attrib)
    else:
        print(f"[*] Requesting Query ID {query_id} from IBKR Servers (This may take up to 60 seconds)...")
        try:
            report = FlexReport(token, query_id)
            df_report = report.df('Trade')
            if not df_report.empty:
                trades = df_report.to_dict('records')
        except Exception as e:
            print(f"[!] API Failed: {e}. Download the XML manually from IBKR and place it in the folder.")
            return

    if not trades:
        print("[+] No trades found in report.")
        return

    df = pd.DataFrame(trades)
    
    # 4. Filter for Alpha Trades (Exclude Options & Zero PnL)
    # Dynamically hunt for IBKR's hidden PnL column name
    pnl_col = next((c for c in df.columns if c.lower() in ['realizedpnl', 'fifopnlrealized', 'fifopnl', 'mtmpnl', 'mtmpnlrealized']), None)

    if pnl_col:
        df['realizedPnl'] = pd.to_numeric(df[pnl_col], errors='coerce').fillna(0.0)
        df_closed = df[df['realizedPnl'] != 0.0].copy()
    else:
        print("[!] No PnL column found. Here are the columns IBKR provided in the XML:")
        print(df.columns.tolist())
        return

    # Keep only Stocks and CFDs for the Champion Journal
    cat_col = next((c for c in df.columns if c.lower() in ['assetcategory', 'sectype']), 'assetCategory')
    if cat_col in df_closed.columns:
        df_closed = df_closed[df_closed[cat_col].isin(['STK', 'CFD', 'CRYPTO'])]

    if df_closed.empty:
        print("[+] No closed Alpha trades found in this timeframe.")
        return

    # 5. Process and Insert
    inserts = 0
    duplicates = 0
    healed = 0
    
    for _, row in df_closed.iterrows():
        sym = str(row.get('symbol', 'UNKNOWN')).upper()
        acc = str(row.get('accountId', 'UNKNOWN'))
        pnl = float(row['realizedPnl'])
        date_str = str(row.get('dateTime', str(row.get('tradeDate', ''))))
        
        # Create a unique cryptographic hash for this specific execution
        hash_str = f"{date_str}_{sym}_{acc}_{pnl}"
        trade_hash = hashlib.md5(hash_str.encode()).hexdigest()
        
        silo = SILO_MAP.get(acc, acc)
        base_nav = get_base_nav(sym, acc)
        r_base = base_nav * 0.0025
        r_multiple = pnl / r_base if r_base > 0 else 0
        
        # ASCII Date Trap Fix: Convert YYYYMMDD to YYYY-MM-DD
        raw_date = str(row.get('tradeDate', date_str)).split(';')[0]
        if len(raw_date) == 8 and '-' not in raw_date:
            formatted_date = f"{raw_date[:4]}-{raw_date[4:6]}-{raw_date[6:8]}"
        else:
            formatted_date = raw_date[:10]
        
        try:
            c.execute('''INSERT INTO champion_closed_trades 
                         (close_date, symbol, account, silo, r_base, realized_pnl, r_multiple, notes, tags, trade_hash) 
                         VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''', 
                      (formatted_date, sym, acc, silo, r_base, pnl, r_multiple, "", "", trade_hash))
            inserts += 1
            
            # --- AUTO-HEALING MECHANISM ---
            # Check if this trade exists in the Accountability Journal
            c.execute('''SELECT id FROM alpha_campaigns 
                         WHERE symbol = ? AND (
                             status IN ('Open 🟢', 'Open', 'Pending Settlement ⏳', 'Pending Settlement') OR 
                             abs(julianday(close_date) - julianday(?)) <= 3
                         )''', (sym, formatted_date))
            
            if not c.fetchone():
                # Orphan trade detected! Inject retroactive campaign.
                c.execute('''INSERT INTO alpha_campaigns 
                             (symbol, type, status, open_date, close_date, regime_in, sector, industry, 
                              sma_20, sma_50, sma_200, entry_price, initial_stop, tags, thesis, 
                              days_active, total_pnl, r_multiple, grade) 
                             VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
                          (sym, 'Unknown', 'Closed (Auto-Healed) 🩹', formatted_date, formatted_date, 
                           'Unknown', 'Unknown', 'Unknown', 0.0, 0.0, 0.0, 0.0, 0.0, '', 
                           'Auto-healed from clearinghouse ledger. Missing thesis.', 
                           0, pnl, r_multiple, 'Auto-Healed 🩹'))
                healed += 1
                
        except sqlite3.IntegrityError:
            duplicates += 1 # Hash already exists, silently ignore

    conn.commit()
    conn.close()
    
    print(f"[+] Flex Sync Complete! {inserts} new trades ingested. {healed} orphan trades auto-healed. ({duplicates} historical trades skipped).")

if __name__ == '__main__':
    run_flex_sync()