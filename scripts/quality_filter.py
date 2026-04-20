"""
Post-processing quality filter for license contracts.

Tags each contract with quality_flag:
  - 'clean'       : likely a real IP license agreement
  - 'noise'       : financial contract misclassified as license (SEC problem)
  - 'duplicate'   : same licensor+tech extracted multiple times
  - 'low_quality' : missing key fields or generic extraction

Run: python scripts/quality_filter.py
"""

import sys
import os
import logging
from collections import defaultdict

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from dotenv import load_dotenv
load_dotenv()

from backend.database import SessionLocal
from backend.models import LicenseContract, FinancialTerm, Filing
from sqlalchemy import func

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("quality_filter")

# === NOISE CATEGORIES (SEC problem: financial contracts misclassified as license) ===
NOISE_CATEGORY_KEYWORDS = [
    'financial', 'equity', 'debt', 'loan', 'lease', 'rental',
    'insurance', 'reinsurance', 'banking', 'credit', 'mortgage',
    'securities', 'investment', 'stock', 'bond', 'compensation',
    'employment', 'real estate', 'derivative', 'securitization',
    'annuity', 'pension', 'lending', 'borrowing', 'hedge',
    'swap', 'warrant', 'option', 'convertible',
]

NOISE_TECH_KEYWORDS = [
    'senior secured term loan', 'credit agreement', 'revolving credit',
    'accounts receivable', 'interest rate', 'common stock',
    'preferred stock', 'lease agreement', 'rental agreement',
    'employment agreement', 'compensation plan', 'stock option',
    'restricted stock', 'annuity', 'insurance policy',
    'promissory note', 'line of credit', 'mortgage',
]

# === GENERIC TECH NAMES (DART problem: vague extraction) ===
GENERIC_TECH_NAMES = {
    '기술', '특허', '특허권', '상표권', '실시권', '라이선스',
    'technology', 'patent', 'license', 'ip', 'intellectual property',
    'N/A', 'n/a', 'None', 'none', '', '미정',
}

# === UNKNOWN LICENSOR PATTERNS ===
UNKNOWN_LICENSOR = {
    'unknown', 'Unknown', 'UNKNOWN', 'N/A', 'n/a', 'Company', 'company',
    '회사', '당사', 'A사', 'B사', '미정', '',
}


def is_noise_category(category: str) -> tuple[bool, str]:
    """Check if tech_category indicates a non-license financial contract."""
    if not category:
        return False, ""
    cat_lower = category.lower()
    for kw in NOISE_CATEGORY_KEYWORDS:
        if kw in cat_lower:
            return True, f"noise_category:{kw}"
    return False, ""


def is_noise_tech(tech_name: str) -> tuple[bool, str]:
    """Check if tech_name indicates a financial contract, not IP license."""
    if not tech_name:
        return False, ""
    tech_lower = tech_name.lower()
    for kw in NOISE_TECH_KEYWORDS:
        if kw in tech_lower:
            return True, f"noise_tech:{kw}"
    return False, ""


def is_generic(tech_name: str, licensor: str) -> tuple[bool, str]:
    """Check if extraction is too generic to be useful."""
    reasons = []
    if tech_name and tech_name.strip() in GENERIC_TECH_NAMES:
        reasons.append(f"generic_tech:{tech_name}")
    if licensor and licensor.strip() in UNKNOWN_LICENSOR:
        reasons.append(f"unknown_licensor:{licensor}")
    if not tech_name and not licensor:
        reasons.append("empty_fields")
    return bool(reasons), "; ".join(reasons)


def find_duplicates(db) -> dict[int, str]:
    """Find duplicate contracts: same filing + licensor + tech_name."""
    # Group by filing_id + licensor + tech
    dupes = db.query(
        LicenseContract.filing_id,
        LicenseContract.licensor_name,
        LicenseContract.tech_name,
        func.count(),
        func.min(LicenseContract.id),
    ).filter(
        LicenseContract.licensor_name.isnot(None),
        LicenseContract.tech_name.isnot(None),
    ).group_by(
        LicenseContract.filing_id,
        LicenseContract.licensor_name,
        LicenseContract.tech_name,
    ).having(func.count() > 1).all()

    dupe_ids = {}
    for filing_id, licensor, tech, count, min_id in dupes:
        # Keep the one with min id, mark rest as duplicate
        contracts = db.query(LicenseContract).filter(
            LicenseContract.filing_id == filing_id,
            LicenseContract.licensor_name == licensor,
            LicenseContract.tech_name == tech,
        ).order_by(LicenseContract.id).all()

        for c in contracts[1:]:  # skip first (keep it)
            dupe_ids[c.id] = f"duplicate_of:{contracts[0].id}"

    return dupe_ids


def main():
    db = SessionLocal()

    total = db.query(func.count(LicenseContract.id)).scalar()
    logger.info("Total contracts: %d", total)

    # Reset all flags
    db.query(LicenseContract).update({
        LicenseContract.quality_flag: None,
        LicenseContract.noise_reason: None,
    })
    db.commit()
    logger.info("Reset all flags")

    # 1. Find duplicates
    logger.info("Finding duplicates...")
    dupe_map = find_duplicates(db)
    logger.info("Found %d duplicates", len(dupe_map))

    # 2. Process all contracts
    stats = defaultdict(int)
    batch_size = 500
    offset = 0

    while True:
        contracts = db.query(LicenseContract).order_by(LicenseContract.id).offset(offset).limit(batch_size).all()
        if not contracts:
            break

        for c in contracts:
            flag = "clean"
            reason = ""

            # Check duplicate first
            if c.id in dupe_map:
                flag = "duplicate"
                reason = dupe_map[c.id]

            # Check noise category (SEC problem)
            elif c.tech_category:
                is_noise, noise_reason = is_noise_category(c.tech_category)
                if is_noise:
                    flag = "noise"
                    reason = noise_reason

            # Check noise tech name
            if flag == "clean" and c.tech_name:
                is_noise, noise_reason = is_noise_tech(c.tech_name)
                if is_noise:
                    flag = "noise"
                    reason = noise_reason

            # Check generic/low quality
            if flag == "clean":
                is_gen, gen_reason = is_generic(c.tech_name, c.licensor_name)
                if is_gen:
                    flag = "low_quality"
                    reason = gen_reason

            c.quality_flag = flag
            c.noise_reason = reason
            stats[flag] += 1

        db.commit()
        offset += batch_size
        logger.info("Processed %d/%d", min(offset, total), total)

    db.close()

    # Report
    print()
    print("=" * 50)
    print("QUALITY FILTER RESULTS")
    print("=" * 50)
    for flag in ["clean", "noise", "duplicate", "low_quality"]:
        cnt = stats[flag]
        pct = cnt / total * 100
        print(f"  {flag:15s}: {cnt:>7,} ({pct:5.1f}%)")
    print(f"  {'TOTAL':15s}: {total:>7,}")
    print()
    clean = stats["clean"]
    print(f"  Paper-ready DB: {clean:,} clean contracts")


if __name__ == "__main__":
    main()
