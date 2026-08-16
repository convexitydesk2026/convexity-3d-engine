# ==============================================================================
# File: C:/Users/donca/Desktop/Desktop HP Envy x360 al 22Abr24/Docs Manuel/IBKR_Options/quant/launch_dashboard_v2.py
# Version: 2.0
# Description: Securely reads the DB .ini file and launches the Optuna dashboard.
# ==============================================================================

import configparser
import subprocess

# Point to your existing INI file
DB_CONFIG_PATH = r"C:\ORB20\Scripts\Py_scripts\DB_upload_config.ini"

def launch_dashboard():
    config = configparser.ConfigParser()
    config.read(DB_CONFIG_PATH)
    
    db_creds = config['database']
    
    # Optuna Dashboard uses 'postgresql://' not 'postgresql+psycopg2://'
    dashboard_url = f"postgresql://{db_creds['username']}:{db_creds['password']}@{db_creds['host']}:{db_creds['port']}/optuna_studies"
    
    print("Launching Optuna Dashboard...")
    print("Go to http://127.0.0.1:8080/ in your web browser.")
    print("Press Ctrl+C in this window to stop the dashboard server.")
    
    subprocess.run(["optuna-dashboard", dashboard_url])

if __name__ == "__main__":
    launch_dashboard()