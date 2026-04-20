import os
import json
import psycopg2
from psycopg2.extras import Json
from datetime import datetime

from utils.common import setup_logging, load_yaml_config

logger = setup_logging(__name__)


class DatabaseLoader:
    def __init__(self, config_path="config.yaml"):
        self.config = load_yaml_config(config_path)
            
        db_cfg = self.config['database']
        self.conn = psycopg2.connect(
            host=db_cfg['host'],
            port=db_cfg['port'],
            dbname=db_cfg['name'],
            user=db_cfg['user'],
            password=os.getenv("DB_PASSWORD")
        )
        self.conn.autocommit = True
        
    def close(self):
        if self.conn:
            self.conn.close()

    def load_schema(self, schema_file):
        with open(schema_file, 'r') as f:
            sql = f.read()
        with self.conn.cursor() as cur:
            cur.execute(sql)
        logger.info("Schema loaded.")

    def insert_agreement(self, data, source_meta):
        """
        Inserts a single agreement record hierarchy.
        data: The 'agreement' object from extractor output
        source_meta: Metadata about the source filing
        """
        with self.conn.cursor() as cur:
            # 1. Ensure Company (Licensor)
            parties = data.get('parties', {})
            licensor = parties.get('licensor', {})
            licensor_name = licensor.get('name')
            
            licensor_id = None
            if licensor_name:
                cur.execute(
                    "INSERT INTO companies (name, created_at) VALUES (%s, NOW()) ON CONFLICT (name) DO NOTHING RETURNING company_id",
                    (licensor_name,)
                )
                res = cur.fetchone()
                if res:
                    licensor_id = res[0]
                else:
                    cur.execute("SELECT company_id FROM companies WHERE name = %s", (licensor_name,))
                    res = cur.fetchone()
                    if res: licensor_id = res[0]

            # 2. Ensure Filing
            cik = source_meta.get('cik')
            accession = source_meta.get('accession')
            
            filing_id = None
            if accession:
                cur.execute("""
                    INSERT INTO sec_filings (cik, accession_number, filing_type, form)
                    VALUES (%s, %s, %s, %s)
                    ON CONFLICT (accession_number) DO UPDATE SET accession_number=EXCLUDED.accession_number
                    RETURNING filing_id
                """, (cik, accession, source_meta.get('filing_type'), source_meta.get('form')))
                filing_id = cur.fetchone()[0]

            # 3. Insert Agreement
            cur.execute("""
                INSERT INTO license_agreements 
                (filing_id, licensor_id, licensor_name, licensee_name, internal_agreement_name, execution_date, territory)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                RETURNING agreement_id
            """, (
                filing_id,
                licensor_id,
                licensor_name or "Unknown",
                parties.get('licensee', {}).get('name'),
                f"Agreement with {licensor_name}",
                data.get('contract_terms', {}).get('execution_date'),
                Json(data.get('contract_terms', {}).get('territory'))
            ))
            agreement_id = cur.fetchone()[0]
            
            # 4. Insert Tech
            tech = data.get('technology', {})
            if tech:
                cur.execute("""
                    INSERT INTO technologies (agreement_id, name, category, capacity_value, capacity_unit)
                    VALUES (%s, %s, %s, %s, %s)
                """, (
                    agreement_id,
                    tech.get('name'),
                    tech.get('category'),
                    tech.get('capacity', {}).get('value'),
                    tech.get('capacity', {}).get('unit')
                ))

            # 5. Insert Financials
            fin = data.get('financial_terms', {})
            if fin:
                cur.execute("""
                    INSERT INTO financial_terms (agreement_id, upfront_amount, upfront_currency, royalty_rate, royalty_unit)
                    VALUES (%s, %s, %s, %s, %s)
                """, (
                    agreement_id,
                    fin.get('upfront_payment', {}).get('amount'),
                    fin.get('upfront_payment', {}).get('currency'),
                    fin.get('royalty', {}).get('rate'),
                    fin.get('royalty', {}).get('unit')
                ))

    def process_directory(self, input_dir):
        count = 0
        for root, dirs, files in os.walk(input_dir):
            if "license_agreements.json" in files:
                path = os.path.join(root, "license_agreements.json")
                try:
                    with open(path, 'r') as f:
                        items = json.load(f)
                        
                    # Parse path for metadata
                    # .../extracted_licenses/{cik}/{form}/{accession}/license_agreements.json
                    parts = path.replace("\\", "/").split("/")
                    accession = parts[-2]
                    form = parts[-3]
                    cik = parts[-4]
                    
                    meta = {
                        'cik': cik, 
                        'form': form, 
                        'accession': accession,
                        'filing_type': form
                    }
                    
                    for item in items:
                        agreement_data = item.get('extraction', {}).get('agreements', [])
                        if isinstance(agreement_data, list):
                            for agr in agreement_data:
                                self.insert_agreement(agr, meta)
                                count += 1
                                
                except Exception as e:
                    logger.error(f"Failed to load {path}: {e}")
        
        logger.info(f"Loaded {count} agreements into database.")

if __name__ == "__main__":
    import sys
    loader = DatabaseLoader()
    
    if len(sys.argv) > 1 and sys.argv[1] == "init":
        loader.load_schema("database/schema.sql")
    elif len(sys.argv) > 1 and sys.argv[1] == "load":
        config_path = "config.yaml"
        with open(config_path, 'r') as f:
            cfg = yaml.safe_load(f)
        loader.process_directory(cfg['paths']['extracted_licenses'])
    
    loader.close()
