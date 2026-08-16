@echo off
echo ========================================================
echo        ESTATE MASTER: AUTOMATED 7:15 PM SYNC
echo ========================================================
cd /d "%~dp0"

echo [*] Triggering TWS Live Sync Engine...
python sync_engine_v39.py

echo [*] Triggering PnL Attribution Engine...
python attribution_engine_v25.py

echo [*] Triggering Flex Ledger Engine...
python flex_ledger_engine_v5.py

echo [*] Triggering Institutional Market Flow Engine...
python market_flow_engine_v8.py

echo [*] Triggering Dashboard Render and Telegram Notifier...
python Telegram_Notifier_v38.py

echo [ok] Sequence Complete.