"""
AI Router: Smart model routing between Qwen (local) and Claude (cloud)

Routes extraction tasks based on text complexity:
- Simple texts → Qwen via Ollama (free)
- Complex texts → Claude API (paid, tracked)
- Medium texts → Qwen first, fallback to Claude if low confidence
"""

import time
import logging
import sqlite3
from datetime import datetime, timezone
from typing import Dict, Any

from .complexity_analyzer import ComplexityAnalyzer, ComplexityScore
from .qwen_processor import QwenProcessor
from .claude_processor import ClaudeProcessor
from .cost_tracker import CostTracker

# Re-export for backward compatibility:
#   from services.ai_router import QwenProcessor, ClaudeProcessor, CostTracker
__all__ = ["AIRouter", "QwenProcessor", "ClaudeProcessor", "CostTracker"]

logger = logging.getLogger(__name__)


class AIRouter:
    """Smart AI routing: complexity analysis → model selection → extraction → validation."""

    def __init__(self, config: Dict[str, Any] = None):
        config = config or {}
        self.complexity_analyzer = ComplexityAnalyzer()
        self.qwen = QwenProcessor(
            base_url=config.get("ollama_base_url"),
            model=config.get("qwen_model", "qwen2.5:7b"),
        )
        self.claude = ClaudeProcessor(
            model=config.get("claude_model", "claude-sonnet-4-20250514"),
        )
        self.cost_tracker = CostTracker(config.get("db_path"))

        self.confidence_threshold = float(config.get("confidence_threshold", 0.7))
        self.monthly_budget = float(config.get("monthly_budget_usd", 50))

    def _is_budget_exceeded(self) -> bool:
        return self.cost_tracker.get_monthly_spend() >= self.monthly_budget

    def process(
        self,
        text: str,
        filing_id: str = "",
        system_prompt: str = "",
    ) -> Dict[str, Any]:
        """
        Main processing: complexity analysis → model selection → extraction → logging.
        """
        start_time = time.time()

        # Step 1: Complexity analysis
        complexity = self.complexity_analyzer.analyze_text(text)
        routing = complexity.get_routing_decision()

        # Budget override: if exceeded, force qwen_only
        if routing != "qwen_only" and self._is_budget_exceeded():
            logger.warning("Monthly budget exceeded. Forcing qwen_only.")
            routing = "qwen_only"

        # Qwen availability check
        qwen_available = self.qwen.is_available()
        if not qwen_available and routing in ("qwen_only", "qwen_with_fallback"):
            if self.claude.is_available():
                routing = "claude_direct"
            else:
                return {
                    "contracts": [],
                    "error": "no_model_available",
                    "model_used": "none",
                }

        logger.info(
            "Complexity: %d/10 → Routing: %s (filing: %s)",
            complexity.total_score, routing, filing_id,
        )

        # Step 2: Execute routing
        result = self._execute_routing(routing, text, system_prompt, complexity)

        # Step 3: Log processing
        processing_time = time.time() - start_time
        log_record = {
            "filing_id": filing_id,
            "model_used": result.get("model_used", "unknown"),
            "routing_decision": routing,
            "complexity_score": complexity.total_score,
            "confidence_score": result.get("confidence", 0.0),
            "processing_time_sec": processing_time,
            "input_tokens": result.get("input_tokens", 0),
            "output_tokens": result.get("output_tokens", 0),
            "cost_usd": result.get("api_cost_usd", 0.0),
            "processing_path": result.get("processing_path", routing),
        }
        self.cost_tracker.log_processing(log_record)

        result["processing_metadata"] = {
            "complexity": {
                "total": complexity.total_score,
                "length": complexity.length_factor,
                "legal_density": complexity.legal_density,
                "numeric": complexity.numeric_complexity,
                "ambiguity": complexity.ambiguity_factor,
            },
            "processing_time_sec": processing_time,
            "routing_decision": routing,
            "filing_id": filing_id,
        }

        return result

    def _execute_routing(
        self, routing: str, text: str, system_prompt: str, complexity: ComplexityScore,
    ) -> Dict[str, Any]:

        if routing == "qwen_only":
            r = self.qwen.extract_contracts(text, system_prompt)
            return {
                "contracts": r["contracts"],
                "confidence": r["average_confidence"],
                "model_used": "qwen",
                "api_cost_usd": 0.0,
                "processing_path": "qwen_only",
            }

        elif routing == "qwen_with_fallback":
            r = self.qwen.extract_contracts(text, system_prompt)
            if r["average_confidence"] >= self.confidence_threshold:
                return {
                    "contracts": r["contracts"],
                    "confidence": r["average_confidence"],
                    "model_used": "qwen",
                    "api_cost_usd": 0.0,
                    "processing_path": "qwen_sufficient",
                }
            # Fallback to Claude
            logger.info(
                "Qwen confidence %.2f < %.2f, falling back to Claude",
                r["average_confidence"], self.confidence_threshold,
            )
            refined = self.claude.refine_qwen_result(r, text)
            return {
                "contracts": refined.get("contracts", []),
                "confidence": refined.get("final_confidence", 0.0),
                "model_used": "qwen_claude_hybrid",
                "api_cost_usd": refined.get("estimated_cost", 0.0),
                "processing_path": "qwen_to_claude_fallback",
                "qwen_initial_confidence": r["average_confidence"],
            }

        else:  # claude_direct
            r = self.claude.extract_with_claude(text, system_prompt)
            return {
                "contracts": r.get("contracts", []),
                "confidence": r.get("confidence", 0.0),
                "model_used": "claude",
                "api_cost_usd": r.get("estimated_cost", 0.0),
                "input_tokens": r.get("input_tokens", 0),
                "output_tokens": r.get("output_tokens", 0),
                "processing_path": "claude_direct",
            }

    def get_stats(self) -> Dict[str, Any]:
        """Get routing statistics from the database."""
        try:
            conn = sqlite3.connect(self.cost_tracker.db_path)
            self.cost_tracker._ensure_table(conn)

            stats = {}
            cur = conn.execute("SELECT COUNT(*) FROM ai_processing_log")
            stats["total_processed"] = cur.fetchone()[0]

            cur = conn.execute(
                "SELECT model_used, COUNT(*) FROM ai_processing_log GROUP BY model_used"
            )
            stats["by_model"] = dict(cur.fetchall())

            cur = conn.execute(
                "SELECT COALESCE(SUM(cost_usd), 0) FROM ai_processing_log"
            )
            stats["total_cost_usd"] = cur.fetchone()[0]

            cur = conn.execute(
                "SELECT COALESCE(AVG(confidence_score), 0) FROM ai_processing_log"
            )
            stats["avg_confidence"] = cur.fetchone()[0]

            month = datetime.now(timezone.utc).strftime("%Y-%m")
            stats["monthly_spend"] = self.cost_tracker.get_monthly_spend(month)
            stats["monthly_budget"] = self.monthly_budget
            stats["budget_remaining"] = self.monthly_budget - stats["monthly_spend"]

            conn.close()
            return stats
        except Exception as e:
            logger.error("Failed to get stats: %s", e)
            return {}
