import json
import os
import requests
import configparser
from fastapi import FastAPI, Request
from pydantic import BaseModel
import uvicorn

app = FastAPI()

# Load Configuration
config = configparser.ConfigParser()
config_path = r"C:\Users\donca\Desktop\Desktop HP Envy x360 al 22Abr24\Docs Manuel\IBKR_Options\estate_config.ini"
config.read(config_path)

# Telegram Configuration
TELEGRAM_TOKEN = config.get("TELEGRAM", "bot_token", fallback="")
TELEGRAM_CHAT_ID = config.get("TELEGRAM", "chat_id", fallback="")
DB_PATH = "goat_database.json"

# Initialize database if it doesn't exist
if not os.path.exists(DB_PATH):
    default_data = [
        {"Ticker": "ARMK", "Trap Type": "Earnings Gap Anchor", "AVWAP Level": 58.15, "Status": "⏳ Waiting for Flush", "Risk/Reward": "1:15"},
        {"Ticker": "AVTR", "Trap Type": "Recent Pivot High", "AVWAP Level": 13.90, "Status": "⏳ Waiting for Flush", "Risk/Reward": "TBD"},
        {"Ticker": "BNY", "Trap Type": "Earnings Gap Anchor", "AVWAP Level": 160.25, "Status": "⏳ Waiting for Flush", "Risk/Reward": "TBD"},
        {"Ticker": "RBRK", "Trap Type": "August 4 Catalyst", "AVWAP Level": 93.50, "Status": "⏳ Waiting for Flush", "Risk/Reward": "1:10"},
        {"Ticker": "XNCR", "Trap Type": "July 17 Gap Anchor", "AVWAP Level": 24.30, "Status": "⏳ Waiting for Flush", "Risk/Reward": "1:5"},
    ]
    with open(DB_PATH, "w") as f:
        json.dump(default_data, f, indent=4)


def send_telegram_message(message: str):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": message,
        "parse_mode": "Markdown"
    }
    try:
        response = requests.post(url, json=payload)
        response.raise_for_status()
        print("Telegram message sent successfully.")
    except Exception as e:
        print(f"Failed to send Telegram message: {e}")

@app.post("/webhook")
async def tradingview_webhook(request: Request):
    """
    Receives webhook from TradingView, updates the database, and sends a Telegram alert.
    Expected JSON from TradingView:
    {
        "ticker": "{{ticker}}",
        "close": "{{close}}",
        "interval": "{{interval}}"
    }
    """
    try:
        data = await request.json()
        ticker = data.get("ticker", "UNKNOWN")
        price = data.get("close", "UNKNOWN")
        interval = data.get("interval", "UNKNOWN")
        
        # 1. Update the Dashboard Database
        with open(DB_PATH, "r") as f:
            db_data = json.load(f)
            
        updated = False
        for entry in db_data:
            if entry["Ticker"] == ticker:
                entry["Status"] = "🚨 Bouncing - Active"
                updated = True
                
        if updated:
            with open(DB_PATH, "w") as f:
                json.dump(db_data, f, indent=4)
            print(f"Updated Dashboard DB for {ticker}")
        else:
            print(f"Ticker {ticker} not found in DB.")

        # 2. Send Telegram Alert
        message = (
            f"🔔 *GOAT Alpha Engine Alert*\n"
            f"*{ticker}* has flushed into the trap!\n"
            f"Price: {price}\n"
            f"Timeframe: {interval}\n\n"
            f"Action: Check 5m chart for a reclaim and enter trade.\n"
            f"[View Chart](https://www.tradingview.com/chart/)"
        )
        send_telegram_message(message)
        
        return {"status": "success", "message": f"Processed alert for {ticker}"}
        
    except Exception as e:
        print(f"Error processing webhook: {e}")
        return {"status": "error", "message": str(e)}

if __name__ == "__main__":
    print("Starting Convexity Webhook Server on port 8000...")
    uvicorn.run(app, host="0.0.0.0", port=8000)
