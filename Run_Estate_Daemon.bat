@echo off
echo ========================================================
echo        ESTATE MASTER: DAEMON LAUNCHER
echo ========================================================
cd /d "%~dp0"
echo [*] Spinning up background daemon...
start /min python estate_daemon.py
exit