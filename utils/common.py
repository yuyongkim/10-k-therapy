"""
Shared utilities for the SEC License Intelligence project.

Consolidates duplicated patterns:
- Logging configuration
- YAML config loading
- Path parsing (CIK/form/accession from directory structure)
- Text normalization
- Float/numeric parsing
- JSON response cleaning (Qwen thinking tags)
- Timestamped filename generation
- Safe nested dict access
"""

import json
import logging
import os
import re
import time
import threading
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml


# ---------------------------------------------------------------------------
# 1. Logging
# ---------------------------------------------------------------------------

def setup_logging(
    name: str,
    log_file: Optional[str] = None,
    level: int = logging.INFO,
    fmt: str = "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
) -> logging.Logger:
    """Configure and return a logger with optional file + stream handlers.

    Calling this once per module replaces the duplicated ``logging.basicConfig``
    blocks that appeared in 8+ files.
    """
    logger = logging.getLogger(name)
    if logger.handlers:
        return logger  # already configured

    logger.setLevel(level)
    formatter = logging.Formatter(fmt)

    stream_handler = logging.StreamHandler()
    stream_handler.setFormatter(formatter)
    logger.addHandler(stream_handler)

    if log_file:
        file_handler = logging.FileHandler(log_file, encoding="utf-8")
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)

    return logger


# ---------------------------------------------------------------------------
# 2. Configuration
# ---------------------------------------------------------------------------

def load_yaml_config(config_path: str = "config.yaml") -> dict:
    """Load a YAML configuration file and return as dict."""
    with open(config_path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def load_json_safe(path, encoding: str = "utf-8") -> Optional[dict]:
    """Load a JSON file, returning None on error."""
    try:
        with open(path, "r", encoding=encoding) as f:
            return json.load(f)
    except (OSError, json.JSONDecodeError):
        return None


def write_json(path, data, *, ensure_ascii: bool = False, indent: int = 2):
    """Write *data* as pretty-printed JSON."""
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=ensure_ascii, indent=indent)


# ---------------------------------------------------------------------------
# 3. Path Parsing (CIK / form / accession from directory structure)
# ---------------------------------------------------------------------------

def parse_filing_path(file_path: str) -> Dict[str, str]:
    """Extract CIK, form type, and accession number from a nested file path.

    Expected layout: ``…/<cik>/<form>/<accession>/<file>``
    """
    parts = file_path.replace("\\", "/").split("/")
    if len(parts) < 4:
        return {}
    return {
        "cik": parts[-4],
        "form": parts[-3],
        "accession": parts[-2],
        "filename": parts[-1],
    }


# ---------------------------------------------------------------------------
# 4. Text Normalization
# ---------------------------------------------------------------------------

def safe_text(value: Any) -> str:
    """Convert *value* to a stripped string (empty string for None)."""
    return str(value).strip() if value is not None else ""


def normalize_text(value: Any) -> str:
    """Lowercase, strip non-alphanumeric, collapse whitespace."""
    text = safe_text(value).lower()
    cleaned = [ch if ch.isalnum() else " " for ch in text]
    return " ".join("".join(cleaned).split())


def normalize_cik(value: Any) -> str:
    """Zero-pad a CIK to 10 digits."""
    digits = "".join(ch for ch in safe_text(value) if ch.isdigit())
    return digits.zfill(10) if digits else ""


# ---------------------------------------------------------------------------
# 5. Numeric Parsing
# ---------------------------------------------------------------------------

def parse_float(value: Any) -> Optional[float]:
    """Robustly parse a numeric value from mixed text."""
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    text = safe_text(value).replace(",", "")
    if not text:
        return None
    chars: list[str] = []
    seen_digit = False
    for ch in text:
        if ch.isdigit() or ch in ".-":
            chars.append(ch)
            if ch.isdigit():
                seen_digit = True
        elif seen_digit:
            break
    numeric = "".join(chars).strip()
    if not numeric or numeric in {".", "-", "-."}:
        return None
    try:
        return float(numeric)
    except ValueError:
        return None


# ---------------------------------------------------------------------------
# 6. JSON / LLM Response Cleaning
# ---------------------------------------------------------------------------

def clean_qwen_json(raw: str) -> Optional[dict]:
    """Extract JSON from a Qwen3 response that may contain ``<think>`` tags.

    Also handles markdown code fences (``\u0060\u0060\u0060json ... \u0060\u0060\u0060``).
    Returns parsed dict/list or *None* on failure.
    """
    cleaned = raw
    if "</think>" in cleaned:
        cleaned = cleaned.split("</think>")[-1].strip()

    # Strip markdown code fences
    cleaned = re.sub(r"```(?:json)?\s*", "", cleaned)
    cleaned = re.sub(r"```\s*$", "", cleaned)

    start = cleaned.find("{")
    end = cleaned.rfind("}") + 1
    if start < 0 or end <= start:
        # try list
        start = cleaned.find("[")
        end = cleaned.rfind("]") + 1
    if start >= 0 and end > start:
        try:
            return json.loads(cleaned[start:end])
        except json.JSONDecodeError:
            pass
    return None


# ---------------------------------------------------------------------------
# 7. Nested Dict Access
# ---------------------------------------------------------------------------

def nested_get(payload: Any, *path: str) -> Any:
    """Safely traverse nested dicts: ``nested_get(d, 'a', 'b', 'c')``."""
    current = payload
    for key in path:
        if not isinstance(current, dict):
            return None
        current = current.get(key)
    return current


# ---------------------------------------------------------------------------
# 8. Timestamped Filename
# ---------------------------------------------------------------------------

def timestamped_filename(prefix: str, ext: str = "json") -> str:
    """Return ``<prefix>_YYYYMMDD_HHMMSS.<ext>``."""
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    return f"{prefix}_{ts}.{ext}"


# ---------------------------------------------------------------------------
# 9. Rate Limiter (token-bucket)
# ---------------------------------------------------------------------------

class RateLimiter:
    """Thread-safe token-bucket rate limiter."""

    def __init__(self, rate: float):
        self.rate = rate
        self.tokens = rate
        self.last_update = time.time()
        self._lock = threading.Lock()

    def acquire(self):
        with self._lock:
            now = time.time()
            elapsed = now - self.last_update
            self.tokens = min(self.rate, self.tokens + elapsed * self.rate)
            self.last_update = now
            if self.tokens < 1:
                sleep_time = (1 - self.tokens) / self.rate
                time.sleep(sleep_time)
                self.tokens = 0
            else:
                self.tokens -= 1
