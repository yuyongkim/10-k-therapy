"""Unified disclosure parser — thin re-export module and CLI entry point.

All classes and functions are re-exported here for backward compatibility.
Imports of the form ``from parser.unified_disclosure_parser import X`` continue
to work unchanged.
"""

import argparse
import json
from pathlib import Path
from typing import Any, Dict, Optional

# Re-export constants (all public names)
from .constants import (  # noqa: F401
    AMOUNT_RE,
    COMMON_TO_DART_LABEL,
    COMMON_TO_SEC_LABEL,
    CURRENCY_CODE_RE,
    CURRENCY_RE,
    DART_HEADING_PATTERNS,
    FINANCIAL_SIGNAL_RE,
    INSIGHT_KEYWORDS,
    ITEM_CODE_RE,
    PARSER_VERSION,
    PERCENT_RE,
    SEC_KEY_METRIC_CONCEPTS,
    SEC_TO_COMMON_TAG,
    YEAR_RE,
)

# Re-export utility functions (both public and underscore-prefixed names)
from .utils import (  # noqa: F401
    clean_text as _clean_text,
    decode_document_bytes as _decode_document_bytes,
    safe_text as _safe_text,
    tag_attr as _tag_attr,
    to_float as _to_float,
)

# Re-export parser classes
from .base_parser import DocumentParser  # noqa: F401
from .sec_parser import SEC10KParser  # noqa: F401
from .dart_disclosure_parser import DARTParser  # noqa: F401


def validate_schema_output(json_output: Dict[str, Any]) -> bool:
    required_top = {"document_id", "source_info", "company", "processing_info", "sections"}
    if not isinstance(json_output, dict):
        return False
    if not required_top.issubset(set(json_output.keys())):
        return False
    if not isinstance(json_output.get("sections"), list):
        return False

    required_section = {"section_id", "section_mapping", "content", "extracted_insights"}
    required_mapping = {"common_tag", "sec_label", "dart_label", "order_index"}
    required_content = {"raw_html", "plain_text", "token_count", "has_tables", "has_financial_data"}

    for section in json_output["sections"]:
        if not isinstance(section, dict):
            return False
        if not required_section.issubset(set(section.keys())):
            return False
        if not required_mapping.issubset(set(section["section_mapping"].keys())):
            return False
        if not required_content.issubset(set(section["content"].keys())):
            return False
    return True


def _load_optional_license_json(path: Optional[str]) -> Any:
    if not path:
        return None
    p = Path(path)
    if not p.exists():
        return None
    try:
        return json.loads(p.read_text(encoding="utf-8", errors="ignore"))
    except json.JSONDecodeError:
        return None


def _default_sample_sec_html() -> str:
    return str(
        Path("data")
        / "raw_filings"
        / "0000002098"
        / "10-K"
        / "0000950170-25-034843"
        / "primary_document.html"
    )


def _default_sample_sec_metadata() -> str:
    return str(
        Path("data")
        / "raw_filings"
        / "0000002098"
        / "10-K"
        / "0000950170-25-034843"
        / "filing_metadata.json"
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="SEC/DART unified disclosure schema parser")
    parser.add_argument("--source-type", choices=["SEC", "DART"], default="SEC")
    parser.add_argument("--html-path", default=_default_sample_sec_html())
    parser.add_argument("--metadata-path", default=_default_sample_sec_metadata())
    parser.add_argument("--license-json", default=None)
    parser.add_argument("--output", default=None)
    parser.add_argument("--print-analysis", action="store_true")
    args = parser.parse_args()

    if args.source_type == "SEC":
        doc_parser: DocumentParser = SEC10KParser(args.html_path, args.metadata_path)
    else:
        doc_parser = DARTParser(args.html_path, args.metadata_path)

    license_payload = _load_optional_license_json(args.license_json)
    if license_payload is not None:
        doc_parser.integrate_license_analysis(license_payload)

    result = doc_parser.to_schema_json()
    is_valid = validate_schema_output(result)

    if args.output:
        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")

    if args.print_analysis:
        payload = doc_parser.get_section_analysis_table()
    else:
        payload = result

    try:
        print(json.dumps(payload, indent=2, ensure_ascii=False))
    except UnicodeEncodeError:
        # Windows cp949 terminals can fail on a few unicode code points.
        print(json.dumps(payload, indent=2, ensure_ascii=True))
    print(f"schema_valid={is_valid}")


if __name__ == "__main__":
    main()
