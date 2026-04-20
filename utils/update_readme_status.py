#!/usr/bin/env python3
"""Refresh the operational status section in README.md from local data."""

from __future__ import annotations

import argparse
import json
import re
import sqlite3
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from xml.etree import ElementTree as ET


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Update README operational status section.")
    parser.add_argument("--readme-path", default="README.md", help="README file path")
    parser.add_argument("--license-summary-path", default="license_summary.json", help="SEC summary json path")
    parser.add_argument("--db-path", default="data/processed/sec_dart_analytics.db", help="SQLite DB path")
    parser.add_argument("--corp-code-xml", default="data/dart/corp_code.xml", help="DART corp code xml path")
    parser.add_argument(
        "--run-summary-dir",
        default="data/dart/unified_schema",
        help="Directory containing run_summary_*.json files",
    )
    parser.add_argument("--recent-runs", type=int, default=4, help="Number of recent DART runs to display")
    return parser.parse_args()


def load_sec_snapshot(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    payload = json.loads(path.read_text(encoding="utf-8"))
    return payload.get("summary") or {}


def load_db_snapshot(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    with sqlite3.connect(path) as conn:
        cur = conn.cursor()
        return {
            "sec_agreements": cur.execute("SELECT COUNT(*) FROM sec_agreements").fetchone()[0],
            "dart_filings": cur.execute("SELECT COUNT(*) FROM dart_filings").fetchone()[0],
            "dart_sections": cur.execute("SELECT COUNT(*) FROM dart_sections").fetchone()[0],
            "dart_companies": cur.execute("SELECT COUNT(DISTINCT company_identifier) FROM dart_filings").fetchone()[0],
            "dart_candidate_sections": cur.execute("SELECT COALESCE(SUM(candidate_sections), 0) FROM dart_filing_rollups").fetchone()[0],
            "dart_high_signal_sections": cur.execute("SELECT COALESCE(SUM(high_signal_sections), 0) FROM dart_filing_rollups").fetchone()[0],
            "dart_avg_filing_score": cur.execute("SELECT ROUND(AVG(avg_score), 4) FROM dart_filing_rollups").fetchone()[0],
        }


def load_listed_total(path: Path) -> int:
    if not path.exists():
        return 0
    root = ET.parse(path).getroot()
    listed = [row for row in root.findall(".//list") if (row.findtext("stock_code") or "").strip()]
    return len(listed)


def format_status_counts(rows: list[dict[str, Any]]) -> dict[str, int]:
    counter = Counter()
    for row in rows:
        counter[str(row.get("status", "unknown"))] += 1
    return dict(counter)


def load_recent_run_summaries(summary_dir: Path, recent_runs: int) -> list[dict[str, Any]]:
    if not summary_dir.exists():
        return []
    files = sorted(summary_dir.glob("run_summary_*.json"))
    selected = files[-max(1, recent_runs) :]
    out: list[dict[str, Any]] = []
    for file_path in selected:
        obj = json.loads(file_path.read_text(encoding="utf-8"))
        rows = obj.get("rows") or []
        offset = obj.get("target_offset")
        limit = obj.get("target_limit")
        target_count = int(obj.get("target_count") or 0)
        if isinstance(offset, int):
            if isinstance(limit, int) and limit > 0:
                end = offset + limit - 1
            elif target_count > 0:
                end = offset + target_count - 1
            else:
                end = offset
            range_text = f"offset {offset}~{end}"
        else:
            range_text = "-"

        out.append(
            {
                "name": file_path.name,
                "target_count": target_count,
                "success": int(obj.get("success") or 0),
                "failed": int(obj.get("failed") or 0),
                "skipped_existing": int(obj.get("skipped_existing") or 0),
                "status_counts": format_status_counts(rows),
                "range_text": range_text,
            }
        )
    return out


def kst_now_text() -> str:
    kst = timezone(timedelta(hours=9))
    return datetime.now(tz=kst).strftime("%Y-%m-%d %H:%M, KST")


def build_section(
    sec_summary: dict[str, Any],
    db_summary: dict[str, Any],
    listed_total: int,
    recent_runs: list[dict[str, Any]],
) -> str:
    def fmt_num(value: Any) -> str:
        if value is None:
            return "-"
        try:
            return f"{int(value):,}"
        except Exception:
            return str(value)

    dart_companies = int(db_summary.get("dart_companies") or 0)
    coverage = (dart_companies / listed_total * 100.0) if listed_total else 0.0

    lines: list[str] = []
    lines.append(f"## 📈 운영 현황 (기준: {kst_now_text()})")
    lines.append("SEC 스냅샷 (`license_summary.json`):")
    lines.append(f"- scan timestamp: `{sec_summary.get('scan_timestamp', '-')}`")
    lines.append(f"- 총 회사: `{fmt_num(sec_summary.get('total_companies'))}`")
    lines.append(f"- 라이선스 보유 회사: `{fmt_num(sec_summary.get('companies_with_licenses'))}`")
    lines.append(f"- 라이선스 파일: `{fmt_num(sec_summary.get('total_license_files'))}`")
    lines.append(f"- 계약 레코드: `{fmt_num(sec_summary.get('total_agreements'))}`")
    lines.append("")
    lines.append(f"DART 배치 확장 현황 (`data/dart/unified_schema`, 상장사 모수 `{listed_total:,}`):")
    if recent_runs:
        lines.append(f"- 최근 run summary (최신 {len(recent_runs)}건)")
        for run in recent_runs:
            counts = run["status_counts"]
            status_text = ", ".join(f"{k} {v}" for k, v in sorted(counts.items()))
            lines.append(
                f"  - `{run['name']}`: `{run['range_text']}` | "
                f"`ok {fmt_num(run['success'])}`, `failed {fmt_num(run['failed'])}`, `skipped {fmt_num(run['skipped_existing'])}` | "
                f"`status: {status_text}`"
            )
    else:
        lines.append("- 최근 run summary: `없음`")
    lines.append("")
    lines.append("통합 SQLite DB 현황 (`data/processed/sec_dart_analytics.db`):")
    lines.append(f"- SEC agreements: `{fmt_num(db_summary.get('sec_agreements'))}`")
    lines.append(f"- DART filings: `{fmt_num(db_summary.get('dart_filings'))}`")
    lines.append(f"- DART sections: `{fmt_num(db_summary.get('dart_sections'))}`")
    lines.append(f"- DART companies: `{fmt_num(dart_companies)}`")
    lines.append(f"- DART 상장사 커버리지: `{coverage:.3f}%` (`{dart_companies:,} / {listed_total:,}`)")
    lines.append(f"- DART candidate sections: `{fmt_num(db_summary.get('dart_candidate_sections'))}`")
    lines.append(f"- DART high-signal sections: `{fmt_num(db_summary.get('dart_high_signal_sections'))}`")
    lines.append(f"- DART avg filing score: `{db_summary.get('dart_avg_filing_score', '-')}`")
    return "\n".join(lines)


def replace_section(readme_text: str, new_section: str) -> str:
    pattern = re.compile(r"## 📈 운영 현황[\s\S]*?(?=\n## 🛠 기술 스택)")
    if not pattern.search(readme_text):
        raise RuntimeError("운영 현황 섹션을 README에서 찾지 못했습니다.")
    return pattern.sub(new_section + "\n", readme_text)


def main() -> None:
    args = parse_args()
    readme_path = Path(args.readme_path)
    sec_summary_path = Path(args.license_summary_path)
    db_path = Path(args.db_path)
    corp_xml_path = Path(args.corp_code_xml)
    run_summary_dir = Path(args.run_summary_dir)

    readme_text = readme_path.read_text(encoding="utf-8")
    sec_summary = load_sec_snapshot(sec_summary_path)
    db_summary = load_db_snapshot(db_path)
    listed_total = load_listed_total(corp_xml_path)
    recent_runs = load_recent_run_summaries(run_summary_dir, args.recent_runs)

    new_section = build_section(
        sec_summary=sec_summary,
        db_summary=db_summary,
        listed_total=listed_total,
        recent_runs=recent_runs,
    )
    updated = replace_section(readme_text, new_section)
    readme_path.write_text(updated, encoding="utf-8")
    print(f"README updated: {readme_path.resolve()}")


if __name__ == "__main__":
    main()
