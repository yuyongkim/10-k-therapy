"""DART analytics routes - SQLite-based analytics endpoints."""
import math
import json
import sqlite3
import os
from fastapi import APIRouter, Query
from typing import Optional

router = APIRouter(tags=["dart"])

SQLITE_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
    "data", "processed", "sec_dart_analytics.db",
)


def _get_conn():
    conn = sqlite3.connect(SQLITE_PATH)
    conn.row_factory = sqlite3.Row
    return conn


@router.get("/stats")
def dart_stats():
    conn = _get_conn()

    total_filings = conn.execute("SELECT COUNT(*) FROM dart_filings").fetchone()[0]
    total_companies = conn.execute("SELECT COUNT(DISTINCT company_name) FROM dart_filings").fetchone()[0]
    total_sections = conn.execute("SELECT COUNT(*) FROM dart_sections").fetchone()[0]
    high_signal = conn.execute("SELECT COUNT(*) FROM dart_sections WHERE candidate_score >= 6").fetchone()[0]
    med_signal = conn.execute("SELECT COUNT(*) FROM dart_sections WHERE candidate_score >= 3 AND candidate_score < 6").fetchone()[0]
    avg_score = conn.execute("SELECT AVG(candidate_score) FROM dart_sections WHERE candidate_score > 0").fetchone()[0]
    sections_with_tables = conn.execute("SELECT COUNT(*) FROM dart_sections WHERE has_tables = 1").fetchone()[0]

    # Top companies by filing count
    top_companies = conn.execute("""
        SELECT company_name, COUNT(*) as cnt
        FROM dart_filings
        WHERE company_name IS NOT NULL
        GROUP BY company_name ORDER BY cnt DESC LIMIT 15
    """).fetchall()

    # Signal distribution
    signal_dist = conn.execute("""
        SELECT
            SUM(CASE WHEN candidate_score >= 6 THEN 1 ELSE 0 END) as high,
            SUM(CASE WHEN candidate_score >= 3 AND candidate_score < 6 THEN 1 ELSE 0 END) as medium,
            SUM(CASE WHEN candidate_score >= 1 AND candidate_score < 3 THEN 1 ELSE 0 END) as low,
            SUM(CASE WHEN candidate_score = 0 THEN 1 ELSE 0 END) as none
        FROM dart_sections
    """).fetchone()

    # By filing date (year-month)
    by_month = conn.execute("""
        SELECT SUBSTR(filing_date, 1, 7) as month, COUNT(*) as cnt
        FROM dart_filings
        WHERE filing_date IS NOT NULL AND LENGTH(filing_date) >= 7
        GROUP BY month ORDER BY month
    """).fetchall()

    conn.close()
    return {
        "total_filings": total_filings,
        "total_companies": total_companies,
        "total_sections": total_sections,
        "high_signal_sections": high_signal,
        "med_signal_sections": med_signal,
        "avg_candidate_score": round(avg_score, 2) if avg_score else 0,
        "sections_with_tables": sections_with_tables,
        "top_companies": [{"name": r["company_name"], "count": r["cnt"]} for r in top_companies],
        "signal_distribution": {
            "high": signal_dist["high"] or 0,
            "medium": signal_dist["medium"] or 0,
            "low": signal_dist["low"] or 0,
            "none": signal_dist["none"] or 0,
        },
        "by_month": [{"month": r["month"], "count": r["cnt"]} for r in by_month],
    }


@router.get("/ip-sections")
def dart_ip_sections(
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=200),
    search: Optional[str] = None,
    min_score: int = Query(3, ge=0),
    sort: str = "candidate_score:desc",
):
    """List IP/license-related sections across all DART filings."""
    conn = _get_conn()

    where_clauses = ["ds.candidate_score >= ?"]
    params: list = [min_score]

    if search:
        where_clauses.append(
            "(LOWER(df.company_name) LIKE ? OR LOWER(ds.plain_text) LIKE ? OR LOWER(ds.dart_label) LIKE ?)"
        )
        term = f"%{search.lower()}%"
        params.extend([term, term, term])

    where_sql = "WHERE " + " AND ".join(where_clauses)

    # Count
    total = conn.execute(
        f"SELECT COUNT(*) FROM dart_sections ds JOIN dart_filings df ON ds.filing_id = df.filing_id {where_sql}",
        params,
    ).fetchone()[0]

    # Sort
    sort_parts = sort.split(":")
    valid_cols = {"candidate_score", "company_name", "token_count", "money_mentions", "filing_date"}
    sort_col = sort_parts[0] if sort_parts[0] in valid_cols else "candidate_score"
    sort_prefix = "ds." if sort_col != "company_name" and sort_col != "filing_date" else "df."
    sort_dir = "ASC" if len(sort_parts) > 1 and sort_parts[1] == "asc" else "DESC"

    total_pages = max(1, math.ceil(total / page_size))
    offset = (page - 1) * page_size

    rows = conn.execute(f"""
        SELECT ds.row_id, df.company_name, df.filing_date, df.document_type,
               ds.section_id, ds.dart_label, ds.sec_label, ds.dart_eng_label,
               ds.candidate_score, ds.token_count,
               ds.money_mentions, ds.percent_mentions,
               ds.has_tables, ds.has_financial_data,
               ds.keyword_hits_json, ds.preview
        FROM dart_sections ds
        JOIN dart_filings df ON ds.filing_id = df.filing_id
        {where_sql}
        ORDER BY {sort_prefix}{sort_col} {sort_dir}
        LIMIT ? OFFSET ?
    """, params + [page_size, offset]).fetchall()

    data = []
    for r in rows:
        row = dict(r)
        keywords = []
        if row.get("keyword_hits_json"):
            try:
                keywords = json.loads(row["keyword_hits_json"])
            except Exception:
                pass
        data.append({
            "id": row["row_id"],
            "company": row["company_name"],
            "filing_date": row["filing_date"],
            "doc_type": row["document_type"],
            "section": row["dart_eng_label"] or row["sec_label"] or row["dart_label"] or row["section_id"],
            "score": row["candidate_score"],
            "tokens": row["token_count"],
            "money_mentions": row["money_mentions"],
            "percent_mentions": row["percent_mentions"],
            "has_tables": bool(row["has_tables"]),
            "has_financial": bool(row["has_financial_data"]),
            "keywords": keywords,
            "preview": row["preview"],
        })

    conn.close()
    return {
        "data": data,
        "pagination": {"page": page, "page_size": page_size, "total": total, "total_pages": total_pages},
    }


@router.get("/ip-sections/{row_id}")
def dart_ip_section_detail(row_id: int):
    """Get full text of a specific IP section."""
    conn = _get_conn()
    row = conn.execute("""
        SELECT ds.*, df.company_name, df.filing_date, df.document_type
        FROM dart_sections ds
        JOIN dart_filings df ON ds.filing_id = df.filing_id
        WHERE ds.row_id = ?
    """, (row_id,)).fetchone()
    conn.close()
    if not row:
        from fastapi import HTTPException
        raise HTTPException(404, "Section not found")
    return dict(row)


@router.get("/filings/{filing_id}/sections")
def dart_filing_sections(filing_id: int, min_score: int = 0):
    conn = _get_conn()

    filing = conn.execute(
        "SELECT * FROM dart_filings WHERE filing_id = ?", (filing_id,)
    ).fetchone()
    if not filing:
        conn.close()
        from fastapi import HTTPException
        raise HTTPException(404, "Filing not found")

    sections = conn.execute("""
        SELECT section_key, section_id, sec_label, dart_label, dart_eng_label,
               token_count, has_tables, has_financial_data,
               money_mentions, percent_mentions, year_mentions,
               candidate_score, keyword_hits_json, preview, plain_text
        FROM dart_sections
        WHERE filing_id = ? AND candidate_score >= ?
        ORDER BY candidate_score DESC
    """, (filing_id, min_score)).fetchall()

    conn.close()
    return {
        "filing": dict(filing),
        "sections": [dict(s) for s in sections],
        "total_sections": len(sections),
    }
