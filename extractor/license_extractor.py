import os
import json
import time
import concurrent.futures
from typing import List, Dict, Optional
from tenacity import retry, wait_exponential, stop_after_attempt
import requests
import google.generativeai as genai
from google.generativeai.types import HarmCategory, HarmBlockThreshold
from tqdm import tqdm
from dotenv import load_dotenv

from utils.common import setup_logging, load_yaml_config, parse_filing_path

load_dotenv()

logger = setup_logging(__name__, log_file="extractor.log")

class LLMLicenseExtractor:
    def __init__(self, config_path: str = "config.yaml"):
        self.config = load_yaml_config(config_path)

        llm_config = self.config.get("llm", {})
        self.provider = str(llm_config.get("provider", "gemini")).strip().lower()
        self.model_name = llm_config.get("model", "models/gemini-2.0-flash")
        self.request_timeout_sec = int(llm_config.get("request_timeout_sec", 180))
        self.api_key = os.getenv("GEMINI_API_KEY")
        self.ollama_base_url = os.getenv(
            "OLLAMA_BASE_URL",
            llm_config.get("ollama_base_url", "http://localhost:11434"),
        ).rstrip("/")
        self.model = None

        if self.provider == "gemini":
            if not self.api_key:
                logger.warning("GEMINI_API_KEY not found in environment variables.")
            else:
                genai.configure(api_key=self.api_key)
                self.model = genai.GenerativeModel(self.model_name)
        elif self.provider == "ollama":
            logger.info("Using local Ollama model: %s", self.model_name)
        else:
            logger.warning(
                "Unsupported llm.provider='%s'. Supported providers: gemini, ollama.",
                self.provider,
            )

        # Load Agent Prompts
        self.prompts_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "prompts", "agents")
        self.interpreter_prompt = self._load_agent_prompt("03_contract_interpreter.md")
        self.quality_prompt = self._load_agent_prompt("05_quality_controller.md")

        # Initialize AI Router and RAG (if enabled in config)
        self.ai_router = None
        self.rag_engine = None
        self._init_smart_services()

    def _init_smart_services(self):
        """Initialize AI Router and RAG engine if configured."""
        router_config = self.config.get("ai_router", {})
        rag_config = self.config.get("rag", {})

        if router_config.get("enabled", False):
            try:
                from services.ai_router import AIRouter
                self.ai_router = AIRouter(config=router_config)
                logger.info("AI Router enabled (Qwen/Claude smart routing)")
            except Exception as e:
                logger.warning("AI Router init failed: %s. Using default provider.", e)

        if rag_config.get("enabled", False):
            try:
                from services.rag_engine import RAGEngine
                self.rag_engine = RAGEngine(persist_dir=rag_config.get("persist_dir"))
                logger.info("RAG Engine enabled (vector-based context retrieval)")
            except Exception as e:
                logger.warning("RAG Engine init failed: %s. Continuing without RAG.", e)

    def _load_agent_prompt(self, filename: str) -> str:
        try:
            path = os.path.join(self.prompts_dir, filename)
            with open(path, 'r', encoding='utf-8') as f:
                return f.read()
        except Exception as e:
            logger.warning(f"Failed to load prompt {filename}: {e}. Using default.")
            return ""

    @retry(wait=wait_exponential(multiplier=2, min=10, max=120), stop=stop_after_attempt(5))
    def _call_llm(self, full_prompt: str) -> str:
        """Calls configured LLM provider with retry logic."""
        if self.provider == "gemini":
            return self._call_gemini(full_prompt)
        if self.provider == "ollama":
            return self._call_ollama(full_prompt)
        raise ValueError(f"Unsupported provider: {self.provider}")

    def _call_gemini(self, full_prompt: str) -> str:
        if not self.api_key:
            raise ValueError("GEMINI_API_KEY missing")

        try:
            response = self.model.generate_content(
                full_prompt,
                generation_config=genai.types.GenerationConfig(
                    temperature=0.0,
                    response_mime_type="application/json"
                ),
                safety_settings={
                    HarmCategory.HARM_CATEGORY_HATE_SPEECH: HarmBlockThreshold.BLOCK_NONE,
                    HarmCategory.HARM_CATEGORY_HARASSMENT: HarmBlockThreshold.BLOCK_NONE,
                    HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT: HarmBlockThreshold.BLOCK_NONE,
                    HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT: HarmBlockThreshold.BLOCK_NONE,
                }
            )
            return response.text
        except Exception as e:
            if "429" in str(e) or "ResourceExhausted" in str(e):
                logger.warning("Resource Exhausted. Sleeping for 60s...")
                time.sleep(60)
            raise e

    def _call_ollama(self, full_prompt: str) -> str:
        payload = {
            "model": self.model_name,
            "prompt": full_prompt,
            "stream": False,
            "format": "json",
            "options": {"temperature": 0},
        }
        endpoint = f"{self.ollama_base_url}/api/generate"
        response = requests.post(endpoint, json=payload, timeout=self.request_timeout_sec)
        response.raise_for_status()
        body = response.json()
        text = body.get("response", "")
        if not text:
            raise ValueError("Empty response from Ollama")
        return text

    @staticmethod
    def _clean_json_response(response_text: str) -> str:
        cleaned_text = response_text.strip()
        if cleaned_text.startswith("```json"):
            cleaned_text = cleaned_text[7:]
        if cleaned_text.endswith("```"):
            cleaned_text = cleaned_text[:-3]
        if cleaned_text.startswith("```"):
            cleaned_text = cleaned_text[3:]

        cleaned_text = cleaned_text.strip()
        json_start = cleaned_text.find("{")
        json_end = cleaned_text.rfind("}")
        if json_start != -1 and json_end != -1 and json_end > json_start:
            cleaned_text = cleaned_text[json_start:json_end + 1]
        return cleaned_text

    def construct_prompt(self, footnote_text: str, metadata: Dict) -> str:
        # Combine the Agent Persona (Contract Interpreter) with the data context and JSON constraint
        
        base_prompt = self.interpreter_prompt if self.interpreter_prompt else "You are an expert license extractor."
        
        return f"""
{base_prompt}

---
## TASK CONTEXT
You are analyzing a specific footnote from an SEC filing to extract license agreements.

**METADATA:**
- Company: {metadata.get('company_name', 'Unknown')} (CIK: {metadata.get('cik', 'Unknown')})
- Filing: {metadata.get('form', 'Unknown')}
- Note: {metadata.get('note_number', 'Unknown')} - {metadata.get('note_title', 'Unknown')}

**TEXT TO ANALYZE:**
{footnote_text}

---
## OUTPUT INSTRUCTION (CRITICAL)
Although the Agent Prompt asks for a text report, **YOU MUST OUTPUT ONLY A VALID JSON OBJECT** matching the following schema. 
Translate your "Contract ID", "Parties", "Financial Terms", etc. directly into this JSON structure.
Do not output any markdown formatting like `**` or section headers outside the JSON.

**JSON SCHEMA:**
{{
  "agreements": [
    {{
      "parties": {{
        "licensor": {{"name": "...", "role": "..."}},
        "licensee": {{"name": "...", "role": "..."}}
      }},
      "technology": {{
        "name": "...",
        "category": "...", 
        "capacity": {{"value": ..., "unit": "..."}}
      }},
      "industry": "One of [Semiconductor, Pharmaceutical, Telecommunications, Software, Medical Device, Automotive, Energy, Consumer Electronics, Other]",
      "financial_terms": {{
        "upfront_payment": {{"amount": ..., "currency": "..."}},
        "royalty": {{"rate": ..., "unit": "..."}}
      }},
      "contract_terms": {{
        "term": {{"years": ...}},
        "territory": {{ "geographic": [...] }}
      }},
      "metadata": {{
        "confidence_score": 0.0 to 1.0,
        "extraction_reasoning": "Briefly explain why you extracted this based on the 'Contract Interpreter' persona logic"
      }}
    }}
  ]
}}
"""

    def extract_agreements(self, footnote_text: str, metadata: Dict) -> Dict:
        """
        Extracts license agreements using the Agentic Prompt.
        If AI Router is enabled, routes to Qwen/Claude based on complexity.
        If RAG is enabled, augments the prompt with similar past extractions.
        """
        # --- RAG context augmentation ---
        rag_context = ""
        if self.rag_engine:
            try:
                rag_context = self.rag_engine.get_context_for_extraction(
                    footnote_text[:2000]  # Use first 2000 chars for similarity search
                )
            except Exception as e:
                logger.warning("RAG context retrieval failed: %s", e)

        # --- AI Router path (smart Qwen/Claude routing) ---
        if self.ai_router:
            try:
                system_prompt = self.construct_prompt("", metadata)
                if rag_context:
                    system_prompt += f"\n\n## REFERENCE DATA (from similar past extractions)\n{rag_context}"

                filing_id = f"{metadata.get('cik', '')}_{metadata.get('form', '')}_{metadata.get('note_number', '')}"
                result = self.ai_router.process(
                    text=footnote_text,
                    filing_id=filing_id,
                    system_prompt=system_prompt,
                )

                # Incrementally index successful extractions into RAG
                if self.rag_engine and result.get("contracts"):
                    try:
                        for i, contract in enumerate(result["contracts"]):
                            doc_id = f"new_{filing_id}_{i}"
                            doc_text = json.dumps(contract, ensure_ascii=False)[:1000]
                            self.rag_engine.add_document(doc_id, doc_text, {
                                "source": "live_extraction",
                                "model": result.get("model_used", "unknown"),
                            })
                    except Exception:
                        pass  # Non-critical

                return {
                    "agreements": result.get("contracts", []),
                    "routing_info": result.get("processing_metadata", {}),
                    "model_used": result.get("model_used", "unknown"),
                    "confidence": result.get("confidence", 0.0),
                }
            except Exception as e:
                logger.warning("AI Router failed, falling back to default: %s", e)

        # --- Default path (original Gemini/Ollama) ---
        prompt = self.construct_prompt(footnote_text, metadata)
        if rag_context:
            prompt += f"\n\n## REFERENCE DATA (from similar past extractions)\n{rag_context}"

        try:
            if self.provider == "gemini" and not self.api_key:
                logging.warning("No API key, returning mock data")
                return {"agreements": [], "status": "mocked"}

            response_text = self._call_llm(prompt)

            cleaned_text = self._clean_json_response(response_text)
            data = json.loads(cleaned_text)
            return data
        except Exception as e:
            logger.error(f"Extraction failed: {e}")
            return {"agreements": [], "error": str(e)}

def process_file_item(args):
    """Worker for batch processing."""
    file_path, output_dir, extractor = args
    
    try:
        with open(file_path, 'r') as f:
            candidates = json.load(f)
            
        if not candidates:
            return 0
            
        # Reconstruct paths
        fp = parse_filing_path(file_path)
        accession = fp.get("accession", "")
        form = fp.get("form", "")
        cik = fp.get("cik", "")
        
        output_subdir = os.path.join(output_dir, cik, form, accession)
        os.makedirs(output_subdir, exist_ok=True)
        
        results = []
        for note in candidates:
            # We treat each candidate note as a separate extraction task
            meta = {
                'cik': cik,
                'form': form,
                'note_number': note.get('note_number'),
                'note_title': note.get('note_title'),
                'company_name': 'Unknown'
            }
            
            extraction = extractor.extract_agreements(note['content'], meta)
            
            # Merge with note metadata
            result_item = {
                "source_note": note,
                "extraction": extraction
            }
            results.append(result_item)
            
        output_file = os.path.join(output_subdir, "license_agreements.json")
        with open(output_file, 'w') as f:
            json.dump(results, f, indent=2)
            
        return len(results)
        
    except Exception as e:
        logger.error(f"Error processing {file_path}: {e}")
        return 0

def batch_process(config_path="config.yaml"):
    extractor = LLMLicenseExtractor(config_path)
    config = load_yaml_config(config_path)
        
    input_dir = config['paths']['parsed_footnotes']
    output_dir = config['paths']['extracted_licenses']
    
    # Find all license_candidates.json
    tasks = []
    for root, dirs, files in os.walk(input_dir):
        if "license_candidates.json" in files:
            tasks.append((os.path.join(root, "license_candidates.json"), output_dir, extractor))
            
    logger.info(f"Found {len(tasks)} candidate files to process.")
    
    # Gemini has strict rate limits (e.g. 15 RPM for free tier, but higher for paid).
    # We should be conservative.
    max_workers = config['llm'].get('max_parallel', 3)
    
    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {executor.submit(process_file_item, task): task for task in tasks}
        
        for future in tqdm(concurrent.futures.as_completed(futures), total=len(tasks)):
            try:
                count = future.result()
            except Exception as e:
                logger.error(f"Batch item failed: {e}")

if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == "batch":
        batch_process()
