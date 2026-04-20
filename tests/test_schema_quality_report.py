import json
import tempfile
from pathlib import Path

from utils.schema_quality_report import evaluate_schema


def test_evaluate_schema_flags_low_coverage_dart():
    payload = {
        "document_id": "DART_001_2025_Q3",
        "source_info": {"system": "DART", "filing_date": "20251114"},
        "company": {"name": "Test", "identifier": "001"},
        "processing_info": {"total_tokens": 1000, "parser_version": "v1.1.0"},
        "document_intelligence": {"core_mapping_completeness": 0.25, "sections_with_tables": 1},
        "sections": [
            {"section_mapping": {"common_tag": "business_overview"}},
            {"section_mapping": {"common_tag": "major_events"}},
        ],
    }
    with tempfile.TemporaryDirectory() as td:
        p = Path(td) / "schema.json"
        p.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
        row = evaluate_schema(p)

    assert row["system"] == "DART"
    assert row["sections_count"] == 2
    assert row["issue_count"] >= 1
    assert "dart_section_coverage_low" in row["issues"]


def test_evaluate_schema_flags_missing_metadata_for_sec():
    payload = {
        "document_id": "SEC_001_2025",
        "source_info": {"system": "SEC", "filing_date": "20251231"},
        "company": {"name": "Acme", "identifier": "0001"},
        "processing_info": {},
        "document_intelligence": {"sections_with_tables": 0},
        "sections": [
            {"section_mapping": {}},
            {"section_mapping": {}},
        ],
        "xbrl_summary": {},
    }
    with tempfile.TemporaryDirectory() as td:
        p = Path(td) / "schema.json"
        p.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
        row = evaluate_schema(p)

    assert row["system"] == "SEC"
    assert "missing_sec_xbrl_facts" in row["issues"]
    assert "missing_common_tags" in row["issues"]
    assert "missing_parser_version" in row["issues"]
    assert "missing_total_tokens" in row["issues"]


def test_evaluate_schema_tolerates_non_dict_company_and_source_info():
    payload = {
        "document_id": "SEC_001",
        "source_info": "not-a-dict",
        "company": ["unexpected"],
        "sections": [],
    }
    with tempfile.TemporaryDirectory() as td:
        p = Path(td) / "schema.json"
        p.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
        row = evaluate_schema(p)

    assert row["system"] == ""
    assert row["company_name"] is None
    assert row["identifier"] is None
    assert row["filing_date"] is None
    assert row["issue_count"] >= 1
