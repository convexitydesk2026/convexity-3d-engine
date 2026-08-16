"""
=============================================================================
Script Name: Telegram_Notifier_v5.py
Purpose: Headless Streamlit rendering and Telegram transmission.
         - Starts the dashboard in the background invisibly.
         - Waits 30 seconds for YFinance & Monte Carlo to complete.
         - FIX: Launches a 7000px tall canvas to force full rendering.
         - FIX: Dynamically measures and crops the viewport to exactly mimic 
                the "Go Full Page" extension, eliminating cropping.
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
    streamlit_process = subprocess.Popen(["streamlit", "run", "dashboard_v15.py", "--server.port", "8599", "--server.headless", "true"],
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
            
            # THE FIX PART 1: Start with a massive 7000px height. 
            # This forces Streamlit to draw all 8 panels immediately, defeating internal scrollbars.
            context = browser.new_context(viewport={'width': 1920, 'height': 7000}, device_scale_factor=2)        
            page = context.new_page()
            
            print("[NOTIFIER] Loading Dashboard...")
            page.goto("http://localhost:8599")
            
            print("[NOTIFIER] Waiting 30 seconds for YFinance and Monte Carlo to render...")
            page.wait_for_timeout(30000)
            
            # THE FIX PART 2: Dynamic Crop. 
            # Find the true pixel height of the rendered content, and shrink the 7000px canvas 
            # down to fit perfectly so there is no dead white space at the bottom.
            try:
                # '.block-container' is the specific internal Streamlit wrapper containing your dashboard
                exact_height = page.evaluate('document.querySelector(".block-container").scrollHeight')
                page.set_viewport_size({"width": 1920, "height": exact_height + 150})
                print(f"[NOTIFIER] Dashboard true height calculated: {exact_height}px. Cropping canvas...")
            except Exception as e:
                print(f"[NOTIFIER] Dynamic crop skipped, defaulting to 7000px. {e}")
            
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