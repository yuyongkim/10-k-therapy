#!/usr/bin/env python3
"""Generate a concise analysis report from sec_dart_analytics SQLite DB.

Optionally append LLM commentary using Ollama.
"""

from __future__ import annotations

import argparse
import json
import sqlite3
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any

import requests
from xml.etree import ElementTree as ET


def fetch_one(cur: sqlite3.Cursor, query: str, params: tuple[Any, ...] = ()) -> Any:
    row = cur.execute(query, params).fetchone()
    return row[0] if row else None


def top_rows(
    cur: sqlite3.Cursor,
    query: str,
    params: tuple[Any, ...] = (),
) -> list[tuple[Any, ...]]:
    return [tuple(row) for row in cur.execute(query, params).fetchall()]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate analytics report from SQLite DB.")
    parser.add_argument(
        "--db-path",
        default="data/processed/sec_dart_analytics.db",
        help="SQLite DB path",
    )
    parser.add_argument(
        "--corp-code-xml",
        default="data/dart/corp_code.xml",
        help="DART corp code XML path (for coverage denominator)",
    )
    parser.add_argument(
        "--out",
        default="data/exports/analysis/sqlite_analysis_latest.md",
        help="Output markdown file path",
    )
    parser.add_argument(
        "--llm-provider",
        choices=["none", "ollama"],
        default="none",
        help="Optional commentary provider",
    )
    parser.add_argument(
        "--ollama-model",
        default="llama3.1:8b-instruct-q8_0",
        help="Ollama model name for commentary",
    )
    parser.add_argument(
        "--ollama-base-url",
        default="http://localhost:11434",
        help="Ollama base URL",
    )
    return parser.parse_args()


def listed_company_count(corp_code_xml: Path) -> int:
    if not corp_code_xml.exists():
        return 0
    root = ET.parse(corp_code_xml).getroot()
    items = root.findall(".//list")
    listed = [
        row
        for row in items
        if (row.findtext("stock_code") or "").strip()
    ]
    return len(listed)


def build_numeric_summary(db_path: Path, corp_code_xml: Path) -> dict[str, Any]:
    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()

        sec_total = fetch_one(cur, "SELECT COUNT(*) FROM sec_agreements") or 0
        sec_companies = fetch_one(cur, "SELECT COUNT(DISTINCT cik) FROM sec_agreements WHERE cik IS NOT NULL AND cik <> ''") or 0
        sec_avg_conf = fetch_one(cur, "SELECT ROUND(AVG(confidence), 4) FROM sec_agreements WHERE confidence IS NOT NULL")
        sec_with_royalty = fetch_one(cur, "SELECT COUNT(*) FROM sec_agreements WHERE has_royalty = 1") or 0
        sec_with_upfront = fetch_one(cur, "SELECT COUNT(*) FROM sec_agreements WHERE has_upfront = 1") or 0

        sec_top_categories = top_rows(
            cur,
            """
            SELECT tech_category, COUNT(*) AS cnt
            FROM sec_agreements
            WHERE tech_category IS NOT NULL AND TRIM(tech_category) <> ''
            GROUP BY tech_category
            ORDER BY cnt DESC
            LIMIT 10
            """,
        )
        sec_top_licensors = top_rows(
            cur,
            """
            SELECT licensor_name, COUNT(*) AS cnt
            FROM sec_agreements
            WHERE licensor_name IS NOT NULL AND TRIM(licensor_name) <> ''
            GROUP BY licensor_name
            ORDER BY cnt DESC
            LIMIT 10
            """,
        )

        dart_filings = fetch_one(cur, "SELECT COUNT(*) FROM dart_filings") or 0
        dart_companies = fetch_one(cur, "SELECT COUNT(DISTINCT company_identifier) FROM dart_filings") or 0
        dart_sections = fetch_one(cur, "SELECT COUNT(*) FROM dart_sections") or 0
        dart_candidates = fetch_one(cur, "SELECT COALESCE(SUM(candidate_sections), 0) FROM dart_filing_rollups") or 0
        dart_structured = fetch_one(cur, "SELECT COALESCE(SUM(structured_sections), 0) FROM dart_filing_rollups") or 0
        dart_avg_score = fetch_one(cur, "SELECT ROUND(AVG(avg_score), 4) FROM dart_filing_rollups")

        rollups = top_rows(
            cur,
            """
            SELECT f.file_name, r.candidate_sections, r.structured_sections, r.high_signal_sections, r.avg_score, r.top_keywords_json
            FROM dart_filing_rollups r
            JOIN dart_filings f ON f.filing_id = r.filing_id
            ORDER BY f.file_name DESC
            LIMIT 20
            """,
        )

    keyword_counter: Counter[str] = Counter()
    for row in rollups:
        raw = row[5]
        if not raw:
            continue
        try:
            arr = json.loads(raw)
        except json.JSONDecodeError:
            continue
        for item in arr:
            keyword = str(item.get("keyword", "")).strip()
            count = int(item.get("count", 0) or 0)
            if keyword:
                keyword_counter[keyword] += count

    listed_total = listed_company_count(corp_code_xml)
    dart_coverage_pct = (dart_companies / listed_total * 100.0) if listed_total else 0.0

    return {
        "generated_at": datetime.now().isoformat(),
        "db_path": str(db_path),
        "sec": {
            "total_agreements": sec_total,
            "distinct_cik_companies": sec_companies,
            "avg_confidence": sec_avg_conf,
            "with_royalty": sec_with_royalty,
            "with_upfront": sec_with_upfront,
            "top_categories": sec_top_categories,
            "top_licensors": sec_top_licensors,
        },
        "dart": {
            "filings": dart_filings,
            "companies": dart_companies,
            "sections": dart_sections,
            "candidate_sections": dart_candidates,
            "structured_sections": dart_structured,
            "avg_filing_score": dart_avg_score,
            "rollups": rollups,
            "top_keywords": keyword_counter.most_common(12),
            "listed_companies_total": listed_total,
            "listed_coverage_pct": round(dart_coverage_pct, 3),
        },
    }


def render_markdown(summary: dict[str, Any]) -> str:
    sec = summary["sec"]
    dart = summary["dart"]
    lines: list[str] = []
    lines.append("# SEC + DART SQLite Analysis")
    lines.append("")
    lines.append(f"- Generated at: `{summary['generated_at']}`")
    lines.append(f"- DB: `{summary['db_path']}`")
    lines.append("")
    lines.append("## SEC Snapshot")
    lines.append(f"- Agreements: **{sec['total_agreements']:,}**")
    lines.append(f"- Distinct CIK companies: **{sec['distinct_cik_companies']:,}**")
    lines.append(f"- Avg confidence: **{sec['avg_confidence']}**")
    lines.append(f"- With royalty: **{sec['with_royalty']:,}**")
    lines.append(f"- With upfront: **{sec['with_upfront']:,}**")
    lines.append("")
    lines.append("### Top Categories")
    for category, count in sec["top_categories"]:
        lines.append(f"- {category}: {count:,}")
    lines.append("")
    lines.append("### Top Licensors")
    for licensor, count in sec["top_licensors"]:
        lines.append(f"- {licensor}: {count:,}")
    lines.append("")
    lines.append("## DART Snapshot")
    lines.append(f"- Filings: **{dart['filings']:,}**")
    lines.append(f"- Companies: **{dart['companies']:,}**")
    lines.append(f"- Sections: **{dart['sections']:,}**")
    lines.append(f"- Candidate sections: **{dart['candidate_sections']:,}**")
    lines.append(f"- Structured sections: **{dart['structured_sections']:,}**")
    lines.append(f"- Avg filing score: **{dart['avg_filing_score']}**")
    lines.append(f"- Listed companies denominator: **{dart['listed_companies_total']:,}**")
    lines.append(f"- Listed coverage: **{dart['listed_coverage_pct']}%**")
    lines.append("")
    lines.append("### DART Top Keywords")
    for keyword, count in dart["top_keywords"]:
        lines.append(f"- {keyword}: {count:,}")
    lines.append("")
    lines.append("### Recent Filing Rollups")
    for row in dart["rollups"]:
        lines.append(
            f"- {row[0]} | candidates={row[1]} structured={row[2]} high={row[3]} avg={row[4]}"
        )
    lines.append("")
    return "\n".join(lines)


def append_ollama_commentary(
    markdown_text: str,
    summary: dict[str, Any],
    model: str,
    base_url: str,
) -> str:
    prompt = (
        "You are a financial/filing analytics reviewer. "
        "Given the JSON summary, produce:\n"
        "1) 5 concise insights\n"
        "2) 5 data-quality risks\n"
        "3) 5 prioritized next actions for scaling DART coverage.\n\n"
        f"Summary JSON:\n{json.dumps(summary, ensure_ascii=False, indent=2)}"
    )

    payload = {
        "model": model,
        "prompt": prompt,
        "stream": False,
    }
    response = requests.post(
        f"{base_url.rstrip('/')}/api/generate",
        json=payload,
        timeout=120,
    )
    response.raise_for_status()
    data = response.json()
    commentary = str(data.get("response", "")).strip()
    if not commentary:
        commentary = "(No commentary generated.)"

    return (
        markdown_text
        + "\n## LLM Commentary (Ollama)\n\n"
        + f"- Model: `{model}`\n"
        + commentary
        + "\n"
    )


def main() -> None:
    args = parse_args()
    db_path = Path(args.db_path).resolve()
    out_path = Path(args.out).resolve()
    corp_code_xml = Path(args.corp_code_xml).resolve()

    if not db_path.exists():
        raise SystemExit(f"DB not found: {db_path}")

    summary = build_numeric_summary(db_path=db_path, corp_code_xml=corp_code_xml)
    markdown = render_markdown(summary)

    if args.llm_provider == "ollama":
        try:
            markdown = append_ollama_commentary(
                markdown_text=markdown,
                summary=summary,
                model=args.ollama_model,
                base_url=args.ollama_base_url,
            )
        except Exception as exc:
            markdown += (
                "\n## LLM Commentary (Ollama)\n\n"
                f"- Failed to generate commentary: `{exc}`\n"
            )

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(markdown, encoding="utf-8")

    print(f"Report written: {out_path}")
    print(f"SEC agreements: {summary['sec']['total_agreements']}")
    print(f"DART filings: {summary['dart']['filings']}")
    print(f"DART listed coverage (%): {summary['dart']['listed_coverage_pct']}")


if __name__ == "__main__":
    main()
