"""
=============================================================================
Script Name: estate_env.py
Purpose: Centralized, dynamic environment pathing for the Estate Architecture.
         Eradicates hardcoded local directories to ensure 100% portability.
=============================================================================
"""
import os

# Dynamically resolve the directory where this script is located
TARGET_DIR = os.path.dirname(os.path.abspath(__file__))

# Define central paths used across all Estate scripts
DB_PATH = os.path.join(TARGET_DIR, "estate_data.db")
CONFIG_PATH = os.path.join(TARGET_DIR, "estate_config.ini")

# Optional: Define future export directories for the Publisher Pipeline
EXPORT_DIR = os.path.join(TARGET_DIR, "exports")

# Ensure the export directory exists
if not os.path.exists(EXPORT_DIR):
    os.makedirs(EXPORT_DIR)