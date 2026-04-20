#!/usr/bin/env python3
"""Inventory and classify project directories for cleanup prioritization."""

from __future__ import annotations

import argparse
import json
import os
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Dict, Iterable, List, Tuple


EXCLUDE_DIRS = {
    ".git",
    ".venv",
    "venv",
    "node_modules",
    "__pycache__",
    ".next",
    "dist",
    "build",
}

DATA_EXTENSIONS = {".db", ".sqlite", ".sqlite3", ".csv", ".xlsx", ".parquet", ".json"}
PY_EXTENSIONS = {".py"}
JS_EXTENSIONS = {".js", ".jsx", ".ts", ".tsx"}


def iter_project_files(project_path: Path) -> Iterable[Path]:
    for root, dirs, files in os.walk(project_path):
        dirs[:] = [d for d in dirs if d not in EXCLUDE_DIRS]
        root_path = Path(root)
        for name in files:
            yield root_path / name


def detect_stack(project_path: Path, suffixes: set[str]) -> Tuple[List[str], List[str]]:
    languages: List[str] = []
    frameworks: List[str] = []

    if suffixes.intersection(PY_EXTENSIONS):
        languages.append("Python")
        requirements = project_path / "requirements.txt"
        if requirements.exists():
            frameworks.append("Python-Package")
            content = requirements.read_text(encoding="utf-8", errors="ignore").lower()
            if "fastapi" in content:
                frameworks.append("FastAPI")
            if "flask" in content:
                frameworks.append("Flask")
            if "streamlit" in content:
                frameworks.append("Streamlit")

    if suffixes.intersection(JS_EXTENSIONS):
        languages.append("JavaScript/TypeScript")
        package_json = project_path / "package.json"
        if package_json.exists():
            frameworks.append("Node.js")
            try:
                pkg = json.loads(package_json.read_text(encoding="utf-8"))
                deps = {**pkg.get("dependencies", {}), **pkg.get("devDependencies", {})}
                if "next" in deps:
                    frameworks.append("Next.js")
                elif "react" in deps:
                    frameworks.append("React")
            except json.JSONDecodeError:
                pass

    return languages, frameworks


def guess_status(project_name: str, project_path: Path) -> str:
    marker_files = ["README.md", "AGENTS.md", "package.json", "requirements.txt", "pyproject.toml"]
    name = project_name.lower()
    if any((project_path / m).exists() for m in marker_files):
        return "active"
    if any(k in name for k in ["backup", "archive", "old", "deprecated"]):
        return "archived"
    return "experimental"


def suggest_track(project_name: str, path_text: str) -> str:
    text = f"{project_name} {path_text}".lower()
    if any(k in text for k in ["chem", "msds", "drug", "patent", "license"]):
        return "Track 3 (B2B SaaS)"
    if any(k in text for k in ["economic", "indicator", "macro", "finance"]):
        return "Track 1 (Data Intelligence)"
    if any(k in text for k in ["legal", "regulation", "compliance", "law"]):
        return "Track 2 (Legal Automation)"
    if any(k in text for k in ["indie", "movie", "pet", "art", "lifestyle"]):
        return "Track 4 (B2C/Lifestyle)"
    return "Unknown"


def analyze_project(project_path: Path) -> Dict[str, object]:
    total_size = 0
    file_count = 0
    suffixes: set[str] = set()

    for file_path in iter_project_files(project_path):
        file_count += 1
        suffixes.add(file_path.suffix.lower())
        try:
            total_size += file_path.stat().st_size
        except OSError:
            continue

    languages, frameworks = detect_stack(project_path, suffixes)
    has_data = any(ext in DATA_EXTENSIONS for ext in suffixes)
    status = guess_status(project_path.name, project_path)
    track = suggest_track(project_path.name, str(project_path))

    return {
        "name": project_path.name,
        "path": str(project_path),
        "size_mb": round(total_size / 1024 / 1024, 2),
        "file_count": file_count,
        "languages": languages,
        "frameworks": frameworks,
        "has_data": has_data,
        "status_guess": status,
        "track_suggestion": track,
    }


def analyze_root(root_path: Path) -> Dict[str, Dict[str, object]]:
    projects: Dict[str, Dict[str, object]] = {}
    for item in sorted(root_path.iterdir()):
        if not item.is_dir() or item.name.startswith("."):
            continue
        projects[item.name] = analyze_project(item)
    return projects


def render_markdown(projects: Dict[str, Dict[str, object]]) -> str:
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    active_count = sum(1 for p in projects.values() if p["status_guess"] == "active")
    experimental_count = sum(1 for p in projects.values() if p["status_guess"] == "experimental")
    archived_count = sum(1 for p in projects.values() if p["status_guess"] == "archived")
    total_size = sum(float(p["size_mb"]) for p in projects.values())

    lines: List[str] = []
    lines.append("# Project Inventory Report")
    lines.append(f"Generated: {now}")
    lines.append("")
    lines.append("## Summary")
    lines.append(f"- Total projects: {len(projects)}")
    lines.append(f"- Active: {active_count}")
    lines.append(f"- Experimental: {experimental_count}")
    lines.append(f"- Archived candidates: {archived_count}")
    lines.append(f"- Total scanned size (MB): {total_size:.2f}")
    lines.append("")
    lines.append("## Projects")
    lines.append("")
    lines.append("| Project | Size (MB) | Files | Languages | Status | Suggested Track |")
    lines.append("|---|---:|---:|---|---|---|")

    sorted_items = sorted(projects.items(), key=lambda x: float(x[1]["size_mb"]), reverse=True)
    for name, info in sorted_items:
        languages = ", ".join(info["languages"]) if info["languages"] else "Unknown"
        lines.append(
            f"| {name} | {info['size_mb']:.2f} | {info['file_count']} | "
            f"{languages} | {info['status_guess']} | {info['track_suggestion']} |"
        )

    lines.append("")
    lines.append("## Prioritization Hints")
    high_priority = [
        info for _, info in sorted_items if info["status_guess"] == "active" and float(info["size_mb"]) >= 10
    ]
    if high_priority:
        lines.append("- High priority cleanup candidates:")
        for info in high_priority[:10]:
            lines.append(
                f"  - {info['name']} ({info['size_mb']:.2f} MB, {info['track_suggestion']})"
            )
    else:
        lines.append("- No high-priority candidates by current heuristic.")

    archived = [info for _, info in sorted_items if info["status_guess"] != "active" and float(info["size_mb"]) <= 5]
    if archived:
        lines.append("- Archive-review candidates:")
        for info in archived[:20]:
            lines.append(f"  - {info['name']} ({info['size_mb']:.2f} MB)")
    else:
        lines.append("- No archive-review candidates by current heuristic.")

    track_counter = Counter(str(p["track_suggestion"]) for p in projects.values())
    lines.append("")
    lines.append("## Track Distribution")
    for track, count in track_counter.most_common():
        lines.append(f"- {track}: {count}")

    return "\n".join(lines) + "\n"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Analyze project directories and produce inventory reports")
    parser.add_argument("--root", required=True, help="Root directory containing project folders")
    parser.add_argument("--output-json", default="project_inventory.json", help="Output JSON path")
    parser.add_argument("--output-md", default="project_inventory_report.md", help="Output markdown path")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    root = Path(args.root).resolve()
    if not root.exists() or not root.is_dir():
        raise SystemExit(f"Invalid --root path: {root}")

    projects = analyze_root(root)
    out_json = Path(args.output_json).resolve()
    out_md = Path(args.output_md).resolve()
    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_md.parent.mkdir(parents=True, exist_ok=True)

    out_json.write_text(json.dumps(projects, indent=2, ensure_ascii=False), encoding="utf-8")
    out_md.write_text(render_markdown(projects), encoding="utf-8")

    print(f"projects={len(projects)}")
    print(f"json={out_json}")
    print(f"markdown={out_md}")


if __name__ == "__main__":
    main()

