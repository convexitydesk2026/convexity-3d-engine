"""
===============================================================================
PROJECT: LoteCalc DR (B2B PropTech SaaS)
FILE: real_estate_math.py
VERSION: 1.0
DATE: August 02, 2026
AUTHOR: P1 (Lead PropTech Developer) & P2 (Financial Modeler)

LOCAL PATH: 
C:\\Users\\donca\\Desktop\\Desktop HP Envy x360 al 22Abr24\\Docs Manuel\\IBKR_Options\\lotecalc\\real_estate_math.py

DESCRIPTION:
The core mathematical and architectural engine for LoteCalc DR. It ingests 
physical lot dimensions and zoning constraints to calculate maximum buildable 
envelope, strict parking geometry (with ramp/core deductions), and outputs 
a 24-36 month cashflow waterfall (Unlevered IRR & ROC) or Residual Land Value.

USAGE:
This is a module. It is NOT run directly. It is imported by the frontend 
(app.py) to process user inputs and database queries.
Example: from real_estate_math import FeasibilityEngine
===============================================================================
"""

import math
import numpy_financial as npf

class FeasibilityEngine:
    def __init__(self, width, depth, zoning_data, project_type, finish_quality, asking_price=None):
        self.width = float(width)
        self.depth = float(depth)
        self.gross_lot_area = self.width * self.depth
        self.zoning = zoning_data
        self.asking_price = float(asking_price) if asking_price else None
        
        # P2's Project Type Divisors (Inhabitants per unit)
        self.unit_divisors = {"Studio/1BR Heavy": 2, "2BR Standard": 3, "3BR Family Heavy": 4.5}
        self.inhab_per_unit = self.unit_divisors.get(project_type, 3)
        
        # P2's Hard Cost Assumptions
        self.hard_costs = {"Ultra": 2000, "High": 1800, "Medium": 1200, "Economical": 1000}
        self.cost_per_m2 = self.hard_costs.get(finish_quality, 1200)
        
        # Standard Assumptions
        self.efficiency_ratio = 0.80
        self.soft_cost_ratio = 0.12
        self.itbis_rate = 0.10
        self.sales_commission = 0.05
        self.sale_price_per_m2 = 2800 # Default Piantini average for MVP
        
        self.warnings = []

    def calculate_physical_envelope(self):
        # 1. Footprint Constraints
        zoning_footprint = self.gross_lot_area * self.zoning['Huella_Max_pct']
        
        setback_width = self.width - (2 * self.zoning['Lindero_Lateral_m'])
        setback_depth = self.depth - self.zoning['Lindero_Frontal_m'] - self.zoning['Lindero_Posterior_m']
        setback_footprint = max(0, setback_width * setback_depth)
        
        buildable_footprint = min(zoning_footprint, setback_footprint)
        
        # 2. Gross Areas
        gba = buildable_footprint * self.zoning['Altura_Max_levels']
        gsa = gba * self.efficiency_ratio
        
        # 3. Zoning Max Units (Density is per Hectare. 1 Ha = 10,000 m2)
        max_inhabitants = (self.gross_lot_area / 10000) * self.zoning['Densidad_Max_hab_ha']
        zoning_max_units = math.floor(max_inhabitants / self.inhab_per_unit)
        
        return gba, gsa, zoning_max_units

    def calculate_parking(self):
        # P2's Strict Parking Geometry
        if self.width < 17.0:
            return 0, "FATAL ERROR: Lot width under 17m. Cannot fit 2 rows of parking."
            
        # Determine Rows
        rows = 3 if self.width >= 28.75 else 2
        
        # Determine Levels (Max 3 underground)
        max_levels = 3 if self.width >= 19.0 else 1
        if max_levels == 3:
            self.warnings.append("Underground parking capped at 3 levels to avoid water/rock.")
            
        # Spaces per row (using total depth for underground lot-to-lot digging)
        spaces_per_row = math.floor(self.depth / 2.75)
        gross_spaces_per_level = spaces_per_row * rows
        
        # Deductions: 2 for core, 6 for ramp
        net_spaces_per_level = gross_spaces_per_level - 2 - 6
        total_parking_spaces = net_spaces_per_level * max_levels
        
        return total_parking_spaces, "Success"

    def run_feasibility(self):
        gba, gsa, zoning_max_units = self.calculate_physical_envelope()
        total_parking, parking_status = self.calculate_parking()
        
        if total_parking == 0:
            return {"Status": parking_status}
            
        # P2's Gap 4: Demand vs Supply Auto-Reduction
        # Assuming 1.5 parking spaces required per unit on average
        parking_max_units = math.floor(total_parking / 1.5)
        
        if parking_max_units < zoning_max_units:
            buildable_units = parking_max_units
            self.warnings.append(f"Zoning allows {zoning_max_units} units, but parking limits project to {buildable_units} units.")
        else:
            buildable_units = zoning_max_units

        # Timeline Logic
        levels = self.zoning['Altura_Max_levels']
        months = 24 if levels <= 8 else (30 if levels <= 12 else 36)

        # Financials
        gross_revenue = gsa * self.sale_price_per_m2
        hard_costs = gba * self.cost_per_m2
        soft_costs = hard_costs * self.soft_cost_ratio
        itbis = hard_costs * self.itbis_rate
        commissions = gross_revenue * self.sales_commission
        
        total_construction_cost = hard_costs + soft_costs + itbis + commissions

        # User Intent Routing (Asking Price vs Residual Land Value)
        if self.asking_price:
            # Calculate IRR
            monthly_cost = total_construction_cost / months
            monthly_revenue = gross_revenue / months # Assuming linear 100% presale
            
cashflow = [-self.asking_price] # Month 0
            for _ in range(months):
                cashflow.append(monthly_revenue - monthly_cost)
                
            irr = npf.irr(cashflow) * 12 # Annualized
            
            # Handle negative/non-existent IRR gracefully
            if math.isnan(irr) or irr < 0:
                irr_display = "N/A (Negative Return)"
            else:
                irr_display = round(irr * 100, 2)
                
            roc = (gross_revenue - total_construction_cost - self.asking_price) / (total_construction_cost + self.asking_price)
            
            return {
                "Status": "Viable",
                "Buildable_Units": buildable_units,
                "GSA_m2": round(gsa, 2),
                "Total_Parking": total_parking,
                "Timeline_Months": months,
                "Total_Cost": round(total_construction_cost, 2),
                "Gross_Revenue": round(gross_revenue, 2),
                "ROC": round(roc * 100, 2),
                "IRR": irr_display,
                "Warnings": self.warnings
            }
        else:
            # Calculate Residual Land Value (Targeting 20% ROC)
            # Formula: (Revenue - Costs - Land) / (Costs + Land) = 0.20
            max_land_value = (gross_revenue - (1.20 * total_construction_cost)) / 1.20
            
            return {
                "Status": "Valuation Mode",
                "Buildable_Units": buildable_units,
                "GSA_m2": round(gsa, 2),
                "Total_Parking": total_parking,
                "Max_Land_Value": round(max_land_value, 2),
                "Warnings": self.warnings
            }