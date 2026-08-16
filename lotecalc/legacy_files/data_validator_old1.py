"""
===============================================================================
PROJECT: LoteCalc DR (B2B PropTech SaaS)
FILE: data_validator.py
VERSION: 1.0
DATE: August 02, 2026
AUTHOR: P1 (Lead PropTech Developer)

LOCAL PATH: 
C:\\Users\\donca\\Desktop\\Desktop HP Envy x360 al 22Abr24\\Docs Manuel\\IBKR_Options\\lotecalc\\data_validator.py

DESCRIPTION:
Sanitizes and validates all user inputs before they hit the math engine.
===============================================================================
"""

def validate_lot_inputs(width, depth, asking_price_str):
    errors = []
    
    # Validate Width
    try:
        w = float(width)
        if w <= 0: errors.append("Lot width must be greater than 0.")
        if w > 200: errors.append("Lot width exceeds maximum supported size (200m).")
    except ValueError:
        errors.append("Invalid lot width. Please enter a number.")

    # Validate Depth
    try:
        d = float(depth)
        if d <= 0: errors.append("Lot depth must be greater than 0.")
    except ValueError:
        errors.append("Invalid lot depth. Please enter a number.")

    # Validate Asking Price (Optional Input)
    p = None
    if asking_price_str and str(asking_price_str).strip() != "":
        try:
            # Remove commas and dollar signs if user typed them
            clean_price = str(asking_price_str).replace(',', '').replace('$', '').strip()
            p = float(clean_price)
            if p < 10000: errors.append("Asking price seems too low. Minimum is $10,000.")
        except ValueError:
            errors.append("Invalid asking price. Please enter numbers only.")

    return {"is_valid": len(errors) == 0, "errors": errors, "clean_data": (w, d, p) if len(errors) == 0 else None}