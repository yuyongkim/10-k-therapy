#!/usr/bin/env python3
"""Create safe multi-layer backups for mixed AI-collaboration projects."""

from __future__ import annotations

import argparse
import datetime as dt
import fnmatch
import json
import os
import shutil
from pathlib import Path
from typing import Dict, Iterable, List, Tuple


DEFAULT_EXCLUDE_DIRS = {
    ".git",
    ".venv",
    "venv",
    "node_modules",
    "__pycache__",
    "dist",
    "build",
    ".next",
}

CRITICAL_PATTERNS = [
    "*.db",
    "*.sqlite",
    "*.sqlite3",
    "*.csv",
    "*.xlsx",
    "*.parquet",
    "*.py",
    "*.ts",
    "*.tsx",
    "*.js",
    "*.jsx",
    "*.json",
    "*.yaml",
    "*.yml",
    ".env",
    ".env.*",
    "requirements.txt",
    "package.json",
    "README.md",
    "AGENTS.md",
]


def default_backup_root() -> Path:
    if os.name == "nt":
        return Path("D:/Backups")
    return Path("~/Backups").expanduser()


def should_skip_path(path: Path, exclude_dirs: set[str]) -> bool:
    return any(part in exclude_dirs for part in path.parts)


def file_size(path: Path) -> int:
    try:
        return path.stat().st_size
    except OSError:
        return 0


def iter_files(source: Path, exclude_dirs: set[str]) -> Iterable[Path]:
    for root, dirs, files in os.walk(source):
        root_path = Path(root)
        dirs[:] = [d for d in dirs if d not in exclude_dirs]
        for name in files:
            file_path = root_path / name
            if should_skip_path(file_path.relative_to(source), exclude_dirs):
                continue
            yield file_path


def copy_file(source: Path, dest: Path, dry_run: bool) -> None:
    if dry_run:
        return
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, dest)


def copy_full_tree(source: Path, target: Path, exclude_dirs: set[str], dry_run: bool) -> None:
    if dry_run:
        return

    def ignore_func(_: str, names: List[str]) -> set[str]:
        ignored = set()
        for name in names:
            if name in exclude_dirs:
                ignored.add(name)
        return ignored

    shutil.copytree(source, target, ignore=ignore_func)


def is_critical(path: Path) -> bool:
    name = path.name
    for pattern in CRITICAL_PATTERNS:
        if fnmatch.fnmatch(name, pattern):
            return True
    return False


def build_db_name(file_path: Path) -> str:
    stem = "_".join(file_path.parts[-3:]).replace(":", "")
    return stem.replace("\\", "_").replace("/", "_")


def run_backup(
    source: Path,
    backup_root: Path,
    exclude_dirs: set[str],
    include_full: bool,
    include_critical: bool,
    include_databases: bool,
    dry_run: bool,
) -> Tuple[Path, Dict[str, object]]:
    timestamp = dt.datetime.now().strftime("%Y%m%d_%H%M%S")
    run_root = backup_root / f"Projects_{timestamp}"

    summary: Dict[str, object] = {
        "source": str(source),
        "backup_root": str(run_root),
        "created_at": dt.datetime.now().isoformat(),
        "dry_run": dry_run,
        "layers": {
            "full_backup": {"enabled": include_full, "file_count": 0, "size_bytes": 0},
            "critical_assets": {"enabled": include_critical, "file_count": 0, "size_bytes": 0},
            "databases": {"enabled": include_databases, "file_count": 0, "size_bytes": 0},
        },
    }

    if not dry_run:
        run_root.mkdir(parents=True, exist_ok=True)

    if include_full:
        full_target = run_root / "FULL_BACKUP"
        copy_full_tree(source, full_target, exclude_dirs, dry_run)
        count = 0
        size = 0
        for file_path in iter_files(source, exclude_dirs):
            count += 1
            size += file_size(file_path)
        summary["layers"]["full_backup"]["file_count"] = count
        summary["layers"]["full_backup"]["size_bytes"] = size

    critical_target = run_root / "CRITICAL_ASSETS"
    db_target = run_root / "DATABASES"
    if not dry_run:
        if include_critical:
            critical_target.mkdir(parents=True, exist_ok=True)
        if include_databases:
            db_target.mkdir(parents=True, exist_ok=True)

    for file_path in iter_files(source, exclude_dirs):
        rel = file_path.relative_to(source)
        size = file_size(file_path)

        if include_critical and is_critical(file_path):
            copy_file(file_path, critical_target / rel, dry_run)
            summary["layers"]["critical_assets"]["file_count"] += 1
            summary["layers"]["critical_assets"]["size_bytes"] += size

        if include_databases and file_path.suffix.lower() in {".db", ".sqlite", ".sqlite3"}:
            db_name = build_db_name(rel)
            target = db_target / db_name
            copy_file(file_path, target, dry_run)
            summary["layers"]["databases"]["file_count"] += 1
            summary["layers"]["databases"]["size_bytes"] += size

    if not dry_run:
        manifest_path = run_root / "backup_manifest.json"
        manifest_path.write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")
    return run_root, summary


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Project multi-layer backup utility")
    parser.add_argument("--source", required=True, help="Project root directory to back up")
    parser.add_argument(
        "--backup-root",
        default=str(default_backup_root()),
        help="Root directory where timestamped backup directory will be created",
    )
    parser.add_argument("--skip-full", action="store_true", help="Skip full backup layer")
    parser.add_argument("--skip-critical", action="store_true", help="Skip critical-assets backup layer")
    parser.add_argument("--skip-databases", action="store_true", help="Skip DB-only backup layer")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show summary without copying files",
    )
    parser.add_argument(
        "--extra-exclude-dir",
        action="append",
        default=[],
        help="Directory name to exclude (can be repeated)",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    source = Path(args.source).resolve()
    if not source.exists() or not source.is_dir():
        raise SystemExit(f"Invalid --source path: {source}")

    backup_root = Path(args.backup_root).expanduser().resolve()
    exclude_dirs = set(DEFAULT_EXCLUDE_DIRS)
    exclude_dirs.update(args.extra_exclude_dir)

    run_root, summary = run_backup(
        source=source,
        backup_root=backup_root,
        exclude_dirs=exclude_dirs,
        include_full=not args.skip_full,
        include_critical=not args.skip_critical,
        include_databases=not args.skip_databases,
        dry_run=args.dry_run,
    )

    print(json.dumps(summary, indent=2, ensure_ascii=False))
    if not args.dry_run:
        print(f"backup_path={run_root}")


if __name__ == "__main__":
    main()

