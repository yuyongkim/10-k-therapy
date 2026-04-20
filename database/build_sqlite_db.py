#!/usr/bin/env python3
"""Build a local SQLite analytics DB from SEC and DART JSON outputs."""

from __future__ import annotations

import argparse
import json
import logging
import sqlite3
from pathlib import Path
from typing import Any

LOGGER = logging.getLogger("build_sqlite_db")

LICENSE_KEYWORDS = (
    "license",
    "licensing",
    "royalty",
    "contract",
    "agreement",
    "patent",
    "ip",
    "technology transfer",
    "exclusive",
    "non-exclusive",
    # Korean IP/license keywords
    "라이선스",
    "로열티",
    "특허",
    "실시권",
    "기술이전",
    "기술료",
    "사용료",
    "지식재산",
    "지재권",
    "산업재산권",
    "저작권",
    "상표권",
    "전용실시권",
    "통상실시권",
    "기술사용",
    "기술도입",
    "기술제휴",
    "특허권",
    "실용신안",
    "디자인권",
    "영업비밀",
    "노하우",
)


def to_int_bool(value: Any) -> int:
    return 1 if bool(value) else 0


def to_float_or_none(value: Any) -> float | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    try:
        return float(text)
    except ValueError:
        return None


def to_int_or_none(value: Any) -> int | None:
    n = to_float_or_none(value)
    return int(n) if n is not None else None


def normalize_text(value: Any) -> str:
    if value is None:
        return ""
    return " ".join(str(value).split())


def load_schema(conn: sqlite3.Connection, schema_path: Path) -> None:
    sql = schema_path.read_text(encoding="utf-8")
    conn.executescript(sql)


def reset_tables(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        DELETE FROM dart_filing_rollups;
        DELETE FROM dart_sections;
        DELETE FROM dart_filings;
        DELETE FROM sec_agreements;
        DELETE FROM sec_scan_summary;
        """
    )


def score_dart_section(section: dict[str, Any]) -> tuple[int, list[str], list[str]]:
    mapping = section.get("section_mapping") or {}
    content = section.get("content") or {}
    insights = section.get("extracted_insights") or {}
    quantitative = insights.get("quantitative_profile") or {}
    license_costs = insights.get("license_costs") or {}

    plain_text = normalize_text(content.get("plain_text"))
    preview = normalize_text(plain_text[:260])
    text_pool = " ".join(
        [
            normalize_text(section.get("section_id")),
            normalize_text(mapping.get("sec_label")),
            normalize_text(mapping.get("dart_label")),
            normalize_text(mapping.get("dart_eng_label")),
            preview,
            plain_text[:2000],
        ]
    ).lower()

    keyword_hits = [keyword for keyword in LICENSE_KEYWORDS if keyword in text_pool]
    structured_keys = [k for k in license_costs.keys() if str(k).strip()]

    money_mentions = int(quantitative.get("money_mentions_count") or 0)
    percent_mentions = int(quantitative.get("percent_mentions_count") or 0)
    has_financial_data = bool(content.get("has_financial_data"))

    score = len(keyword_hits) * 2
    if has_financial_data:
        score += 1
    if money_mentions > 0:
        score += 1
    if percent_mentions > 0:
        score += 1
    if structured_keys:
        score += 4

    return score, keyword_hits, structured_keys


def insert_sec_data(conn: sqlite3.Connection, license_summary_path: Path) -> int:
    if not license_summary_path.exists():
        LOGGER.warning("SEC source not found: %s", license_summary_path)
        return 0

    payload = json.loads(license_summary_path.read_text(encoding="utf-8"))
    summary = payload.get("summary") or {}
    rows = payload.get("all_agreements") or []

    conn.execute(
        """
        INSERT OR REPLACE INTO sec_scan_summary (
            id,
            scan_timestamp,
            total_companies,
            companies_with_licenses,
            total_license_files,
            total_agreements,
            scan_errors
        ) VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (
            1,
            summary.get("scan_timestamp"),
            summary.get("total_companies"),
            summary.get("companies_with_licenses"),
            summary.get("total_license_files"),
            summary.get("total_agreements"),
            summary.get("scan_errors"),
        ),
    )

    sec_rows = []
    for row in rows:
        sec_rows.append(
            (
                row.get("company"),
                row.get("cik"),
                row.get("ticker"),
                row.get("filing_type"),
                to_int_or_none(row.get("filing_year")),
                row.get("licensor_name"),
                row.get("licensee_name"),
                row.get("tech_name"),
                row.get("tech_category"),
                to_float_or_none(row.get("confidence")),
                to_float_or_none(row.get("royalty_rate")),
                row.get("royalty_unit"),
                to_float_or_none(row.get("upfront_amount")),
                row.get("upfront_currency"),
                to_int_bool(row.get("has_upfront")),
                to_int_bool(row.get("has_royalty")),
                to_float_or_none(row.get("term_years")),
                json.dumps(row.get("territory"), ensure_ascii=False),
                row.get("reasoning"),
            )
        )

    conn.executemany(
        """
        INSERT INTO sec_agreements (
            company,
            cik,
            ticker,
            filing_type,
            filing_year,
            licensor_name,
            licensee_name,
            tech_name,
            tech_category,
            confidence,
            royalty_rate,
            royalty_unit,
            upfront_amount,
            upfront_currency,
            has_upfront,
            has_royalty,
            term_years,
            territory,
            reasoning
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        sec_rows,
    )

    LOGGER.info("Inserted SEC agreements: %s", len(sec_rows))
    return len(sec_rows)


def list_dart_docs(dart_root: Path) -> list[Path]:
    if not dart_root.exists():
        return []

    docs: list[Path] = []
    for path in dart_root.rglob("*.json"):
        if path.name.startswith("run_summary_"):
            continue
        docs.append(path)
    return sorted(docs)


def insert_dart_data(conn: sqlite3.Connection, dart_root: Path) -> tuple[int, int]:
    docs = list_dart_docs(dart_root)
    if not docs:
        LOGGER.warning("No DART documents found under: %s", dart_root)
        return 0, 0

    filing_count = 0
    section_count = 0

    for doc_path in docs:
        payload = json.loads(doc_path.read_text(encoding="utf-8"))
        source_info = payload.get("source_info") or {}
        company = payload.get("company") or {}
        processing = payload.get("processing_info") or {}
        intelligence = payload.get("document_intelligence") or {}
        sections = payload.get("sections") or []

        file_name = f"{doc_path.parent.name}/{doc_path.name}"
        cursor = conn.execute(
            """
            INSERT INTO dart_filings (
                company_identifier,
                company_name,
                company_country,
                source_system,
                document_id,
                file_name,
                filing_date,
                period_end,
                document_type,
                language,
                parser_version,
                total_tokens,
                total_sections,
                sections_with_tables,
                risk_keyword_signal,
                detected_currencies_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                company.get("identifier"),
                company.get("name"),
                company.get("country"),
                source_info.get("system"),
                payload.get("document_id"),
                file_name,
                source_info.get("filing_date"),
                source_info.get("period_end"),
                source_info.get("document_type"),
                source_info.get("language"),
                processing.get("parser_version"),
                to_int_or_none(processing.get("total_tokens")),
                to_int_or_none(intelligence.get("total_sections")),
                to_int_or_none(intelligence.get("sections_with_tables")),
                to_int_or_none(intelligence.get("risk_keyword_signal")),
                json.dumps(intelligence.get("detected_currencies") or {}, ensure_ascii=False),
            ),
        )
        filing_id = cursor.lastrowid
        filing_count += 1

        candidate_sections = 0
        structured_sections = 0
        high_signal_sections = 0
        score_sum = 0
        keyword_frequency: dict[str, int] = {}

        for index, section in enumerate(sections):
            mapping = section.get("section_mapping") or {}
            content = section.get("content") or {}
            insights = section.get("extracted_insights") or {}
            quantitative = insights.get("quantitative_profile") or {}
            keywords = insights.get("topic_keyword_counts") or {}
            license_costs = insights.get("license_costs") or {}

            section_id = normalize_text(section.get("section_id")) or f"section_{index + 1}"
            section_key = f"{section_id}__{index + 1}"
            plain_text = normalize_text(content.get("plain_text"))
            preview = normalize_text(plain_text[:260])

            score, keyword_hits, structured_keys = score_dart_section(section)

            if score > 0 or structured_keys:
                candidate_sections += 1
            if structured_keys:
                structured_sections += 1
            if score >= 6:
                high_signal_sections += 1
            score_sum += score

            for keyword in keyword_hits:
                keyword_frequency[keyword] = keyword_frequency.get(keyword, 0) + 1

            conn.execute(
                """
                INSERT INTO dart_sections (
                    filing_id,
                    section_key,
                    section_id,
                    common_tag,
                    sec_label,
                    dart_label,
                    dart_eng_label,
                    order_index,
                    token_count,
                    has_tables,
                    has_financial_data,
                    money_mentions,
                    percent_mentions,
                    year_mentions,
                    keyword_business,
                    keyword_advantage,
                    keyword_regulation,
                    candidate_score,
                    keyword_hits_json,
                    structured_cost_keys_json,
                    license_costs_json,
                    preview,
                    plain_text
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    filing_id,
                    section_key,
                    section_id,
                    mapping.get("common_tag"),
                    mapping.get("sec_label"),
                    mapping.get("dart_label"),
                    mapping.get("dart_eng_label"),
                    to_int_or_none(mapping.get("order_index")),
                    to_int_or_none(content.get("token_count")),
                    to_int_bool(content.get("has_tables")),
                    to_int_bool(content.get("has_financial_data")),
                    to_int_or_none(quantitative.get("money_mentions_count")) or 0,
                    to_int_or_none(quantitative.get("percent_mentions_count")) or 0,
                    to_int_or_none(quantitative.get("year_mentions_count")) or 0,
                    to_int_or_none(keywords.get("business")) or 0,
                    to_int_or_none(keywords.get("advantage")) or 0,
                    to_int_or_none(keywords.get("regulation")) or 0,
                    score,
                    json.dumps(keyword_hits, ensure_ascii=False),
                    json.dumps(structured_keys, ensure_ascii=False),
                    json.dumps(license_costs, ensure_ascii=False),
                    preview,
                    plain_text,
                ),
            )
            section_count += 1

        top_keywords = sorted(
            keyword_frequency.items(),
            key=lambda item: item[1],
            reverse=True,
        )[:8]
        avg_score = round(score_sum / len(sections), 2) if sections else 0.0
        signal_buckets = {
            "high_6_plus": sum(1 for s in sections if (score_dart_section(s)[0] >= 6)),
            "medium_3_to_5": sum(1 for s in sections if (3 <= score_dart_section(s)[0] <= 5)),
            "low_1_to_2": sum(1 for s in sections if (1 <= score_dart_section(s)[0] <= 2)),
            "none_0": sum(1 for s in sections if (score_dart_section(s)[0] == 0)),
        }

        conn.execute(
            """
            INSERT INTO dart_filing_rollups (
                filing_id,
                candidate_sections,
                structured_sections,
                high_signal_sections,
                avg_score,
                top_keywords_json,
                signal_buckets_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                filing_id,
                candidate_sections,
                structured_sections,
                high_signal_sections,
                avg_score,
                json.dumps([{"keyword": k, "count": v} for k, v in top_keywords], ensure_ascii=False),
                json.dumps(signal_buckets, ensure_ascii=False),
            ),
        )

    LOGGER.info("Inserted DART filings: %s, sections: %s", filing_count, section_count)
    return filing_count, section_count


def build_db(
    project_root: Path,
    db_path: Path,
    sec_source: Path,
    dart_source: Path,
    reset: bool,
) -> None:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    schema_path = project_root / "database" / "sqlite_schema.sql"

    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        load_schema(conn, schema_path)
        if reset:
            reset_tables(conn)

        sec_count = insert_sec_data(conn, sec_source)
        dart_filings, dart_sections = insert_dart_data(conn, dart_source)
        conn.commit()

        LOGGER.info("SQLite DB build complete: %s", db_path)
        LOGGER.info(
            "Final counts -> SEC agreements: %s, DART filings: %s, DART sections: %s",
            sec_count,
            dart_filings,
            dart_sections,
        )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build sec_dart_analytics.sqlite from local JSON outputs.",
    )
    parser.add_argument(
        "--project-root",
        default=".",
        help="Project root directory (default: current directory).",
    )
    parser.add_argument(
        "--db-path",
        default="data/processed/sec_dart_analytics.db",
        help="Output SQLite DB path.",
    )
    parser.add_argument(
        "--sec-source",
        default="license_summary.json",
        help="Path to license_summary.json",
    )
    parser.add_argument(
        "--dart-source",
        default="data/dart/unified_schema",
        help="Path to DART unified schema directory.",
    )
    parser.add_argument(
        "--no-reset",
        action="store_true",
        help="Do not wipe existing rows before loading.",
    )
    return parser.parse_args()


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s - %(message)s",
    )

    args = parse_args()
    root = Path(args.project_root).resolve()
    db_path = (root / args.db_path).resolve()
    sec_source = (root / args.sec_source).resolve()
    dart_source = (root / args.dart_source).resolve()

    build_db(
        project_root=root,
        db_path=db_path,
        sec_source=sec_source,
        dart_source=dart_source,
        reset=not args.no_reset,
    )


if __name__ == "__main__":
    main()
