#!/usr/bin/env python3
"""Reinitialize Git history safely for a reorganized project."""

from __future__ import annotations

import argparse
import datetime as dt
import shutil
import subprocess
from pathlib import Path


DEFAULT_GITIGNORE = """# Python
__pycache__/
*.py[cod]
*.so
.venv/
venv/

# Node.js
node_modules/
.next/
dist/
build/

# Environment
.env
.env.*
secrets.json

# Data
*.db
*.sqlite
*.sqlite3
data/*.csv
data/*.xlsx
data/*.parquet
data/*.json
!data/README.md
!data/.gitkeep

# IDE
.vscode/
.cursor/
.idea/

# OS
.DS_Store
Thumbs.db

# Logs and backups
*.log
*.bak
*.backup
*_old.*
"""


def run(cmd: list[str], cwd: Path) -> None:
    result = subprocess.run(cmd, cwd=str(cwd), capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"Command failed: {' '.join(cmd)}\n{result.stderr.strip()}")


def ensure_git_available() -> None:
    if shutil.which("git") is None:
        raise SystemExit("git is not installed or not available in PATH.")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Safe Git reinitialization")
    parser.add_argument("--project-path", required=True, help="Project root directory")
    parser.add_argument("--commit", action="store_true", help="Create initial commit")
    parser.add_argument("--message", default="feat: Initial commit after project reorganization", help="Commit message")
    parser.add_argument("--branch", default="main", help="Default branch name")
    parser.add_argument("--no-backup", action="store_true", help="Do not backup existing .git directory")
    return parser.parse_args()


def main() -> None:
    ensure_git_available()
    args = parse_args()
    project = Path(args.project_path).resolve()
    if not project.exists() or not project.is_dir():
        raise SystemExit(f"Invalid --project-path: {project}")

    git_dir = project / ".git"
    if git_dir.exists():
        if args.no_backup:
            shutil.rmtree(git_dir)
        else:
            backup = project / f".git_backup_{dt.datetime.now().strftime('%Y%m%d_%H%M%S')}"
            git_dir.rename(backup)
            print(f"git_backup={backup}")

    gitignore = project / ".gitignore"
    if not gitignore.exists():
        gitignore.write_text(DEFAULT_GITIGNORE, encoding="utf-8")
        print("generated_gitignore=true")

    run(["git", "init"], cwd=project)
    run(["git", "branch", "-M", args.branch], cwd=project)

    if args.commit:
        run(["git", "add", "."], cwd=project)
        run(["git", "commit", "-m", args.message], cwd=project)
        print("initial_commit=true")
    else:
        print("initial_commit=false")

    print(f"project={project}")
    print("status=ok")


if __name__ == "__main__":
    main()

