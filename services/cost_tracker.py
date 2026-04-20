"""
Cost tracker: Tracks AI API costs in SQLite for budget management.
"""

import os
import logging
import sqlite3
from datetime import datetime, timezone
from typing import Dict, Any

logger = logging.getLogger(__name__)


class CostTracker:
    """Tracks API costs in SQLite."""

    def __init__(self, db_path: str = None):
        self.db_path = db_path or os.path.join(
            os.path.dirname(os.path.dirname(__file__)),
            "data", "processed", "sec_dart_analytics.db",
        )

    def _ensure_table(self, conn: sqlite3.Connection):
        conn.execute("""
            CREATE TABLE IF NOT EXISTS ai_processing_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                filing_id TEXT,
                model_used TEXT NOT NULL,
                routing_decision TEXT,
                complexity_score INTEGER,
                confidence_score REAL,
                processing_time_sec REAL,
                input_tokens INTEGER DEFAULT 0,
                output_tokens INTEGER DEFAULT 0,
                cost_usd REAL DEFAULT 0.0,
                processing_path TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS cost_tracking (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                month TEXT NOT NULL,
                model TEXT NOT NULL,
                total_requests INTEGER DEFAULT 0,
                total_input_tokens INTEGER DEFAULT 0,
                total_output_tokens INTEGER DEFAULT 0,
                total_cost_usd REAL DEFAULT 0.0,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(month, model)
            )
        """)
        conn.commit()

    def log_processing(self, record: Dict[str, Any]):
        try:
            conn = sqlite3.connect(self.db_path)
            self._ensure_table(conn)
            conn.execute(
                """INSERT INTO ai_processing_log
                   (filing_id, model_used, routing_decision, complexity_score,
                    confidence_score, processing_time_sec, input_tokens,
                    output_tokens, cost_usd, processing_path)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    record.get("filing_id", ""),
                    record.get("model_used", ""),
                    record.get("routing_decision", ""),
                    record.get("complexity_score", 0),
                    record.get("confidence_score", 0.0),
                    record.get("processing_time_sec", 0.0),
                    record.get("input_tokens", 0),
                    record.get("output_tokens", 0),
                    record.get("cost_usd", 0.0),
                    record.get("processing_path", ""),
                ),
            )

            # Update monthly cost tracking
            month = datetime.now(timezone.utc).strftime("%Y-%m")
            model = record.get("model_used", "unknown")
            conn.execute(
                """INSERT INTO cost_tracking (month, model, total_requests,
                   total_input_tokens, total_output_tokens, total_cost_usd)
                   VALUES (?, ?, 1, ?, ?, ?)
                   ON CONFLICT(month, model) DO UPDATE SET
                     total_requests = total_requests + 1,
                     total_input_tokens = total_input_tokens + excluded.total_input_tokens,
                     total_output_tokens = total_output_tokens + excluded.total_output_tokens,
                     total_cost_usd = total_cost_usd + excluded.total_cost_usd,
                     updated_at = CURRENT_TIMESTAMP""",
                (
                    month, model,
                    record.get("input_tokens", 0),
                    record.get("output_tokens", 0),
                    record.get("cost_usd", 0.0),
                ),
            )
            conn.commit()
            conn.close()
        except Exception as e:
            logger.error("Failed to log processing: %s", e)

    def get_monthly_spend(self, month: str = None) -> float:
        month = month or datetime.now(timezone.utc).strftime("%Y-%m")
        try:
            conn = sqlite3.connect(self.db_path)
            self._ensure_table(conn)
            cursor = conn.execute(
                "SELECT COALESCE(SUM(total_cost_usd), 0) FROM cost_tracking WHERE month = ?",
                (month,),
            )
            result = cursor.fetchone()[0]
            conn.close()
            return result
        except Exception:
            return 0.0
