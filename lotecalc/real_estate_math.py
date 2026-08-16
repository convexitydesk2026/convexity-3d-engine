"""
===============================================================================
PROJECT: LoteCalc DR (B2B PropTech SaaS)
FILE: real_estate_math.py
VERSION: 1.5 (Dynamic Cloud Paths)
DATE: August 03, 2026
AUTHOR: P1 (Lead PropTech Developer)
===============================================================================
"""
import os
import json
import math
import numpy_financial as npf

# CRITICAL FIX: Dynamic Path for Cloud Deployment
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
ASSUMPTIONS_PATH = os.path.join(BASE_DIR, 'market_assumptions.json')

class FeasibilityEngine:
    def __init__(self, width, depth, zoning_data, project_type, finish_quality, asking_price=None, permuta_pct=0, parking_size="Mid Size (2.50 x 5.20)"):
        self.width = float(width)
        self.depth = float(depth)
        self.gross_lot_area = self.width * self.depth
        self.zoning = zoning_data
        self.asking_price = float(asking_price) if asking_price else None
        self.permuta_pct = float(permuta_pct) if permuta_pct else 0.0
        
        # Parking Dimensions Mapping (Width in meters)
        self.parking_dims = {
            "Legal Minimum (2.30 x 5.00)": 2.30,
            "Mid Size (2.50 x 5.20)": 2.50,
            "Large (2.70 x 5.50)": 2.70
        }
        self.parking_width = self.parking_dims.get(parking_size, 2.50)
        
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
        
        # Pulled directly from the CSV column
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
            
        # Tiered Parking Logic based on Lanes and Width
        if self.width >= 28.75:
            rows = 3
            max_levels = 4  # 2 lanes allow deep excavation
            self.warnings.append("Underground parking capped at 4 levels to avoid water/rock.")
        elif self.width >= 19.0:
            rows = 2
            max_levels = 2  # 1 lane restricts depth to 2 levels
            self.warnings.append("Parking capped at 2 levels due to single-lane ramp constraints (width < 28.75m).")
        else:
            rows = 2
            max_levels = 1  # Bare minimum width restricts to 1 level
            
        # Use dynamic parking width selected by user
        spaces_per_row = math.floor(self.depth / self.parking_width)
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
            
        parking_max_units = math.floor(total_parking / 1.5)
        if parking_max_units < zoning_max_units:
            buildable_units = parking_max_units
            capping_reason = f"Capped by Parking (Zoning allowed {zoning_max_units})"
            self.warnings.append(f"Zoning allows {zoning_max_units} units, but parking limits project to {buildable_units} units.")
        else:
            buildable_units = zoning_max_units
            capping_reason = "Capped by Zoning Density"

        # Detailed Math Metrics
        avg_unit_size = gsa / buildable_units if buildable_units > 0 else 0
        parkings_per_unit = math.floor(total_parking / buildable_units) if buildable_units > 0 else 0
        visitor_parkings = total_parking - (parkings_per_unit * buildable_units)

        # TIMELINE LOGIC
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
            permuta_amount = self.asking_price * (self.permuta_pct / 100.0)
            net_land_cost = max(0, self.asking_price - permuta_amount)
            
            monthly_cost = total_construction_cost / months
            
            monthly_revenue_during_const = (gross_revenue * 0.30) / months
            final_delivery_revenue = (gross_revenue * 0.70)
            
            cashflow = [-net_land_cost] # Month 0
            
            for m in range(1, months): # Months 1 to N-1
                cashflow.append(monthly_revenue_during_const - monthly_cost)
                
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
                "Capping_Reason": capping_reason,
                "Avg_Unit_Size_m2": round(avg_unit_size, 2),
                "Parkings_Per_Unit": parkings_per_unit,
                "Visitor_Parkings": visitor_parkings,
                "GSA_m2": round(gsa, 2),
                "Total_Parking": total_parking,
                "Timeline_Months": months,
                "Total_Cost": round(total_construction_cost, 2),
                "Gross_Revenue": round(gross_revenue, 2),
                "Permuta_Value_USD": round(permuta_amount, 2),
                "ROC": round(roc * 100, 2),
                "IRR": irr_display,
                "Warnings": self.warnings
            }
        else:
            max_land_value = (gross_revenue - (1.20 * total_construction_cost)) / 1.20
            return {
                "Status": "Valuation Mode",
                "Buildable_Units": buildable_units,
                "Capping_Reason": capping_reason,
                "Avg_Unit_Size_m2": round(avg_unit_size, 2),
                "Parkings_Per_Unit": parkings_per_unit,
                "Visitor_Parkings": visitor_parkings,
                "GSA_m2": round(gsa, 2),
                "Total_Parking": total_parking,
                "Max_Land_Value": round(max_land_value, 2),
                "Warnings": self.warnings
            }