"""
===============================================================================
PROJECT: LoteCalc DR (B2B PropTech SaaS)
FILE: pdf_generator.py
VERSION: 1.8 (Default Logo & Branding)
DATE: August 03, 2026
AUTHOR: P1 (Lead PropTech Developer)
===============================================================================
"""
import os
import json
import tempfile
import urllib.request
import urllib.error
from fpdf import FPDF

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
ASSUMPTIONS_PATH = os.path.join(BASE_DIR, 'market_assumptions.json')
DEFAULT_LOGO_PATH = os.path.join(BASE_DIR, 'default_logo.jpg')

def generate_tear_sheet(results, inputs):
    pdf = FPDF()
    pdf.add_page()
    
    # --- BROKER BRANDING HEADER ---
    logo_to_print = None
    
    if inputs.get('broker_logo'):
        ext = inputs.get('logo_ext', 'png')
        logo_path = os.path.join(tempfile.gettempdir(), f"broker_logo_temp.{ext}")
        with open(logo_path, "wb") as f:
            f.write(inputs['broker_logo'])
        logo_to_print = logo_path
    elif os.path.exists(DEFAULT_LOGO_PATH):
        # Fallback to LoteCalc default logo
        logo_to_print = DEFAULT_LOGO_PATH
        
    if logo_to_print:
        try:
            pdf.image(logo_to_print, x=10, y=8, h=15)
        except Exception:
            pass 
            
    pdf.set_font('Arial', 'B', 16)
    pdf.set_text_color(0, 122, 255) 
    
    align = 'R' if logo_to_print else 'C'
    pdf.cell(0, 8, 'LoteCalc DR - Financial Tear-Sheet', 0, 1, align)
    
    pdf.set_font('Arial', '', 10)
    pdf.set_text_color(100, 100, 100) 
    
    # Default Text Logic
    b_name = inputs.get('broker_name', '').strip()
    b_phone = inputs.get('broker_phone', '').strip()
    
    if b_name or b_phone:
        name_part = b_name if b_name else "Independent Broker"
        phone_part = f" | {b_phone}" if b_phone else ""
        broker_text = f"Prepared by: {name_part}{phone_part}"
    else:
        broker_text = "Prepared by LoteCalc | lotecalc.com | 1-809-000-0000"
        
    pdf.cell(0, 6, broker_text, 0, 1, align)
    pdf.ln(8)
    
    # --- STATIC MAP IMAGE ---
    lat = inputs.get('lat')
    lon = inputs.get('lon')
    api_key = inputs.get('api_key')
    
    if lat and lon and api_key:
        # CRITICAL FIX: Explicitly request format=png and save as .png
        map_url = f"https://maps.googleapis.com/maps/api/staticmap?center={lat},{lon}&zoom=17&size=600x250&maptype=hybrid&format=png&markers=color:red%7C{lat},{lon}&key={api_key}"
        map_path = os.path.join(tempfile.gettempdir(), "static_map_temp.png")
        
        try:
            req = urllib.request.Request(map_url, headers={'User-Agent': 'Mozilla/5.0'})
            with urllib.request.urlopen(req) as response, open(map_path, 'wb') as out_file:
                out_file.write(response.read())
                
            pdf.image(map_path, x=10, w=190)
            pdf.ln(5)
        except urllib.error.HTTPError as e:
            pdf.set_font('Arial', 'I', 10)
            pdf.set_text_color(200, 0, 0)
            pdf.cell(0, 10, f'(Map Error: Google API returned HTTP {e.code}. Check Static API status.)', 0, 1)
        except Exception as e:
            pdf.set_font('Arial', 'I', 10)
            pdf.set_text_color(200, 0, 0)
            pdf.cell(0, 10, f'(Map Error: {str(e)})', 0, 1)
    
    # --- 1. LOT DETAILS ---
    pdf.set_font('Arial', 'B', 12)
    pdf.set_text_color(0, 0, 0)
    pdf.cell(0, 10, '1. Lot & Project Details', 0, 1)
    
    pdf.set_font('Arial', '', 11)
    pdf.cell(0, 8, f"Sector: {inputs['sector']}", 0, 1)
    pdf.cell(0, 8, f"Dimensions: {inputs['width']}m Frontage x {inputs['depth']}m Depth", 0, 1)
    pdf.cell(0, 8, f"Asking Price: ${inputs['price']:,.2f}", 0, 1)
    pdf.cell(0, 8, f"Permuta (Land Equity): {inputs['permuta']}%", 0, 1)
    pdf.ln(5)
    
    # --- 2. ARCHITECTURAL FEASIBILITY & MATH BREAKDOWN ---
    pdf.set_font('Arial', 'B', 12)
    pdf.cell(0, 10, '2. Architectural Feasibility & Math Breakdown', 0, 1)
    
    pdf.set_font('Arial', '', 11)
    pdf.cell(0, 8, f"Status: {results['Status']}", 0, 1)
    if results['Status'] != "FATAL ERROR":
        pdf.cell(0, 8, f"Gross Sellable Area (GSA): {results.get('GSA_m2', 0):,.0f} m2", 0, 1)
        pdf.cell(0, 8, f"Buildable Units: {results.get('Buildable_Units', 0)} ({results.get('Capping_Reason', '')})", 0, 1)
        pdf.cell(0, 8, f"Average Unit Size: {results.get('Avg_Unit_Size_m2', 0)} m2", 0, 1)
        pdf.cell(0, 8, f"Total Parking Spaces: {results.get('Total_Parking', 0)}", 0, 1)
        pdf.cell(0, 8, f"Parking Distribution: {results.get('Parkings_Per_Unit', 0)} per unit | {results.get('Visitor_Parkings', 0)} visitor spaces", 0, 1)
        pdf.cell(0, 8, f"Estimated Timeline: {results.get('Timeline_Months', 0)} Months", 0, 1)
    pdf.ln(5)
    
    # --- 3. FINANCIAL PROJECTIONS ---
    if results['Status'] == 'Viable':
        pdf.set_font('Arial', 'B', 12)
        pdf.cell(0, 10, '3. Financial Projections', 0, 1)
        
        pdf.set_font('Arial', '', 11)
        pdf.cell(0, 8, f"Gross Revenue: ${results.get('Gross_Revenue', 0):,.2f}", 0, 1)
        pdf.cell(0, 8, f"Total Construction Cost: ${results.get('Total_Cost', 0):,.2f}", 0, 1)
        pdf.cell(0, 8, f"Return on Cost (ROC): {results.get('ROC', 0)}%", 0, 1)
        pdf.cell(0, 8, f"Unlevered IRR: {results.get('IRR', 'N/A')}%", 0, 1)
    elif results['Status'] == 'Valuation Mode':
        pdf.set_font('Arial', 'B', 12)
        pdf.cell(0, 10, '3. Land Valuation', 0, 1)
        pdf.set_font('Arial', '', 11)
        pdf.cell(0, 8, f"Max Viable Land Value: ${results.get('Max_Land_Value', 0):,.2f}", 0, 1)
        
    # --- 4. WARNINGS ---
    if results.get('Warnings'):
        pdf.ln(5)
        pdf.set_font('Arial', 'B', 12)
        pdf.set_text_color(200, 0, 0) 
        pdf.cell(0, 10, 'Architectural Warnings:', 0, 1)
        
        pdf.set_font('Arial', '', 11)
        for w in results['Warnings']:
            pdf.cell(0, 8, f"- {w}", 0, 1)
            
    # --- 5. GLOSSARY & SOURCES ---
    pdf.add_page()
    pdf.set_text_color(0, 0, 0)
    pdf.set_font('Arial', 'B', 12)
    pdf.cell(0, 10, '5. Glossary, Sources & Methodology', 0, 1)
    
    pdf.set_font('Arial', 'B', 10)
    pdf.cell(0, 6, 'Construction Quality Tiers (Hard Costs):', 0, 1)
    pdf.set_font('Arial', '', 9)
    pdf.multi_cell(0, 5, "- Economical: Basic finishes, standard ceramics, MDF doors.\n- Medium: Porcelanato floors, imported modular cabinets.\n- High: Premium porcelanato, semi-precious wood, high-end fixtures.\n- Ultra: Marble/granite floors, solid precious wood, smart home integration.\n(Note: Costs are updated monthly based on local market averages).")
    pdf.ln(3)
    
    pdf.set_font('Arial', 'B', 10)
    pdf.cell(0, 6, 'Parking Regulations:', 0, 1)
    pdf.set_font('Arial', '', 9)
    pdf.multi_cell(0, 5, "Parking dimensions comply with local regulations. Source: MOPC R-002 Estacionamiento Vehicular.\nLink: https://topodata.com/wp-content/uploads/2019/09/R-002-ESTACIONAMIENTO-VEHICULAR_compressed.pdf")
    pdf.ln(3)
    
    pdf.set_font('Arial', 'B', 10)
    pdf.cell(0, 6, f"Market Data (Average Sale Price in {inputs['sector']}):", 0, 1)
    pdf.set_font('Arial', '', 9)
    pdf.multi_cell(0, 5, "The sale price per M2 is the average of publicly available units in this sector. This average is updated weekly. Sources include:")
    
    try:
        with open(ASSUMPTIONS_PATH, 'r') as f:
            market_data = json.load(f)
            
        for i, link in enumerate(market_data.get("reference_links", [])):
            pdf.cell(0, 5, f"{i+1}) {link}", 0, 1)
    except Exception as e:
        pdf.cell(0, 5, "Sources currently unavailable.", 0, 1)

    temp_path = os.path.join(tempfile.gettempdir(), "lotecalc_report.pdf")
    pdf.output(temp_path)
    
    with open(temp_path, "rb") as f:
        pdf_bytes = f.read()
        
    return pdf_bytes