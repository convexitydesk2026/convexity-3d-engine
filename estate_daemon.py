"""
=============================================================================
Script Name: estate_daemon.py
Purpose: Native System Tray Daemon & Timezone-Aware Scheduler.
         Replaces Run_Estate_Sync.bat and Windows Task Scheduler.
         Uses Option B (Subprocess Isolation) for maximum stability.
         - UPDATE: Pointed launch_dashboard to dashboard_pro.py
=============================================================================
"""
import os
import sys
import subprocess
import threading
import pytz
from datetime import datetime
from apscheduler.schedulers.background import BackgroundScheduler
import pystray
from PIL import Image, ImageDraw
from estate_env import TARGET_DIR

# Define the strict Eastern Timezone anchor
EST = pytz.timezone('US/Eastern')

def run_script(script_name):
    """Runs a python script in a detached subprocess."""
    script_path = os.path.join(TARGET_DIR, script_name)
    if os.path.exists(script_path):
        print(f"[{datetime.now(EST).strftime('%H:%M:%S')}] Launching {script_name}...")
        try:
            subprocess.Popen([sys.executable, script_name], cwd=TARGET_DIR)
        except Exception as e:
            print(f"[!] Failed to launch {script_name}: {e}")
    else:
        print(f"[!] Error: {script_name} not found in {TARGET_DIR}")

def run_eod_cushion_check():
    run_script("EOD_Cushion_Check.py")

def run_price_monitor_job():
    """Runs the intraday price monitor between 9:30 AM and 4:00 PM EST."""
    now = datetime.now(EST).time()
    market_open = datetime.strptime("09:30", "%H:%M").time()
    market_close = datetime.strptime("16:00", "%H:%M").time()
    if market_open <= now <= market_close:
        run_script("price_monitor_engine.py")

def run_morning_publishing():
    """Executes the 7:00 AM ET morning publishing sequence."""
    def sequence():
        scripts = [
            "market_flow_engine.py",
            "ghost_publisher.py",
            "Telegram_Notifier.py"
        ]
        for script in scripts:
            script_path = os.path.join(TARGET_DIR, script)
            if os.path.exists(script_path):
                print(f"[{datetime.now(EST).strftime('%H:%M:%S')}] Running {script}...")
                try:
                    subprocess.run([sys.executable, script], cwd=TARGET_DIR, check=True)
                except subprocess.CalledProcessError as e:
                    print(f"[!] Error executing {script}: {e}")
                    break
            else:
                print(f"[!] Error: {script} not found.")
        print(f"[{datetime.now(EST).strftime('%H:%M:%S')}] Morning Publishing Sequence Complete.")
        
    threading.Thread(target=sequence, daemon=True).start()

def run_full_sync_sequence():
    """Executes the full 7:15 PM sync sequence sequentially in a background thread."""
    def sequence():
        scripts = [
            "sync_engine.py",
            "attribution_engine.py",
            "flex_ledger_engine.py",
            "Telegram_Notifier.py"
        ]
        for script in scripts:
            script_path = os.path.join(TARGET_DIR, script)
            if os.path.exists(script_path):
                print(f"[{datetime.now(EST).strftime('%H:%M:%S')}] Running {script}...")
                try:
                    # Use run() to wait for completion before starting the next script
                    subprocess.run([sys.executable, script], cwd=TARGET_DIR, check=True)
                except subprocess.CalledProcessError as e:
                    print(f"[!] Error executing {script}: {e}")
                    break # Halt the sequence if a critical engine fails
            else:
                print(f"[!] Error: {script} not found.")
        print(f"[{datetime.now(EST).strftime('%H:%M:%S')}] Full Sync Sequence Complete.")
        
    # Run the blocking sequence in a separate thread so the system tray doesn't freeze
    threading.Thread(target=sequence, daemon=True).start()

def launch_dashboard():
    """Launches the Streamlit dashboard."""
    print(f"[{datetime.now(EST).strftime('%H:%M:%S')}] Launching Dashboard...")
    try:
        subprocess.Popen([sys.executable, "-m", "streamlit", "run", "dashboard_pro.py"], cwd=TARGET_DIR)
    except Exception as e:
        print(f"[!] Failed to launch dashboard: {e}")

def create_image():
    """Creates a simple geometric icon for the system tray."""
    image = Image.new('RGB', (64, 64), color=(15, 23, 42)) # Dark slate background
    d = ImageDraw.Draw(image)
    d.rectangle([16, 16, 48, 48], fill=(59, 130, 246)) # Blue square
    return image

def setup_scheduler():
    """Initializes the APScheduler anchored to US/Eastern."""
    scheduler = BackgroundScheduler(timezone=EST)
    
    # Intraday Price Monitor (Mon-Fri, Every Minute)
    scheduler.add_job(run_price_monitor_job, 'cron', day_of_week='mon-fri', hour='9-16', minute='*')
    
    # 7:00 AM ET: Morning Publishing Sequence (Mon-Fri)
    scheduler.add_job(run_morning_publishing, 'cron', day_of_week='mon-fri', hour=7, minute=0)
    
    # 3:30 PM ET: EOD Cushion Check (Mon-Fri)
    scheduler.add_job(run_eod_cushion_check, 'cron', day_of_week='mon-fri', hour=15, minute=30)
    
    # 7:15 PM ET: Full Estate Sync (Mon-Fri)
    scheduler.add_job(run_full_sync_sequence, 'cron', day_of_week='mon-fri', hour=19, minute=15)
    
    scheduler.start()
    return scheduler

def on_quit(icon, item):
    """Gracefully shuts down the daemon."""
    print("Shutting down Estate Daemon...")
    scheduler.shutdown(wait=False)
    icon.stop()

if __name__ == "__main__":
    print("========================================================")
    print("   ESTATE DAEMON INITIALIZED (Timezone: US/Eastern)")
    print("========================================================")
    
    # Start the background scheduler
    scheduler = setup_scheduler()
    
    # Build the System Tray Menu
    menu = pystray.Menu(
        pystray.MenuItem("Launch Dashboard", lambda: launch_dashboard()),
        pystray.Menu.SEPARATOR,
        pystray.MenuItem("Run Morning Publishing Now", lambda: run_morning_publishing()),
        pystray.MenuItem("Run EOD Cushion Check Now", lambda: run_eod_cushion_check()),
        pystray.MenuItem("Run Full Estate Sync Now", lambda: run_full_sync_sequence()),
        pystray.Menu.SEPARATOR,
        pystray.MenuItem("Exit", on_quit)
    )
    
    # Launch the System Tray Icon (This blocks the main thread)
    icon = pystray.Icon("EstateDaemon", create_image(), "Estate Master Daemon", menu)
    icon.run()