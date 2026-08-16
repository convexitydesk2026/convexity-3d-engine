@echo off
echo ========================================================
echo        ESTATE MASTER: AUTOMATED 4:15 PM SYNC
echo ========================================================

cd "C:\Users\donca\Desktop\Desktop HP Envy x360 al 22Abr24\Docs Manuel\IBKR_Options"

echo [*] Triggering TWS Live Sync Engine...
python sync_engine_v23.py

echo [*] Triggering PnL Attribution Engine...
python attribution_engine.py

echo [*] Triggering Dashboard Render and Telegram Notifier...
python Telegram_Notifier_v11.py

echo [ok] Sequence Complete.