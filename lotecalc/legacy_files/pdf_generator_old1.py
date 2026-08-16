"""
===============================================================================
PROJECT: LoteCalc DR (B2B PropTech SaaS)
FILE: pdf_generator.py
VERSION: 1.0
DATE: August 03, 2026
AUTHOR: P1 (Lead PropTech Developer)

LOCAL PATH: 
C:\\Users\\donca\\Desktop\\Desktop HP Envy x360 al 22Abr24\\Docs Manuel\\IBKR_Options\\lotecalc\\pdf_generator.py

DESCRIPTION:
Generates a branded PDF tear-sheet from the feasibility engine results.
===============================================================================
"""
import os
import tempfile
from fpdf import FPDF

def generate_tear_sheet(results, inputs):
    pdf = FPDF()
    pdf.add_page()
    
    # --- HEADER ---
    pdf.set_font('Arial', 'B', 16)
    pdf.set_text_color(0, 122, 255) # LoteCalc Blue
    pdf.cell(0, 10, 'LoteCalc DR - Financial Tear-Sheet', 0, 1, 'C')
    pdf.ln(5)
    
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
    
    # --- 2. ARCHITECTURAL METRICS ---
    pdf.set_font('Arial', 'B', 12)
    pdf.cell(0, 10, '2. Architectural Feasibility', 0, 1)
    
    pdf.set_font('Arial', '', 11)
    pdf.cell(0, 8, f"Status: {results['Status']}", 0, 1)
    if results['Status'] != "FATAL ERROR":
        pdf.cell(0, 8, f"Buildable Units: {results.get('Buildable_Units', 0)}", 0, 1)
        pdf.cell(0, 8, f"Total Parking Spaces: {results.get('Total_Parking', 0)}", 0, 1)
        pdf.cell(0, 8, f"Gross Sellable Area (GSA): {results.get('GSA_m2', 0):,.0f} m2", 0, 1)
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
        pdf.ln(10)
        pdf.set_font('Arial', 'B', 12)
        pdf.set_text_color(200, 0, 0) # Red
        pdf.cell(0, 10, 'Architectural Warnings:', 0, 1)
        
        pdf.set_font('Arial', '', 11)
        for w in results['Warnings']:
            pdf.cell(0, 8, f"- {w}", 0, 1)
            
    # Save to a temporary file and read as bytes (Bulletproof method for Streamlit)
    temp_path = os.path.join(tempfile.gettempdir(), "lotecalc_report.pdf")
    pdf.output(temp_path)
    
    with open(temp_path, "rb") as f:
        pdf_bytes = f.read()
        
    return pdf_bytes