# Reproduction code — SEC–DART licensing royalty analysis

These scripts regenerate every statistic and figure reported in §5–§6 of the accompanying
manuscript from the released corpus. They are the code referred to by the article's Code
Availability statement.

## Get the data

The corpus is archived on Zenodo under CC BY 4.0:

- **Version DOI (cite this): https://doi.org/10.5281/zenodo.21545436** — frozen v2.0.1,
  the exact files the reported numbers were computed from
- Concept DOI: https://doi.org/10.5281/zenodo.21544899 — always the current version

Download `license_corpus_v2.0.1.zip` (5.15 MB, MD5 `1b38c18190f1f698f065d789e887000c`) and
unpack it so the CSVs sit in a directory named `dataset_v2.0/` beside this `scripts/`
folder — that is the layout the scripts resolve relative to their own location:

```
jtt/
├── dataset_v2.0/          <- unpacked corpus
├── figures/               <- created by make_figures.py
└── scripts/               <- this directory
```

## Run

```bash
python analyze_results.py          # §5 field population, §6 descriptive statistics, Table 5, baseline OLS
python robustness_jurisdiction.py  # Table 6: year fixed effects, FY2025-matched subsample, TOST
python make_figures.py             # Figs 1-5 at 600 dpi, plus TIFF versions
```

`analyze_results.py` and `robustness_jurisdiction.py` print JSON to stdout. Every headline
number in the paper appears there: 19,054 clean records, 2,046 royalty observations, the
963-observation sales-based subset, the 2.5% median, the category table, and the three
regression specifications with their confidence intervals and equivalence tests.

Requires `pandas`, `numpy`, `statsmodels`, `scipy`, `matplotlib`, and `Pillow` for the TIFF
step.

## Provenance

`build_deposit_v2.py` documents how the release was assembled — which of three candidate
exports was canonical, why, and what was corrected. It is included for transparency and
will not run outside the authoring environment, since it reads source trees that are not
part of this repository. Its docstring is the authoritative record of that reconciliation.

## Note on figure files

`make_figures.py` writes PNG at 600 dpi and LZW-compressed TIFF alongside. Figure lettering
is sans-serif at 8.5 pt or larger and figures are held under 174 mm wide, per Springer's
artwork specification.
