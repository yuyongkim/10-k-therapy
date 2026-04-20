#!/usr/bin/env python3
"""Phase-1 bootstrap: run backup (dry-run optional) + inventory in one command."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from audit_projects import analyze_root, render_markdown
from backup_projects import default_backup_root, run_backup, DEFAULT_EXCLUDE_DIRS


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run phase-1 AI debt cleanup bootstrap")
    parser.add_argument("--source", required=True, help="Workspace root to scan/back up")
    parser.add_argument("--output-dir", default="ops/outputs", help="Where to write reports")
    parser.add_argument("--backup-root", default=None, help="Backup root (default OS-specific)")
    parser.add_argument("--backup-dry-run", action="store_true", help="Do not copy files")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    source = Path(args.source).resolve()
    output_dir = Path(args.output_dir).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    backup_root = Path(args.backup_root).resolve() if args.backup_root else default_backup_root().resolve()
    backup_path, backup_summary = run_backup(
        source=source,
        backup_root=backup_root,
        exclude_dirs=set(DEFAULT_EXCLUDE_DIRS),
        include_full=True,
        include_critical=True,
        include_databases=True,
        dry_run=args.backup_dry_run,
    )
    backup_summary_path = output_dir / "backup_summary.json"
    backup_summary_path.write_text(json.dumps(backup_summary, indent=2, ensure_ascii=False), encoding="utf-8")

    projects = analyze_root(source)
    inventory_json = output_dir / "project_inventory.json"
    inventory_md = output_dir / "project_inventory_report.md"
    inventory_json.write_text(json.dumps(projects, indent=2, ensure_ascii=False), encoding="utf-8")
    inventory_md.write_text(render_markdown(projects), encoding="utf-8")

    print(f"backup_path={backup_path}")
    print(f"backup_summary={backup_summary_path}")
    print(f"inventory_json={inventory_json}")
    print(f"inventory_report={inventory_md}")


if __name__ == "__main__":
    main()

