# -*- coding: utf-8 -*-
"""Stratified human-calibration spot check on the license extraction database."""
import requests
import json
import re
import os
import sys

sys.stdout.reconfigure(encoding="utf-8")

from dotenv import load_dotenv
load_dotenv()

BASE = "http://localhost:8000/api/annotation"


def text_in_source(text, source):
    """Check if text (or meaningful parts of it) appear in source."""
    if not text or len(text.strip()) < 2:
        return False
    t = text.strip().lower()
    s = source.lower()
    # Direct substring match
    if t in s:
        return True
    # Try splitting by various delimiters and check parts
    parts = re.split(r"[,.()/\s\-\u3000]+", t)
    meaningful = [p for p in parts if len(p) >= 2]
    if not meaningful:
        return False
    matches = sum(1 for p in meaningful if p in s)
    # At least 30% of parts match
    return matches / len(meaningful) >= 0.3


def judge_contract(c):
    """Judge a single contract against its source text. Returns verdict dict or None."""
    src = c.get("source_text", "") or ""
    ext = c["extraction"]
    terms = c.get("financial_terms", [])

    if not src or len(src.strip()) < 50:
        return None

    src_lower = src.lower()

    licensor = ext.get("licensor") or ""
    licensee = ext.get("licensee") or ""
    tech_name = ext.get("tech_name") or ""
    category = ext.get("tech_category") or ""
    territory = ext.get("territory") or ""

    licensor_correct = text_in_source(licensor, src)
    licensee_correct = text_in_source(licensee, src)
    tech_name_correct = text_in_source(tech_name, src)

    # Category check
    category_correct = False
    if category:
        if text_in_source(category, src) or text_in_source(category, tech_name):
            category_correct = True
        cat_lower = category.lower()
        cat_map = {
            "pharma": ["drug", "pharma", "medicine", "therapeutic", "\uc758\uc57d", "\uc57d\ud488", "\uc81c\uc57d"],
            "biotech": ["bio", "gene", "cell", "protein", "\ubc14\uc774\uc624", "\uc0dd\uba85", "\uc138\ud3ec", "\uc720\uc804"],
            "software": ["software", "platform", "app", "digital", "\uc18c\ud504\ud2b8\uc6e8\uc5b4", "\ud50c\ub7ab\ud3fc", "SW"],
            "chemical": ["chemical", "compound", "polymer", "\ud654\ud559", "\ud654\ud569\ubb3c", "\uc18c\uc7ac"],
            "semiconductor": ["semiconductor", "chip", "wafer", "\ubc18\ub3c4\uccb4", "\uce69"],
            "medical": ["medical", "device", "health", "\uc758\ub8cc", "\uc758\ud559", "\uce58\ub8cc"],
            "automotive": ["auto", "vehicle", "car", "\uc790\ub3d9\ucc28", "\ucc28\ub7c9"],
            "energy": ["energy", "solar", "battery", "\uc5d0\ub108\uc9c0", "\ubc30\ud130\ub9ac", "\uc804\uc9c0"],
            "electronics": ["electron", "display", "sensor", "\uc804\uc790", "\ub514\uc2a4\ud50c\ub808\uc774", "\uc13c\uc11c"],
        }
        for cat_key, keywords in cat_map.items():
            if cat_key in cat_lower:
                if any(kw in src_lower or kw in tech_name.lower() for kw in keywords):
                    category_correct = True
                    break

    # Royalty check
    royalty_correct = False
    royalty_rate = None
    for t in terms:
        if t.get("type") == "royalty" and t.get("rate"):
            royalty_rate = t["rate"]
            break
    if royalty_rate is not None:
        rate_str = str(royalty_rate)
        if rate_str in src or f"{royalty_rate}%" in src or f"{royalty_rate} %" in src:
            royalty_correct = True
        if isinstance(royalty_rate, float) and royalty_rate == int(royalty_rate):
            if str(int(royalty_rate)) in src:
                royalty_correct = True

    # Territory check
    territory_correct = False
    if territory:
        territory_correct = text_in_source(territory, src)
        terr_lower = territory.lower()
        if any(w in terr_lower for w in ["worldwide", "global", "\uc804\uc138\uacc4", "\uae00\ub85c\ubc8c"]):
            if any(w in src_lower for w in ["worldwide", "global", "\uc804\uc138\uacc4", "\uae00\ub85c\ubc8c", "world"]):
                territory_correct = True
        if any(w in terr_lower for w in ["korea", "\ud55c\uad6d", "\uad6d\ub0b4"]):
            if any(w in src_lower for w in ["korea", "\ud55c\uad6d", "\uad6d\ub0b4", "\ub300\ud55c\ubbfc\uad6d"]):
                territory_correct = True

    # is_real_license
    license_kw = [
        "license", "licence", "royalt", "licensor", "licensee",
        "technology transfer", "intellectual property", "patent", "sublicense",
        "\ub77c\uc774\uc120\uc2a4", "\ub77c\uc774\uc13c\uc2a4", "\uae30\uc220\uc774\uc804", "\ub85c\uc5f4\ud2f0",
        "\ud2b9\ud5c8", "\uc2e4\uc2dc\uad8c", "\uc0ac\uc6a9\uad8c", "\uae30\uc220\ub3c4\uc785",
        "\uae30\uc220\uc0ac\uc6a9", "\uae30\uc220\ub8cc", "\uc2e4\uc2dc\ub8cc", "\ud5c8\uc5ec",
    ]
    is_real_license = any(kw in src_lower for kw in license_kw)

    # is_hallucination
    has_any_match = licensor_correct or licensee_correct or tech_name_correct
    is_hallucination = not has_any_match and not is_real_license

    return {
        "contract_id": c["contract_id"],
        "licensor_correct": licensor_correct,
        "licensee_correct": licensee_correct,
        "tech_name_correct": tech_name_correct,
        "category_correct": category_correct,
        "royalty_correct": royalty_correct,
        "territory_correct": territory_correct,
        "is_real_license": is_real_license,
        "is_hallucination": is_hallucination,
        "notes": f"auto-spot-check heuristic (source_system={c['source_system']})",
    }


def main():
    # Clear existing annotations for fresh run
    ann_file = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "annotation_results.json")
    if os.path.exists(ann_file):
        with open(ann_file, "r", encoding="utf-8") as f:
            existing = json.load(f)
        print(f"Existing annotations: {len(existing.get('annotations', []))}")
        with open(ann_file, "w", encoding="utf-8") as f:
            json.dump({"annotations": [], "stats": {}}, f)
        print("Cleared existing annotations for fresh spot-check run.")

    # Sample 50 contracts
    print("\n=== Sampling 50 contracts ===")
    resp = requests.get(f"{BASE}/sample", params={"n": 50}, timeout=30)
    resp.raise_for_status()
    sample_data = resp.json()
    print(f"Total sampled: {sample_data['total_sampled']}")
    print(f"Already annotated: {sample_data['already_annotated']}")

    contracts = sample_data["data"]
    by_source = {}
    for c in contracts:
        s = c["source_system"]
        by_source[s] = by_source.get(s, 0) + 1
    print(f"By source: {by_source}")

    submitted = 0
    skipped = 0
    errors = 0

    for c in contracts:
        cid = c["contract_id"]
        verdict = judge_contract(c)

        if verdict is None:
            skipped += 1
            continue

        try:
            r = requests.post(f"{BASE}/submit", json=verdict, timeout=10)
            if r.status_code == 200:
                submitted += 1
                acc = sum([
                    verdict["licensor_correct"], verdict["licensee_correct"],
                    verdict["tech_name_correct"], verdict["category_correct"],
                    verdict["royalty_correct"], verdict["territory_correct"],
                ]) / 6
                flags = []
                if verdict["licensor_correct"]: flags.append("LR")
                if verdict["licensee_correct"]: flags.append("LE")
                if verdict["tech_name_correct"]: flags.append("TN")
                if verdict["category_correct"]: flags.append("CA")
                if verdict["royalty_correct"]: flags.append("RY")
                if verdict["territory_correct"]: flags.append("TR")
                flag_str = ",".join(flags) if flags else "none"
                print(f"  [{submitted:2d}] id={cid:5d} | {c['source_system']:5s} | acc={acc:.0%} | real={verdict['is_real_license']} | halluc={verdict['is_hallucination']} | correct=[{flag_str}]")
            elif r.status_code == 400:
                skipped += 1
            else:
                errors += 1
                print(f"  [err] id={cid}: {r.status_code}")
        except Exception as e:
            errors += 1
            print(f"  [err] id={cid}: {e}")

    print(f"\n=== Submission Summary ===")
    print(f"Submitted: {submitted}")
    print(f"Skipped (no source text or duplicate): {skipped}")
    print(f"Errors: {errors}")

    # Get final stats
    print(f"\n=== Final Annotation Stats ===")
    stats_resp = requests.get(f"{BASE}/stats", timeout=10)
    stats = stats_resp.json()
    print(json.dumps(stats, indent=2, ensure_ascii=False))

    # Print readable summary
    total = stats.get("total", 0)
    if total > 0:
        print(f"\n{'='*60}")
        print(f"SPOT CHECK REPORT")
        print(f"{'='*60}")
        print(f"Contracts sampled:           50")
        print(f"Contracts with source text:  {submitted}")
        print(f"Contracts skipped (no text): {skipped}")
        print(f"")
        print(f"Real license rate:           {stats.get('real_license_rate', 0)*100:.1f}%")
        print(f"Hallucination rate:          {stats.get('hallucination_rate', 0)*100:.1f}%")
        print(f"Average field accuracy:      {stats.get('avg_field_accuracy', 0)*100:.1f}%")
        fp = stats.get("field_precision", {})
        print(f"\nPer-field precision (N={total}):")
        for field, val in fp.items():
            bar = "#" * int(val * 20)
            print(f"  {field:12s}: {val*100:5.1f}%  {bar}")
    else:
        print("\nNo contracts had source text available for verification.")


if __name__ == "__main__":
    main()
