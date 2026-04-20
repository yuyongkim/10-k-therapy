import os
import json
import time
from pathlib import Path
from typing import List, Dict
import sys
from tqdm import tqdm
import concurrent.futures

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from extractor.license_extractor import LLMLicenseExtractor
from utils.common import setup_logging

logger = setup_logging("BatchContractExtractor", log_file="batch_extractor.log")

class FullContractExtractor(LLMLicenseExtractor):
    """
    Extended extractor for full contract text (Exhibit 10).
    Overrides prompt construction to be specific to full agreements.
    """
    
    def construct_prompt(self, contract_text: str, metadata: Dict) -> str:
        # Adjusted prompt for full agreement
        base_prompt = "You are an expert legal analyst specializing in intellectual property licensing."
        
        # Truncate text if absolutely massive (though 1.5 Flash handles ~1M tokens)
        # Let's keep it safe at 100k chars for now to avoid timeout/cost issues if not needed
        # But we want header paragraphs mostly.
        # Actually, let's pass the first 50k characters which usually contain the definitions and grant clauses.
        truncated_text = contract_text[:50000]
        if len(contract_text) > 50000:
            truncated_text += "\n...[TRUNCATED]..."

        return f"""
{base_prompt}

---
## TASK CONTEXT
You are analyzing a **FULL EXECUTION COPY** of a material contract (Exhibit 10) filed with the SEC.
Your goal is to determine if this is a **LICENSE AGREEMENT** (IP, Software, Patent, Joint Venture with tech transfer) and extract key terms.

**METADATA:**
- Filename: {metadata.get('filename')}
- Title: {metadata.get('title')}
- Company: {metadata.get('company_name', 'Unknown')} (CIK: {metadata.get('cik', 'Unknown')})

**TEXT TO ANALYZE (Truncated):**
{truncated_text}

---
## OUTPUT INSTRUCTION
1. **CLASSIFICATION**: First, determine if this is a License Agreement. 
   - IGNORE: Employment agreements, Stock purchase, Leases, Credit agreements, generalized Service agreements without specific IP grant.
   - KEEP: Patent licenses, Software licenses, Joint Development, Manufacturing with IP license, Distribution with Trademark license.

2. **JSON OUTPUT**: Output a valid JSON object.

**JSON SCHEMA:**
{{
  "is_license": boolean,
  "agreement_type": "Patent License | Software License | JV | Manufacturing | Other | Not a License",
  "parties": {{
    "licensor": {{"name": "...", "role": "..."}},
    "licensee": {{"name": "...", "role": "..."}}
  }},
  "technology": {{
    "name": "...",
    "category": "Pharmaceutical | Semiconductor | Software | etc",
    "description": "Short summary of the licensed technology"
  }},
  "financial_terms": {{
    "upfront_payment": {{"amount": "Number or null", "currency": "..."}},
    "royalty_rate": "String description (e.g. '5% of Net Sales')",
    "exclusivity": "Exclusive | Non-Exclusive | Co-Exclusive"
  }},
  "date": "Effective Date YYYY-MM-DD",
  "term": "Duration in years or 'Perpetual' or 'Until Expiry'",
  "confidence_score": 0.0 to 1.0,
  "reasoning": "Why you classified it this way"
}}
"""

def process_batch_file(file_path: Path, extractor: FullContractExtractor, output_dir: Path):
    """Process a single JSON file containing multiple parsed contracts."""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            contracts = json.load(f)
            
        results = []
        # We can process contracts within this batch in parallel or serial
        # Given we run multiple batch files in parallel, let's do serial here to manage global rate limit better
        for contract in contracts:
            meta = contract.get('filing_meta', {})
            meta['start_index'] = 0 # Placeholder
            meta['filename'] = contract.get('filename')
            meta['title'] = contract.get('title')
            
            # Simple heuristic filter before LLM: Title contains 'License', 'Agreement', 'Technology'
            # To save tokens, we might skip obviously non-relevant ones if title is clear.
            # But titles are often vague "EXHIBIT 10.1". Let's trust the LLM for now or do a quick keyword check.
            text_lower = contract['text'][:2000].lower()
            if not any(x in text_lower for x in ['license', 'intellectual property', 'patent', 'royalty', 'software', 'technology', 'grant', 'agreement']):
                 # Skip purely financial/admin docs
                 continue

            extraction = extractor.extract_agreements(contract['text'], meta)
            
            # Save if it is a license
            if extraction.get('is_license'):
                result_item = {
                    "source_meta": meta,
                    "extraction": extraction,
                    "source_file": str(file_path)
                }
                results.append(result_item)
        
        if results:
            out_name = f"extracted_{file_path.stem}.json"
            with open(output_dir / out_name, 'w', encoding='utf-8') as f:
                json.dump(results, f, indent=2)
                
        return len(results)
        
    except Exception as e:
        logger.error(f"Failed to process {file_path}: {e}")
        return 0

def run_batch_extraction():
    # Project root. Override with PROJECT_ROOT env var if running elsewhere.
    BASE_DIR = Path(os.environ.get("PROJECT_ROOT", ".")).resolve()
    INPUT_DIR = BASE_DIR / "data/parsed_contracts"
    OUTPUT_DIR = BASE_DIR / "data/extracted_licenses"
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    
    extractor = FullContractExtractor("config.yaml")
    
    # Get all parsed json files
    files = list(INPUT_DIR.glob("parsed_contracts_*.json"))
    logger.info(f"Found {len(files)} batch files to process.")
    
    # Process in parallel
    # Be careful with rate limits. 
    max_workers = 1 # VERY CONSERVATIVE for Free Tier
    
    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {executor.submit(process_batch_file, f, extractor, OUTPUT_DIR): f for f in files}
        
        total_licenses = 0
        for future in tqdm(concurrent.futures.as_completed(futures), total=len(files)):
            try:
                count = future.result()
                total_licenses += count
                # Add delay between files to let quota cool down
                time.sleep(10) 
            except Exception as e:
                logger.error(f"Worker failed: {e}")
                
    logger.info(f"Extraction complete. Total potential licenses found: {total_licenses}")

if __name__ == "__main__":
    run_batch_extraction()
