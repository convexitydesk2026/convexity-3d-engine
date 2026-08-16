"""
===============================================================================
PROJECT: LoteCalc DR (B2B PropTech SaaS)
FILE: spatial_engine.py
VERSION: 1.1 (Dynamic Cloud Paths)
DATE: August 03, 2026
AUTHOR: P1 (Lead PropTech Developer)
===============================================================================
"""
import os
import json
from shapely.geometry import shape, Point

# CRITICAL FIX: Dynamic Path for Cloud Deployment
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
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
            
    return None