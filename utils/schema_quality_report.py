import argparse
import csv
import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List


def _safe(value: Any) -> str:
    return str(value) if value is not None else ""


def _as_dict(value: Any) -> Dict[str, Any]:
    return value if isinstance(value, dict) else {}


def evaluate_schema_payload(payload: Dict[str, Any], path: Path) -> Dict[str, Any]:
    source_info = _as_dict(payload.get("source_info"))
    company = _as_dict(payload.get("company"))
    source_system = _safe(source_info.get("system")).upper()
    sections = payload.get("sections", []) if isinstance(payload.get("sections"), list) else []
    intelligence = payload.get("document_intelligence", {}) if isinstance(payload.get("document_intelligence"), dict) else {}
    processing = payload.get("processing_info", {}) if isinstance(payload.get("processing_info"), dict) else {}
    xbrl = payload.get("xbrl_summary", {}) if isinstance(payload.get("xbrl_summary"), dict) else {}

    section_tags = [s.get("section_mapping", {}).get("common_tag") for s in sections if isinstance(s, dict)]
    unique_tags = sorted({t for t in section_tags if t})
    completeness = intelligence.get("core_mapping_completeness")
    sections_with_tables = intelligence.get("sections_with_tables")
    total_tokens = processing.get("total_tokens")
    parser_version = processing.get("parser_version")
    xbrl_facts = xbrl.get("total_facts") if source_system == "SEC" else None

    issues: List[str] = []
    if len(sections) < 2:
        issues.append("too_few_sections")
    if isinstance(completeness, (int, float)) and completeness < 0.5:
        issues.append("low_core_mapping")
    if source_system == "DART" and len(sections) < 4:
        issues.append("dart_section_coverage_low")
    if source_system == "SEC" and not isinstance(xbrl_facts, int):
        issues.append("missing_sec_xbrl_facts")
    if not unique_tags:
        issues.append("missing_common_tags")
    if not parser_version:
        issues.append("missing_parser_version")
    if total_tokens in (None, ""):
        issues.append("missing_total_tokens")

    return {
        "schema_path": str(path),
        "document_id": payload.get("document_id"),
        "system": source_system,
        "company_name": company.get("name"),
        "identifier": company.get("identifier"),
        "filing_date": source_info.get("filing_date"),
        "sections_count": len(sections),
        "unique_common_tags": ";".join(unique_tags),
        "core_mapping_completeness": completeness,
        "sections_with_tables": sections_with_tables,
        "total_tokens": total_tokens,
        "parser_version": parser_version,
        "sec_total_facts": xbrl_facts,
        "issue_count": len(issues),
        "issues": ";".join(issues),
    }


def evaluate_schema(path: Path) -> Dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8", errors="ignore"))
    return evaluate_schema_payload(payload, path)


def is_schema_payload(payload: Dict[str, Any]) -> bool:
    if not isinstance(payload, dict):
        return False
    if not payload.get("document_id"):
        return False
    if not isinstance(payload.get("sections"), list):
        return False
    if not isinstance(payload.get("source_info"), dict):
        return False
    return True


def collect_schema_files(root: Path) -> List[Path]:
    return sorted(p for p in root.rglob("*.json") if p.is_file())


def write_csv(rows: List[Dict[str, Any]], path: Path) -> None:
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    fieldnames = list(rows[0].keys())
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate quality report for unified schema JSON files")
    parser.add_argument("--schema-root", required=True, help="Root directory containing schema JSON files")
    parser.add_argument("--output-dir", default="data/exports/schema_quality", help="Output directory")
    args = parser.parse_args()

    root = Path(args.schema_root)
    if not root.exists():
        raise FileNotFoundError(f"Schema root not found: {root}")

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    files = collect_schema_files(root)
    rows: List[Dict[str, Any]] = []
    skipped = 0
    for path in files:
        try:
            payload = json.loads(path.read_text(encoding="utf-8", errors="ignore"))
        except json.JSONDecodeError:
            skipped += 1
            continue
        if not is_schema_payload(payload):
            skipped += 1
            continue
        rows.append(evaluate_schema_payload(payload, path))
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    json_path = output_dir / f"schema_quality_{timestamp}.json"
    csv_path = output_dir / f"schema_quality_{timestamp}.csv"
    summary_path = output_dir / f"schema_quality_summary_{timestamp}.json"

    json_path.write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")
    write_csv(rows, csv_path)

    issue_rows = [row for row in rows if row.get("issue_count", 0) > 0]
    systems = {}
    for row in rows:
        systems[row["system"]] = systems.get(row["system"], 0) + 1
    avg_sections = round(sum(row["sections_count"] for row in rows) / len(rows), 2) if rows else None
    completeness_values = [
        row["core_mapping_completeness"]
        for row in rows
        if isinstance(row.get("core_mapping_completeness"), (int, float))
    ]
    avg_completeness = (
        round(sum(completeness_values) / len(completeness_values), 3)
        if completeness_values
        else None
    )

    summary = {
        "schema_root": str(root),
        "total_files": len(rows),
        "skipped_non_schema_files": skipped,
        "systems": systems,
        "issue_files": len(issue_rows),
        "avg_sections_count": avg_sections,
        "avg_core_mapping_completeness": avg_completeness,
        "generated_at": datetime.now().isoformat(),
        "json_output": str(json_path),
        "csv_output": str(csv_path),
    }
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")

    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
