"""
Auto-validation: LLM-as-Judge + Industry Benchmark comparison.
Run: python scripts/auto_validate.py
"""

import argparse
import json
import os
import sys
import random
import sqlite3
import logging
import re
from pathlib import Path
from typing import Any, Dict, Optional

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

try:
    from dotenv import load_dotenv
except ImportError:  # pragma: no cover - optional dependency in test environments
    def load_dotenv(*_args, **_kwargs):
        return False

load_dotenv()

try:
    from backend.database import SessionLocal
    from backend.models import LicenseContract, FinancialTerm, Filing, Company
    from services.qwen_processor import OllamaProcessor
except Exception:  # pragma: no cover - allows helper tests without app env configured
    SessionLocal = None
    LicenseContract = FinancialTerm = Filing = Company = None
    OllamaProcessor = None

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("auto_validate")

PROJECT_ROOT = Path(os.path.dirname(os.path.dirname(__file__)))
SQLITE_PATH = str(PROJECT_ROOT / "data" / "processed" / "sec_dart_analytics.db")
OUTPUT_PATH = str(PROJECT_ROOT / "data" / "validation_results.json")

# Published benchmarks with real sources
INDUSTRY_BENCHMARKS = {
    "Pharmaceutical": {"median_royalty": 5.0, "range": (3.0, 10.0),
        "source": "RoyaltyStat (3,704 pharma agreements), IAM Media"},
    "Biotechnology": {"median_royalty": 7.6, "range": (3.0, 14.0),
        "source": "PLOS ONE 2023 (corporate biotech licenses)"},
    "Chemical": {"median_royalty": 4.0, "range": (1.0, 8.0),
        "source": "Seton Hall Law, Industry Norms study"},
    "Software": {"median_royalty": 10.0, "range": (3.0, 25.0),
        "source": "PatentPC 2024, UpCounsel industry survey"},
    "Semiconductor": {"median_royalty": 3.5, "range": (1.0, 7.0),
        "source": "ktmine semiconductor IP benchmarks"},
    "Automotive": {"median_royalty": 3.0, "range": (1.0, 5.0),
        "source": "ktmine automotive IP benchmarks"},
    "Energy": {"median_royalty": 3.0, "range": (1.0, 6.0),
        "source": "RoyaltyStat energy sector"},
}

JUDGE_PROMPT = """Compare the EXTRACTION against the SOURCE TEXT below.
For each field, answer true if the extracted value matches the source text, false if it doesn't or the info is not in the source.

SOURCE TEXT:
{source_text}

EXTRACTION:
- Licensor: {licensor}
- Licensee: {licensee}
- Technology: {tech_name}
- Category: {category}
- Royalty: {royalty}
- Territory: {territory}

Output ONLY this JSON:
{{"licensor_correct": true, "licensee_correct": true, "tech_name_correct": true, "category_correct": true, "royalty_correct": true, "territory_correct": true, "is_real_license": true}}
"""


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run validation using LLM-as-judge and industry benchmarks")
    parser.add_argument("--output", default=OUTPUT_PATH, help="Path for validation JSON output")
    parser.add_argument("--llm-model", default="gemma3:4b", help="Ollama model used for LLM-as-judge")
    parser.add_argument("--llm-timeout", type=int, default=30, help="Timeout in seconds for each judge request")
    parser.add_argument("--sample-size-per-source", type=int, default=30, help="Sample size for each source system")
    parser.add_argument("--min-confidence", type=float, default=0.7, help="Minimum confidence required for judged samples")
    parser.add_argument("--seed", type=int, default=42, help="Random seed for reproducible sampling")
    parser.add_argument("--skip-llm", action="store_true", help="Skip the LLM-as-judge phase and run benchmarks only")
    return parser


def sample_contracts(db, source_system: str, limit: int, min_confidence: float, rng: random.Random) -> list:
    contracts = (
        db.query(LicenseContract)
        .filter(
            LicenseContract.source_system == source_system,
            LicenseContract.quality_flag == "clean",
            LicenseContract.confidence_score >= min_confidence,
        )
        .order_by(LicenseContract.id.asc())
        .all()
    )
    if len(contracts) <= limit:
        return contracts
    indices = sorted(rng.sample(range(len(contracts)), limit))
    return [contracts[index] for index in indices]


def get_sec_source_text(contract, db) -> str:
    """Get SEC source text from raw HTML filings."""
    if not contract.filing_id:
        return ""
    filing = db.query(Filing).filter(Filing.id == contract.filing_id).first()
    if not filing:
        return ""
    company = db.query(Company).filter(Company.id == filing.company_id).first()
    if not company:
        return ""

    # Try to find the raw filing HTML
    raw_dir = PROJECT_ROOT / "data" / "raw_filings"
    # CIK might be in company identifiers or filing metadata
    cik = None
    if company.cik:
        cik = str(company.cik).zfill(10)

    if not cik:
        return ""

    cik_dir = _find_cik_directory(raw_dir, cik)
    if cik_dir is None:
        return ""

    # Find HTML files
    html_files = list(cik_dir.rglob("*.htm*"))
    if not html_files:
        return ""

    # Read first HTML and extract text around license keywords
    try:
        from bs4 import BeautifulSoup
        html = html_files[0].read_text(encoding="utf-8", errors="ignore")
        soup = BeautifulSoup(html, "html.parser")
        text = soup.get_text(" ", strip=True)

        # Find section mentioning license/royalty
        keywords = ["license", "royalty", "licensor", "licensee"]
        if contract.licensor_name:
            keywords.append(contract.licensor_name.lower()[:20])

        text_lower = text.lower()
        for kw in keywords:
            idx = text_lower.find(kw.lower())
            if idx >= 0:
                start = max(0, idx - 500)
                end = min(len(text), idx + 1500)
                return text[start:end]

        return text[:2000]
    except Exception:
        return ""


def _find_cik_directory(raw_dir: Path, cik: str) -> Optional[Path]:
    """Locate a raw SEC filing directory, tolerating zero-padded/non-padded CIKs."""
    if not cik or not raw_dir.exists():
        return None

    direct_match = raw_dir / cik
    if direct_match.exists():
        return direct_match

    target = cik.lstrip("0")
    for candidate in raw_dir.iterdir():
        if candidate.is_dir() and candidate.name.lstrip("0") == target:
            return candidate
    return None


def _extract_judge_verdict(raw_response: Any) -> Optional[Dict[str, Any]]:
    """Parse the first JSON object from an LLM response."""
    if isinstance(raw_response, dict):
        return raw_response

    if raw_response is None:
        return None

    raw_text = str(raw_response).strip()
    if not raw_text:
        return None

    match = re.search(r"\{.*\}", raw_text, re.DOTALL)
    if not match:
        return None

    try:
        payload = json.loads(match.group(0))
    except json.JSONDecodeError:
        return None
    return payload if isinstance(payload, dict) else None


def get_dart_source_text(contract, db) -> str:
    """Get DART source text from SQLite."""
    reasoning = contract.reasoning or ""
    if "DART section" not in reasoning:
        return ""

    try:
        conn = sqlite3.connect(SQLITE_PATH)
        conn.row_factory = sqlite3.Row

        # Extract section label from reasoning
        parts = reasoning.split("section=")
        if len(parts) > 1:
            label = parts[1].strip()[:30]
            # Search without score filter
            row = conn.execute(
                "SELECT plain_text FROM dart_sections WHERE dart_label LIKE ? ORDER BY candidate_score DESC LIMIT 1",
                (f"%{label}%",)
            ).fetchone()
            if row:
                conn.close()
                return row["plain_text"][:2000]

        # Fallback: match by company name
        if contract.filing_id:
            filing = db.query(Filing).filter(Filing.id == contract.filing_id).first()
            if filing:
                company = db.query(Company).filter(Company.id == filing.company_id).first()
                if company and company.name_local:
                    row = conn.execute(
                        """SELECT ds.plain_text FROM dart_sections ds
                           JOIN dart_filings df ON ds.filing_id = df.filing_id
                           WHERE df.company_name LIKE ? AND ds.candidate_score >= 3
                           ORDER BY ds.candidate_score DESC LIMIT 1""",
                        (f"%{company.name_local}%",)
                    ).fetchone()
                    if row:
                        conn.close()
                        return row["plain_text"][:2000]

        conn.close()
    except Exception as e:
        logger.debug("DART source text error: %s", e)
    return ""


def run_llm_judge(llm, contracts, db) -> list:
    results = []
    for i, c in enumerate(contracts):
        # Get source text based on source system
        if c.source_system == "DART":
            source_text = get_dart_source_text(c, db)
        else:
            source_text = get_sec_source_text(c, db)

        if not source_text or len(source_text) < 50:
            logger.info("[%d/%d] Skip %s (no source text, %s)", i+1, len(contracts),
                       c.licensor_name or "?", c.source_system)
            continue

        terms = db.query(FinancialTerm).filter(FinancialTerm.contract_id == c.id).all()
        royalty = next((t.rate for t in terms if t.term_type == "royalty" and t.rate), None)

        prompt = JUDGE_PROMPT.format(
            source_text=source_text[:1500],
            licensor=c.licensor_name or "N/A",
            licensee=c.licensee_name or "N/A",
            tech_name=c.tech_name or "N/A",
            category=c.tech_category or "N/A",
            royalty=f"{royalty}%" if royalty else "N/A",
            territory=c.territory or "N/A",
        )

        try:
            result = llm.extract_contracts(prompt, "")
            verdict = _extract_judge_verdict(result.get("raw_response", ""))
            if verdict is None:
                logger.warning("[%d/%d] No JSON in response", i+1, len(contracts))
                continue

            fields = ["licensor_correct", "licensee_correct", "tech_name_correct",
                      "category_correct", "royalty_correct", "territory_correct"]
            correct_count = sum(1 for f in fields if verdict.get(f, False))

            record = {
                "contract_id": c.id,
                "source_system": c.source_system,
                "licensor": c.licensor_name,
                "tech_name": c.tech_name,
                "confidence": c.confidence_score,
                "model": c.extraction_model,
                "verdict": verdict,
                "field_accuracy": correct_count / 6,
                "is_real_license": verdict.get("is_real_license", None),
            }
            results.append(record)

            real = "REAL" if verdict.get("is_real_license") else "NOT_LICENSE"
            logger.info("[%d/%d] %s | %s | accuracy=%.0f%% | %s",
                       i+1, len(contracts), (c.licensor_name or "?")[:30], real,
                       record["field_accuracy"] * 100, c.source_system)

        except Exception as e:
            logger.error("[%d/%d] Judge failed: %s", i+1, len(contracts), e)

    return results


def run_benchmark_comparison(db) -> dict:
    results = {}
    for industry, benchmark in INDUSTRY_BENCHMARKS.items():
        royalties = db.query(FinancialTerm.rate).join(LicenseContract).filter(
            LicenseContract.tech_category.ilike(f"%{industry}%"),
            LicenseContract.quality_flag == "clean",
            FinancialTerm.term_type == "royalty",
            FinancialTerm.rate > 0, FinancialTerm.rate < 100,
        ).all()
        rates = [r[0] for r in royalties]
        if not rates:
            continue
        import statistics
        our_median = statistics.median(rates)
        bench_low, bench_high = benchmark["range"]
        in_range = sum(1 for r in rates if bench_low <= r <= bench_high)

        results[industry] = {
            "our_count": len(rates),
            "our_median": round(our_median, 2),
            "our_mean": round(statistics.mean(rates), 2),
            "benchmark_median": benchmark["median_royalty"],
            "benchmark_range": list(benchmark["range"]),
            "benchmark_source": benchmark["source"],
            "pct_in_benchmark_range": round(in_range / len(rates) * 100, 1),
        }
    return results


def main():
    if not all([SessionLocal, LicenseContract, FinancialTerm, Filing, Company, OllamaProcessor]):
        raise RuntimeError("auto_validate requires backend models, SQLAlchemy, and Ollama dependencies")

    args = build_arg_parser().parse_args()
    db = SessionLocal()
    rng = random.Random(args.seed)

    # === 1. LLM-as-Judge ===
    logger.info(
        "=== Phase 1: LLM-as-Judge (%d clean samples/source, min_confidence=%.2f) ===",
        args.sample_size_per_source,
        args.min_confidence,
    )

    if args.skip_llm:
        logger.info("Skipping LLM-as-Judge phase (--skip-llm).")
        judge_results = []
    else:
        llm = OllamaProcessor(model=args.llm_model)
        llm.timeout = args.llm_timeout

        if not llm.is_available():
            logger.error("Ollama not available.")
            judge_results = []
        else:
            dart_samples = sample_contracts(
                db, "DART", args.sample_size_per_source, args.min_confidence, rng
            )
            sec_samples = sample_contracts(
                db, "EDGAR", args.sample_size_per_source, args.min_confidence, rng
            )

            all_samples = dart_samples + sec_samples
            rng.shuffle(all_samples)
            logger.info("Sampled %d DART + %d SEC", len(dart_samples), len(sec_samples))

            judge_results = run_llm_judge(llm, all_samples, db)

    # === 2. Industry Benchmark ===
    logger.info("=== Phase 2: Industry Benchmark (clean only) ===")
    benchmark_results = run_benchmark_comparison(db)
    for ind, d in benchmark_results.items():
        logger.info("  %s: ours=%.1f%% vs ref=%.1f%% (N=%d, %.0f%% in range)",
                    ind, d["our_median"], d["benchmark_median"], d["our_count"], d["pct_in_benchmark_range"])

    # === Aggregate ===
    if judge_results:
        n = len(judge_results)
        aggregate = {
            "total_judged": n,
            "by_source": {
                "SEC": len([r for r in judge_results if r["source_system"] == "EDGAR"]),
                "DART": len([r for r in judge_results if r["source_system"] == "DART"]),
            },
            "avg_field_accuracy": round(sum(r["field_accuracy"] for r in judge_results) / n, 3),
            "real_license_rate": round(sum(1 for r in judge_results if r.get("is_real_license")) / n, 3),
            "field_precision": {},
        }
        for field in ["licensor_correct", "licensee_correct", "tech_name_correct",
                      "category_correct", "royalty_correct", "territory_correct"]:
            correct = sum(1 for r in judge_results if r.get("verdict", {}).get(field, False))
            aggregate["field_precision"][field.replace("_correct", "")] = round(correct / n, 3)
    else:
        aggregate = {"total_judged": 0}

    output = {
        "llm_judge": {"summary": aggregate, "details": judge_results},
        "industry_benchmark": benchmark_results,
    }

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2, default=str)

    logger.info("=== Saved to %s ===", output_path)

    print("\n" + "=" * 60)
    print("VALIDATION SUMMARY")
    print("=" * 60)
    if aggregate.get("total_judged"):
        print(f"\nLLM-as-Judge (N={aggregate['total_judged']}, SEC={aggregate['by_source']['SEC']}, DART={aggregate['by_source']['DART']}):")
        print(f"  Avg field accuracy:  {aggregate['avg_field_accuracy']*100:.1f}%")
        print(f"  Real license rate:   {aggregate['real_license_rate']*100:.1f}%")
        for field, pct in aggregate.get("field_precision", {}).items():
            print(f"    {field:15s}: {pct*100:.0f}%")

    print(f"\nIndustry Benchmark ({len(benchmark_results)} industries, clean only):")
    for ind, d in benchmark_results.items():
        print(f"  {ind:20s}: ours={d['our_median']:.1f}% vs ref={d['benchmark_median']:.1f}% "
              f"({d['pct_in_benchmark_range']:.0f}% in range, N={d['our_count']})")

    db.close()


if __name__ == "__main__":
    main()
