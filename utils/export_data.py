
import os
import json
import pandas as pd
from datetime import datetime
from typing import List, Dict

from utils.common import setup_logging, load_yaml_config

logger = setup_logging(__name__)


class DataExporter:
    def __init__(self, config_path="config.yaml"):
        self.config = load_yaml_config(config_path)
        self.input_dir = self.config['paths']['extracted_licenses']
        self.output_dir = os.path.join(os.path.dirname(self.input_dir), 'exports')
        os.makedirs(self.output_dir, exist_ok=True)

    def flatten_agreement(self, agreement: Dict, source_meta: Dict) -> Dict:
        """Flattens a nested agreement dictionary for CSV/Excel export."""
        flat = {
            'cik': source_meta.get('cik'),
            'form': source_meta.get('form'),
            'accession': source_meta.get('accession'),
            'filing_date': source_meta.get('filing_date'), # Might not be in extracted metadata, but good to have
            
            # Parties
            'licensor_name': agreement.get('parties', {}).get('licensor', {}).get('name'),
            'licensor_role': agreement.get('parties', {}).get('licensor', {}).get('role'),
            'licensee_name': agreement.get('parties', {}).get('licensee', {}).get('name'),
            'licensee_role': agreement.get('parties', {}).get('licensee', {}).get('role'),
            
            # Technology
            'tech_name': agreement.get('technology', {}).get('name'),
            'tech_category': agreement.get('technology', {}).get('category'),
            'tech_capacity_value': agreement.get('technology', {}).get('capacity', {}).get('value'),
            'tech_capacity_unit': agreement.get('technology', {}).get('capacity', {}).get('unit'),
            
            # Financials
            'upfront_amount': agreement.get('financial_terms', {}).get('upfront_payment', {}).get('amount'),
            'upfront_currency': agreement.get('financial_terms', {}).get('upfront_payment', {}).get('currency'),
            'royalty_rate': agreement.get('financial_terms', {}).get('royalty', {}).get('rate'),
            'royalty_unit': agreement.get('financial_terms', {}).get('royalty', {}).get('unit'),
            
            # Contract
            'term_years': agreement.get('contract_terms', {}).get('term', {}).get('years'),
            'territory': str(agreement.get('contract_terms', {}).get('territory', {}).get('geographic', [])),
            
            # Meta
            'confidence_score': agreement.get('metadata', {}).get('confidence_score')
        }
        return flat

    def collect_data(self) -> List[Dict]:
        """Walks through the extraction directory and collects all agreements."""
        data = []
        for root, dirs, files in os.walk(self.input_dir):
            if "license_agreements.json" in files:
                path = os.path.join(root, "license_agreements.json")
                try:
                    with open(path, 'r') as f:
                        items = json.load(f)
                        
                    # Parse path for metadata: .../extracted_licenses/{cik}/{form}/{accession}/license_agreements.json
                    parts = path.replace("\\", "/").split("/")
                    accession = parts[-2]
                    form = parts[-3]
                    cik = parts[-4]
                    
                    meta = {'cik': cik, 'form': form, 'accession': accession}
                    
                    for item in items:
                        # item structure: { "source_note": ..., "extraction": { "agreements": [...] } }
                        agreements = item.get('extraction', {}).get('agreements', [])
                        if isinstance(agreements, list):
                            for agr in agreements:
                                flattened = self.flatten_agreement(agr, meta)
                                data.append(flattened)
                        elif isinstance(agreements, dict): # Handle edge case where it might be a dict
                             flattened = self.flatten_agreement(agreements, meta)
                             data.append(flattened)
                                
                except Exception as e:
                    logger.error(f"Failed to read {path}: {e}")
        return data

    def export(self, format='excel'):
        data = self.collect_data()
        if not data:
            logger.warning("No data found to export.")
            return

        df = pd.DataFrame(data)
        
        timestamp = pd.Timestamp.now().strftime("%Y%m%d_%H%M%S")
        
        if format == 'excel':
            output_file = os.path.join(self.output_dir, f'license_agreements_{timestamp}.xlsx')
            df.to_excel(output_file, index=False)
            logger.info(f"Exported {len(df)} records to {output_file}")
            
        elif format == 'csv':
            output_file = os.path.join(self.output_dir, f'license_agreements_{timestamp}.csv')
            df.to_csv(output_file, index=False)
            logger.info(f"Exported {len(df)} records to {output_file}")

    def export_litigation_data(self, json_path: str):
        """Phase 2: Export Litigation JSON to CSV"""
        logger.info(f"Exporting Litigation data from {json_path}...")
        
        try:
            with open(json_path, 'r') as f:
                data = json.load(f)
                
            if not data:
                logger.warning("No litigation data to export")
                return None

            rows = []
            for item in data:
                royalty = item.get('royalty_rate', {})
                row = {
                    'Case Name': item.get('case_name'),
                    'Docket Number': item.get('docket_number'),
                    'Date': item.get('decision_date'),
                    'Industry': item.get('industry', 'Unknown'),
                    'Product': item.get('product_category'),
                    'Royalty Rate': royalty.get('rate'),
                    'Royalty Base': royalty.get('base'),
                    'Royalty Type': royalty.get('type'),
                    'Source Name': item.get('source_name', 'CourtListener (Federal Circuit)'),
                    'Source URL': item.get('source_url'),
                    'Reasoning': item.get('extraction_reasoning')
                }
                rows.append(row)
                
            df = pd.DataFrame(rows)
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_path = os.path.join(self.output_dir, f"litigation_royalties_{timestamp}.csv")
            
            df.to_csv(output_path, index=False, encoding='utf-8-sig')
            logger.info(f"Exported {len(df)} litigation records to {output_path}")
            return output_path
            
        except Exception as e:
            logger.error(f"Failed to export litigation data: {e}")
            return None

if __name__ == "__main__":
    import sys
    exporter = DataExporter()
    if len(sys.argv) > 2 and sys.argv[1] == 'litigation':
        exporter.export_litigation_data(sys.argv[2])
    else:
        fmt = sys.argv[1] if len(sys.argv) > 1 else 'excel'
        exporter.export(fmt)
