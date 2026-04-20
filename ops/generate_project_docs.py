#!/usr/bin/env python3
"""Generate README.md and AGENTS.md from current project state."""

from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path
from typing import Dict, List


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="ignore")


def detect_tech_stack(project_path: Path) -> Dict[str, List[str]]:
    stack = {
        "languages": [],
        "frameworks": [],
        "databases": [],
        "apis": [],
    }

    if (project_path / "requirements.txt").exists():
        stack["languages"].append("Python 3.10+")
        req = read_text(project_path / "requirements.txt").lower()
        if "fastapi" in req:
            stack["frameworks"].append("FastAPI")
        if "streamlit" in req:
            stack["frameworks"].append("Streamlit")
        if "flask" in req:
            stack["frameworks"].append("Flask")
        if "pandas" in req:
            stack["frameworks"].append("Pandas")

    package_json = project_path / "package.json"
    if package_json.exists():
        stack["languages"].append("TypeScript/JavaScript")
        try:
            pkg = json.loads(read_text(package_json))
            deps = {**pkg.get("dependencies", {}), **pkg.get("devDependencies", {})}
            if "next" in deps:
                stack["frameworks"].append("Next.js")
            if "react" in deps:
                stack["frameworks"].append("React")
            if "tailwindcss" in deps:
                stack["frameworks"].append("Tailwind CSS")
        except json.JSONDecodeError:
            pass

    db_files = list(project_path.rglob("*.db")) + list(project_path.rglob("*.sqlite")) + list(project_path.rglob("*.sqlite3"))
    if db_files:
        stack["databases"].append("SQLite")

    env_paths = [project_path / ".env.example", project_path / ".env"]
    env_text = ""
    for env_path in env_paths:
        if env_path.exists():
            env_text += "\n" + read_text(env_path).upper()
    api_hints = {
        "OPENAI": "OpenAI API",
        "GEMINI": "Gemini API",
        "DART": "OpenDART API",
        "FRED": "FRED API",
        "TMDB": "TMDB API",
        "KIWOOM": "Kiwoom API",
    }
    for key, label in api_hints.items():
        if key in env_text:
            stack["apis"].append(label)

    stack["languages"] = sorted(set(stack["languages"]))
    stack["frameworks"] = sorted(set(stack["frameworks"]))
    stack["databases"] = sorted(set(stack["databases"]))
    stack["apis"] = sorted(set(stack["apis"]))
    return stack


def infer_project_type(stack: Dict[str, List[str]]) -> str:
    frameworks = " ".join(stack["frameworks"]).lower()
    if "streamlit" in frameworks:
        return "Data Dashboard"
    if "fastapi" in frameworks or "flask" in frameworks:
        return "API Platform"
    if "next.js" in frameworks or "react" in frameworks:
        return "Web Application"
    return "Software Project"


def generate_readme(project_name: str, stack: Dict[str, List[str]], year: str) -> str:
    project_slug = project_name.lower().replace(" ", "-")
    project_type = infer_project_type(stack)

    languages = ", ".join(stack["languages"]) if stack["languages"] else "TBD"
    frameworks = ", ".join(stack["frameworks"]) if stack["frameworks"] else "TBD"
    databases = ", ".join(stack["databases"]) if stack["databases"] else "N/A"
    apis = ", ".join(stack["apis"]) if stack["apis"] else "N/A"

    return f"""# {project_name}

> {project_type} - standardized for AI collaboration

## Overview
- Focus: core product delivery with maintainable structure
- Collaboration mode: Codex + Claude + Cursor compatible
- Last updated: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}

## Key Features
- Structured source layout (`src/backend`, `src/frontend`)
- Isolated data zone (`data/raw`, `data/processed`)
- Explicit AI collaboration context (`AGENTS.md`)
- Repeatable automation scripts (`scripts/` and `ops/`)

## Tech Stack
| Category | Value |
|---|---|
| Languages | {languages} |
| Frameworks | {frameworks} |
| Databases | {databases} |
| External APIs | {apis} |

## Quick Start
```bash
# 1) Setup env
cp .env.example .env

# 2) Python deps (if used)
pip install -r requirements.txt

# 3) Frontend deps (if used)
npm install

# 4) Run app (replace with your entrypoint)
python src/backend/main.py
```

## Project Structure
```text
{project_slug}/
  README.md
  AGENTS.md
  src/
    backend/
    frontend/
  data/
    raw/
    processed/
  scripts/
  docs/
  tests/
  archive/
```

## Environment Variables
Create `.env` and set required values:
```env
API_KEY=replace_me
DEBUG=false
```

## AI Collaboration Rules
1. Read `AGENTS.md` before making changes.
2. Keep data assets in `data/` and out of Git.
3. Prefer incremental refactors over full rewrites.

## License
Internal / private use unless otherwise specified.

---
Maintainer: Kim Yuyong ({year})
"""


def generate_agents(project_name: str, track: str) -> str:
    return f"""# AGENTS.md - {project_name}

## Project Context
- Project: {project_name}
- Track: {track}
- Goal: reduce AI collaboration debt and keep delivery velocity

## Collaboration Roles
- `@code-reviewer`: bug risk, regression, test coverage
- `@ai-architect`: structure, boundaries, long-term maintainability
- `@data-engineer`: ingestion/parsing/quality pipelines
- `@ux-designer`: practical UX and operator workflow

## Hard Constraints
1. Never delete or rewrite large data assets without explicit backup.
2. Keep secrets out of Git (`.env`, keys, credentials).
3. Preserve backward compatibility for existing APIs by default.
4. Use dry-run first for destructive operations.

## Repository Map
- Backend: `src/backend/`
- Frontend: `src/frontend/`
- Data: `data/raw/`, `data/processed/`
- Docs: `docs/`
- Tests: `tests/`
- Archive: `archive/`

## Workflow
1. Analyze current behavior.
2. Apply smallest safe change.
3. Run tests/verification.
4. Update docs if behavior or structure changed.

## Forbidden Actions
- Mass file moves without plan output.
- Secret rotation inside code.
- Direct mutation of production DB dumps.
- Force-push or history rewrite without explicit approval.

## Performance Targets
- API response under 2 seconds for common endpoints.
- Batch jobs should log progress and failures.
- Keep memory profile bounded for large file processing.
"""


def write_if_allowed(path: Path, content: str, force: bool) -> str:
    if path.exists() and not force:
        return f"skipped:{path}"
    if path.exists() and force:
        backup = path.with_suffix(path.suffix + ".bak")
        path.replace(backup)
    path.write_text(content, encoding="utf-8")
    return str(path)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate README.md and AGENTS.md from project state")
    parser.add_argument("--project-path", required=True, help="Project root path")
    parser.add_argument("--project-name", default=None, help="Display project name")
    parser.add_argument("--track", default="Track 3 (B2B SaaS)", help="Track label for AGENTS.md")
    parser.add_argument("--force", action="store_true", help="Overwrite without backing up existing files")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    project_path = Path(args.project_path).resolve()
    if not project_path.exists() or not project_path.is_dir():
        raise SystemExit(f"Invalid --project-path: {project_path}")

    project_name = args.project_name or project_path.name
    year = str(datetime.now().year)
    stack = detect_tech_stack(project_path)

    readme_content = generate_readme(project_name, stack, year)
    agents_content = generate_agents(project_name, args.track)
    readme_path = write_if_allowed(project_path / "README.md", readme_content, force=args.force)
    agents_path = write_if_allowed(project_path / "AGENTS.md", agents_content, force=args.force)

    print(f"README={readme_path}")
    print(f"AGENTS={agents_path}")


if __name__ == "__main__":
    main()
