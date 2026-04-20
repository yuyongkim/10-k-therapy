import os
from pathlib import Path
from typing import List, Dict, Optional
import json
from tqdm import tqdm
import sys

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from parser.contract_parser import ContractParser
from utils.common import setup_logging

logger = setup_logging("BatchParser", log_file="parser.log")

class BatchContractParser:
    def __init__(self, data_dir: str, output_dir: str):
        self.data_dir = Path(data_dir)
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
    def find_all_exhibits(self) -> List[Path]:
        """Recursively find all Exhibit 10 HTML files."""
        logger.info(f"Scanning {self.data_dir} for exhibits...")
        # Look for files in 'exhibits' directories
        # Pattern: raw_filings/{cik}/{form}/{accession}/exhibits/*.htm*
        # We can just search for all files in any 'exhibits' folder
        exhibit_files = []
        
        # Walk potentially large directory structure
        for root, dirs, files in os.walk(self.data_dir):
            if 'exhibits' in Path(root).parts:
                for file in files:
                    if file.endswith(('.htm', '.html')):
                        exhibit_files.append(Path(root) / file)
                        
        logger.info(f"Found {len(exhibit_files)} total exhibit files.")
        return exhibit_files

    def parse_file(self, file_path: Path) -> Optional[Dict]:
        """Parse a single file and return structured data."""
        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
                
            parser = ContractParser(content)
            clean_text = parser.get_clean_text()
            title = parser.get_title()
            
            # Extract metadata from path or sibling filing_metadata.json if possible
            # Path: .../accession/exhibits/filename
            # Metadata: .../accession/filing_metadata.json
            parent_dir = file_path.parent.parent # Accession dir
            meta_path = parent_dir / "filing_metadata.json"
            
            meta = {}
            if meta_path.exists():
                with open(meta_path, 'r') as f:
                    meta = json.load(f)
            
            return {
                "filename": file_path.name,
                "title": title,
                "text": clean_text,
                "filing_meta": meta,
                "source_path": str(file_path)
            }
            
        except Exception as e:
            logger.error(f"Failed to parse {file_path}: {e}")
            return None

    def run(self):
        files = self.find_all_exhibits()
        
        results = []
        # Process in batches to verify progress
        for i, file_path in enumerate(tqdm(files)):
            data = self.parse_file(file_path)
            if data:
                # Basic validation: filter out very short texts (likely empty or errors)
                if len(data['text']) > 1000:
                    results.append(data)
            
            # Save intermediate results every 1000 files
            if (i + 1) % 1000 == 0:
                self._save_batch(results, i)
                results = [] # Clear memory
                
        # Save remaining
        if results:
            self._save_batch(results, "final")
            
    def _save_batch(self, data: List[Dict], distinct_id):
        out_path = self.output_dir / f"parsed_contracts_{distinct_id}.json"
        logger.info(f"Saving batch of {len(data)} to {out_path}")
        with open(out_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

if __name__ == "__main__":
    # Project root. Override with PROJECT_ROOT env var if running elsewhere.
    BASE_DIR = Path(os.environ.get("PROJECT_ROOT", ".")).resolve()
    RAW_DATA = BASE_DIR / "data/raw_filings"
    OUTPUT_DIR = BASE_DIR / "data/parsed_contracts"
    
    parser = BatchContractParser(RAW_DATA, OUTPUT_DIR)
    parser.run()
