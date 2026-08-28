"""
=============================================================================
Script Name: price_monitor_engine.py
Purpose: Intraday daemon to fetch live prices via yfinance, evaluate EP/GOAT 
         thresholds, and fire Telegram push notifications.
=============================================================================
"""

import os
import sqlite3
import pandas as pd
import yfinance as yf
import datetime
import requests
import configparser
import logging

from estate_env import DB_PATH, CONFIG_PATH

# Suppress yfinance warnings
logging.getLogger('yfinance').setLevel(logging.CRITICAL)

# Load configurations
config = configparser.ConfigParser()
config.read(CONFIG_PATH)

# Using .get to avoid KeyError if section doesn't exist yet in user's config
try:
    TELEGRAM_TOKEN = config['TELEGRAM']['BOT_TOKEN']
    CHAT_ID = config['TELEGRAM']['CHAT_ID']
except KeyError:
    TELEGRAM_TOKEN = ""
    CHAT_ID = ""

def send_telegram_alert(message):
    if not TELEGRAM_TOKEN or not CHAT_ID:
        print(f"[NOTIFIER] Telegram Token/Chat ID missing. Would have sent: {message}")
        return
        
    try:
        url_msg = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
        payload_msg = {"chat_id": CHAT_ID, "text": message, "parse_mode": "Markdown"}
        response = requests.post(url_msg, data=payload_msg)
        if response.status_code != 200:
            print(f"[ERROR] Failed to send Telegram alert: {response.text}")
    except Exception as e:
        print(f"[ERROR] Telegram exception: {e}")

def run_price_monitor():
    print(f"[{datetime.datetime.now().strftime('%H:%M:%S')}] Executing Price Monitor Engine...")
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    
    # --- 1. Evaluate GOAT Oven (200 SMA Target) ---
    try:
        df_goat = pd.read_sql_query("SELECT * FROM goat_oven WHERE alert_sent = 0", conn)
        if not df_goat.empty:
            tickers_goat = df_goat['ticker'].tolist()
            # Fetch live prices
            data_goat = yf.download(tickers_goat, period="1d", interval="1m", progress=False, auto_adjust=False)
            
            for _, row in df_goat.iterrows():
                ticker = row['ticker']
                target_sma = float(row['target_sma'])
                
                if target_sma == 0.0:
                    continue
                
                try:
                    if len(tickers_goat) == 1:
                        # yfinance structure differs when there's only 1 ticker
                        live_price = float(data_goat['Close'].iloc[-1])
                    else:
                        live_price = float(data_goat['Close'][ticker].iloc[-1])
                        
                    if live_price >= target_sma:
                        msg = f"🍳 *GOAT OVEN ALERT ({ticker}):*\nLive Price (${live_price:.2f}) has breached your 200 SMA Target (${target_sma:.2f})."
                        print(msg)
                        send_telegram_alert(msg)
                        c.execute("UPDATE goat_oven SET alert_sent = 1 WHERE ticker = ?", (ticker,))
                        conn.commit()
                except Exception as e:
                    print(f"[!] Error processing GOAT {ticker}: {e}")
    except Exception as e:
        print(f"[!] Error fetching goat_oven data: {e}")

    # --- 2. Evaluate EP Waiting Room (ORB High + RVol) ---
    try:
        df_ep = pd.read_sql_query("SELECT * FROM ep_waiting_room WHERE alert_sent = 0", conn)
        if not df_ep.empty:
            for _, row in df_ep.iterrows():
                ticker = row['ticker']
                orb_high = float(row['orb_high']) if pd.notna(row.get('orb_high')) else 0.0
                rvol_target = float(row['rvol_target']) if pd.notna(row.get('rvol_target')) else 300.0
                
                if orb_high == 0.0:
                    continue # Skip if no valid ORB high is set
                    
                try:
                    # Fetch 5-minute intraday data
                    data_5m = yf.download(ticker, period="1d", interval="5m", progress=False, auto_adjust=False)
                    if data_5m.empty:
                        continue
                        
                    # Fetch daily data for 14-day ADV
                    data_daily = yf.download(ticker, period="1mo", interval="1d", progress=False, auto_adjust=False)
                    if len(data_daily) < 14:
                        continue
                        
                    if isinstance(data_5m.columns, pd.MultiIndex):
                        # For a single ticker in yfinance >= 0.2.x, it's not MultiIndex usually, but just in case
                        close_series = data_5m['Close'].squeeze()
                        vol_series = data_5m['Volume'].squeeze()
                    else:
                        close_series = data_5m['Close']
                        vol_series = data_5m['Volume']
                        
                    if isinstance(data_daily.columns, pd.MultiIndex):
                        daily_vol_series = data_daily['Volume'].squeeze()
                    else:
                        daily_vol_series = data_daily['Volume']
                        
                    live_price = float(close_series.iloc[-1])
                    
                    if live_price >= orb_high:
                        # Price breached, now calculate RVol for the first 5-min candle
                        first_5m_vol = float(vol_series.iloc[0])
                        adv_14 = float(daily_vol_series.tail(14).mean())
                        avg_5m_vol = adv_14 / 78.0 # Assuming 78 5-min bars in a day
                        
                        rvol_pct = (first_5m_vol / avg_5m_vol) * 100 if avg_5m_vol > 0 else 0
                        
                        if rvol_pct >= rvol_target:
                            msg = (f"⚡ *EP ORB BREAKOUT ({ticker}):*\n"
                                   f"Live Price: ${live_price:.2f} (Target: ${orb_high:.2f})\n"
                                   f"Opening 5-min RVol: {rvol_pct:.0f}% (Target: {rvol_target:.0f}%)")
                            print(msg)
                            send_telegram_alert(msg)
                            c.execute("UPDATE ep_waiting_room SET alert_sent = 1 WHERE ticker = ?", (ticker,))
                            conn.commit()
                except Exception as e:
                    print(f"[!] Error processing EP {ticker}: {e}")
    except Exception as e:
        print(f"[!] Error fetching ep_waiting_room data: {e}")
        
    conn.close()

if __name__ == "__main__":
    run_price_monitor()
