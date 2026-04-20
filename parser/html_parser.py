import os
import re
import json
import multiprocessing
from typing import List, Dict, Optional, Tuple
from bs4 import BeautifulSoup
import unicodedata
from tqdm import tqdm

from utils.common import setup_logging, load_yaml_config, parse_filing_path

logger = setup_logging(__name__, log_file="parser.log")

class SECHTMLParser:
    def __init__(self, html_content: str):
        self.soup = BeautifulSoup(html_content, 'lxml')
        self.text_content = self.soup.get_text(" ", strip=True)

    def find_footnotes_section(self) -> Optional[str]:
        """
        Attempts to find the 'Notes to Financial Statements' section.
        This is a heuristic approach and might needing tuning for specific filing formats.
        """
        # Common headers for notes section
        patterns = [
            r"Notes\s+to\s+(?:the\s+)?(?:Consolidated\s+)?Financial\s+Statements",
            r"NOTES\s+TO\s+FINANCIAL\s+STATEMENTS",
            r"Notes\s+to\s+Consolidated\s+Financial\s+Statements"
        ]
        
        # We look for the header. If found, we try to find the end.
        # This is simplified; robust parsing often requires iterating reliably through siblings.
        # For this implementation, we will try to extract the text between the start header 
        # and a likely end header (e.g., "Item 9", "Signatures", "Report of Independent...").
        
        # Normalize text for regex search
        text = self.text_content
        start_idx = -1
        
        for p in patterns:
            match = re.search(p, text, re.IGNORECASE)
            if match:
                start_idx = match.start()
                break
        
        if start_idx == -1:
            return None
            
        # Try to find end
        end_patterns = [
            r"Item\s+9",
            r"SIGNATURES",
            r"Report\s+of\s+Independent",
            r"Item\s+9A"
        ]
        
        end_idx = len(text)
        for p in end_patterns:
            match = re.search(p, text[start_idx+100:], re.IGNORECASE) # offset to avoid immediate match
            if match:
                found_end = start_idx + 100 + match.start()
                if found_end < end_idx:
                    end_idx = found_end
        
        return text[start_idx:end_idx]

    def extract_all_footnotes(self, footnotes_text: str) -> List[Dict]:
        """
        Splits the full footnotes text into individual notes.
        """
        # Regex to find "Note X" or "NOTE X" starts
        note_pattern = r"(Note\s+\d+|NOTE\s+\d+)\.?\s+([A-Z].+?)(?=(?:Note\s+\d+|NOTE\s+\d+)|$)"
        
        notes = []
        matches = list(re.finditer(note_pattern, footnotes_text, re.DOTALL))
        
        for i, match in enumerate(matches):
            number_str = match.group(1) # e.g. "Note 1"
            title = match.group(2).split('\n')[0].strip() # Take first line as title
            
            # proper content extraction (until next match or end)
            start = match.start()
            end = matches[i+1].start() if i+1 < len(matches) else len(footnotes_text)
            content = footnotes_text[start:end].strip()
            
            # Simple number extraction
            num_match = re.search(r"\d+", number_str)
            note_num = num_match.group(0) if num_match else str(i)
            
            notes.append({
                "note_number": note_num,
                "note_title": title,
                "content": content
            })
            
        return notes

    def filter_license_related_notes(self, notes: List[Dict]) -> List[Dict]:
        """
        Filters notes based on relevance to licensing/technology.
        """
        primary_keywords = [
            "license", "licensing", "technology transfer",
            "royalty", "royalties", "intellectual property", "know-how",
            "joint venture", "collaboration", "reseller", "distributor"
        ]
        secondary_keywords = [
            "intangible assets", "commitments", "related party",
            "agreement", "contract", "revenue", "payment", "development"
        ]
        companies = ["UOP", "Lummus", "Shell", "Axens", "Technip", "Dow", "Basell", "Exxon", "Lotte"]
        
        relevant_notes = []
        
        for note in notes:
            content_lower = note['content'].lower()
            score = 0
            
            # Scoring
            matched_primary = [k for k in primary_keywords if k in content_lower]
            matched_secondary = [k for k in secondary_keywords if k in content_lower]
            matched_companies = [c for c in companies if c.lower() in content_lower]
            
            score += len(matched_primary) * 3
            score += len(matched_secondary) * 1
            score += len(matched_companies) * 2
            
            if score >= 1: # Threshold lowered for demo purposes
                note['relevance_score'] = score
                note['matched_keywords'] = matched_primary + matched_secondary
                note['matched_companies'] = matched_companies
                relevant_notes.append(note)
                
        return relevant_notes

def process_single_filing(args):
    """Worker function for batch processing."""
    file_path, output_dir = args
    try:
        if not os.path.exists(file_path):
            return None
            
        with open(file_path, 'r', encoding='utf-8') as f:
            html = f.read()
            
        parser = SECHTMLParser(html)
        footnotes_text = parser.find_footnotes_section()
        
        if not footnotes_text:
            return None
            
        all_notes = parser.extract_all_footnotes(footnotes_text)
        license_notes = parser.filter_license_related_notes(all_notes)
        
        # Save results
        # Structure: output_dir/{cik}/{form}/{accession}/...
        # We need to reconstruct the path structure from file_path or pass metadata
        # For simplicity, assuming file_path is .../raw_filings/{cik}/{form}/{accession}/primary_document.html
        
        fp = parse_filing_path(file_path)
        accession = fp.get("accession", "")
        form = fp.get("form", "")
        cik = fp.get("cik", "")
        
        save_path = os.path.join(output_dir, cik, form, accession)
        os.makedirs(save_path, exist_ok=True)
        
        with open(os.path.join(save_path, "license_candidates.json"), 'w') as f:
            json.dump(license_notes, f, indent=2)
            
        with open(os.path.join(save_path, "full_footnotes.txt"), 'w', encoding='utf-8') as f:
            f.write(footnotes_text)
            
        return {
            "accession": accession,
            "total_notes": len(all_notes),
            "license_notes": len(license_notes)
        }
        
    except Exception as e:
        logger.error(f"Error processing {file_path}: {e}")
        return None

def batch_process(config_path="config.yaml"):
    config = load_yaml_config(config_path)
        
    raw_dir = config['paths']['raw_filings']
    parsed_dir = config['paths']['parsed_footnotes']
    
    # Collect all HTML files
    tasks = []
    for root, dirs, files in os.walk(raw_dir):
        for file in files:
            if file.endswith(".html") or file.endswith(".htm"):
                tasks.append((os.path.join(root, file), parsed_dir))
                
    logger.info(f"Found {len(tasks)} files to process.")
    
    # Multiprocessing
    workers = max(1, multiprocessing.cpu_count() - 1)
    results = []
    
    with multiprocessing.Pool(workers) as pool:
        for res in tqdm(pool.imap_unordered(process_single_filing, tasks), total=len(tasks)):
            if res:
                results.append(res)
                
    logger.info(f"Processed {len(results)} filings successfully.")

if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == "batch":
        batch_process()
