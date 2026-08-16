"""
===============================================================================
PROJECT: LoteCalc DR (B2B PropTech SaaS)
FILE: data_validator.py
VERSION: 1.1 (Added Permuta Percentage)
DATE: August 03, 2026
AUTHOR: P1 (Lead PropTech Developer)

LOCAL PATH: 
C:\\Users\\donca\\Desktop\\Desktop HP Envy x360 al 22Abr24\\Docs Manuel\\IBKR_Options\\lotecalc\\data_validator.py
===============================================================================
"""

def validate_lot_inputs(width, depth, asking_price_str, permuta_pct_str="0"):
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
            clean_price = str(asking_price_str).replace(',', '').replace('$', '').strip()
            p = float(clean_price)
            if p < 10000: errors.append("Asking price seems too low. Minimum is $10,000.")
        except ValueError:
            errors.append("Invalid asking price. Please enter numbers only.")

    # Validate Permuta Percentage
    permuta_pct = 0.0
    if permuta_pct_str and str(permuta_pct_str).strip() != "":
        try:
            clean_pct = str(permuta_pct_str).replace('%', '').strip()
            permuta_pct = float(clean_pct)
            if permuta_pct < 0 or permuta_pct > 100:
                errors.append("Permuta percentage must be between 0 and 100.")
        except ValueError:
            errors.append("Invalid permuta percentage.")

    return {
        "is_valid": len(errors) == 0, 
        "errors": errors, 
        "clean_data": (w, d, p, permuta_pct) if len(errors) == 0 else None
    }