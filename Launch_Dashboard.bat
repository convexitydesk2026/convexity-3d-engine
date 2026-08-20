@echo off
echo ========================================================
echo        ESTATE MASTER: DASHBOARD LAUNCHER
echo ========================================================
cd /d "%~dp0"
echo [*] Spinning up local Streamlit server...
streamlit run dashboard_pro.py