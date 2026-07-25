# -*- coding: utf-8 -*-
"""Generate JTT v2.1 figures from canonical data (no in-image titles — captions live in the manuscript) → ../figures/ (resolved relative to this file)."""
import pandas as pd, numpy as np, re, os
from pathlib import Path
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyArrowPatch

# Springer artwork rules: sans-serif lettering (Helvetica/Arial) at 8-12 pt,
# 174 mm maximum width, 600 dpi for combination art. DejaVu Sans is the
# metrically-compatible substitute available here.
plt.rcParams.update({
    "font.family":"sans-serif","font.sans-serif":["Arial","Helvetica","DejaVu Sans"],
    "font.size":9,"axes.titlesize":10,"axes.labelsize":9,
    "xtick.labelsize":8.5,"ytick.labelsize":8.5,"legend.fontsize":8.5,
    "axes.spines.top":False,"axes.spines.right":False,
    "figure.dpi":150,"savefig.dpi":600,"savefig.bbox":"tight",
})
MM = 1/25.4
FULL_W = 174*MM   # Springer full-width figure
SEC_C="#2f4b7c"; DART_C="#c1663a"; GREY="#7a7a7a"
BASE=str(Path(__file__).resolve().parent.parent / "dataset_v2.0")
OUT=str(Path(__file__).resolve().parent.parent / "figures")
os.makedirs(OUT,exist_ok=True)
clean=pd.read_csv(BASE+r"\license_contracts_clean.csv",dtype=str,keep_default_na=False)
ft=pd.read_csv(BASE+r"\financial_terms.csv",dtype=str,keep_default_na=False)
clean["fy"]=pd.to_numeric(clean.fiscal_year,errors="coerce")

# ---- Fig 1: quality funnel ----
fig,ax=plt.subplots(figsize=(FULL_W,3.9))
stages=["Raw candidate\nrecords","Quality-filtered\n(clean)","With royalty\nrate","Sales-based %\nroyalties"]
sec_vals=[31252,13951,None,None]; dart_vals=[6862,5103,None,None]
tot=[38114,19054,2046,963]
x=np.arange(len(stages))
ax.bar(x,tot,color=[SEC_C,DART_C,"#6b8cae","#9bb0c9"],width=0.62,edgecolor="white")
for i,v in enumerate(tot):
    ax.text(i,v+600,f"{v:,}",ha="center",va="bottom",fontweight="bold",fontsize=9)
ax.text(0,31252/2,"SEC 31,252",ha="center",color="white",fontsize=8.5)
ax.text(0,31252+6862/2,"DART 6,862",ha="center",color="white",fontsize=8.5)
ax.text(1,13951/2,"SEC 13,951",ha="center",color="white",fontsize=8.5)
ax.text(1,13951+5103/2,"DART 5,103",ha="center",color="white",fontsize=8.5)
ax.set_xticks(x); ax.set_xticklabels(stages,fontsize=8.5)
ax.set_ylabel("Records"); ax.set_ylim(0,42000)
ax.get_yaxis().set_major_formatter(matplotlib.ticker.FuncFormatter(lambda v,_:f"{int(v):,}"))
plt.savefig(OUT+r"\figure1_quality_funnel.png"); plt.close()

# ---- Fig 2: temporal coverage ----
ct=pd.crosstab(clean.fy.astype("Int64"),clean.source_system).reindex(range(2019,2027),fill_value=0)
fig,ax=plt.subplots(figsize=(FULL_W,3.7))
ax.bar(ct.index.astype(str),ct["EDGAR"],color=SEC_C,label="SEC EDGAR")
ax.bar(ct.index.astype(str),ct["DART"],bottom=ct["EDGAR"],color=DART_C,label="Korean DART")
ax.set_ylabel("Quality-filtered records"); ax.set_xlabel("Fiscal year")
ax.legend(frameon=False,fontsize=9)
plt.savefig(OUT+r"\figure2_temporal.png"); plt.close()

# ---- Fig 3: category mix by source (share within source) ----
cats=["Pharmaceutical","Software","Biotechnology","Energy","Automotive","Materials","Chemical","Semiconductor","Other"]
sec_sh=(clean[clean.source_system=="EDGAR"].tech_category_normalized.value_counts(normalize=True)*100).reindex(cats,fill_value=0)
dart_sh=(clean[clean.source_system=="DART"].tech_category_normalized.value_counts(normalize=True)*100).reindex(cats,fill_value=0)
y=np.arange(len(cats)); h=0.38
fig,ax=plt.subplots(figsize=(FULL_W,4.4))
ax.barh(y+h/2,sec_sh.values,height=h,color=SEC_C,label="SEC EDGAR")
ax.barh(y-h/2,dart_sh.values,height=h,color=DART_C,label="Korean DART")
ax.set_yticks(y); ax.set_yticklabels(cats); ax.invert_yaxis()
ax.set_xlabel("Share of source's clean records (%)")
ax.legend(frameon=False,fontsize=9,loc="lower right")
plt.savefig(OUT+r"\figure3_category_mix.png"); plt.close()

# ---- Fig 4: royalty rate distribution by category (boxplot) ----
clean_ids=set(clean.contract_id)
roy=ft[(ft.term_type=="royalty")&(ft.contract_id.isin(clean_ids))&(ft.rate.str.strip()!="")].copy()
roy=roy.merge(clean[["contract_id","tech_category_normalized"]],on="contract_id",how="left")
def pr(x):
    m=re.search(r"-?\d+\.?\d*",str(x).replace(",",""));return float(m.group()) if m else np.nan
roy["r"]=roy.rate.map(pr); ru=roy.rate_unit.str.lower().fillna("")
isint=ru.str.contains("interest")|(ru.str.contains("per annum")&~ru.str.contains("sales"))
ispct=ru.str.contains("%")|ru.str.contains("percent")|ru.str.contains("net sales")|(ru.str.strip()=="")
sales=roy[(~isint)&ispct&roy.r.notna()&(roy.r>0)&(roy.r<=50)]
order=[c for c in ["Other","Pharmaceutical","Biotechnology","Automotive","Chemical","Energy","Software"]
       if (sales.tech_category_normalized==c).sum()>=20]
data=[sales[sales.tech_category_normalized==c].r.values for c in order]
labels=[f"{c}\n(n={len(d)})" for c,d in zip(order,data)]
fig,ax=plt.subplots(figsize=(FULL_W,4.0))
bp=ax.boxplot(data,labels=labels,showfliers=False,patch_artist=True,widths=0.6,medianprops=dict(color="black"))
for p in bp["boxes"]: p.set_facecolor("#9bb0c9"); p.set_edgecolor(GREY)
ax.axhline(sales.r.median(),ls="--",lw=0.8,color=DART_C,label=f"Overall median {sales.r.median():.1f}%")
ax.set_ylabel("Running royalty rate (%)"); ax.set_ylim(0,25)
ax.legend(frameon=False,fontsize=8.5)
ax.tick_params(axis="x",labelsize=8)
plt.savefig(OUT+r"\figure4_royalty_by_category.png"); plt.close()

# ---- Fig 5: field population by source ----
def nonempty(s): return (s.astype(str).str.strip().replace({"nan":"","None":"","N/A":""})!="")
fields=["territory","term_years","exclusivity"]
def anyterm(src,tt):
    ids=set(clean[clean.source_system==src].contract_id)
    sub=ft[(ft.term_type==tt)&(ft.contract_id.isin(ids))]
    if tt=="royalty": sub=sub[sub.rate.str.strip()!=""]
    else: sub=sub[sub.amount.str.strip()!=""]
    return 100*len(set(sub.contract_id)&ids)/len(ids)
rows=["Territory","Term (years)","Exclusivity","Royalty rate","Upfront amount"]
sec=[100*nonempty(clean[clean.source_system=="EDGAR"][f]).mean() for f in fields]+[anyterm("EDGAR","royalty"),anyterm("EDGAR","upfront")]
dart=[100*nonempty(clean[clean.source_system=="DART"][f]).mean() for f in fields]+[anyterm("DART","royalty"),anyterm("DART","upfront")]
y=np.arange(len(rows)); h=0.38
fig,ax=plt.subplots(figsize=(FULL_W,3.9))
ax.barh(y+h/2,sec,height=h,color=SEC_C,label="SEC EDGAR")
ax.barh(y-h/2,dart,height=h,color=DART_C,label="Korean DART")
for i,(s,d) in enumerate(zip(sec,dart)):
    ax.text(s+1,i+h/2,f"{s:.0f}",va="center",fontsize=8)
    ax.text(d+1,i-h/2,f"{d:.0f}",va="center",fontsize=8)
ax.set_yticks(y); ax.set_yticklabels(rows); ax.invert_yaxis()
ax.set_xlabel("Field population rate (% of source's clean records)"); ax.set_xlim(0,100)
ax.legend(frameon=False,fontsize=9,loc="lower right")
plt.savefig(OUT+r"\figure5_field_population.png"); plt.close()

# Springer prefers TIFF for halftone/combination art; emit both.
try:
    from PIL import Image
    for f in sorted(os.listdir(OUT)):
        if f.endswith(".png"):
            src = os.path.join(OUT, f)
            dst = os.path.join(OUT, "tiff", f[:-4] + ".tif")
            os.makedirs(os.path.join(OUT, "tiff"), exist_ok=True)
            im = Image.open(src).convert("RGB")
            im.save(dst, format="TIFF", compression="tiff_lzw", dpi=(600, 600))
except ImportError:
    print("Pillow not installed - TIFF versions skipped")

print("figures written to",OUT)
for f in sorted(os.listdir(OUT)): print(" ",f,os.path.getsize(os.path.join(OUT,f)),"bytes")
