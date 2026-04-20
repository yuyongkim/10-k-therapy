"""Utility functions for the unified disclosure parser."""

import re
from typing import Any, Optional

from bs4 import Tag


def safe_text(value: Any) -> str:
    return str(value).strip() if value is not None else ""


def clean_text(text: str) -> str:
    return re.sub(r"\s+", " ", safe_text(text)).strip()


def to_float(value: Any) -> Optional[float]:
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    text = safe_text(value).replace(",", "")
    match = re.search(r"-?\d+(?:\.\d+)?", text)
    if not match:
        return None
    try:
        return float(match.group(0))
    except ValueError:
        return None


def decode_document_bytes(raw: bytes) -> str:
    # SEC and DART sources can contain mixed encodings.
    for enc in ("utf-8", "cp949", "euc-kr", "latin-1"):
        try:
            return raw.decode(enc)
        except UnicodeDecodeError:
            continue
    return raw.decode("utf-8", errors="ignore")


def tag_attr(tag: Tag, attr_name: str) -> str:
    return safe_text(tag.get(attr_name) or tag.get(attr_name.lower()) or tag.get(attr_name.upper()))


# Backward-compatible aliases with underscore prefix
_safe_text = safe_text
_clean_text = clean_text
_to_float = to_float
_decode_document_bytes = decode_document_bytes
_tag_attr = tag_attr
