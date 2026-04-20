#!/usr/bin/env python3
"""Safely reorganize project files into a standard structure (dry-run first)."""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import List, Optional


STANDARD_DIRS = [
    "src/backend",
    "src/frontend",
    "data/raw",
    "data/processed",
    "scripts",
    "docs",
    "tests",
    "archive",
]

EXCLUDE_DIRS = {
    ".git",
    ".venv",
    "venv",
    "__pycache__",
    "node_modules",
    ".next",
    "dist",
    "build",
}

ROOT_KEEP = {
    "README.md",
    "AGENTS.md",
    "LICENSE",
    ".gitignore",
    ".env",
    ".env.example",
    "requirements.txt",
    "package.json",
    "package-lock.json",
    "pyproject.toml",
    "config.yaml",
    "config.yml",
    "config_demo.yaml",
    "config_demo.yml",
}


@dataclass
class MovePlan:
    source: str
    target: str
    action: str
    reason: str


def in_standard_tree(rel_path: Path) -> bool:
    text = rel_path.as_posix()
    return any(text.startswith(prefix) for prefix in STANDARD_DIRS)


def choose_bucket(rel_path: Path, move_data_files: bool) -> tuple[str, str]:
    name = rel_path.name
    ext = rel_path.suffix.lower()
    text = rel_path.as_posix().lower()
    parts_lower = [part.lower() for part in rel_path.parts]

    if name in ROOT_KEEP:
        return ".", "root_keep"
    if ext in {".yaml", ".yml", ".toml", ".ini"}:
        return ".", "config_file"
    if "data" in parts_lower:
        if move_data_files:
            return "data/raw", "data_file_relocated"
        return ".", "data_preserved"
    if re.search(r"(backup|old|temp|tmp)", text):
        return "archive", "backup_or_temp"
    if ext == ".py":
        return "src/backend", "python_source"
    if ext in {".ts", ".tsx", ".js", ".jsx", ".mjs", ".cjs"}:
        return "src/frontend", "frontend_source"
    if ext in {".html", ".css", ".scss"}:
        return "src/frontend", "frontend_asset"
    if ext in {".md", ".txt", ".pdf"}:
        return "docs", "documentation"
    if ext in {".db", ".sqlite", ".sqlite3", ".csv", ".xlsx", ".parquet", ".json"}:
        if move_data_files:
            return "data/raw", "data_file"
        return ".", "data_preserved"
    return "archive", "unclassified"


def relative_target(base: Path, rel_source: Path, bucket: str) -> Path:
    if bucket == ".":
        return base / rel_source.name
    parent_rel = rel_source.parent
    if str(parent_rel) in {".", ""}:
        return base / bucket / rel_source.name
    return base / bucket / parent_rel / rel_source.name


def dedupe_target(target: Path) -> Path:
    if not target.exists():
        return target
    stem = target.stem
    suffix = target.suffix
    counter = 1
    while True:
        candidate = target.parent / f"{stem}_duplicate_{counter}{suffix}"
        if not candidate.exists():
            return candidate
        counter += 1


def build_plan(project_path: Path, move_data_files: bool) -> List[MovePlan]:
    plan: List[MovePlan] = []
    for root, dirs, files in os.walk(project_path):
        dirs[:] = [d for d in dirs if d not in EXCLUDE_DIRS]
        root_path = Path(root)
        for name in files:
            source = root_path / name
            rel = source.relative_to(project_path)

            if in_standard_tree(rel):
                continue
            if any(part in EXCLUDE_DIRS for part in rel.parts):
                continue

            bucket, reason = choose_bucket(rel, move_data_files=move_data_files)
            if bucket == "." and rel.parent == Path("."):
                continue

            raw_target = relative_target(project_path, rel, bucket)
            target = dedupe_target(raw_target)
            action = "move" if bucket != "." else "keep"
            if action == "keep":
                continue
            plan.append(
                MovePlan(
                    source=str(rel.as_posix()),
                    target=str(target.relative_to(project_path).as_posix()),
                    action=action,
                    reason=reason,
                )
            )
    return plan


def execute_plan(project_path: Path, plan: List[MovePlan]) -> None:
    for item in plan:
        src = project_path / item.source
        dst = project_path / item.target
        if not src.exists():
            continue
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(src), str(dst))


def ensure_standard_dirs(project_path: Path) -> None:
    for rel in STANDARD_DIRS:
        (project_path / rel).mkdir(parents=True, exist_ok=True)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Reorganize project into standard structure")
    parser.add_argument("--project-path", required=True, help="Target project directory")
    parser.add_argument("--apply", action="store_true", help="Execute moves (default: dry-run)")
    parser.add_argument(
        "--move-data-files",
        action="store_true",
        help="Move data files to data/raw (default keeps data in place)",
    )
    parser.add_argument(
        "--plan-json",
        default="reorganization_plan.json",
        help="Where to write plan JSON",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    project_path = Path(args.project_path).resolve()
    if not project_path.exists() or not project_path.is_dir():
        raise SystemExit(f"Invalid --project-path: {project_path}")

    ensure_standard_dirs(project_path)
    plan = build_plan(project_path, move_data_files=args.move_data_files)
    plan_path = Path(args.plan_json).resolve()
    plan_path.parent.mkdir(parents=True, exist_ok=True)
    plan_path.write_text(
        json.dumps([asdict(item) for item in plan], indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    print(f"planned_moves={len(plan)}")
    print(f"plan_json={plan_path}")
    if args.apply:
        execute_plan(project_path, plan)
        print("applied=true")
    else:
        print("applied=false")


if __name__ == "__main__":
    main()
