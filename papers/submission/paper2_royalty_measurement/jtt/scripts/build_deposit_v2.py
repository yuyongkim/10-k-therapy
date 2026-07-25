"""Build the canonical JTT deposit set (v2.0) with full record-level provenance.

Resolution of the v2.1 CHANGELOG blocker
----------------------------------------
Three candidate copies existed:

  A. data/exports/publication/                       (all paper numbers computed here)
  B. papers/submission/lre/zenodo_deposit/           (staged for Zenodo)
  C. .../scientometrics/archive/license_corpus_v1.0.2/

Verified 2026-07-25 (row keys align exactly across all three: 38,114 / 19,054 /
17,497 / 2,523 / 5,598):

  * A and B both have accession_number / rcept_no / filing_date / corp_code
    100% EMPTY.  The upstream PostgreSQL master is empty in those columns too,
    so neither A nor B can back the source-traceback claim.
  * C is a strict superset of A on every shared column, and is the ONLY copy
    carrying populated source identifiers.
  * Every apparent A-vs-C "value conflict" is a formatting artefact where C is
    the better representation: cik '1961.0' (float coercion) vs '0000001961'
    (zero-padded, EDGAR-URL-ready); complexity_score '2.0' vs '2';
    term_years float truncation.  No substantive disagreement.
  * The single column A has that C lacks is `tech_category_normalized`, which
    §6 depends on (category mix, royalty-by-category, OLS).

So: base = C, graft `tech_category_normalized` from A, attach the extraction
artefacts (prompts/, keyword_lists/) that only B staged.

Run: python papers/submission/paper2_royalty_measurement/jtt/scripts/build_deposit_v2.py
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import pandas as pd

# repo root, resolved from this file: .../papers/submission/paper2_royalty_measurement/jtt/scripts
JTT = Path(__file__).resolve().parent.parent
ROOT = JTT.parents[3]
PUB = ROOT / "data" / "exports" / "publication"
V102 = (JTT.parent / "past" / "scientometrics_jict" / "archive" / "license_corpus_v1.0.2")
LRE = (ROOT / "papers" / "submission" / "paper3_crosslingual_corpus" / "lre" / "zenodo_deposit")
OUT = JTT / "dataset_v2.0"

ENC = "utf-8-sig"
CSVS = [
    "license_contracts.csv",
    "license_contracts_clean.csv",
    "financial_terms.csv",
    "companies.csv",
    "filings.csv",
]
# Carried over from the v1.0.2 package unchanged. CITATION.cff is deliberately NOT in
# this list: it is generated below. Copying it from v1.0.2 silently reverted the version
# header to "v1.0.2" on every rebuild, and that stale file reached a published deposit.
DOCS = [
    "source_resolution_audit.json",
    "schema_manifest.json",
    "DATA_DICTIONARY.md",
    "LICENSE-CC-BY-4.0.txt",
]

VERSION = "2.0.1"
ZENODO_CONCEPT_DOI = "10.5281/zenodo.21544899"
# Version DOI of the published v2.0.1 deposit. Used for preferred-citation, since
# reproducing the reported numbers requires the exact frozen files.
ZENODO_VERSION_DOI = "10.5281/zenodo.21545436"

CITATION_CFF = f"""cff-version: 1.2.0
message: "If you use this dataset, please cite it using the metadata below."
title: "Source-Aware Cross-Lingual Corpus of IP License Agreements from SEC EDGAR and Korean DART Filings"
type: dataset
authors:
  - family-names: Kim
    given-names: Yuyong
    orcid: "https://orcid.org/0009-0006-4842-666X"
version: "{VERSION}"
date-released: "2026-07-25"
license: "CC-BY-4.0"
doi: "{ZENODO_CONCEPT_DOI}"
url: "https://doi.org/{ZENODO_CONCEPT_DOI}"
repository-code: "https://github.com/yuyongkim/10-k-therapy"
abstract: "A source-aware, cross-lingual corpus of intellectual property license-agreement records extracted from U.S. SEC EDGAR 10-K filings (fiscal 2019-2025) and Korean DART business reports (fiscal 2023-2026). Every record carries the identifier of the filing it was extracted from: 98.9% of the 38,114 extraction rows and 99.0% of the 19,054 quality-filtered rows resolve to a SEC accession number or a DART receipt number, with unresolved rows explicitly flagged."
keywords:
  - technology transfer
  - technology licensing
  - royalty rates
  - intellectual property
  - regulatory filings
  - cross-lingual corpus
  - open data
  - reproducibility
preferred-citation:
  type: dataset
  title: "Source-Aware Cross-Lingual Corpus of IP License Agreements from SEC EDGAR and Korean DART Filings"
  authors:
    - family-names: Kim
      given-names: Yuyong
      orcid: "https://orcid.org/0009-0006-4842-666X"
  year: 2026
  version: "{VERSION}"
  publisher:
    name: "Zenodo"
  doi: "{ZENODO_VERSION_DOI}"
  url: "https://doi.org/{ZENODO_VERSION_DOI}"
"""


def read(path: Path) -> pd.DataFrame:
    return pd.read_csv(path, encoding=ENC, dtype=str, keep_default_na=False, low_memory=False)


def write(df: pd.DataFrame, path: Path) -> None:
    df.to_csv(path, index=False, encoding=ENC, lineterminator="\n")


def build() -> dict:
    OUT.mkdir(parents=True, exist_ok=True)
    report: dict[str, object] = {}

    # ---- 1. base CSVs from v1.0.2 -------------------------------------------
    for name in CSVS:
        shutil.copy2(V102 / name, OUT / name)

    # ---- 2. graft tech_category_normalized onto the clean table -------------
    clean = read(OUT / "license_contracts_clean.csv")
    pub_clean = read(PUB / "license_contracts_clean.csv")[
        ["contract_id", "tech_category_normalized"]
    ]
    before = len(clean)
    clean = clean.merge(pub_clean, on="contract_id", how="left", validate="one_to_one")
    assert len(clean) == before, "graft changed row count"
    unfilled = int((clean["tech_category_normalized"].fillna("") == "").sum())
    # Place it next to tech_category rather than at the end.
    cols = list(clean.columns)
    cols.remove("tech_category_normalized")
    cols.insert(cols.index("tech_category") + 1, "tech_category_normalized")
    clean = clean[cols]
    write(clean, OUT / "license_contracts_clean.csv")
    report["clean_rows"] = before
    report["tech_category_normalized_unfilled"] = unfilled

    # ---- 2b. normalise serialised-null literals ----------------------------
    # The v1.0.2 exporter wrote the LLM's literal `null` token into text fields
    # instead of an empty cell.  The publication exporter blanked them in the
    # clean table but not the full table, so the two disagreed on field
    # population (DART territory read as 100% populated instead of 76.5%).
    # A literal "null" is a missing value in every case; blank it everywhere so
    # population rates are computed consistently across both tables.
    sentinels = {"null", "NULL", "None", "none", "nan", "NaN"}
    blanked: dict[str, dict[str, int]] = {}
    for name in CSVS:
        df = read(OUT / name)
        per_col: dict[str, int] = {}
        for col in df.columns:
            mask = df[col].isin(sentinels)
            n = int(mask.sum())
            if n:
                df.loc[mask, col] = ""
                per_col[col] = n
        if per_col:
            blanked[name] = per_col
            write(df, OUT / name)
    report["null_literals_blanked"] = blanked

    # ---- 3. extraction artefacts that only the LRE staging had --------------
    for sub in ("prompts", "keyword_lists"):
        src = LRE / sub
        dst = OUT / sub
        if dst.exists():
            shutil.rmtree(dst)
        if src.exists():
            shutil.copytree(src, dst)
            report[f"{sub}_files"] = len(list(dst.rglob("*")))

    # ---- 4. carry the v1.0.2 documentation ---------------------------------
    for name in DOCS:
        src = V102 / name
        if src.exists():
            shutil.copy2(src, OUT / name)

    # ---- 4b. citation metadata (generated, never copied) --------------------
    (OUT / "CITATION.cff").write_text(CITATION_CFF, encoding="utf-8", newline="\n")

    # ---- 5. provenance population audit ------------------------------------
    prov: dict[str, dict] = {}
    for name in CSVS:
        df = read(OUT / name)
        entry: dict[str, object] = {"rows": len(df)}
        for col in ("accession_number", "rcept_no", "source_file_path", "filing_date"):
            if col in df.columns:
                entry[col] = int((df[col].fillna("") != "").sum())
        if "source_resolution_status" in df.columns:
            entry["source_resolution_status"] = (
                df["source_resolution_status"].value_counts().to_dict()
            )
        if {"accession_number", "rcept_no"} <= set(df.columns):
            has_id = ((df["accession_number"] != "") | (df["rcept_no"] != "")).sum()
            entry["any_source_id"] = int(has_id)
            entry["any_source_id_pct"] = round(100 * has_id / len(df), 1)
        prov[name] = entry
    report["provenance"] = prov

    # ---- 6. dataset_summary.json -------------------------------------------
    summary = json.loads((V102 / "dataset_summary.json").read_text(encoding="utf-8"))
    summary["version"] = VERSION
    summary["release_note"] = (
        f"v{VERSION} supersedes v1.0.0/v1.0.2. Base tables are the v1.0.2 provenance-complete "
        "exports (record-level SEC accession numbers and DART receipt numbers, plus "
        "source-resolution status for every row). Adds tech_category_normalized to "
        "license_contracts_clean.csv and bundles the extraction prompts and keyword "
        "lists. The earlier data/exports/publication and lre/zenodo_deposit stagings "
        "carried empty source-identifier columns and are superseded."
    )
    summary["provenance_population"] = prov
    (OUT / "dataset_summary.json").write_text(
        json.dumps(summary, indent=2, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n"
    )

    return report


if __name__ == "__main__":
    rep = build()
    print(json.dumps(rep, indent=2, ensure_ascii=False))
