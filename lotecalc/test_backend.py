"""
===============================================================================
PROJECT: LoteCalc DR (B2B PropTech SaaS)
FILE: test_backend.py
VERSION: 1.4 (Restored Verbose Logging + Permuta Pct)
DATE: August 03, 2026
AUTHOR: P1 (Lead PropTech Developer)

LOCAL PATH: 
C:\\Users\\donca\\Desktop\\Desktop HP Envy x360 al 22Abr24\\Docs Manuel\\IBKR_Options\\lotecalc\\test_backend.py

DESCRIPTION:
Simulates a full user journey in the backend without the Streamlit UI. 
Tests GPS spatial matching, database querying, input validation, and the 
updated financial math engine (including Permuta % and 30/70 cashflow).
===============================================================================
"""

import os
import sqlite3
from spatial_engine import get_sector_from_gps
from data_validator import validate_lot_inputs
from real_estate_math import FeasibilityEngine

BASE_DIR = r"C:\Users\donca\Desktop\Desktop HP Envy x360 al 22Abr24\Docs Manuel\IBKR_Options\lotecalc"
DB_PATH = os.path.join(BASE_DIR, 'zoning_dr.db')

def run_full_backend_test():
    print("\n--- STARTING LOTECALC BACKEND INTEGRATION TEST ---\n")

    # STEP 1: Simulate GPS Ping (User is standing in Piantini)
    test_lat = 18.472
    test_lon = -69.932
    print(f"1. Pinging GPS: Lat {test_lat}, Lon {test_lon}")
    
    sector_id = get_sector_from_gps(test_lat, test_lon)
    if not sector_id:
        print("❌ TEST FAILED: GPS point not found in any GeoJSON polygon.")
        return
    print(f"✅ GPS Matched to Sector: {sector_id}")

    # STEP 2: Query the SQLite Database for Zoning Rules
    print(f"\n2. Querying Database for {sector_id} zoning rules...")
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row # Allows us to access columns by name
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM zoning_parameters WHERE Sector_ID = ?", (sector_id,))
    zoning_row = cursor.fetchone()
    conn.close()

    if not zoning_row:
        print(f"❌ TEST FAILED: {sector_id} not found in SQLite database.")
        return
    
    zoning_data = dict(zoning_row)
    print(f"✅ Zoning Data Retrieved: Max Height {zoning_data['Altura_Max_levels']} levels, Density {zoning_data['Densidad_Max_hab_ha']} hab/ha")

    # STEP 3: Simulate User Inputs & Validation
    print("\n3. Simulating User Inputs (Width: 30m, Depth: 40m, Price: $1,500,000, Permuta: 30%)...")
    validation = validate_lot_inputs(width="30", depth="40", asking_price_str="1,500,000", permuta_pct_str="30")
    
    if not validation["is_valid"]:
        print(f"❌ TEST FAILED: Validation Errors: {validation['errors']}")
        return
    
    width, depth, asking_price, permuta_pct = validation["clean_data"]
    print("✅ Inputs Validated Successfully.")

    # STEP 4: Run the Math Engine
    print("\n4. Running Financial Math Engine (With 30/70 Cashflow & 30% Permuta)...")
    engine = FeasibilityEngine(
        width=width, 
        depth=depth, 
        zoning_data=zoning_data, 
        project_type="2BR Standard", 
        finish_quality="Medium", 
        asking_price=asking_price,
        permuta_pct=permuta_pct  # Passing the percentage!
    )
    
    results = engine.run_feasibility()

    # STEP 5: Output Results
    print("\n--- 📊 TEST RESULTS 📊 ---")
    for key, value in results.items():
        if key != "Warnings": # We print warnings separately below
            print(f"{key}: {value}")
    
    if results.get("Warnings"):
        print("\n⚠️ WARNINGS TRIGGERED:")
        for warning in results["Warnings"]:
            print(f" - {warning}")
            
    print("\n--- BACKEND TEST COMPLETE ---\n")

if __name__ == "__main__":
    run_full_backend_test()