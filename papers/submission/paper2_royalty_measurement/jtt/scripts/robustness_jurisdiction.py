# -*- coding: utf-8 -*-
"""Robustness for the jurisdiction-parity result (reviewer feedback, 2026-07-25).

Three things the feedback asked for:

  M1  baseline           — category + jurisdiction + exclusivity (Table 5 as published)
  M2  + year fixed effects
        The DART subset is 91.8% fiscal-2025 while SEC spans 2019-2025, so the
        jurisdiction coefficient in M1 may be absorbing a time-composition effect.
  M3  fiscal-2025-matched subsample
        The cleanest cut: both sources restricted to the one year they overlap in.

  TOST equivalence test on the jurisdiction coefficient, margin +/- 2.0 pp.
        "Not significant" is not evidence of no difference. TOST turns the null
        into a positive claim if both one-sided tests reject.

Run: python .../jtt/scripts/robustness_jurisdiction.py
"""

import io
import json
import re
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import statsmodels.formula.api as smf
from scipy import stats

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

BASE = Path(__file__).resolve().parent.parent / "dataset_v2.0"
clean = pd.read_csv(BASE / "license_contracts_clean.csv", dtype=str, keep_default_na=False)
ft = pd.read_csv(BASE / "financial_terms.csv", dtype=str, keep_default_na=False)

EQUIV_MARGIN = 2.0  # percentage points


def nonempty(s):
    return s.astype(str).str.strip().replace({"nan": "", "None": "", "N/A": "", "n/a": ""}) != ""


def parse_rate(x):
    m = re.search(r"-?\d+\.?\d*", str(x).replace(",", "").strip())
    return float(m.group()) if m else np.nan


def build_sales_subset() -> pd.DataFrame:
    """The same 963-observation subset used for Table 5."""
    clean_ids = set(clean.contract_id)
    f = ft[ft.contract_id.isin(clean_ids)].merge(
        clean[["contract_id", "source_system", "tech_category_normalized",
               "exclusivity", "fiscal_year"]],
        on="contract_id", how="left", suffixes=("", "_c"))
    roy = f[(f.term_type == "royalty") & nonempty(f.rate)].copy()
    roy["rate_num"] = roy.rate.map(parse_rate)
    ru = roy.rate_unit.str.lower().fillna("")
    is_interest = ru.str.contains("interest") | (ru.str.contains("per annum") & ~ru.str.contains("sales"))
    is_pct = (ru.str.contains("%") | ru.str.contains("percent")
              | ru.str.contains("net sales") | (ru.str.strip() == ""))
    sales = roy[(~is_interest) & is_pct & roy.rate_num.notna()
                & (roy.rate_num > 0) & (roy.rate_num <= 50)].copy()
    sales["is_exclusive"] = (sales.exclusivity.str.lower().str.contains("exclusive")
                             & ~sales.exclusivity.str.lower().str.contains("non"))
    sales["src"] = sales.source_system
    big = [c for c, n in sales.tech_category_normalized.value_counts().items() if n >= 20]
    sales["cat"] = sales.tech_category_normalized.where(
        sales.tech_category_normalized.isin(big), "Other")
    sales["fy"] = pd.to_numeric(sales.fiscal_year, errors="coerce")
    return sales


def tost(coef: float, se: float, df: int, margin: float) -> dict:
    """Two one-sided tests. Equivalence declared if both reject at alpha=.05."""
    t_lower = (coef + margin) / se           # H0: beta <= -margin
    t_upper = (coef - margin) / se           # H0: beta >= +margin
    p_lower = stats.t.sf(t_lower, df)
    p_upper = stats.t.cdf(t_upper, df)
    p_tost = max(p_lower, p_upper)
    crit = stats.t.ppf(0.95, df)             # 90% CI == the TOST interval at alpha=.05
    lo, hi = coef - crit * se, coef + crit * se
    # Smallest symmetric margin at which equivalence would be declared. Reported so the
    # result stays informative when the pre-specified margin is not met — it is just the
    # outer edge of the 90% interval, not a margin chosen after seeing the answer.
    min_margin = max(abs(lo), abs(hi))
    return {
        "margin_pp": margin,
        "coef": round(coef, 3),
        "se": round(se, 3),
        "p_lower": round(float(p_lower), 4),
        "p_upper": round(float(p_upper), 4),
        "p_tost": round(float(p_tost), 4),
        "ci90": [round(lo, 3), round(hi, 3)],
        "equivalent_at_prespecified_margin": bool(p_tost < 0.05),
        "min_margin_for_equivalence_pp": round(float(min_margin), 2),
    }


def summarize(model, label: str, src_term: str) -> dict:
    coef = float(model.params[src_term])
    se = float(model.bse[src_term])
    return {
        "model": label,
        "n": int(model.nobs),
        "r2": round(float(model.rsquared), 4),
        "r2_adj": round(float(model.rsquared_adj), 4),
        "jurisdiction_coef": round(coef, 3),
        "jurisdiction_se": round(se, 3),
        "jurisdiction_p": round(float(model.pvalues[src_term]), 4),
        "exclusive_coef": (round(float(model.params["is_exclusive[T.True]"]), 3)
                           if "is_exclusive[T.True]" in model.params else None),
        "exclusive_p": (round(float(model.pvalues["is_exclusive[T.True]"]), 4)
                        if "is_exclusive[T.True]" in model.params else None),
        "tost": tost(coef, se, int(model.df_resid), EQUIV_MARGIN),
    }


def main() -> int:
    sales = build_sales_subset()
    out = {"equivalence_margin_pp": EQUIV_MARGIN}

    out["year_composition"] = {
        "SEC": clean[clean.source_system == "EDGAR"].fiscal_year.value_counts().sort_index().to_dict(),
        "DART": clean[clean.source_system == "DART"].fiscal_year.value_counts().sort_index().to_dict(),
    }
    out["royalty_subset_year_composition"] = {
        src: sales[sales.src == s].fy.value_counts().sort_index().astype(int).to_dict()
        for src, s in [("SEC", "EDGAR"), ("DART", "DART")]
    }

    SRC = "C(src)[T.EDGAR]"
    m1 = smf.ols("rate_num ~ C(cat, Treatment('Other')) + C(src) + is_exclusive", data=sales).fit()
    out["M1_baseline"] = summarize(m1, "category + jurisdiction + exclusivity", SRC)

    m2 = smf.ols("rate_num ~ C(cat, Treatment('Other')) + C(src) + is_exclusive + C(fy)",
                 data=sales.dropna(subset=["fy"])).fit()
    out["M2_year_fe"] = summarize(m2, "M1 + year fixed effects", SRC)

    s25 = sales[sales.fy == 2025]
    out["M3_fy2025_matched"] = {
        "n_sec": int((s25.src == "EDGAR").sum()),
        "n_dart": int((s25.src == "DART").sum()),
    }
    if out["M3_fy2025_matched"]["n_sec"] >= 20 and out["M3_fy2025_matched"]["n_dart"] >= 20:
        m3 = smf.ols("rate_num ~ C(cat, Treatment('Other')) + C(src) + is_exclusive", data=s25).fit()
        out["M3_fy2025_matched"].update(summarize(m3, "fiscal-2025-matched subsample", SRC))
    else:
        out["M3_fy2025_matched"]["skipped"] = "fewer than 20 observations on one side"

    # Unconditional medians, for the "conditional parity" wording in the text.
    out["medians"] = {
        src: {"n": int((sales.src == s).sum()),
              "median": round(float(sales[sales.src == s].rate_num.median()), 2)}
        for src, s in [("SEC", "EDGAR"), ("DART", "DART")]
    }

    print(json.dumps(out, indent=2, ensure_ascii=False, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
