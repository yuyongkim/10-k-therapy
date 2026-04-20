import os
import sys
import json
import logging
from dotenv import load_dotenv

load_dotenv()

# Add the project root to the python path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from extractor.license_extractor import LLMLicenseExtractor

# Configure logging
logging.basicConfig(level=logging.INFO)

def test_extraction():
    # Mock config path - assuming we run from 'tests' dir or project root
    config_path = "config.yaml"
    
    # Initialize extractor
    try:
        extractor = LLMLicenseExtractor(config_path)
    except Exception as e:
        print(f"Failed to initialize extractor: {e}")
        return

    # Sample text from Worlds Inc. filing (CIK 0000001961)
    sample_text = """
    NOTE 8 – SALE OF MARKETABLE SECURITIES When Worlds Inc. spun off Worlds Online Inc. in January
    2011, the Company retained 5,936,115 shares of common stock in Worlds Online Inc. (now named MariMed Inc.).
    The Company’s sources of revenue after the spinoff was expected to be from sublicenses
    of the patented technology by Worlds Online and any revenue that may be generated from enforcing its patents.
    Commencing in the first half of 2023, the Company expects that its revenues will come from its expansion of its legacy celebrity worlds and its collection of
    non-fungible tokens.
    """

    metadata = {
        'cik': '0000001961',
        'form': '10-K',
        'note_number': '8',
        'note_title': 'SALE OF MARKETABLE SECURITIES',
        'company_name': 'Worlds Inc.'
    }

    print("Running extraction on sample text...")
    result = extractor.extract_agreements(sample_text, metadata)
    
    print("\nExtraction Result:")
    print(json.dumps(result, indent=2))

    # Verification
    if "agreements" in result:
        for agreement in result["agreements"]:
            industry = agreement.get("industry")
            print(f"\nExtracted Industry: {industry}")
            if industry in ["Semiconductor", "Pharmaceutical", "Telecommunications", "Software", "Medical Device", "Automotive", "Energy", "Consumer Electronics", "Other"]:
                print("SUCCESS: Industry is in the valid list.")
            else:
                print(f"WARNING: Industry '{industry}' is NOT in the standard list.")
    else:
        print("FAILED: No agreements extracted or API Error.")

if __name__ == "__main__":
    test_extraction()
