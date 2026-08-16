@echo off
echo ========================================================
echo        ESTATE MASTER: AUTOMATED 7:15 PM SYNC
echo ========================================================
cd "C:\\Users\\donca\\Desktop\\Desktop HP Envy x360 al 22Abr24\\Docs Manuel\\IBKR_Options"

echo [*] Triggering TWS Live Sync Engine...
python sync_engine_v36.py

echo [*] Triggering PnL Attribution Engine...
python attribution_engine_v24.py

echo [*] Triggering Flex Ledger Engine...
python flex_ledger_engine_v2.py

echo [*] Triggering Institutional Market Flow Engine...
python market_flow_engine_v7.py

echo [*] Triggering Dashboard Render and Telegram Notifier...
python Telegram_Notifier_v31.py

echo [ok] Sequence Complete.