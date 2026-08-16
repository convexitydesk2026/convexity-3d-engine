"""
=============================================================================
Script Name: Telegram_Notifier_v18.py
Purpose: Headless Streamlit rendering and Telegram transmission.
         - UPDATED: Handled NoneType DB casting to prevent crash loops.
         - UPDATED: Pointing to dashboard_v72.py.
=============================================================================
"""

import os
import time
import requests
import configparser
import subprocess
import sqlite3
import pandas as pd
import datetime
import yfinance as yf
from playwright.sync_api import sync_playwright

# --- 1. Load Configurations ---
TARGET_DIR = r"C:\Users\donca\Desktop\Desktop HP Envy x360 al 22Abr24\Docs Manuel\IBKR_Options"
CONFIG_PATH = os.path.join(TARGET_DIR, 'estate_config.ini')
DB_PATH = os.path.join(TARGET_DIR, 'estate_data.db')

config = configparser.ConfigParser()
config.read(CONFIG_PATH)

TELEGRAM_TOKEN = config['TELEGRAM']['BOT_TOKEN']
CHAT_ID = config['TELEGRAM']['CHAT_ID']
REPORT_PATH = os.path.join(TARGET_DIR, "Estate_Briefing.png")

def evaluate_cfo_alerts():
    print("[NOTIFIER] Scanning for Priority CFO Alerts...")
    priority_alerts = []
    
    try:
        conn = sqlite3.connect(DB_PATH)
        today = datetime.date.today()
        
        # 1. Eve of Destruction (22-DTE) Alert
        try:
            journal_df = pd.read_sql_query("SELECT * FROM options_journal", conn)
            open_trades = journal_df[pd.isnull(journal_df['Close Date']) | (journal_df['Close Date'] == '')]
            for _, row in open_trades.iterrows():
                try:
                    open_date = datetime.datetime.strptime(row['Open Date'], '%Y-%m-%d').date()
                    dte_at_entry = int(row['DTE at Entry'])
                    days_in_trade = (today - open_date).days
                    dte_rem = dte_at_entry - days_in_trade
                    
                    if dte_rem == 22:
                        priority_alerts.append(f"⚡ *EVE OF DESTRUCTION (22 DTE):*\nContract {row['Ticker']} ({row['Short Strike']}/{row['Long Strike']}) hits the Gamma Cliff tomorrow. Prepare for mechanical ejection.")
                except Exception:
                    pass
        except Exception as e:
            print(f"  [!] Failed to evaluate 22-DTE alerts: {e}")

        # 2. Alpha Conviction Watchlist Alert (FIXED: Bulletproof casting)
        try:
            wl_df = pd.read_sql_query("SELECT * FROM alpha_watchlist", conn)
            for _, row in wl_df.iterrows():
                c_iv = float(row['current_iv']) if pd.notna(row['current_iv']) else 0.0
                t_iv = float(row['target_iv']) if pd.notna(row['target_iv']) else 0.0
                
                if c_iv >= t_iv and c_iv > 0:
                    priority_alerts.append(f"🎯 *ALPHA OPPORTUNITY ({row['symbol']}):*\nLive IV ({c_iv:.1f}%) has breached your target ({t_iv:.1f}%). Ready for Conviction CSPs.")
        except Exception as e:
            print(f"  [!] Failed to evaluate Alpha Watchlist alerts: {e}")

        conn.close()
    except Exception as e:
        print(f"  [!] Database connection failed for alerts: {e}")

    # 3. VIX Crush Alert
    try:
        vix_live = float(yf.Ticker('^VIX').history(period='1d')['Close'].iloc[-1])
        if vix_live < 15.0:
            priority_alerts.append(f"🟢 *VIX CRUSH DETECTED (VIX: {vix_live:.2f}):*\nTail insurance is historically cheap! Check your Dashboard for exact Tail Hedge budget tranches to deploy today.")
    except Exception as e:
        print(f"  [!] Failed to fetch live VIX: {e}")

    if priority_alerts:
        print(f"[NOTIFIER] {len(priority_alerts)} Priority Alerts found. Transmitting push notification...")
        alert_text = "🚨 *VIRTUAL CFO PRIORITY ALERTS* 🚨\n\n" + "\n\n".join(priority_alerts)
        url_msg = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
        payload_msg = {"chat_id": CHAT_ID, "text": alert_text, "parse_mode": "Markdown"}
        requests.post(url_msg, data=payload_msg)
    else:
        print("[NOTIFIER] No priority alerts triggered today.")

def snap_and_send():
    evaluate_cfo_alerts()
    
    print("\n[NOTIFIER] Spinning up headless Streamlit server (Invisible Background Process)...")
    # API FIX: Pointing to dashboard_v72.py
    streamlit_process = subprocess.Popen(["streamlit", "run", "dashboard_v72.py", "--server.port", "8599", "--server.headless", "true"],
        cwd=TARGET_DIR,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL
    )
    
    print("[NOTIFIER] Waiting for local server to boot...")
    time.sleep(12)
    
    try:
        print("[NOTIFIER] Launching invisible Playwright browser...")
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            context = browser.new_context(viewport={'width': 1920, 'height': 8500}, device_scale_factor=2)        
            page = context.new_page()
            
            print("[NOTIFIER] Loading Dashboard...")
            page.goto("http://localhost:8599")
            print("[NOTIFIER] Waiting 40 seconds for external API feeds and Monte Carlo to render...")
            page.wait_for_timeout(40000)

            print("[NOTIFIER] Scrolling down to force rendering of lazy-loaded UI components...")
            for _ in range(5):
                page.mouse.wheel(0, 2000)
                page.wait_for_timeout(1000)
                
            print("[NOTIFIER] Snapping back to the top of the dashboard...")
            page.evaluate("window.scrollTo(0, 0)")
            page.wait_for_timeout(2000)
            
            try:
                exact_height = page.evaluate('document.querySelector(".block-container").scrollHeight')
                page.set_viewport_size({"width": 1920, "height": exact_height + 150})
                print(f"[NOTIFIER] Dashboard true height calculated: {exact_height}px. Cropping canvas...")
            except Exception as e:
                print(f"[NOTIFIER] Dynamic crop skipped, defaulting to 8500px. {e}")
            
            print("[NOTIFIER] Snapping Lossless 4K Full-Page Screenshot...")
            page.screenshot(path=REPORT_PATH, full_page=True)
            browser.close()
            
        print("[NOTIFIER] Transmitting to Telegram...")
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendDocument"
        
        with open(REPORT_PATH, "rb") as image_file:
            payload = {"chat_id": CHAT_ID, "caption": "📊 *EOD Estate Briefing*\nAutomated TWS Sync Complete. Systems nominal.", "parse_mode": "Markdown"}
            files = {"document": image_file}
            response = requests.post(url, data=payload, files=files)
            if response.status_code == 200: print("[OK] Dashboard delivered to Telegram.")
            else: print(f"[ERROR] Telegram Transmission Failed: {response.text}")
                
    finally:
        print("[NOTIFIER] Shutting down background server...")
        streamlit_process.terminate()
        if os.path.exists(REPORT_PATH): os.remove(REPORT_PATH)

if __name__ == "__main__":
    snap_and_send()