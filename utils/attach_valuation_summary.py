import argparse
import json
import statistics
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional


def _safe_float(value: Any) -> Optional[float]:
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    text = str(value).replace(",", "").strip()
    if not text:
        return None
    try:
        return float(text)
    except ValueError:
        return None


def _normalize_cik(value: Any) -> str:
    text = str(value).strip()
    if not text:
        return ""
    digits = "".join(ch for ch in text if ch.isdigit())
    return digits.zfill(10) if digits else ""


def _normalize_name(value: Any) -> str:
    text = str(value).strip().lower()
    text = " ".join(text.split())
    return text


def _load_valuation_rows(path: Path) -> List[Dict[str, Any]]:
    payload = json.loads(path.read_text(encoding="utf-8", errors="ignore"))
    if isinstance(payload, list):
        return [row for row in payload if isinstance(row, dict)]
    if isinstance(payload, dict):
        # Accept {"rows":[...]} style as fallback.
        rows = payload.get("rows")
        if isinstance(rows, list):
            return [row for row in rows if isinstance(row, dict)]
    return []


def _build_valuation_summary(rows: Iterable[Dict[str, Any]]) -> Dict[str, Dict[str, Dict[str, Any]]]:
    grouped_by_cik: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    grouped_by_name: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for row in rows:
        cik = _normalize_cik(row.get("CIK") or row.get("cik") or row.get("identifier"))
        if cik:
            grouped_by_cik[cik].append(row)
        name_key = _normalize_name(
            row.get("company_name")
            or row.get("Company")
            or row.get("CIK")
            or row.get("cik")
            or row.get("Issuer")
            or ""
        )
        if name_key:
            grouped_by_name[name_key].append(row)

    def summarize(items: List[Dict[str, Any]]) -> Dict[str, Any]:
        finals = [_safe_float(it.get("Final Estimate")) for it in items]
        finals = [v for v in finals if isinstance(v, float)]

        dcf_npvs = [_safe_float(it.get("DCF NPV")) for it in items]
        dcf_npvs = [v for v in dcf_npvs if isinstance(v, float)]

        implied_vals = [_safe_float(it.get("Implied Value")) for it in items]
        implied_vals = [v for v in implied_vals if isinstance(v, float)]

        methods = [str(it.get("Methodology", "")).strip() for it in items if str(it.get("Methodology", "")).strip()]
        categories = [str(it.get("Category", "")).strip() for it in items if str(it.get("Category", "")).strip()]

        return {
            "record_count": len(items),
            "final_estimate": {
                "mean": round(statistics.mean(finals), 4) if finals else None,
                "median": round(statistics.median(finals), 4) if finals else None,
                "min": min(finals) if finals else None,
                "max": max(finals) if finals else None,
            },
            "dcf_npv": {
                "mean": round(statistics.mean(dcf_npvs), 4) if dcf_npvs else None,
                "median": round(statistics.median(dcf_npvs), 4) if dcf_npvs else None,
            },
            "implied_value": {
                "mean": round(statistics.mean(implied_vals), 4) if implied_vals else None,
                "median": round(statistics.median(implied_vals), 4) if implied_vals else None,
            },
            "top_methodologies": dict(Counter(methods).most_common(5)),
            "top_categories": dict(Counter(categories).most_common(5)),
        }

    summary_by_cik: Dict[str, Dict[str, Any]] = {k: summarize(v) for k, v in grouped_by_cik.items()}
    summary_by_name: Dict[str, Dict[str, Any]] = {k: summarize(v) for k, v in grouped_by_name.items()}
    return {"by_cik": summary_by_cik, "by_name": summary_by_name}


def _iter_schema_files(path: Path) -> List[Path]:
    if path.is_file():
        return [path]
    if path.is_dir():
        return sorted(path.rglob("*.json"))
    return []


def attach_valuation_summary(
    schema_path: Path,
    valuation_path: Path,
    output_dir: Optional[Path] = None,
    in_place: bool = False,
) -> Dict[str, Any]:
    valuation_rows = _load_valuation_rows(valuation_path)
    summary_maps = _build_valuation_summary(valuation_rows)
    summary_by_cik = summary_maps["by_cik"]
    summary_by_name = summary_maps["by_name"]

    schema_files = _iter_schema_files(schema_path)
    if output_dir and not in_place:
        output_dir.mkdir(parents=True, exist_ok=True)

    matched = 0
    processed = 0
    outputs: List[str] = []

    for file_path in schema_files:
        try:
            data = json.loads(file_path.read_text(encoding="utf-8", errors="ignore"))
        except json.JSONDecodeError:
            continue
        if not isinstance(data, dict):
            continue
        processed += 1

        identifier = _normalize_cik(data.get("company", {}).get("identifier"))
        company_name = _normalize_name(data.get("company", {}).get("name"))

        valuation_summary = None
        if identifier:
            valuation_summary = summary_by_cik.get(identifier)
        if valuation_summary is None and company_name:
            valuation_summary = summary_by_name.get(company_name)
        if valuation_summary is None:
            continue

        data["valuation_summary"] = valuation_summary
        matched += 1

        if in_place:
            dest = file_path
        elif output_dir:
            try:
                rel = file_path.relative_to(schema_path) if schema_path.is_dir() else Path(file_path.name)
            except ValueError:
                rel = Path(file_path.name)
            dest = output_dir / rel
            dest.parent.mkdir(parents=True, exist_ok=True)
        else:
            dest = file_path

        dest.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        outputs.append(str(dest))

    return {
        "schema_files_processed": processed,
        "schema_files_matched": matched,
        "valuation_companies_by_cik": len(summary_by_cik),
        "valuation_companies_by_name": len(summary_by_name),
        "outputs": outputs[:20],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Attach valuation summary to unified schema JSON")
    parser.add_argument(
        "--schema-path",
        default="data/exports/unified_schema_sample.json",
        help="Unified schema file or directory",
    )
    parser.add_argument(
        "--valuation-path",
        default="../data/valuation_reports/valuation_details_20260114_221020.json",
        help="Valuation details JSON path",
    )
    parser.add_argument(
        "--output-dir",
        default="data/exports/valuation_enriched",
        help="Output directory (ignored with --in-place)",
    )
    parser.add_argument("--in-place", action="store_true", help="Overwrite original schema file(s)")
    args = parser.parse_args()

    result = attach_valuation_summary(
        schema_path=Path(args.schema_path),
        valuation_path=Path(args.valuation_path),
        output_dir=Path(args.output_dir) if args.output_dir else None,
        in_place=args.in_place,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
