# -*- coding: utf-8 -*-
"""JTT v2.1 results analysis — canonical data at ../dataset_v2.0/ (resolved relative to this file).
Produces real numbers for §6 (Descriptive Results) and figures."""
import pandas as pd, numpy as np, json, re, sys, io
from pathlib import Path
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
import statsmodels.formula.api as smf

BASE = str(Path(__file__).resolve().parent.parent / "dataset_v2.0")
clean = pd.read_csv(BASE + r"\license_contracts_clean.csv", dtype=str, keep_default_na=False)
ft    = pd.read_csv(BASE + r"\financial_terms.csv", dtype=str, keep_default_na=False)

def nonempty(s):
    return s.astype(str).str.strip().replace({"nan":"","None":"","N/A":"","n/a":""}) != ""

R = {}  # results bag

# ---------- A. Reconciliation ----------
R['n_clean'] = len(clean)
R['n_sec'] = int((clean.source_system=="EDGAR").sum())
R['n_dart'] = int((clean.source_system=="DART").sum())
R['n_unique_companies'] = int(clean.company_name.str.strip().replace({"":np.nan}).dropna().nunique())

# ---------- B. Field population by source ----------
def pop_rate(df, col):
    return round(100*nonempty(df[col]).mean(),1)
pop = {}
for src,label in [("EDGAR","SEC"),("DART","DART")]:
    sub = clean[clean.source_system==src]
    pop[label] = {
        "n": len(sub),
        "territory": pop_rate(sub,"territory"),
        "term_years": pop_rate(sub,"term_years"),
        "exclusivity": pop_rate(sub,"exclusivity"),
    }
R['pop'] = pop

# upfront & royalty population require financial_terms joined to clean
clean_ids = set(clean.contract_id)
ft_clean = ft[ft.contract_id.isin(clean_ids)].copy()
ft_clean = ft_clean.merge(clean[["contract_id","source_system","tech_category_normalized","exclusivity"]],
                          on="contract_id", how="left", suffixes=("","_c"))
# royalty term rows (rate populated)
roy = ft_clean[(ft_clean.term_type=="royalty") & nonempty(ft_clean.rate)].copy()
R['n_royalty_rows_clean'] = len(roy)
# upfront rows
upf = ft_clean[(ft_clean.term_type=="upfront") & nonempty(ft_clean.amount)].copy()
# per-source contract-level population of any royalty / any upfront
for label,src in [("SEC","EDGAR"),("DART","DART")]:
    sub_ids = set(clean[clean.source_system==src].contract_id)
    roy_ids = set(roy[roy.source_system==src].contract_id)
    upf_ids = set(upf[upf.source_system==src].contract_id)
    pop[label]["royalty_any"] = round(100*len(roy_ids & sub_ids)/len(sub_ids),1)
    pop[label]["upfront_any"] = round(100*len(upf_ids & sub_ids)/len(sub_ids),1)

# ---------- C. Royalty-rate cleaning (separate sales-royalty % from interest %) ----------
def parse_rate(x):
    x=str(x).replace(",","").strip()
    m=re.search(r"-?\d+\.?\d*", x)
    return float(m.group()) if m else np.nan
roy["rate_num"] = roy.rate.map(parse_rate)
ru = roy.rate_unit.str.lower().fillna("")
is_interest = ru.str.contains("interest") | ru.str.contains("per annum") & ~ru.str.contains("sales")
is_pct = ru.str.contains("%") | ru.str.contains("percent") | ru.str.contains("net sales") | (ru.str.strip()=="")
# sales-based royalty %: percent-like AND not interest AND plausible 0<r<=50
roy["is_interest"] = is_interest
sales = roy[(~is_interest) & is_pct & roy.rate_num.notna() & (roy.rate_num>0) & (roy.rate_num<=50)].copy()
R['n_royalty_interest_contam'] = int(is_interest.sum())
R['n_royalty_sales_pct'] = len(sales)

# ---------- D. Category x source cross-tab (clean contracts) ----------
ct = pd.crosstab(clean.tech_category_normalized, clean.source_system)
ct["Total"]=ct.sum(axis=1)
ct=ct.sort_values("Total",ascending=False)
R['cat_source'] = ct.to_dict(orient="index")

# ---------- E. Royalty by category: N, median, IQR, mean (sales %) ----------
by = sales.groupby("tech_category_normalized")["rate_num"]
cat_stats={}
for cat,g in by:
    if len(g)>=5:
        cat_stats[cat]={"n":int(len(g)),"median":round(float(g.median()),2),
                        "q1":round(float(g.quantile(.25)),2),"q3":round(float(g.quantile(.75)),2),
                        "mean":round(float(g.mean()),2)}
R['royalty_by_cat']=dict(sorted(cat_stats.items(), key=lambda kv:-kv[1]["n"]))
R['royalty_overall']={"n":int(len(sales)),"median":round(float(sales.rate_num.median()),2),
                      "q1":round(float(sales.rate_num.quantile(.25)),2),"q3":round(float(sales.rate_num.quantile(.75)),2),
                      "mean":round(float(sales.rate_num.mean()),2)}

# ---------- F. OLS: royalty rate ~ category + source + exclusivity ----------
reg = sales.copy()
reg["is_exclusive"] = reg["exclusivity"].str.lower().str.contains("exclusive") & ~reg["exclusivity"].str.lower().str.contains("non")
reg["src"] = reg["source_system"]
reg["cat"] = reg["tech_category_normalized"]
# keep categories with >=20 obs for stable dummies, else 'Other'
big = [c for c,n in reg.cat.value_counts().items() if n>=20]
reg["cat"] = reg.cat.where(reg.cat.isin(big),"Other")
try:
    m = smf.ols("rate_num ~ C(cat, Treatment('Other')) + C(src) + is_exclusive", data=reg).fit()
    R['ols'] = {"n":int(m.nobs),"r2":round(float(m.rsquared),3),
                "params":{k:round(float(v),3) for k,v in m.params.items()},
                "pvalues":{k:round(float(v),4) for k,v in m.pvalues.items()}}
except Exception as e:
    R['ols']={"error":str(e)}

# ---------- G. Cross-jurisdiction category mix (share within source) ----------
mix={}
for src,label in [("EDGAR","SEC"),("DART","DART")]:
    s=clean[clean.source_system==src].tech_category_normalized.value_counts(normalize=True)*100
    mix[label]={k:round(float(v),1) for k,v in s.items()}
R['cat_mix']=mix

print(json.dumps(R, ensure_ascii=False, indent=2))
