"""
Migrate existing SQLite data (31,252 SEC agreements) into PostgreSQL.
Run: python -m backend.migrate_data
"""
import json
import sqlite3
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from backend.database import engine, SessionLocal
from backend.models import Base, Company, Filing, LicenseContract, FinancialTerm


SQLITE_PATH = os.path.join(
    os.path.dirname(os.path.dirname(__file__)),
    "data", "processed", "sec_dart_analytics.db",
)
BATCH_SIZE = 500


def migrate():
    # Ensure tables exist
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()

    # Check if already migrated
    existing = db.query(LicenseContract).count()
    if existing > 0:
        print(f"PostgreSQL already has {existing} contracts. Skipping migration.")
        print("Delete and recreate tables to re-migrate.")
        db.close()
        return

    conn = sqlite3.connect(SQLITE_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.execute("SELECT COUNT(*) FROM sec_agreements")
    total = cursor.fetchone()[0]
    print(f"Migrating {total} SEC agreements from SQLite to PostgreSQL...")

    # Phase 1: Build company lookup
    print("Phase 1: Companies...")
    company_cache = {}  # (cik) -> company_id

    cursor = conn.execute(
        "SELECT DISTINCT company, cik, ticker FROM sec_agreements WHERE cik IS NOT NULL"
    )
    batch = []
    for row in cursor:
        cik = row["cik"]
        if cik in company_cache:
            continue
        c = Company(
            country="US",
            name_en=row["company"] or f"CIK-{cik}",
            cik=cik,
            ticker=row["ticker"],
        )
        batch.append(c)
        if len(batch) >= BATCH_SIZE:
            db.add_all(batch)
            db.flush()
            for b in batch:
                company_cache[b.cik] = b.id
            batch = []

    if batch:
        db.add_all(batch)
        db.flush()
        for b in batch:
            company_cache[b.cik] = b.id

    db.commit()
    print(f"  {len(company_cache)} companies created")

    # Phase 2: Filings (one per company+year)
    print("Phase 2: Filings...")
    filing_cache = {}  # (cik, year) -> filing_id

    cursor = conn.execute(
        "SELECT DISTINCT cik, filing_type, filing_year FROM sec_agreements WHERE cik IS NOT NULL"
    )
    batch = []
    for row in cursor:
        key = (row["cik"], row["filing_year"])
        if key in filing_cache:
            continue
        company_id = company_cache.get(row["cik"])
        if not company_id:
            continue
        f = Filing(
            company_id=company_id,
            source_system="EDGAR",
            filing_type=row["filing_type"],
            fiscal_year=row["filing_year"],
        )
        batch.append((key, f))
        if len(batch) >= BATCH_SIZE:
            db.add_all([b[1] for b in batch])
            db.flush()
            for k, obj in batch:
                filing_cache[k] = obj.id
            batch = []

    if batch:
        db.add_all([b[1] for b in batch])
        db.flush()
        for k, obj in batch:
            filing_cache[k] = obj.id

    db.commit()
    print(f"  {len(filing_cache)} filings created")

    # Phase 3: Contracts + Financial Terms
    print("Phase 3: Contracts + Financial Terms...")
    cursor = conn.execute("SELECT * FROM sec_agreements")
    contract_count = 0
    batch_contracts = []
    batch_terms = []

    for row in cursor:
        r = dict(row)
        cik = r.get("cik")
        year = r.get("filing_year")
        filing_id = filing_cache.get((cik, year))

        # Parse territory
        territory = r.get("territory")
        if territory and isinstance(territory, str):
            try:
                parsed = json.loads(territory)
                if isinstance(parsed, list):
                    territory = ", ".join(parsed)
            except (json.JSONDecodeError, TypeError):
                pass

        contract = LicenseContract(
            filing_id=filing_id,
            licensor_name=r.get("licensor_name"),
            licensee_name=r.get("licensee_name"),
            tech_name=r.get("tech_name"),
            tech_category=r.get("tech_category"),
            industry=None,
            territory=territory,
            term_years=r.get("term_years"),
            extraction_model="gemini",  # original extraction model
            confidence_score=r.get("confidence"),
            reasoning=r.get("reasoning"),
            source_system="EDGAR",
        )
        batch_contracts.append((contract, r))

        if len(batch_contracts) >= BATCH_SIZE:
            _flush_contracts(db, batch_contracts, batch_terms)
            contract_count += len(batch_contracts)
            batch_contracts = []
            batch_terms = []
            if contract_count % 5000 == 0:
                print(f"  {contract_count}/{total} contracts migrated...")

    if batch_contracts:
        _flush_contracts(db, batch_contracts, batch_terms)
        contract_count += len(batch_contracts)

    db.commit()
    conn.close()
    db.close()
    print(f"\nMigration complete: {contract_count} contracts migrated to PostgreSQL")


def _flush_contracts(db, batch_contracts, batch_terms):
    contracts = [bc[0] for bc in batch_contracts]
    db.add_all(contracts)
    db.flush()

    terms = []
    for contract, row in batch_contracts:
        # Royalty term
        if row.get("royalty_rate") is not None:
            terms.append(FinancialTerm(
                contract_id=contract.id,
                term_type="royalty",
                rate=row["royalty_rate"],
                rate_unit=row.get("royalty_unit", "%"),
            ))
        # Upfront term
        if row.get("upfront_amount") is not None:
            terms.append(FinancialTerm(
                contract_id=contract.id,
                term_type="upfront",
                amount=row["upfront_amount"],
                currency=row.get("upfront_currency", "USD"),
            ))

    if terms:
        db.add_all(terms)
        db.flush()

    db.commit()


if __name__ == "__main__":
    migrate()
