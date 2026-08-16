"""
=============================================================================
Script Name: Telegram_Notifier_v3.py
Purpose: Headless Streamlit rendering and Telegram transmission.
         - Starts the dashboard_v15.py server in the background.
         - Uses Playwright to render and snap the local web interface.
         - Securely transmits to Telegram, then kills the background server.
=============================================================================
"""

import os
import time
import requests
import configparser
import subprocess
from playwright.sync_api import sync_playwright

# --- 1. Load Configurations ---
TARGET_DIR = r"C:\Users\donca\Desktop\Desktop HP Envy x360 al 22Abr24\Docs Manuel\IBKR_Options"
CONFIG_PATH = os.path.join(TARGET_DIR, 'estate_config.ini')

config = configparser.ConfigParser()
config.read(CONFIG_PATH)

TELEGRAM_TOKEN = config['TELEGRAM']['BOT_TOKEN']
CHAT_ID = config['TELEGRAM']['CHAT_ID']
SCREENSHOT_PATH = os.path.join(TARGET_DIR, "Dashboard_Snapshot.png")

def snap_and_send():
    print("\n[NOTIFIER] Spinning up headless Streamlit server...")
    # Start Streamlit on a custom port to avoid conflicts
    streamlit_process = subprocess.Popen(["streamlit", "run", "dashboard_v15.py", "--server.port", "8599", "--server.headless", "true"],
        cwd=TARGET_DIR,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL
    )
    
    # Give Streamlit 8 seconds to boot up locally
    time.sleep(8)
    
    try:
        print("[NOTIFIER] Launching Playwright browser...")
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            context = browser.new_context(viewport={'width': 1920, 'height': 2800}, device_scale_factor=2)        
            page = context.new_page()
            
            print("[NOTIFIER] Loading Dashboard...")
            page.goto("http://localhost:8599")
            
            # Wait 5 seconds for Plotly charts to finish drawing
            page.wait_for_timeout(5000)
            
            print("[NOTIFIER] Snapping High-Res Screenshot...")
            page.screenshot(path=SCREENSHOT_PATH, full_page=True)
            browser.close()
            
        print("[NOTIFIER] Transmitting to Telegram...")
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendDocument"
        
        with open(SCREENSHOT_PATH, "rb") as image_file:
            payload = {
                "chat_id": CHAT_ID,
                "caption": "📊 *EOD Estate Briefing*\nAutomated TWS Sync Complete. Systems nominal.",
                "parse_mode": "Markdown"
            }
            files = {"document": image_file}
            response = requests.post(url, data=payload, files=files)
            
            if response.status_code == 200:
                print("[OK] Dashboard delivered to Telegram.")
            else:
                print(f"[ERROR] Telegram Transmission Failed: {response.text}")
                
    finally:
        # ALWAYS kill the Streamlit background process
        print("[NOTIFIER] Shutting down background server...")
        streamlit_process.terminate()
        if os.path.exists(SCREENSHOT_PATH):
            os.remove(SCREENSHOT_PATH)

if __name__ == "__main__":
    snap_and_send()