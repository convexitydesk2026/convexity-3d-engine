r"""
=============================================================================
Script Name: Estate_Notifier_v1.py
Purpose: Headless browser automation and secure Telegram notification engine.
         - Uses Playwright to render the local Estate Dashboard silently.
         - Waits 3 seconds for Plotly JS charts to complete rendering.
         - Captures a high-resolution, full-page PNG.
         - Securely transmits the snapshot to the CIO's Telegram account 
           via the Telegram Bot API using local credentials.
Author: Chief Investment Officer AI Advisor
Date: May 2026
=============================================================================
"""

import os
import time
import requests
import configparser
from playwright.sync_api import sync_playwright

# --- 1. Load Configurations ---
target_directory = r"C:\Users\donca\Desktop\Desktop HP Envy x360 al 22Abr24\Docs Manuel\IBKR_Options"
config_path = os.path.join(target_directory, 'estate_config.ini')

config = configparser.ConfigParser()
config.read(config_path)

TELEGRAM_TOKEN = config['TELEGRAM']['BOT_TOKEN']
CHAT_ID = config['TELEGRAM']['CHAT_ID']

# Pointing to the latest v59 HTML Dashboard
html_file = f"file:///{os.path.join(target_directory, 'Family_Estate_Dashboard_v59.html').replace(chr(92), '/')}"
screenshot_path = os.path.join(target_directory, "Dashboard_Snapshot.png")

def take_screenshot():
    print("\n[NOTIFIER] Launching Headless Browser...")
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
                
        # device_scale_factor=2 forces 4K Retina resolution
        context = browser.new_context(viewport={'width': 1920, 'height': 2400}, device_scale_factor=2)        
        page = context.new_page()
        
        print(f"[NOTIFIER] Loading Dashboard: {html_file}")
        page.goto(html_file)
        
        # Wait 3 seconds for Plotly charts to finish their drawing animations
        page.wait_for_timeout(3000)
        
        print("[NOTIFIER] Snapping High-Res Screenshot...")
        page.screenshot(path=screenshot_path, full_page=True)
        browser.close()

def send_to_telegram():
    print("[NOTIFIER] Transmitting securely to CIO's Telegram...")
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendDocument"
    
    with open(screenshot_path, "rb") as image_file:
        payload = {
            "chat_id": CHAT_ID,
            "caption": "📊 *Morning Estate Briefing*\nAutomated Sync Complete. Systems nominal.",
            "parse_mode": "Markdown"
        }
        files = {"document": image_file}
        response = requests.post(url, data=payload, files=files)
        
        if response.status_code == 200:
            print("[OK] Dashboard securely delivered to Telegram.")
        else:
            print(f"[ERROR] Telegram Transmission Failed: {response.text}")

if __name__ == "__main__":
    try:
        take_screenshot()
        send_to_telegram()
        
        # Clean up the image file to save disk space
        if os.path.exists(screenshot_path):
            os.remove(screenshot_path)
            
    except Exception as e:
        print(f"[FATAL ERROR] Notifier Pipeline Failed: {e}")