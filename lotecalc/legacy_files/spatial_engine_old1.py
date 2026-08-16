"""
===============================================================================
PROJECT: LoteCalc DR (B2B PropTech SaaS)
FILE: spatial_engine.py
VERSION: 1.0
DATE: August 02, 2026
AUTHOR: P1 (Lead PropTech Developer)

LOCAL PATH: 
C:\\Users\\donca\\Desktop\\Desktop HP Envy x360 al 22Abr24\\Docs Manuel\\IBKR_Options\\lotecalc\\spatial_engine.py

DESCRIPTION:
Loads the GeoJSON boundary file and uses the 'shapely' library to perform 
Point-in-Polygon calculations. It takes a user's GPS coordinates and returns 
the Sector_ID (e.g., PIAN-01) if they are inside the coverage area.
===============================================================================
"""

import os
import json
from shapely.geometry import shape, Point

BASE_DIR = r"C:\Users\donca\Desktop\Desktop HP Envy x360 al 22Abr24\Docs Manuel\IBKR_Options\lotecalc"
GEOJSON_PATH = os.path.join(BASE_DIR, 'poligono_central.geojson')

def get_sector_from_gps(lat, lon):
    """
    Takes latitude and longitude, checks them against the GeoJSON polygons,
    and returns the Sector_ID. Returns None if outside coverage area.
    """
    if not os.path.exists(GEOJSON_PATH):
        print("ERROR: GeoJSON file not found.")
        return None

    # Load the GeoJSON file
    with open(GEOJSON_PATH, 'r', encoding='utf-8') as f:
        geo_data = json.load(f)

    # Create a Shapely Point (Note: Shapely uses Longitude, Latitude order)
    user_point = Point(lon, lat)

    # Loop through all islands to see which one contains the point
    for feature in geo_data['features']:
        polygon = shape(feature['geometry'])
        if polygon.contains(user_point):
            return feature['properties']['Sector_ID']
            
    # If the loop finishes and no polygon contains the point:
    return None

# --- Quick Test ---
if __name__ == "__main__":
    # Test coordinates inside PIAN-01 dummy data
    test_lat = 18.472
    test_lon = -69.932
    sector = get_sector_from_gps(test_lat, test_lon)
    print(f"Test GPS ({test_lat}, {test_lon}) is in Sector: {sector}")