"""
SEC License Data Scanner
========================
Scans all extracted license data directories and produces a consolidated
JSON summary for the HTML visualization dashboard.
"""

import json
import os
from pathlib import Path
from collections import Counter, defaultdict
from datetime import datetime


def load_company_mapping(data_dir: Path) -> dict:
    """Load CIK -> Company Name mapping from company_tickers.json."""
    mapping = {}
    paths_to_try = [
        data_dir / "company_tickers.json",
        data_dir.parent / "data" / "company_tickers.json",
    ]
    for p in paths_to_try:
        if p.exists():
            with open(p, "r", encoding="utf-8") as f:
                data = json.load(f)
            for val in data.values():
                cik_str = str(val.get("cik_str", "")).zfill(10)
                mapping[cik_str] = {
                    "name": val.get("title", "Unknown"),
                    "ticker": val.get("ticker", ""),
                }
            break
    return mapping


def extract_agreement_info(agreement: dict) -> dict:
    """Extract structured info from a single agreement object."""
    parties = agreement.get("parties", {})
    licensor = parties.get("licensor", {})
    licensee = parties.get("licensee", {})
    tech = agreement.get("technology", {})
    fin = agreement.get("financial_terms", {})
    upfront = fin.get("upfront_payment", {})
    royalty = fin.get("royalty", {})
    contract = agreement.get("contract_terms", {})
    meta = agreement.get("metadata", {})

    has_upfront = upfront.get("amount") is not None
    has_royalty = royalty.get("rate") is not None

    return {
        "licensor_name": licensor.get("name") or "Unknown",
        "licensee_name": licensee.get("name") or "Unknown",
        "tech_name": tech.get("name") or "Unknown",
        "tech_category": tech.get("category") or "Unknown",
        "industry": agreement.get("industry") or "Other",
        "confidence": meta.get("confidence_score", 0),
        "has_upfront": has_upfront,
        "has_royalty": has_royalty,
        "upfront_amount": upfront.get("amount"),
        "upfront_currency": upfront.get("currency"),
        "royalty_rate": royalty.get("rate"),
        "royalty_unit": royalty.get("unit"),
        "territory": contract.get("territory", {}).get("geographic", []),
        "term_years": contract.get("term", {}).get("years"),
        "reasoning": meta.get("extraction_reasoning", ""),
    }


def scan_all_licenses(base_dir: Path, cik_map: dict) -> dict:
    """Scan all extracted_licenses directories and aggregate data."""
    all_agreements = []
    company_stats = defaultdict(lambda: {"count": 0, "ticker": "", "agreements": []})
    industry_counter = Counter()
    category_counter = Counter()
    licensor_counter = Counter()
    licensee_counter = Counter()
    confidence_buckets = Counter()  # 0.0-0.1, 0.1-0.2, ...
    financial_completeness = {"both": 0, "upfront_only": 0, "royalty_only": 0, "neither": 0}
    filing_year_counter = Counter()

    total_files = 0
    total_companies = 0
    errors = 0

    # Walk through all company directories
    if not base_dir.exists():
        print(f"ERROR: Base directory {base_dir} does not exist!")
        return {}

    company_dirs = sorted([d for d in base_dir.iterdir() if d.is_dir()])
    total_companies = len(company_dirs)
    print(f"Scanning {total_companies} company directories...")

    for i, company_dir in enumerate(company_dirs):
        cik = company_dir.name
        company_info = cik_map.get(cik, {"name": f"CIK-{cik}", "ticker": ""})
        company_name = company_info["name"]
        ticker = company_info["ticker"]

        # Find all license_agreements.json files recursively
        json_files = list(company_dir.rglob("license_agreements.json"))
        if not json_files:
            continue

        for json_file in json_files:
            total_files += 1
            try:
                with open(json_file, "r", encoding="utf-8") as f:
                    data = json.load(f)

                if not isinstance(data, list):
                    data = [data]

                # Try to infer filing year from path
                # Path: {cik}/{form_type}/{accession}/license_agreements.json
                parts = json_file.relative_to(company_dir).parts
                filing_type = parts[0] if len(parts) >= 2 else "Unknown"
                accession = parts[1] if len(parts) >= 2 else ""

                # Try to extract year from accession (format: 0001234567-YY-NNNNNN)
                filing_year = None
                if accession and "-" in accession:
                    try:
                        year_part = accession.split("-")[1]
                        year_int = int(year_part)
                        filing_year = 2000 + year_int if year_int < 100 else year_int
                    except (ValueError, IndexError):
                        pass

                for item in data:
                    if not isinstance(item, dict):
                        continue

                    extraction = item.get("extraction", {})
                    
                    # Handle case where extraction is None or not a dict
                    if extraction is None:
                        extraction = {}
                    elif not isinstance(extraction, dict):
                        # If extraction is a list (rare but possible artifact), ignore or handle
                        extraction = {}

                    if not extraction:
                        # Fallback: Maybe the item itself is the extraction?
                        # Check for common keys that would indicate it's an agreement
                        if item.get('parties') or item.get('financial_terms') or item.get('technology'):
                            extraction = item
                        else:
                            continue # If still no extraction, skip this item

                    agreements_list = extraction.get("agreements", [])
                    if not agreements_list:
                        # Sometimes extraction IS the agreement itself
                        if extraction.get("parties"):
                            agreements_list = [extraction]
                        else:
                            continue

                    for ag in agreements_list:
                        info = extract_agreement_info(ag)
                        info["company"] = company_name
                        info["cik"] = cik
                        info["ticker"] = ticker
                        info["filing_type"] = filing_type
                        info["filing_year"] = filing_year

                        all_agreements.append(info)

                        # Update counters
                        company_stats[cik]["count"] += 1
                        company_stats[cik]["ticker"] = ticker
                        company_stats[cik]["name"] = company_name

                        industry_counter[info["industry"]] += 1
                        category_counter[info["tech_category"]] += 1
                        licensor_counter[info["licensor_name"]] += 1
                        licensee_counter[info["licensee_name"]] += 1

                        # Confidence buckets
                        try:
                            conf = float(info["confidence"])
                            bucket = min(int(conf * 10), 9)  # 0-9
                            bucket_label = f"{bucket/10:.1f}-{(bucket+1)/10:.1f}"
                            confidence_buckets[bucket_label] += 1
                        except (ValueError, TypeError):
                            confidence_buckets["unknown"] += 1

                        # Financial completeness
                        if info["has_upfront"] and info["has_royalty"]:
                            financial_completeness["both"] += 1
                        elif info["has_upfront"]:
                            financial_completeness["upfront_only"] += 1
                        elif info["has_royalty"]:
                            financial_completeness["royalty_only"] += 1
                        else:
                            financial_completeness["neither"] += 1

                        # Filing year
                        if filing_year:
                            filing_year_counter[str(filing_year)] += 1

            except Exception as e:
                errors += 1
                if errors <= 10:
                    print(f"  Error reading {json_file}: {e}")

        if (i + 1) % 200 == 0:
            print(f"  Processed {i+1}/{total_companies} companies, {len(all_agreements)} agreements so far...")

    print(f"\nScan complete!")
    print(f"  Companies scanned: {total_companies}")
    print(f"  License JSON files: {total_files}")
    print(f"  Total agreements: {len(all_agreements)}")
    print(f"  Errors: {errors}")

    # Build summary
    summary = {
        "scan_timestamp": datetime.now().isoformat(),
        "total_companies": total_companies,
        "companies_with_licenses": len(company_stats),
        "total_license_files": total_files,
        "total_agreements": len(all_agreements),
        "scan_errors": errors,
    }

    # Sort counters for top-N
    top_licensors = dict(licensor_counter.most_common(30))
    top_licensees = dict(licensee_counter.most_common(30))
    top_companies = sorted(
        [{"cik": k, **v} for k, v in company_stats.items()],
        key=lambda x: x["count"],
        reverse=True,
    )[:30]

    # Build output
    result = {
        "summary": summary,
        "by_industry": dict(industry_counter.most_common()),
        "by_tech_category": dict(category_counter.most_common()),
        "top_licensors": top_licensors,
        "top_licensees": top_licensees,
        "top_companies": top_companies,
        "confidence_distribution": dict(sorted(confidence_buckets.items())),
        "financial_completeness": financial_completeness,
        "by_filing_year": dict(sorted(filing_year_counter.items())),
        "all_agreements": all_agreements,
    }

    return result


def main():
    # Determine paths
    script_dir = Path(__file__).parent
    
    # Data directory candidates
    data_dirs = [
        script_dir / "data" / "extracted_licenses",
        script_dir.parent / "data" / "extracted_licenses",
    ]

    base_dir = None
    for d in data_dirs:
        if d.exists() and any(d.iterdir()):
            base_dir = d
            break

    if not base_dir:
        print("ERROR: Could not find extracted_licenses directory!")
        print(f"Tried: {[str(d) for d in data_dirs]}")
        return

    print(f"Using data directory: {base_dir}")
    print(f"Script directory: {script_dir}")

    # Load CIK mapping
    cik_map = load_company_mapping(base_dir.parent)
    print(f"Loaded {len(cik_map)} company mappings")

    # Scan
    result = scan_all_licenses(base_dir, cik_map)

    if not result:
        print("No data found!")
        return

    # Save full output
    output_file = script_dir / "license_summary.json"
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2, ensure_ascii=False, default=str)

    print(f"\nSaved summary to: {output_file}")
    print(f"File size: {output_file.stat().st_size / 1024:.1f} KB")

    # Print quick overview
    s = result["summary"]
    print(f"\n{'='*50}")
    print(f"  SCAN RESULTS OVERVIEW")
    print(f"{'='*50}")
    print(f"  Total Companies:        {s['total_companies']}")
    print(f"  Companies w/ Licenses:  {s['companies_with_licenses']}")
    print(f"  Total Agreements:       {s['total_agreements']}")
    print(f"  License JSON Files:     {s['total_license_files']}")
    print(f"  Scan Errors:            {s['scan_errors']}")
    print(f"\n  Top 5 Industries:")
    for ind, cnt in list(result["by_industry"].items())[:5]:
        print(f"    {ind}: {cnt}")
    print(f"\n  Financial Completeness:")
    for k, v in result["financial_completeness"].items():
        print(f"    {k}: {v}")


if __name__ == "__main__":
    main()
