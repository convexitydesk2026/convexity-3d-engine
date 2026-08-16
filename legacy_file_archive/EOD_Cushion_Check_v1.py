"""
=============================================================================
Script Name: EOD_Cushion_Check_v1.py
Purpose: Enforces the Minervini "Day 1 Squat" and Trend Retest rules.
         Runs at 3:30 PM ET to check if Open Alpha Campaigns are negative.
         - v1: Fixed SQL query to recognize 'Open 🟢' emoji strings.
=============================================================================
"""
import sqlite3
import pandas as pd
import yfinance as yf
import requests
import configparser
import os
import datetime

TARGET_DIR = r"C:\Users\donca\Desktop\Desktop HP Envy x360 al 22Abr24\Docs Manuel\IBKR_Options"
DB_PATH = os.path.join(TARGET_DIR, 'estate_data.db')
CONFIG_PATH = os.path.join(TARGET_DIR, 'estate_config.ini')

def run_cushion_check():
    print("[*] Initiating 3:30 PM EOD Cushion Check...")
    
    config = configparser.ConfigParser()
    config.read(CONFIG_PATH)
    try:
        TELEGRAM_TOKEN = config['TELEGRAM']['BOT_TOKEN']
        CHAT_ID = config['TELEGRAM']['CHAT_ID']
    except KeyError:
        print("[!] Telegram credentials missing.")
        return

    conn = sqlite3.connect(DB_PATH)
    # Fetch Open campaigns (Fixed to include emoji strings)
    df_open = pd.read_sql_query("SELECT symbol, entry_price, initial_stop, days_active FROM alpha_campaigns WHERE status IN ('Open 🟢', 'Open')", conn)
    conn.close()

    if df_open.empty:
        print("[+] No Open Alpha Campaigns to check.")
        return

    critical_alerts = []
    warning_alerts = []

    for _, row in df_open.iterrows():
        sym = row['symbol']
        entry = float(row['entry_price'])
        stop = float(row['initial_stop'])
        days_active = int(row['days_active'])

        try:
            # Fetch live price
            clean_sym = sym.split()[0]
            live_price = float(yf.Ticker(clean_sym).history(period='1d')['Close'].iloc[-1])
            
            # Check if price is negative on the trade, but hasn't hit the hard stop yet
            if stop < live_price < entry:
                if days_active == 0:
                    critical_alerts.append(f"🚨 **DAY 1 SQUAT (KILL):** {sym} is trading at ${live_price:.2f} (Below Entry: ${entry:.2f}). The breakout failed. Close immediately before the bell.")
                else:
                    warning_alerts.append(f"⚠️ **TREND RETEST:** {sym} is trading at ${live_price:.2f} (Below Entry: ${entry:.2f}). Verify moving average support.")
        except Exception as e:
            print(f"[!] Could not fetch live price for {sym}: {e}")

    # Compile and send Telegram message
    msg_parts = []
    if critical_alerts:
        msg_parts.append("🔥 **CRITICAL EOD ACTION REQUIRED** 🔥\n" + "\n".join(critical_alerts))
    if warning_alerts:
        msg_parts.append("📉 **PORTFOLIO WARNINGS**\n" + "\n".join(warning_alerts))

    if msg_parts:
        alert_text = "\n\n".join(msg_parts)
        url_msg = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
        payload_msg = {"chat_id": CHAT_ID, "text": alert_text, "parse_mode": "Markdown"}
        requests.post(url_msg, data=payload_msg)
        print("[+] EOD Alerts transmitted to Telegram.")
    else:
        print("[+] All Open Campaigns have a positive EOD cushion. No alerts needed.")

if __name__ == "__main__":
    run_cushion_check()