
import os
import json
import logging
from typing import List, Dict, Optional
import google.generativeai as genai
from dotenv import load_dotenv

# Load environment variables (for Gemini API)
load_dotenv()
logger = logging.getLogger(__name__)

class JudgmentParser:
    """
    Parses court opinion text to extract royalty rate information using LLM.
    Uses 'Contract Interpreter' persona logic adapted for litigation.
    """
    
    def __init__(self, model_name: str = "gemini-2.0-flash"):
        self.api_key = os.getenv("GEMINI_API_KEY")
        if not self.api_key:
            logger.warning("GEMINI_API_KEY not found. Parsing will fail.")
        else:
            genai.configure(api_key=self.api_key)
            self.model = genai.GenerativeModel(model_name)
            
        # Defines the extraction schema
        self.output_schema = {
            "type": "OBJECT",
            "properties": {
                "case_name": {"type": "STRING"},
                "docket_number": {"type": "STRING"},
                "decision_date": {"type": "STRING"},
                "royalty_rate": {
                    "type": "OBJECT",
                    "properties": {
                        "rate": {"type": "STRING", "description": "Percentage or lump sum amount"},
                        "base": {"type": "STRING", "description": "Royalty base (e.g., net sales)"},
                        "type": {"type": "STRING", "enum": ["Lump Sum", "Running Royalty", "Hybrid", "Unknown"]}
                    }
                },
                "product_category": {"type": "STRING"},
                "industry": {
                    "type": "STRING", 
                    "description": "Industry sector (e.g., Semiconductor, Pharmaceutical, Telecommunications, Software, Medical Device, Automotive, Energy, Consumer Electronics)",
                },
                "extraction_reasoning": {"type": "STRING", "description": "Why this rate was identified as reasonable royalty"},
                "source_name": {"type": "STRING"},
                "source_url": {"type": "STRING"}
            },
            "required": ["case_name", "royalty_rate", "extraction_reasoning", "industry"]
        }

    def _construct_prompt(self, opinion_text: str) -> str:
        """Constructs the prompt for the LLM."""
        return f"""
        You are a highly skilled Legal Contract Interpreter and Valuation Analyst.
        Your task is to analyze the following court opinion text related to a patent infringement case.
        
        GOAL: Identify and extract the "Reasonable Royalty" rate or damages amount determined by the court or jury.
        
        INSTRUCTIONS:
        1. Locate sections discussing damages, reasonable royalty, or Georgia-Pacific factors.
        2. Extract the specific royalty rate (e.g., "5%", "$2.00 per unit") or lump sum damages awarded.
        3. Identify the product or technology category involved.
        4. Classify the **Industry** into one of these categories: 
           [Semiconductor, Pharmaceutical, Telecommunications, Software, Medical Device, Automotive, Energy, Consumer Electronics, Other].
        5. Explain your reasoning in the 'extraction_reasoning' field.
        6. If no specific rate is mentioned or the text is irrelevant, return an empty object for royalty_rate.
        
        OPINION TEXT (Snippet):
        {opinion_text[:10000]}  # Truncate to avoid context limit if necessary
        """

    def parse_case(self, case_data: Dict) -> Optional[Dict]:
        """
        Parse a single case to extract royalty info.
        case_data should contain 'plain_text' or similar field from CourtListener.
        """
        if not self.api_key:
            return None
            
        # For now, we assume case_data has a 'snippet' or we need to fetch full text.
        # This implementation assumes we have some text to process.
        text_to_analyze = case_data.get('plain_text') or case_data.get('snippet', '')
        
        if not text_to_analyze or len(text_to_analyze) < 50:
            logger.warning(f"No sufficient text to analyze for case {case_data.get('caseName')}")
            return None

        prompt = self._construct_prompt(text_to_analyze)
        
        try:
            response = self.model.generate_content(
                prompt,
                generation_config=genai.GenerationConfig(
                    response_mime_type="application/json",
                    response_schema=self.output_schema
                )
            )
            result = json.loads(response.text)
            
            # Inject Metadata from Crawler Source
            if result:
                result['source_name'] = "CourtListener (CAFC)"
                # Construct full URL if absolute_url is partial
                abs_url = case_data.get('absolute_url', '')
                if abs_url and not abs_url.startswith('http'):
                    abs_url = f"https://www.courtlistener.com{abs_url}"
                result['source_url'] = abs_url
                
            return result
        except Exception as e:
            logger.error(f"LLM Parsing failed for case {case_data.get('caseName')}: {e}")
            return None

if __name__ == "__main__":
    # Test
    logging.basicConfig(level=logging.INFO)
    parser = JudgmentParser()
    sample_case = {
        "caseName": "Apple Inc. v. Samsung Electronics Co.",
        "snippet": "The jury awarded Apple $1.05 billion in damages. The expert testified that a reasonable royalty would be $7.14 per unit for the '381 patent."
    }
    result = parser.parse_case(sample_case)
    print(json.dumps(result, indent=2))
