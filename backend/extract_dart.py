"""
Extract license contract info from DART high-signal sections using Qwen3.
Stores results in PostgreSQL. Tracks processed sections to avoid re-scanning.

Features:
- Incremental: skips already-processed sections
- Timeout-safe: marks timed-out sections so they don't block re-runs
- Dedup: checks for duplicate contracts before inserting
- Ollama health check: waits and retries if Ollama is down
- Progress file: writes progress to dart_extraction_status.json
- Graceful shutdown: catches SIGINT/SIGTERM

Run: python -m backend.extract_dart
Options:
  --min-score 6    Minimum candidate score (default: 6)
  --max-sections 0 Max sections to process (0 = all)
  --resume         Skip to where we left off (default behavior)
"""
import json
import sqlite3
import sys
import os
import time
import signal
import logging
import argparse
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from backend.database import engine, SessionLocal
from backend.models import Base, Company, Filing, LicenseContract, FinancialTerm, AIProcessingLog
from services.qwen_processor import OllamaProcessor
from services.complexity_analyzer import ComplexityAnalyzer
from services.rag_engine import RAGEngine

from utils.common import setup_logging, clean_qwen_json
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("extract_dart")

SQLITE_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "processed", "sec_dart_analytics.db")
STATUS_FILE = os.path.join(os.path.dirname(os.path.dirname(__file__)), "dart_extraction_status.json")

# Graceful shutdown
_shutdown = False
def _handle_signal(signum, frame):
    global _shutdown
    logger.info("Shutdown signal received. Finishing current section...")
    _shutdown = True

signal.signal(signal.SIGINT, _handle_signal)
signal.signal(signal.SIGTERM, _handle_signal)


EXTRACTION_PROMPT = """당신은 한국 기업공시(DART)에서 지식재산권 및 라이선스 계약 정보를 추출하는 전문가입니다.

아래 한국어 텍스트를 분석하여 언급된 모든 라이선스/IP 계약을 추출하세요.

각 계약에 대해 다음을 추출하세요:
- licensor_name: 라이선스 부여자 (기술 제공자)
- licensee_name: 라이선스 수취자 (기술 도입자)
- tech_name: 라이선스 대상 기술, 특허 또는 IP
- tech_category: [Pharmaceutical, Chemical, Software, Semiconductor, Energy, Biotechnology, Automotive, Materials, Other] 중 하나
- royalty_rate: 숫자만 (예: 3.5), 없으면 null
- royalty_unit: %, 원/톤, 정액, 매출액 대비 등
- upfront_amount: 숫자만, 없으면 null
- upfront_currency: USD, KRW, EUR, JPY 등
- territory: 지역 범위 (예: "전세계", "한국", "아시아")
- term_years: 기간(년), 없으면 null
- exclusivity: exclusive, non-exclusive, 또는 null
- confidence_score: 0.0 ~ 1.0

주의사항:
- 실제 라이선스/기술도입 계약만 추출하세요.
- 일반 사업 설명, 대출 계약, 임대차 계약은 제외하세요.
- "기술도입", "로열티", "실시권", "특허", "라이선스", "기술이전", "사용료" 등의 핵심 용어에 주목하세요.
- 계약이 없으면 {"agreements": []} 를 반환하세요.
- 유효한 JSON만 출력하세요.

{rag_context}
TEXT:
"""

EXTRACTION_PROMPT_NO_RAG = EXTRACTION_PROMPT.replace("{rag_context}\n", "")


def write_status(data: dict):
    """Write progress to status file."""
    try:
        with open(STATUS_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2, default=str)
    except Exception:
        pass


def read_status() -> dict:
    try:
        with open(STATUS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def wait_for_ollama(llm: OllamaProcessor, max_retries: int = 5) -> bool:
    """Wait for Ollama to become available."""
    for i in range(max_retries):
        if llm.is_available():
            return True
        logger.warning("Ollama not available. Retry %d/%d in 30s...", i + 1, max_retries)
        time.sleep(30)
    return False


def get_processed_ids(db) -> set:
    rows = db.query(AIProcessingLog.filing_id).filter(
        AIProcessingLog.filing_id.like("dart_section_%")
    ).all()
    return {r[0] for r in rows}


def get_or_create_company(db, company_name: str) -> int:
    existing = db.query(Company).filter(
        Company.name_en == company_name, Company.country == "KR"
    ).first()
    if existing:
        return existing.id
    company = Company(country="KR", name_en=company_name, name_local=company_name)
    db.add(company)
    db.flush()
    return company.id


def get_or_create_filing(db, company_id: int, filing_date: str, doc_type: str) -> int:
    year = None
    if filing_date and len(filing_date) >= 4:
        try:
            year = int(filing_date[:4])
        except ValueError:
            pass

    existing = db.query(Filing).filter(
        Filing.company_id == company_id,
        Filing.source_system == "DART",
        Filing.fiscal_year == year,
    ).first()
    if existing:
        return existing.id

    from datetime import date
    f_date = None
    if filing_date and len(filing_date) == 10:
        try:
            f_date = date.fromisoformat(filing_date)
        except ValueError:
            pass

    filing = Filing(
        company_id=company_id, source_system="DART",
        filing_type=doc_type, filing_date=f_date, fiscal_year=year,
    )
    db.add(filing)
    db.flush()
    return filing.id


def is_duplicate(db, filing_id: int, licensor: str, tech_name: str) -> bool:
    """Check if this contract already exists to prevent duplicates."""
    if not licensor and not tech_name:
        return False
    q = db.query(LicenseContract).filter(
        LicenseContract.filing_id == filing_id,
        LicenseContract.source_system == "DART",
    )
    if licensor:
        q = q.filter(LicenseContract.licensor_name == licensor)
    if tech_name:
        q = q.filter(LicenseContract.tech_name == tech_name)
    return q.first() is not None


SKIP_PATTERNS = [
    "주요계약 없습니다",
    "해당사항 없습니다",
    "해당사항이 없습니다",
    "해당 사항 없습니다",
    "해당 사항이 없습니다",
    "체결중인 경영상의 주요계약은 없습니다",
    "해당없음",
    "not applicable",
    "no material contracts",
]


def extract_section(llm: OllamaProcessor, text: str, rag_context: str = "") -> dict:
    """Send section text to LLM with optional RAG context. Returns parsed result or empty."""
    # Skip sections that explicitly say no contracts
    text_lower = text[:500].lower().replace(" ", "")
    for pattern in SKIP_PATTERNS:
        if pattern.replace(" ", "") in text_lower:
            return {"agreements": [], "_skipped": pattern}

    if len(text) > 1000:
        text = text[:1000]

    if rag_context:
        rag_block = f"""
아래는 유사한 산업/기술 분야의 기존 라이선스 계약 참고 사례입니다. 추출 시 참고하세요:
---
{rag_context[:800]}
---
"""
        prompt = EXTRACTION_PROMPT.replace("{rag_context}", rag_block) + text[:1200]
    else:
        prompt = EXTRACTION_PROMPT_NO_RAG + text

    try:
        result = llm.extract_contracts(prompt, "")
        raw = result.get("raw_response", "{}")
        parsed = clean_qwen_json(raw)
        if parsed is not None:
            return parsed
    except Exception as e:
        if "timed out" in str(e).lower() or "timeout" in str(e).lower():
            raise TimeoutError(f"Qwen timeout: {e}")
        raise

    return {"agreements": []}


LOCK_FILE = os.path.join(os.path.dirname(os.path.dirname(__file__)), "dart_extraction.lock")

def _acquire_lock():
    """Prevent duplicate extraction processes."""
    if os.path.exists(LOCK_FILE):
        try:
            with open(LOCK_FILE, "r") as f:
                old_pid = int(f.read().strip())
            # Check if old process is actually alive (Windows)
            import subprocess
            result = subprocess.run(["tasklist", "/FI", f"PID eq {old_pid}", "/NH"], capture_output=True, text=True)
            if str(old_pid) in result.stdout:
                logger.error("Another extraction is running (PID %d). Exiting.", old_pid)
                return False
        except Exception:
            pass
    with open(LOCK_FILE, "w") as f:
        f.write(str(os.getpid()))
    return True

def _release_lock():
    try:
        os.remove(LOCK_FILE)
    except OSError:
        pass


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--min-score", type=int, default=6)
    parser.add_argument("--max-sections", type=int, default=0)
    args = parser.parse_args()

    if not _acquire_lock():
        return

    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    llm = OllamaProcessor(model="gemma3:4b")
    llm.timeout = 120
    analyzer = ComplexityAnalyzer()

    # RAG disabled for 4b model to stay within context window
    rag = None
    logger.info("RAG disabled for qwen3:4b (context window optimization)")

    if not wait_for_ollama(llm):
        logger.error("Ollama not available after retries. Exiting.")
        return

    processed = get_processed_ids(db)
    logger.info("Already processed: %d sections", len(processed))

    conn = sqlite3.connect(SQLITE_PATH)
    conn.row_factory = sqlite3.Row
    rows = conn.execute("""
        SELECT ds.row_id, df.company_name, df.filing_date, df.document_type,
               ds.candidate_score, ds.plain_text, ds.dart_label, ds.sec_label, ds.token_count
        FROM dart_sections ds
        JOIN dart_filings df ON ds.filing_id = df.filing_id
        WHERE ds.candidate_score >= ?
        AND ds.plain_text IS NOT NULL AND LENGTH(ds.plain_text) > 100
        ORDER BY ds.candidate_score DESC
    """, (args.min_score,)).fetchall()
    conn.close()

    to_process = [r for r in rows if f"dart_section_{r['row_id']}" not in processed]
    if args.max_sections > 0:
        to_process = to_process[:args.max_sections]

    logger.info("Total eligible: %d, to process: %d (min_score=%d)", len(rows), len(to_process), args.min_score)

    if not to_process:
        logger.info("Nothing to process.")
        return

    stats = {"total": len(to_process), "processed": 0, "contracts": 0, "errors": 0, "timeouts": 0, "skipped_dupes": 0}
    write_status({"status": "running", "started": time.strftime("%Y-%m-%d %H:%M:%S"), **stats})

    for i, row in enumerate(to_process):
        if _shutdown:
            logger.info("Graceful shutdown at section %d/%d", i, len(to_process))
            break

        section_key = f"dart_section_{row['row_id']}"
        company_name = row["company_name"] or "Unknown"
        text = row["plain_text"]

        logger.info("[%d/%d] %s (score=%d, tokens=%d)",
                    i + 1, len(to_process), company_name, row["candidate_score"], row["token_count"])

        start_time = time.time()
        processing_path = ""

        try:
            # Check Ollama health before each section
            if not llm.is_available():
                if not wait_for_ollama(llm, max_retries=3):
                    logger.error("Ollama down. Stopping extraction.")
                    break

            # Get RAG context for this section
            rag_context = ""
            if rag:
                try:
                    # Detect tech category from section labels for better RAG filtering
                    section_label = row["dart_label"] or row["sec_label"] or ""
                    rag_context = rag.get_context_for_extraction(
                        text[:1500],  # Use first 1500 chars as query
                        tech_category=None,  # Let vector search determine relevance
                        n_results=3,
                    )
                    if rag_context:
                        logger.info("  RAG: injected %d chars of context", len(rag_context))
                except Exception as e:
                    logger.debug("  RAG context failed: %s", e)

            result = extract_section(llm, text, rag_context=rag_context)
            elapsed = time.time() - start_time
            agreements = result.get("agreements", [])

            if agreements:
                company_id = get_or_create_company(db, company_name)
                filing_id = get_or_create_filing(db, company_id, row["filing_date"], row["document_type"])
                complexity = analyzer.analyze_text(text)
                inserted = 0

                for ag in agreements:
                    licensor = ag.get("licensor_name")
                    tech = ag.get("tech_name")

                    if is_duplicate(db, filing_id, licensor, tech):
                        stats["skipped_dupes"] += 1
                        continue

                    contract = LicenseContract(
                        filing_id=filing_id,
                        licensor_name=licensor,
                        licensee_name=ag.get("licensee_name"),
                        tech_name=tech,
                        tech_category=ag.get("tech_category"),
                        exclusivity=ag.get("exclusivity"),
                        territory=ag.get("territory") if isinstance(ag.get("territory"), str)
                            else json.dumps(ag.get("territory", ""), ensure_ascii=False),
                        term_years=ag.get("term_years"),
                        extraction_model="gemma3:4b",
                        confidence_score=ag.get("confidence_score", 0.7),
                        complexity_score=complexity.total_score,
                        processing_cost_usd=0,
                        reasoning=f"DART section score={row['candidate_score']}, section={row['dart_label'] or row['sec_label']}",
                        source_system="DART",
                    )
                    db.add(contract)
                    db.flush()

                    if ag.get("royalty_rate") is not None:
                        db.add(FinancialTerm(
                            contract_id=contract.id, term_type="royalty",
                            rate=ag["royalty_rate"], rate_unit=ag.get("royalty_unit", "%"),
                        ))
                    if ag.get("upfront_amount") is not None:
                        db.add(FinancialTerm(
                            contract_id=contract.id, term_type="upfront",
                            amount=ag["upfront_amount"], currency=ag.get("upfront_currency", "KRW"),
                        ))
                    inserted += 1

                stats["contracts"] += inserted
                processing_path = f"extracted_{inserted}_agreements"
                logger.info("  -> %d agreements (%.1fs)%s",
                            inserted, elapsed,
                            f" ({stats['skipped_dupes']} dupes skipped)" if stats["skipped_dupes"] else "")
            else:
                processing_path = "extracted_0_agreements"
                logger.info("  -> No agreements (%.1fs)", elapsed)

        except TimeoutError as e:
            elapsed = time.time() - start_time
            stats["timeouts"] += 1
            processing_path = f"timeout_{elapsed:.0f}s"
            logger.warning("  -> Timeout (%.1fs), marking as processed to skip next time", elapsed)

        except Exception as e:
            elapsed = time.time() - start_time
            stats["errors"] += 1
            processing_path = f"error: {str(e)[:100]}"
            logger.error("  -> Error: %s (%.1fs)", e, elapsed)
            db.rollback()

        # Always log processing (even errors/timeouts) to prevent re-processing
        try:
            db.add(AIProcessingLog(
                filing_id=section_key,
                model_used="gemma3:4b",
                routing_decision="dart_extraction",
                complexity_score=row["candidate_score"],
                confidence_score=0,
                processing_time_sec=time.time() - start_time,
                cost_usd=0,
                processing_path=processing_path,
            ))
            db.commit()
        except Exception:
            db.rollback()

        stats["processed"] = i + 1
        write_status({"status": "running", **stats, "last_company": company_name, "updated": time.strftime("%H:%M:%S")})

    write_status({"status": "completed" if not _shutdown else "stopped", **stats, "finished": time.strftime("%Y-%m-%d %H:%M:%S")})
    db.close()
    _release_lock()
    logger.info("=== Done === Processed: %d | Contracts: %d | Errors: %d | Timeouts: %d | Dupes skipped: %d",
                stats["processed"], stats["contracts"], stats["errors"], stats["timeouts"], stats["skipped_dupes"])


if __name__ == "__main__":
    main()
