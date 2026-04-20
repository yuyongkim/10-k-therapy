import os
import re
import json
import requests
from typing import List, Dict, Optional
from datetime import datetime
from tenacity import retry, wait_exponential, stop_after_attempt, retry_if_exception_type
from bs4 import BeautifulSoup

from utils.common import setup_logging, load_yaml_config, RateLimiter

logger = setup_logging(__name__, log_file="crawler.log")


class SECEdgarCrawler:
    def __init__(self, config_path: str = "config.yaml"):
        self.config = load_yaml_config(config_path)
            
        self.user_agent = self.config['sec']['user_agent']
        self.rate_limiter = RateLimiter(self.config['sec']['rate_limit'])
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': self.user_agent,
            'Accept-Encoding': 'gzip, deflate',
        })
        
        self.base_url = "https://data.sec.gov"
        self.archives_url = "https://www.sec.gov/Archives"
        
        # Ensure directories exist
        self.paths = self.config['paths']
        os.makedirs(self.paths['raw_filings'], exist_ok=True)

    @retry(
        wait=wait_exponential(multiplier=1, min=1, max=60),
        stop=stop_after_attempt(5),
        retry=retry_if_exception_type((requests.ConnectionError, requests.Timeout, requests.exceptions.ChunkedEncodingError))
    )
    def _make_request(self, url: str, stream: bool = False) -> requests.Response:
        self.rate_limiter.acquire()
        try:
            response = self.session.get(url, stream=stream, timeout=30)
            if response.status_code == 429:
                logger.warning("Rate limit hit (429). Waiting 60s...")
                time.sleep(60)
                raise requests.ConnectionError("Rate limit hit")
            if response.status_code == 503:
                logger.warning("Service unavailable (503). Waiting 300s...")
                time.sleep(300)
                raise requests.ConnectionError("Service unavailable")
                
            response.raise_for_status()
            return response
        except Exception as e:
            logger.error(f"Request failed: {url} - {str(e)}")
            raise

    def get_company_cik(self, company_name: str) -> Optional[str]:
        """
        Searches for a company's CIK. 
        Note: The official SEC API for searching is limited. 
        Ideally, we should cache a mapping or use the tickers.json endpoint.
        For this implementation, we'll try to use the tickers.json endpoint to find a match.
        """
        try:
            # SEC provides a full list of tickers and CIKs
            # We cache this to avoid repeated large downloads
            tickers_file = os.path.join(self.paths['data_dir'], "company_tickers.json")
            
            if not os.path.exists(tickers_file):
                logger.info("Downloading company tickers list...")
                url = "https://www.sec.gov/files/company_tickers.json"
                resp = self._make_request(url)
                with open(tickers_file, 'w') as f:
                    json.dump(resp.json(), f)
            
            with open(tickers_file, 'r') as f:
                tickers_data = json.load(f)
            
            # Search logic (simple substring match for now, can be improved with fuzzy matching)
            search_name = company_name.lower()
            for entry in tickers_data.values():
                if search_name in entry['title'].lower():
                    # Return CIK as 10-digit string
                    return str(entry['cik_str']).zfill(10)
                    
            logger.warning(f"CIK not found for {company_name}")
            return None
            
        except Exception as e:
            logger.error(f"Error looking up CIK for {company_name}: {e}")
            return None

    def collect_filing_metadata(self, cik: str) -> List[Dict]:
        """Fetch filing history for a CIK."""
        url = f"{self.base_url}/submissions/CIK{cik}.json"
        try:
            response = self._make_request(url)
            data = response.json()
            
            filings = data.get('filings', {}).get('recent', {})
            if not filings:
                return []
                
            results = []
            target_forms = set(self.config['sec']['filing_types'])
            start_date = self.config['sec']['date_range']['start']
            end_date = self.config['sec']['date_range']['end']
            
            count = len(filings['accessionNumber'])
            for i in range(count):
                form = filings['form'][i]
                filing_date = filings['filingDate'][i]
                
                if form in target_forms and start_date <= filing_date <= end_date:
                    meta = {
                        'accessionNumber': filings['accessionNumber'][i],
                        'filingDate': filing_date,
                        'reportDate': filings['reportDate'][i],
                        'form': form,
                        'primaryDocument': filings['primaryDocument'][i],
                        'primaryDocDescription': filings['primaryDocDescription'][i],
                        'cik': cik,
                        'company_name': data.get('name', 'Unknown')
                    }
                    results.append(meta)
            
            return results
        except Exception as e:
            logger.error(f"Error collecting metadata for CIK {cik}: {e}")
            return []


    def _get_exhibit_list(self, cik: str, accession: str) -> List[Dict]:
        """
        Parses the filing index page to find Exhibit 10 documents.
        Returns a list of dicts with 'url', 'type', 'description'.
        """
        accession_no_dashes = accession.replace("-", "")
        # The index page URL format: .../10-K/0001047469-19-004266-index.html
        # or standard archive root: .../000104746919004266/{accession}-index.html
        index_url = f"{self.archives_url}/edgar/data/{int(cik)}/{accession_no_dashes}/{accession}-index.html"
        
        try:
            logger.info(f"Checking index for exhibits: {index_url}")
            # Use _make_request but allow 404 (some old filings might differ)
            try:
                response = self._make_request(index_url)
            except requests.ConnectionError:
                logger.warning(f"Could not fetch index page for {accession}")
                return []

            soup = BeautifulSoup(response.content, 'html.parser')
            # Look for the "Document Format Files" table
            # Usually the first table, header "Document Format Files"
            
            exhibits = []
            tables = soup.find_all('table')
            for table in tables:
                headers = [th.get_text().strip() for th in table.find_all('th')]
                if "Document" in headers and "Type" in headers:
                    # Found the right table
                    rows = table.find_all('tr')
                    for row in rows:
                        cols = row.find_all('td')
                        if len(cols) < 3:
                            continue
                        
                        # Columns are usually: Seq, Description, Document, Type, Size
                        # But we found headers so let's try to map dynamically or assume order
                        # Standard order: Seq | Description | Document | Type | Size
                        
                        # Filter for strictly Exhibit 10 (Material Contracts)
                        # Exclude EX-101 (XBRL) or others starting with EX-10
                        doc_type = cols[3].get_text().strip()
                        if re.match(r"^EX-10(\.\d+)?$", doc_type):
                            doc_link = cols[2].find('a')
                            if doc_link:
                                href = doc_link['href']
                                # href is usually relative: /Archives/edgar/data/...
                                full_url = f"https://www.sec.gov{href}"
                                desc = cols[1].get_text().strip()
                                exhibits.append({
                                    "url": full_url,
                                    "type": doc_type,
                                    "description": desc,
                                    "filename": doc_link.get_text().strip()
                                })
            return exhibits

        except Exception as e:
            logger.error(f"Error parsing index for exhibits {accession}: {e}")
            return []

    def download_filing(self, metadata: Dict) -> bool:
        """Download the primary document AND Exhibit 10s for a filing."""
        cik = metadata['cik']
        accession = metadata['accessionNumber']
        doc_name = metadata['primaryDocument']
        
        # SEC URL format for archives uses CIK limit 0s stripped usually, but let's check
        # Usually it is data/{cik}/{accession_no_dashes}/{primary_doc}
        accession_no_dashes = accession.replace("-", "")
        
        # Save path structure:
        # raw_filings/{cik}/{form}/{accession}/primary_document.html
        # raw_filings/{cik}/{form}/{accession}/exhibits/EX-10.1_filename.htm
        
        save_dir = os.path.join(self.paths['raw_filings'], cik, metadata['form'], accession)
        os.makedirs(save_dir, exist_ok=True)
        
        html_path = os.path.join(save_dir, "primary_document.html")
        meta_path = os.path.join(save_dir, "filing_metadata.json")
        exhibits_dir = os.path.join(save_dir, "exhibits")
        
        # 1. Download Primary Document
        # Skip if already exists
        primary_downloaded = False
        if os.path.exists(html_path):
             primary_downloaded = True
        else:
            url = f"{self.archives_url}/edgar/data/{int(cik)}/{accession_no_dashes}/{doc_name}"
            try:
                logger.info(f"Downloading primary: {url}...")
                response = self._make_request(url, stream=True)
                
                with open(html_path, 'wb') as f:
                    for chunk in response.iter_content(chunk_size=8192):
                        f.write(chunk)
                
                with open(meta_path, 'w') as f:
                    json.dump(metadata, f, indent=2)
                    
                primary_downloaded = True
            except Exception as e:
                logger.error(f"Failed to download primary {accession}: {e}")
                # Clean up partial
                if os.path.exists(html_path):
                    os.remove(html_path)
        
        # 2. Download Exhibits (EX-10)
        if primary_downloaded:
            try:
                exhibits = self._get_exhibit_list(cik, accession)
                if exhibits:
                    os.makedirs(exhibits_dir, exist_ok=True)
                    logger.info(f"Found {len(exhibits)} exhibits for {accession}")
                    
                    for ex in exhibits:
                        # Create safe filename
                        safe_name = f"{ex['type']}_{ex['filename']}".replace("/", "_")
                        ex_path = os.path.join(exhibits_dir, safe_name)
                        
                        if os.path.exists(ex_path):
                            continue
                            
                        logger.info(f"Downloading exhibit: {safe_name}")
                        resp = self._make_request(ex['url'], stream=True)
                        with open(ex_path, 'wb') as f:
                            for chunk in resp.iter_content(chunk_size=8192):
                                f.write(chunk)
            except Exception as e:
                 logger.error(f"Error downloading exhibits for {accession}: {e}")
                 
        return primary_downloaded

    def batch_process(self):
        """Main entry point to process target companies."""
        ticker_source = self.config['sec'].get('ticker_source', 'list')
        
        if ticker_source == 'json':
            json_path = self.config['sec'].get('ticker_json_path', 'data/company_tickers.json')
            logger.info(f"Batch processing using ALL companies from {json_path}")
            
            # Resolve absolute path if needed, or use relative to data_dir
            if not os.path.isabs(json_path):
                 # Try config path relative to cwd, or relative to data dir
                 if not os.path.exists(json_path):
                     json_path = os.path.join(self.paths['data_dir'], "company_tickers.json")

            try:
                with open(json_path, 'r') as f:
                    tickers_data = json.load(f)
                
                # Check format (dict of dicts "0": {...})
                companies = list(tickers_data.values())
                logger.info(f"Loaded {len(companies)} companies. Starting processing...")
                
                for i, entry in enumerate(companies):
                    cik = str(entry['cik_str']).zfill(10)
                    ticker = entry['ticker']
                    title = entry['title']
                    
                    logger.info(f"[{i+1}/{len(companies)}] Processing {title} ({ticker}, CIK: {cik})...")
                    
                    # 1. Collect Metadata
                    metadatas = self.collect_filing_metadata(cik)
                    if not metadatas:
                        continue
                        
                    logger.info(f"Found {len(metadatas)} filings for {ticker}")
                    
                    # 2. Download
                    for meta in metadatas:
                        self.download_filing(meta)
                        
            except FileNotFoundError:
                logger.error(f"Ticker JSON file not found at {json_path}")
                return
                
        else:
            # Legacy/List Mode
            targets = self.config['sec']['target_companies']
            all_companies = targets.get('licensors', []) + targets.get('licensees', [])
            
            for company in all_companies:
                logger.info(f"Processing {company}...")
                cik = self.get_company_cik(company)
                if not cik:
                    logger.warning(f"Could not find CIK for {company}, skipping.")
                    continue
                    
                logger.info(f"Found CIK {cik} for {company}")
                metadatas = self.collect_filing_metadata(cik)
                logger.info(f"Found {len(metadatas)} target filings for {company}")
                
                for meta in metadatas:
                    self.download_filing(meta)
                
if __name__ == "__main__":
    crawler = SECEdgarCrawler()
    # Simple CLI for testing
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == "test":
        # Test 1 company
        print("Running test mode for UOP...")
        cik = crawler.get_company_cik("Honeywell International")
        if cik:
             metas = crawler.collect_filing_metadata(cik)
             print(f"Found {len(metas)} filings. Downloading first 2...")
             for m in metas[:2]:
                 crawler.download_filing(m)
    else:
        crawler.batch_process()
