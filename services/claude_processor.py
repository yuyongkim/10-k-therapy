"""
Claude processor: Claude API processor for complex license agreement extraction.
"""

import os
import json
import logging
from typing import Dict, Any

from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger(__name__)


class ClaudeProcessor:
    """Claude API processor for complex texts."""

    def __init__(self, model: str = "claude-sonnet-4-20250514"):
        self.api_key = os.getenv("ANTHROPIC_API_KEY", "")
        self.model = model
        self.max_tokens = 4096

    def is_available(self) -> bool:
        return bool(self.api_key)

    def _estimate_cost(self, input_tokens: int, output_tokens: int) -> float:
        """Estimate cost in USD based on Claude pricing."""
        # Sonnet 4 pricing (approximate)
        input_cost = (input_tokens / 1_000_000) * 3.0
        output_cost = (output_tokens / 1_000_000) * 15.0
        return input_cost + output_cost

    def extract_with_claude(self, text: str, system_prompt: str = "") -> Dict[str, Any]:
        if not self.api_key:
            return {"contracts": [], "confidence": 0.0, "error": "no_api_key"}

        try:
            import anthropic
            client = anthropic.Anthropic(api_key=self.api_key)

            message = client.messages.create(
                model=self.model,
                max_tokens=self.max_tokens,
                system=system_prompt or "You are an expert license agreement extractor. Output valid JSON only.",
                messages=[
                    {
                        "role": "user",
                        "content": f"Extract all license agreements from the following text. Output valid JSON with an 'agreements' array.\n\n{text}",
                    }
                ],
            )

            raw = message.content[0].text
            # Clean markdown wrapping
            cleaned = raw.strip()
            if cleaned.startswith("```json"):
                cleaned = cleaned[7:]
            if cleaned.endswith("```"):
                cleaned = cleaned[:-3]
            cleaned = cleaned.strip()

            data = json.loads(cleaned)
            agreements = data.get("agreements", [])

            input_tokens = message.usage.input_tokens
            output_tokens = message.usage.output_tokens
            cost = self._estimate_cost(input_tokens, output_tokens)

            confidences = [
                a.get("metadata", {}).get("confidence_score", 0.7)
                for a in agreements
            ]
            avg_confidence = sum(confidences) / len(confidences) if confidences else 0.0

            return {
                "contracts": agreements,
                "confidence": avg_confidence,
                "estimated_cost": cost,
                "input_tokens": input_tokens,
                "output_tokens": output_tokens,
            }
        except ImportError:
            logger.error("anthropic package not installed. Run: pip install anthropic")
            return {"contracts": [], "confidence": 0.0, "error": "anthropic_not_installed"}
        except Exception as e:
            logger.error("Claude extraction failed: %s", e)
            return {"contracts": [], "confidence": 0.0, "error": str(e)}

    def refine_qwen_result(self, qwen_result: Dict, original_text: str) -> Dict[str, Any]:
        """Refine a low-confidence Qwen result using Claude."""
        if not self.api_key:
            return qwen_result

        try:
            import anthropic
            client = anthropic.Anthropic(api_key=self.api_key)

            refinement_prompt = f"""You are refining a license agreement extraction that had low confidence.

ORIGINAL TEXT:
{original_text}

INITIAL EXTRACTION (low confidence):
{json.dumps(qwen_result.get('contracts', []), indent=2)}

Please re-analyze the original text and provide a corrected, complete extraction.
Fix any errors, fill in missing fields, and improve confidence scores.
Output valid JSON with an 'agreements' array."""

            message = client.messages.create(
                model=self.model,
                max_tokens=self.max_tokens,
                messages=[{"role": "user", "content": refinement_prompt}],
            )

            raw = message.content[0].text
            cleaned = raw.strip()
            if cleaned.startswith("```json"):
                cleaned = cleaned[7:]
            if cleaned.endswith("```"):
                cleaned = cleaned[:-3]

            data = json.loads(cleaned.strip())
            cost = self._estimate_cost(message.usage.input_tokens, message.usage.output_tokens)

            return {
                "contracts": data.get("agreements", []),
                "final_confidence": 0.85,
                "estimated_cost": cost,
                "refinement_applied": True,
            }
        except Exception as e:
            logger.error("Claude refinement failed: %s", e)
            return qwen_result
