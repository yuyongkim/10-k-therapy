import numpy as np
import pandas as pd
from datetime import datetime
from typing import Dict, List, Optional
import logging
import csv
import re
from difflib import SequenceMatcher

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class DCFLicenseValuator:
    def _parse_rate(self, rate_str: str) -> Optional[float]:
        """
        Helper to parse royalty rate from string (e.g., "5%", "0.05").
        """
        if isinstance(rate_str, (int, float)):
            return float(rate_str)
        if not isinstance(rate_str, str):
            return None
        
        clean_r = rate_str.replace('%', '').strip()
        try:
            val = float(clean_r)
            if val > 1.0: # assume 5.0 means 5%
                return val / 100.0
            return val
        except ValueError:
            return None

    def get_utilization_curve(self, year: int) -> float:
        """
        Placeholder for a more complex utilization curve.
        For now, a simple linear increase or constant.
        """
        # Example: starts at 50% and increases by 5% per year up to 90%
        initial_utilization = 0.50
        annual_increase = 0.05
        max_utilization = 0.90
        
        utilization = min(initial_utilization + (year - 1) * annual_increase, max_utilization)
        return utilization

    def calculate_npv(self, agreement_data: Dict, assumptions: Dict):
        """
        Calculate Net Present Value of license agreement using DCF.
        """
        contract_term = assumptions.get('contract_term_years', 15)
        contract_term = assumptions.get('contract_term_years', 15)
        
        tech = agreement_data.get('technology')
        if not isinstance(tech, dict): tech = {}
        
        design_capacity = tech.get('capacity')
        if not isinstance(design_capacity, dict): design_capacity = {}
        
        design_capacity_value = design_capacity.get('value', 0)
        product_price = assumptions.get('product_price', 1000) # Placeholder
        discount_rate = assumptions.get('discount_rate', 0.12)
        escalation_rate = assumptions.get('escalation_rate', 0.02)
        
        # Financials from Agreement
        financials = agreement_data.get('financial_terms')
        if not isinstance(financials, dict): financials = {}
        
        royalty = financials.get('royalty')
        if not isinstance(royalty, dict): royalty = {}
        
        royalty_rate_raw = royalty.get('rate', 0)
        royalty_rate = self._parse_rate(royalty_rate_raw) if isinstance(royalty_rate_raw, str) else (royalty_rate_raw if isinstance(royalty_rate_raw, (int, float)) else 0)
        if royalty_rate is None: royalty_rate = 0.0
        
        royalty_type = royalty.get('type', 'percentage') # percentage or per_unit
        
        upfront = financials.get('upfront_payment')
        if not isinstance(upfront, dict): upfront = {}
        upfront_amount = 0.0
        if isinstance(upfront, dict):
            try:
                val = upfront.get('amount', 0)
                if isinstance(val, (int, float)):
                    upfront_amount = float(val)
                elif isinstance(val, str):
                    # Try extract digits
                    digits = re.findall(r"[\d\.]+", val)
                    if digits: upfront_amount = float(digits[0])
            except:
                upfront_amount = 0.0
        
        # Assumption: Revenue Base
        # In a real system, this would come from financial statements or projection models
        base_revenue = assumptions.get('projected_revenue_year1', 10_000_000)

        annual_cash_flows = []
        
        for year in range(1, contract_term + 1):
            utilization = self.get_utilization_curve(year)
            # Safe access to value
            cap_val = design_capacity_value
            if not isinstance(cap_val, (int, float)): cap_val = 0
            
            # Simple growth model for revenue or production
            if royalty_type == 'per_unit':
                production = cap_val * utilization
                # Assuming product price escalates
                current_product_price = product_price * ((1 + escalation_rate) ** (year - 1))
                annual_royalty = production * current_product_price * royalty_rate # If royalty rate is per unit price
                # Or if royalty rate is a fixed amount per unit:
                # annual_royalty = production * royalty_rate 
            else: # percentage or lump_sum implied
                year_revenue = base_revenue * ((1 + 0.05) ** (year - 1)) # 5% revenue growth
                annual_royalty = year_revenue * royalty_rate
            
            # Escalation on royalty amount (inflation)
            escalated_royalty = annual_royalty * ((1 + escalation_rate) ** (year - 1))
            annual_cash_flows.append(escalated_royalty)
            
        # NPV Calculation
        npv = -upfront_amount
        for t, cf in enumerate(annual_cash_flows, 1):
            npv += cf / ((1 + discount_rate) ** t)
            
        return {
            "method": "DCF",
            "npv": round(npv, 2),
            "royalty_rate_used": royalty_rate,
            "implied_value": round(npv + upfront_amount, 2) 
        }

class LitigationComparator:
    def __init__(self, csv_path: str):
        self.comps_db = []
        try:
            with open(csv_path, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    # Parse Royalty Rate
                    rate_str = row.get('Royalty Rate', '')
                    parsed_rate = self._parse_rate(rate_str)
                    if parsed_rate:
                        row['parsed_rate'] = parsed_rate
                        self.comps_db.append(row)
        except Exception as e:
            logger.error(f"Failed to load litigation data: {e}")

    def _parse_rate(self, rate_str: str) -> Optional[float]:
        try:
            if not rate_str or not isinstance(rate_str, str): return None
            # Handle "3.5%"
            if '%' in rate_str:
                val_str = re.findall(r"[\d\.]+", rate_str)
                if val_str:
                    return float(val_str[0]) / 100.0
            
            # Try finding any float, but ensure it's reasonable (< 1.0 for rate)
            vals = re.findall(r"[\d\.]+", rate_str)
            if vals:
                val = float(vals[0])
                if val < 1.0: return val
                
            return None
        except Exception:
            return None

    def find_comparables(self, agreement_data: Dict, top_n=5) -> List[Dict]:
        """
        Find litigation cases that match the technology/industry of the agreement.
        """
        matches = []
        
        # SEC Agreement
        comparables = []
        target_tech = agreement_data.get('technology')
        if not isinstance(target_tech, dict): target_tech = {}
        
        target_category = target_tech.get('category', '')
        target_name = target_tech.get('name', '')
        if target_name: target_name = str(target_name).lower()
        
        # Parties (to check logic if needed, but mostly focused on tech)
        
        for case in self.comps_db:
            score = 0
            case_ind = case.get('Industry', '').lower()
            case_prod = case.get('Product', '').lower()
            
            # 1. Direct Product Match (Text Similarity)
            if target_name and case_prod:
                sim = SequenceMatcher(None, target_name, case_prod).ratio()
                if sim > 0.4: score += sim * 2.0
                if target_name in case_prod or case_prod in target_name:
                    score += 1.0
                    
            # 2. Category/Industry Match
            # We don't have Industry in SEC extraction explicitly usually, 
            # but we can try to match tech category to industry
            if target_category and case_ind:
                if target_category in case_ind or case_ind in target_category:
                    score += 1.5
                    
            if score > 0.5:
                case['match_score'] = score
                matches.append(case)
                
        # Sort by score
        matches.sort(key=lambda x: x['match_score'], reverse=True)
        return matches[:top_n]

class IntegratedValuationEngine:
    def __init__(self, litigation_csv_path: str):
        self.dcf = DCFLicenseValuator()
        self.comps = LitigationComparator(litigation_csv_path)
        
    def valuate(self, agreement_data: Dict, assumptions: Dict = None):
        if assumptions is None:
            assumptions = {}
            
        # 1. DCF Valuation
        dcf_result = self.dcf.calculate_npv(agreement_data, assumptions)
        
        # 2. Market Comparable Valuation
        matches = self.comps.find_comparables(agreement_data)
        
        comp_rates = [m['parsed_rate'] for m in matches if m.get('parsed_rate')]
        median_market_rate = np.median(comp_rates) if comp_rates else 0.0
        
        # Calculate Implied Market Value (using Market Rate in DCF Model)
        market_dcf = 0
        if median_market_rate > 0:
            market_assumptions = assumptions.copy()
            # Inject market rate into a temporary agreement structure to reuse DCF logic
            temp_agr = agreement_data.copy()
            temp_agr['financial_terms'] = {
                'royalty': {'rate': median_market_rate, 'unit': 'percentage'},
                'upfront_payment': {'amount': 0} # Ignore upfront for pure royalty compare
            }
            market_dcf = self.dcf.calculate_npv(temp_agr, market_assumptions)['npv']
            
        return {
            "agreement_id": agreement_data.get('parties', {}).get('licensee', {}).get('name', 'Unknown'),
            "dcf_valuation": dcf_result,
            "market_comparables": {
                "median_rate": round(median_market_rate, 4),
                "count": len(matches),
                "top_matches": [
                    f"{m.get('Case Name')} ({m.get('Industry')} - {m.get('Product')}) Rate: {m.get('Royalty Rate')}"
                    for m in matches
                ],
                "implied_market_value": round(market_dcf, 2)
            },
            "valuation_summary": {
                "final_estimate": max(dcf_result['implied_value'], market_dcf), # Simple logic
                "methodology": "Hybrid Matches" if matches else "DCF Only"
            }
        }

if __name__ == "__main__":
    # Test
    # Point to the expanded CSV
    csv_path = "data/exports/litigation_royalties_20260114_215742.csv"
    
    # Mock SEC Agreement
    test_agr = {
        "parties": {"licensee": {"name": "Test Co"}},
        "technology": {
            "name": "semiconductor memory chip",
            "category": "Semiconductor"
        },
        "financial_terms": {
            "upfront_payment": {"amount": 1000000},
            "royalty": {"rate": "3.0%", "unit": "percentage"}
        }
    }
    
    import os
    if os.path.exists(csv_path):
        engine = IntegratedValuationEngine(csv_path)
        res = engine.valuate(test_agr)
        import json
        print(json.dumps(res, indent=2))
    else:
        print(f"Test CSV not found at {csv_path}")
