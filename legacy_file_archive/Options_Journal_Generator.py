"""
=============================================================================
Script Name: Options_Journal_Generator.py
Purpose: Generates a standardized Excel (.xlsx) journal for tracking the 
         Family Office XSP Put Credit Spread Options Ladder.
Author: Chief Investment Officer AI Advisor
Date: March 2026

How to Run:
1. Ensure Python is installed on your Windows PC.
2. Save this script as 'Options_Journal_Generator.py' in your designated folder:
   C:\\Users\\donca\\Desktop\\Desktop HP Envy x360 al 22Abr24\\Docs Manuel\\IBKR_Options
3. Open your Command Prompt (cmd) or run it directly from your Python IDE 
   (such as VS Code, PyCharm, or Jupyter).
4. The script will automatically check for the required libraries (pandas, openpyxl).
   If they are missing, it will install them automatically.
5. The script will output the blank Excel template to your exact folder path.
=============================================================================
"""

import os
import sys
import subprocess

# ---------------------------------------------------------
# Step 1: Auto-Install Missing Libraries
# ---------------------------------------------------------
def install_packages():
    """Checks for required libraries and installs them via pip if missing."""
    required_packages =['pandas', 'openpyxl']
    for package in required_packages:
        try:
            __import__(package)
        except ImportError:
            print(f"Missing library '{package}' detected. Installing now...")
            subprocess.check_call([sys.executable, "-m", "pip", "install", package])
            print(f"'{package}' successfully installed.")

# Run the installation check before proceeding
install_packages()

# Now we can safely import pandas
import pandas as pd

# ---------------------------------------------------------
# Step 2: Define the Exact Directory and File Path
# ---------------------------------------------------------
target_directory = r"C:\Users\donca\Desktop\Desktop HP Envy x360 al 22Abr24\Docs Manuel\IBKR_Options"
file_name = "XSP_Options_Journal.xlsx"
full_file_path = os.path.join(target_directory, file_name)

# Create the directory if it does not already exist on your PC
if not os.path.exists(target_directory):
    os.makedirs(target_directory)
    print(f"Created new directory: {target_directory}")

# ---------------------------------------------------------
# Step 3: Define the Journal Columns
# ---------------------------------------------------------
columns =[
    "Tranche ID", 
    "Open Date", 
    "Ticker", 
    "VIX at Entry", 
    "DTE at Entry", 
    "Short Strike", 
    "Long Strike", 
    "Quantity", 
    "Premium Collected (USD)", 
    "Collateral Locked (USD)", 
    "Total Net Credit (USD)", 
    "Target 50% Exit Price (USD)", 
    "Close Date", 
    "Closing Price (USD)", 
    "Days in Trade", 
    "Total P&L (USD)", 
    "Return on Capital (ROC) %", 
    "Annualized ROC %", 
    "Notes / Adjustments"
]

# ---------------------------------------------------------
# Step 4: Generate and Save the Excel File
# ---------------------------------------------------------
try:
    # Create an empty DataFrame using the specified columns
    df = pd.DataFrame(columns=columns)
    
    # Save the DataFrame to the specific path
    df.to_excel(full_file_path, index=False, engine='openpyxl')
    
    print("\n========================================================")
    print(f"SUCCESS! The Options Journal has been created.")
    print(f"Location: {full_file_path}")
    print("========================================================")

except PermissionError:
    print("\nERROR: Permission denied. If the Excel file is currently open on your PC, please close it and run the script again.")
except Exception as e:
    print(f"\nAn unexpected error occurred: {e}")