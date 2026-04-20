
import os
import requests
import json
import logging
import time
from typing import List, Dict, Optional
from datetime import datetime

logger = logging.getLogger(__name__)

class CourtListenerCrawler:
    """
    Crawls CourtListener API for patent infringement cases involving royalty damages.
    Requires COURTLISTENER_API_KEY in environment variables.
    """
    
    BASE_URL = "https://www.courtlistener.com/api/rest/v4/search/"
    
    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.getenv("COURTLISTENER_API_KEY")
        if not self.api_key:
            logger.warning("COURTLISTENER_API_KEY not found. API calls will likely fail (403).")
            
        self.headers = {
            "Authorization": f"Token {self.api_key}" if self.api_key else ""
        }

    def search_royalty_cases(self, pages: int = 1, query: str = None, court: str = None, start_date: str = None, end_date: str = None) -> List[Dict]:
        """
        Search for cases with dynamic parameters.
        """
        results = []
        # Default query if not provided
        q_val = query if query else 'patent AND "reasonable royalty" AND damages'
        
        params = {
            "q": q_val,
            "order_by": "dateFiled desc",
            "stat_Precedential": "on",
        }
        
        # Optional filters
        if court:
            params["court"] = court
        if start_date:
            params["filed_after"] = start_date
        if end_date:
            params["filed_before"] = end_date
            
        current_url = self.BASE_URL
        
        for page in range(1, pages + 1):
            if not current_url:
                break
                
            try:
                logger.info(f"Fetching CourtListener search page {page} with params: {params}...")
                response = requests.get(current_url, params=params if page == 1 else None, headers=self.headers)
                
                if response.status_code == 403:
                    logger.error("Authentication failed. Please check COURTLISTENER_API_KEY in .env")
                    return results
                
                response.raise_for_status()
                data = response.json()
                
                current_results = data.get('results', [])
                logger.info(f"Found {len(current_results)} cases on page {page}.")
                results.extend(current_results)
                
                current_url = data.get('next')
                # Respect rate limits usually handled by headers, but let's be safe
                time.sleep(1) 
                
            except Exception as e:
                logger.error(f"Error searching CourtListener: {e}")
                break
                
        return results

    def get_opinion_text(self, opinion_id: int) -> str:
        """Fetch full text for a specific opinion ID."""
        url = f"https://www.courtlistener.com/api/rest/v4/opinions/{opinion_id}/"
        try:
            response = requests.get(url, headers=self.headers)
            if response.status_code == 200:
                data = response.json()
                return data.get('plain_text') or data.get('html_with_citations') or ""
            elif response.status_code == 429:
                logger.warning("Rate limit hit fetching opinion. Sleeping...")
                time.sleep(5)
                return ""
            else:
                logger.warning(f"Failed to fetch opinion {opinion_id}: {response.status_code}")
                return ""
        except Exception as e:
            logger.error(f"Error fetching opinion {opinion_id}: {e}")
            return ""

    def enrich_cases_with_text(self, cases: List[Dict], limit: int = 100) -> List[Dict]:
        """
        Fetch full text for a subset of cases to enable better LLM extraction.
        """
        logger.info(f"Enriching top {limit} cases with full opinion text...")
        enriched_count = 0
        
        for i, case in enumerate(cases):
            if enriched_count >= limit:
                break
                
            opinions = case.get('opinions', [])
            if not opinions:
                continue
                
            # Use the first opinion
            op_id = opinions[0].get('id')
            if op_id:
                text = self.get_opinion_text(op_id)
                if text:
                    case['plain_text'] = text
                    enriched_count += 1
                    # Rate limit kindness
                    time.sleep(0.5) 
            
            if i % 10 == 0:
                logger.info(f"Enriched {enriched_count} cases so far...")
                
        logger.info(f"Finished enriching. Total with text: {enriched_count}")
        return cases

    def save_raw_cases(self, cases: List[Dict], output_dir: str):
        """Save raw case metadata to JSON."""
        os.makedirs(output_dir, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"court_cases_{timestamp}.json"
        filepath = os.path.join(output_dir, filename)
        
        with open(filepath, 'w') as f:
            json.dump(cases, f, indent=2)
            
        logger.info(f"Saved {len(cases)} raw cases to {filepath}")
        return filepath

if __name__ == "__main__":
    # Test run
    logging.basicConfig(level=logging.INFO)
    from dotenv import load_dotenv
    load_dotenv()
    
    crawler = CourtListenerCrawler()
    if crawler.api_key:
        cases = crawler.search_royalty_cases(pages=1)
        if cases:
            crawler.save_raw_cases(cases, "data/litigation/raw")
    else:
        print("Skipping test run: No API Key")
