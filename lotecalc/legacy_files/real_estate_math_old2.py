"""
===============================================================================
PROJECT: LoteCalc DR (B2B PropTech SaaS)
FILE: real_estate_math.py
VERSION: 1.2 (Permuta, 30/70 Cashflow, JSON Assumptions)
DATE: August 03, 2026
AUTHOR: P1 (Lead PropTech Developer)
===============================================================================
"""
import os
import json
import math
import numpy_financial as npf

BASE_DIR = r"C:\Users\donca\Desktop\Desktop HP Envy x360 al 22Abr24\Docs Manuel\IBKR_Options\lotecalc"
ASSUMPTIONS_PATH = os.path.join(BASE_DIR, 'market_assumptions.json')

class FeasibilityEngine:
    def __init__(self, width, depth, zoning_data, project_type, finish_quality, asking_price=None, permuta_amount=0):
        self.width = float(width)
        self.depth = float(depth)
        self.gross_lot_area = self.width * self.depth
        self.zoning = zoning_data
        self.asking_price = float(asking_price) if asking_price else None
        self.permuta_amount = float(permuta_amount) if permuta_amount else 0
        
        # Load Manager's Weekly Assumptions
        with open(ASSUMPTIONS_PATH, 'r') as f:
            self.market_data = json.load(f)
            
        self.unit_divisors = {"Studio/1BR Heavy": 2, "2BR Standard": 3, "3BR Family Heavy": 4.5}
        self.inhab_per_unit = self.unit_divisors.get(project_type, 3)
        
        self.cost_per_m2 = self.market_data["hard_costs_usd"].get(finish_quality, 1200)
        self.efficiency_ratio = self.market_data["global_rates"]["efficiency_ratio"]
        self.soft_cost_ratio = self.market_data["global_rates"]["soft_cost_ratio"]
        self.itbis_rate = self.market_data["global_rates"]["itbis_rate"]
        self.sales_commission = self.market_data["global_rates"]["sales_commission"]
        
        # Pulled directly from the new CSV column
        self.sale_price_per_m2 = float(self.zoning.get('Sale_Price_per_m2', 2800))
        
        self.warnings = []

    def calculate_physical_envelope(self):
        zoning_footprint = self.gross_lot_area * self.zoning['Huella_Max_pct']
        setback_width = self.width - (2 * self.zoning['Lindero_Lateral_m'])
        setback_depth = self.depth - self.zoning['Lindero_Frontal_m'] - self.zoning['Lindero_Posterior_m']
        setback_footprint = max(0, setback_width * setback_depth)
        
        buildable_footprint = min(zoning_footprint, setback_footprint)
        gba = buildable_footprint * self.zoning['Altura_Max_levels']
        gsa = gba * self.efficiency_ratio
        
        max_inhabitants = (self.gross_lot_area / 10000) * self.zoning['Densidad_Max_hab_ha']
        zoning_max_units = math.floor(max_inhabitants / self.inhab_per_unit)
        
        return gba, gsa, zoning_max_units

    def calculate_parking(self):
        if self.width < 17.0:
            return 0, "FATAL ERROR: Lot width under 17m. Cannot fit 2 rows of parking."
            
        rows = 3 if self.width >= 28.75 else 2
        max_levels = 3 if self.width >= 19.0 else 1
        if max_levels == 3:
            self.warnings.append("Underground parking capped at 3 levels to avoid water/rock.")
            
        spaces_per_row = math.floor(self.depth / 2.75)
        gross_spaces_per_level = spaces_per_row * rows
        net_spaces_per_level = gross_spaces_per_level - 2 - 6
        total_parking_spaces = net_spaces_per_level * max_levels
        
        return total_parking_spaces, "Success"

    def run_feasibility(self):
        gba, gsa, zoning_max_units = self.calculate_physical_envelope()
        total_parking, parking_status = self.calculate_parking()
        
        if total_parking == 0:
            return {"Status": parking_status}
            
        parking_max_units = math.floor(total_parking / 1.5)
        if parking_max_units < zoning_max_units:
            buildable_units = parking_max_units
            self.warnings.append(f"Zoning allows {zoning_max_units} units, but parking limits project to {buildable_units} units.")
        else:
            buildable_units = zoning_max_units

        # NEW TIMELINE LOGIC
        levels = self.zoning['Altura_Max_levels']
        if levels <= 4: months = 15
        elif levels <= 8: months = 18
        elif levels <= 12: months = 24
        elif levels <= 16: months = 30
        elif levels <= 20: months = 36
        else: months = 42

        gross_revenue = gsa * self.sale_price_per_m2
        hard_costs = gba * self.cost_per_m2
        soft_costs = hard_costs * self.soft_cost_ratio
        itbis = hard_costs * self.itbis_rate
        commissions = gross_revenue * self.sales_commission
        total_construction_cost = hard_costs + soft_costs + itbis + commissions

        if self.asking_price:
            # NEW 30/70 CASHFLOW & PERMUTA LOGIC
            net_land_cost = max(0, self.asking_price - self.permuta_amount)
            monthly_cost = total_construction_cost / months
            
            # 30% collected during construction, 70% at delivery
            monthly_revenue_during_const = (gross_revenue * 0.30) / months
            final_delivery_revenue = (gross_revenue * 0.70)
            
            cashflow = [-net_land_cost] # Month 0
            
            for m in range(1, months): # Months 1 to N-1
                cashflow.append(monthly_revenue_during_const - monthly_cost)
                
            # Final Month N
            cashflow.append(monthly_revenue_during_const + final_delivery_revenue - monthly_cost)
                
            irr = npf.irr(cashflow) * 12 
            
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
            max_land_value = (gross_revenue - (1.20 * total_construction_cost)) / 1.20
            return {
                "Status": "Valuation Mode",
                "Buildable_Units": buildable_units,
                "GSA_m2": round(gsa, 2),
                "Total_Parking": total_parking,
                "Max_Land_Value": round(max_land_value, 2),
                "Warnings": self.warnings
            }