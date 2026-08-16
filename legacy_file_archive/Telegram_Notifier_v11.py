"""
=============================================================================
Script Name: Telegram_Notifier_v11.py
Purpose: Headless Streamlit rendering and Telegram transmission.
         - Updated to target dashboard_v46.py
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
REPORT_PATH = os.path.join(TARGET_DIR, "Estate_Briefing.png")

def snap_and_send():
    print("\n[NOTIFIER] Spinning up headless Streamlit server (Invisible Background Process)...")
    streamlit_process = subprocess.Popen(["streamlit", "run", "dashboard_v46.py", "--server.port", "8599", "--server.headless", "true"],
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
            
            # EXPANDED starting canvas to 8500px to account for the larger layout
            context = browser.new_context(viewport={'width': 1920, 'height': 8500}, device_scale_factor=2)        
            page = context.new_page()
            
            print("[NOTIFIER] Loading Dashboard...")
            page.goto("http://localhost:8599")
            
            # EXTENDED wait time to 40 seconds to ensure 10k Monte Carlo and live yFinance network calls finish
            print("[NOTIFIER] Waiting 40 seconds for external API feeds and Monte Carlo to render...")
            page.wait_for_timeout(40000)
            
            # Dynamic Crop
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
        if os.path.exists(REPORT_PATH):
            os.remove(REPORT_PATH)

if __name__ == "__main__":
    snap_and_send()