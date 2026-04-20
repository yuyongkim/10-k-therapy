"""
Ollama processor: Local LLM via Ollama for license agreement extraction.
Supports any Ollama model (gemma3, qwen3, llama, etc.)
"""

import os
import json
import re
import logging
from typing import Dict, Any

import requests
from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger(__name__)


def _extract_json_from_text(text: str) -> str:
    """Extract JSON object from text that may contain thinking tags or markdown."""
    cleaned = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL).strip()
    cleaned = re.sub(r"```json\s*", "", cleaned)
    cleaned = re.sub(r"```\s*$", "", cleaned).strip()
    match = re.search(r"\{.*\}", cleaned, flags=re.DOTALL)
    return match.group(0) if match else cleaned


class OllamaProcessor:
    """Local LLM via Ollama."""

    def __init__(self, base_url: str = None, model: str = "gemma3:4b"):
        self.base_url = (base_url or os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")).rstrip("/")
        self.model = model
        self.timeout = 300

    def is_available(self) -> bool:
        try:
            resp = requests.get(f"{self.base_url}/api/tags", timeout=5)
            return resp.status_code == 200
        except Exception:
            return False

    def extract_contracts(self, text: str, system_prompt: str = "") -> Dict[str, Any]:
        prompt_prefix = "/no_think\n" if "qwen" in self.model else ""
        payload = {
            "model": self.model,
            "prompt": f"{prompt_prefix}{system_prompt}\n\n---\nTEXT TO ANALYZE:\n{text}\n\n---\nOutput valid JSON only. No explanation.",
            "stream": False,
            "format": "json" if "qwen" not in self.model else None,
            "options": {"temperature": 0, "num_ctx": 4096},
        }
        # Remove None values
        payload = {k: v for k, v in payload.items() if v is not None}

        try:
            resp = requests.post(
                f"{self.base_url}/api/generate",
                json=payload,
                timeout=self.timeout,
            )
            resp.raise_for_status()
            body = resp.json()
            raw = body.get("response", "")

            json_str = _extract_json_from_text(raw)
            data = json.loads(json_str)

            if "agreements" in data:
                agreements = data["agreements"]
            elif isinstance(data, dict) and ("licensor" in data or "licensee" in data or "licensor_name" in data):
                agreements = [data]
            elif isinstance(data, list):
                agreements = data
            else:
                agreements = []

            confidences = [
                a.get("metadata", {}).get("confidence_score", 0.5)
                for a in agreements
            ]
            avg_confidence = sum(confidences) / len(confidences) if confidences else 0.0

            return {
                "contracts": agreements,
                "average_confidence": avg_confidence,
                "raw_response": raw,
                "eval_duration_ms": body.get("eval_duration", 0) / 1_000_000,
            }
        except requests.exceptions.ConnectionError:
            logger.warning("Ollama not reachable at %s", self.base_url)
            return {"contracts": [], "average_confidence": 0.0, "error": "ollama_unreachable"}
        except Exception as e:
            logger.error("Ollama extraction failed: %s", e)
            return {"contracts": [], "average_confidence": 0.0, "error": str(e)}


# Backward compatibility alias
QwenProcessor = OllamaProcessor
