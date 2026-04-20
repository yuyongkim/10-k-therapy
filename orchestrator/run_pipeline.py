import time
import sys
import os
from dotenv import load_dotenv

# Load environment variables
env_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), '.env')
load_dotenv(env_path)

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from crawler.sec_crawler import SECEdgarCrawler
from parser.html_parser import batch_process as parse_batch
from extractor.license_extractor import batch_process as extract_batch
from database.load_data import DatabaseLoader
from utils.export_data import DataExporter
# Phase 2 Imports
from litigation.court_crawler import CourtListenerCrawler
from litigation.judgment_parser import JudgmentParser
import json
import glob

from utils.common import setup_logging, load_yaml_config

logger = setup_logging("Orchestrator")

class Pipeline:
    def __init__(self, config_path="config.yaml"):
        self.config_path = config_path
        self.config = load_yaml_config(config_path)
        
    def run_step(self, step_name, func, *args, **kwargs):
        logger.info(f"STARTING STEP: {step_name}")
        start = time.time()
        try:
            func(*args, **kwargs)
            duration = time.time() - start
            logger.info(f"COMPLETED STEP: {step_name} in {duration:.2f}s")
            return True
        except Exception as e:
            logger.error(f"FAILED STEP: {step_name} - {e}")
            return False

    def run_litigation_collection(self):
        """Phase 2: Collect Court Data"""
        crawler = CourtListenerCrawler()
        if not crawler.api_key:
            logger.warning("Skipping Litigation Collection: No API Key")
            return


        # Get Config
        lit_config = self.config.get('litigation', {})
        max_pages = lit_config.get('max_pages', 2)
        court = lit_config.get('court')
        query = lit_config.get('query')
        start_date = lit_config.get('start_date')
        end_date = lit_config.get('end_date')
        
        # Crawl or Load
        logger.info(f"Starting Litigation Crawl for {max_pages} pages (Court: {court}, Date: {start_date}-{end_date})...")
        cases = crawler.search_royalty_cases(
            pages=max_pages,
            court=court,
            query=query,
            start_date=start_date,
            end_date=end_date
        ) 
        
        if not cases:
            logger.warning("Crawling failed or returned no results. Attempting to load latest VALID raw data...")
            list_of_files = glob.glob('data/litigation/raw/*.json')
            # Sort by time desc
            list_of_files.sort(key=os.path.getctime, reverse=True)
            
            for file_path in list_of_files:
                try:
                    with open(file_path, 'r') as f:
                        data = json.load(f)
                        if data and len(data) > 0:
                            logger.info(f"Loaded {len(data)} cases from: {file_path}")
                            cases = data
                            break
                except Exception as e:
                    logger.warning(f"Failed to check {file_path}: {e}")
            
            if not cases:
                logger.error("No valid local raw data found (all empty). Exiting step.")
                return

        # Enrich with Full Opinion Text (Crucial for extraction)
        logger.info("Enriching cases with full opinion text (Limit: 200)...")
        cases = crawler.enrich_cases_with_text(cases, limit=200)

        save_path = crawler.save_raw_cases(cases, "data/litigation/raw")
        
        # Parse
        parser = JudgmentParser()
        parsed_results = []
        
        logger.info(f"Parsing {len(cases)} cases for royalty rates...")
        for case in cases:
            res = parser.parse_case(case)
            if res:
                parsed_results.append(res)
        
        # Save Parsed
        os.makedirs("data/litigation/parsed", exist_ok=True)
        out_path = f"data/litigation/parsed/royalty_rates_{time.strftime('%Y%m%d')}.json"
        with open(out_path, 'w') as f:
            json.dump(parsed_results, f, indent=2)
        logger.info(f"Saved {len(parsed_results)} analyzed royalty records to {out_path}")
        
        # Export CSV (Phase 2 Addition)
        exporter = DataExporter(self.config_path)
        csv_path = exporter.export_litigation_data(out_path)
        if csv_path:
            logger.info(f"Generated CSV report at: {csv_path}")

    def run(self):
        # 1. Crawl (SEC)
        # crawler = SECEdgarCrawler(self.config_path)
        # if not self.run_step("SEC Crawler", crawler.batch_process):
        #    return

        # 2. Parse (SEC)
        # if not self.run_step("HTML Parser", parse_batch, self.config_path):
        #    return

        # 3. Extract (SEC)
        # if not self.run_step("License Extractor", extract_batch, self.config_path):
        #    return

        # 4. Load DB (Optional)
        # ... (DB Loading logic omitted for brevity in this replace)

        # 5. Export (SEC)
        # exporter = DataExporter(self.config_path)
        # self.run_step("Export to Excel", exporter.export, 'excel')

        # 6. Litigation Collection (Phase 2)
        self.run_step("Litigation Collection (Courts)", self.run_litigation_collection)

        logger.info("Pipeline execution completed.")

        logger.info("Pipeline execution completed.")

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Run SEC License Extraction Pipeline")
    parser.add_argument("--config", default="config.yaml", help="Path to configuration file")
    args = parser.parse_args()
    
    pipeline = Pipeline(args.config)
    pipeline.run()
