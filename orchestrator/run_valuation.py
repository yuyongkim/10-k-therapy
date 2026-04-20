
import os
import json
import pandas as pd
from tqdm import tqdm
from datetime import datetime
import sys

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from valuation.valuator import IntegratedValuationEngine
from utils.common import setup_logging, load_yaml_config

logger = setup_logging(__name__, log_file="valuation.log")


def load_config(config_path="config.yaml"):
    return load_yaml_config(config_path)

def run_valuation_pipeline(config_path):
    config = load_config(config_path)
    
    # 1. Initialize Engine
    litigation_csv = config['litigation'].get('csv_export_path')
    if not litigation_csv or not os.path.exists(litigation_csv):
        logger.error(f"Litigation CSV not found at: {litigation_csv}. Please run litigation collection first.")
        # Try to find any csv in exports if explicit path fails? No, fail fast.
        return

    logger.info(f"Initializing Valuation Engine with market data from: {litigation_csv}")
    engine = IntegratedValuationEngine(litigation_csv)
    
    # 2. Find Extracted License JSONs
    search_dir = config['paths']['extracted_licenses']
    json_files = []
    for root, dirs, files in os.walk(search_dir):
        if "license_agreements.json" in files:
            json_files.append(os.path.join(root, "license_agreements.json"))
            
    logger.info(f"Found {len(json_files)} extracted license files.")
    
    all_valuations = []
    
    # 3. Process Each File
    for json_path in tqdm(json_files, desc="Valuating Agreements"):
        try:
            with open(json_path, 'r') as f:
                data = json.load(f)
                
            # data is a list of note items, each having 'extraction' -> 'agreements'
            if isinstance(data, list):
                for item in data:
                    if not isinstance(item, dict): continue # Skip if item is malformed (e.g. list inside list)
                    
                    extraction = item.get('extraction')
                    if not extraction: continue
                    
                    agreements = []
                    if isinstance(extraction, dict):
                        agreements = extraction.get('agreements', [])
                    elif isinstance(extraction, list):
                        agreements = extraction
                    
                    if not isinstance(agreements, list):
                        agreements = []
                    
                    # Metadata for traceability
                    source_meta = item.get('source_note', {}) or {} # Ensure dict
                    company_ciks = source_meta.get('matched_companies', [])
                    cik = company_ciks[0] if company_ciks else "Unknown"
                    
                    for agr in agreements:
                        # Skip if no confidence or extremely empty or malformed
                        if not agr or not isinstance(agr, dict): continue
                        
                        # Apply Valuation
                        valuation_res = engine.valuate(agr)
                        
                        # Flatten for Report
                        flat_res = {
                            "CIK": cik,
                            "Filing": source_meta.get('note_title', '')[:50], # Truncate title
                            "Agreement ID": valuation_res.get('agreement_id'),
                            "Technology": agr.get('technology', {}).get('name'),
                            "Category": agr.get('technology', {}).get('category'),
                            "DCF NPV": valuation_res['dcf_valuation']['npv'],
                            "Implied Value": valuation_res['dcf_valuation']['implied_value'],
                            "Market Median Rate": valuation_res['market_comparables']['median_rate'],
                            "Market Comps Count": valuation_res['market_comparables']['count'],
                            "Market Implied Value": valuation_res['market_comparables']['implied_market_value'],
                            "Final Estimate": valuation_res['valuation_summary']['final_estimate'],
                            "Methodology": valuation_res['valuation_summary']['methodology'],
                            "Top Match": valuation_res['market_comparables']['top_matches'][0] if valuation_res['market_comparables']['top_matches'] else "None"
                        }
                        
                        all_valuations.append(flat_res)
                        
        except Exception as e:
            logger.error(f"Error processing {json_path}: {e}")
            
    # 4. Export Results
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_dir = "data/valuation_reports"
    os.makedirs(output_dir, exist_ok=True)
    
    df = pd.DataFrame(all_valuations)
    
    if not df.empty:
        csv_filename = f"valuation_summary_{timestamp}.csv"
        csv_path = os.path.join(output_dir, csv_filename)
        df.to_csv(csv_path, index=False)
        logger.info(f"Valuation Report saved to: {csv_path}")
        logger.info(f"Total Valued Agreements: {len(df)}")
        
        # Also save detailed JSON
        json_filename = f"valuation_details_{timestamp}.json"
        json_path = os.path.join(output_dir, json_filename)
        df.to_json(json_path, orient='records', indent=2)
    else:
        logger.warning("No valuations generated.")

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="sec-license-extraction/config.yaml")
    args = parser.parse_args()
    
    run_valuation_pipeline(args.config)
