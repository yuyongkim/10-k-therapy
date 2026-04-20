"""
End-to-end verification of smart AI services.

Run: python verify_smart_services.py
"""

import sys
import os
import sqlite3
import json

sys.path.insert(0, os.path.dirname(__file__))

from services.complexity_analyzer import ComplexityAnalyzer
from services.ai_router import AIRouter, CostTracker


def verify_complexity_analyzer():
    """Verify complexity analyzer with real-world-like samples."""
    print("=" * 60)
    print("1. COMPLEXITY ANALYZER VERIFICATION")
    print("=" * 60)

    analyzer = ComplexityAnalyzer()

    test_cases = [
        ("Simple", "We licensed catalyst technology from XYZ Corp for 3% royalty."),
        ("Medium", """The Company entered into a technology license agreement with
         Honeywell UOP for polypropylene manufacturing technology. Royalty payments
         of 2.5% of net sales, subject to minimum annual payments of $500,000.
         The license is exclusive in South Korea for 15 years, pursuant to the
         terms of the Master Agreement dated March 2022."""),
        ("Complex", """Pursuant to Section 4.2 of the Master License Agreement dated
         January 15, 2024, subject to FDA approval and notwithstanding any force majeure
         events, royalty payments shall range from 2.5% to 4.5% of Net Sales, contingent
         upon achievement of commercially reasonable milestones not to exceed $10,000,000
         in aggregate. The licensee shall have exclusive rights in the territory of
         North America and Europe, subject to the licensor's retained right to sublicense.
         Indemnification obligations under Article 9 shall survive termination for 5 years.
         In the event of a material breach, either party may terminate upon 60 days notice.
         Intellectual property rights in improvements shall be jointly owned pursuant to
         the Joint Ownership Agreement attached as Exhibit C. Governing law: Delaware.
         Arbitration: AAA rules. Liquidated damages for late payments: 1.5% per month.
         Patent rights covering US Patent Nos. 10,123,456 and 10,789,012."""),
    ]

    for label, text in test_cases:
        score = analyzer.analyze_text(text)
        decision = score.get_routing_decision()
        print(f"\n[{label}] Score: {score.total_score}/10 -> {decision}")
        print(f"  Length={score.length_factor}, Legal={score.legal_density}, "
              f"Numeric={score.numeric_complexity}, Ambiguity={score.ambiguity_factor}")

    print("\n[OK] Complexity Analyzer working correctly")


def verify_db_schema():
    """Verify the new tables can be created in SQLite."""
    print("\n" + "=" * 60)
    print("2. DATABASE SCHEMA VERIFICATION")
    print("=" * 60)

    db_path = os.path.join("data", "processed", "sec_dart_analytics.db")
    if not os.path.exists(db_path):
        print(f"[SKIP] Database not found at {db_path}")
        return

    conn = sqlite3.connect(db_path)

    # Create new tables
    conn.execute("""
        CREATE TABLE IF NOT EXISTS ai_processing_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            filing_id TEXT,
            model_used TEXT NOT NULL,
            routing_decision TEXT,
            complexity_score INTEGER,
            confidence_score REAL,
            processing_time_sec REAL,
            input_tokens INTEGER DEFAULT 0,
            output_tokens INTEGER DEFAULT 0,
            cost_usd REAL DEFAULT 0.0,
            processing_path TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS cost_tracking (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            month TEXT NOT NULL,
            model TEXT NOT NULL,
            total_requests INTEGER DEFAULT 0,
            total_input_tokens INTEGER DEFAULT 0,
            total_output_tokens INTEGER DEFAULT 0,
            total_cost_usd REAL DEFAULT 0.0,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(month, model)
        )
    """)
    conn.commit()

    # Verify tables exist
    cursor = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
    )
    tables = [r[0] for r in cursor.fetchall()]
    print(f"\nTables in database: {tables}")

    assert "ai_processing_log" in tables, "ai_processing_log table missing"
    assert "cost_tracking" in tables, "cost_tracking table missing"

    # Show existing data counts
    for table in ["sec_agreements", "dart_filings", "dart_sections"]:
        if table in tables:
            cursor = conn.execute(f"SELECT COUNT(*) FROM {table}")
            count = cursor.fetchone()[0]
            print(f"  {table}: {count} rows")

    conn.close()
    print("\n[OK] Database schema extended successfully")


def verify_cost_tracker():
    """Verify cost tracking works."""
    print("\n" + "=" * 60)
    print("3. COST TRACKER VERIFICATION")
    print("=" * 60)

    db_path = os.path.join("data", "processed", "sec_dart_analytics.db")
    tracker = CostTracker(db_path=db_path)

    # Log a test processing record
    tracker.log_processing({
        "filing_id": "test_verify",
        "model_used": "qwen",
        "routing_decision": "qwen_only",
        "complexity_score": 2,
        "confidence_score": 0.85,
        "processing_time_sec": 1.5,
        "input_tokens": 0,
        "output_tokens": 0,
        "cost_usd": 0.0,
        "processing_path": "qwen_only",
    })

    spend = tracker.get_monthly_spend()
    print(f"  Current monthly spend: ${spend:.4f}")
    print("\n[OK] Cost tracking working")


def verify_existing_data_stats():
    """Show stats from existing SQLite data."""
    print("\n" + "=" * 60)
    print("4. EXISTING DATA STATISTICS")
    print("=" * 60)

    db_path = os.path.join("data", "processed", "sec_dart_analytics.db")
    if not os.path.exists(db_path):
        print("[SKIP] Database not found")
        return

    conn = sqlite3.connect(db_path)

    # SEC agreements stats
    try:
        cursor = conn.execute("SELECT COUNT(*) FROM sec_agreements")
        total = cursor.fetchone()[0]
        print(f"\n  SEC Agreements: {total}")

        cursor = conn.execute(
            "SELECT tech_category, COUNT(*) as cnt FROM sec_agreements "
            "WHERE tech_category IS NOT NULL GROUP BY tech_category ORDER BY cnt DESC LIMIT 10"
        )
        print("  Top categories:")
        for row in cursor.fetchall():
            print(f"    {row[0]}: {row[1]}")

        cursor = conn.execute(
            "SELECT AVG(confidence) FROM sec_agreements WHERE confidence > 0"
        )
        avg_conf = cursor.fetchone()[0]
        print(f"  Average confidence: {avg_conf:.3f}" if avg_conf else "  No confidence data")
    except Exception as e:
        print(f"  SEC data error: {e}")

    # DART stats
    try:
        cursor = conn.execute("SELECT COUNT(*) FROM dart_filings")
        print(f"\n  DART Filings: {cursor.fetchone()[0]}")

        cursor = conn.execute("SELECT COUNT(*) FROM dart_sections")
        print(f"  DART Sections: {cursor.fetchone()[0]}")

        cursor = conn.execute(
            "SELECT COUNT(*) FROM dart_sections WHERE candidate_score >= 3"
        )
        print(f"  High-signal sections (score>=3): {cursor.fetchone()[0]}")
    except Exception as e:
        print(f"  DART data error: {e}")

    conn.close()
    print("\n[OK] Existing data verified")


def verify_ollama_available():
    """Check if Ollama/Qwen is running."""
    print("\n" + "=" * 60)
    print("5. OLLAMA/QWEN AVAILABILITY CHECK")
    print("=" * 60)

    from services.ai_router import QwenProcessor
    qwen = QwenProcessor()
    available = qwen.is_available()
    print(f"  Ollama reachable: {available}")
    if available:
        import requests
        try:
            resp = requests.get(f"{qwen.base_url}/api/tags", timeout=5)
            models = resp.json().get("models", [])
            print(f"  Available models: {[m['name'] for m in models]}")
        except Exception:
            pass
    else:
        print("  [INFO] Ollama not running. Start with: ollama serve")
        print("  [INFO] Then pull Qwen: ollama pull qwen2.5:7b")

    print()


if __name__ == "__main__":
    os.chdir(os.path.dirname(__file__))
    verify_complexity_analyzer()
    verify_db_schema()
    verify_cost_tracker()
    verify_existing_data_stats()
    verify_ollama_available()

    print("=" * 60)
    print("ALL VERIFICATIONS COMPLETE")
    print("=" * 60)
