# Contributing to 10-k-therapy

Thanks for wanting to make SEC/DART disclosure reading less painful.

## Quick orientation

- **Backend:** FastAPI + SQLAlchemy. Code lives in `backend/`, extraction pipeline in `extractor/` · `crawler/` · `parser/`.
- **Frontend:** Next.js 16 + React 19. Code lives in `next-finance-dashboard/src/`.
- **Data:** stored locally, not in git. See `.gitignore` for what's excluded (`data/raw_filings/`, `data/dart/unified_schema/`, etc.)
- **Design system:** Courthouse Archive — see `DESIGN.md` and `next-finance-dashboard/src/app/globals.css`.

## Setup

```bash
# Backend
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\Activate.ps1
pip install -r requirements.txt
cp .env.example .env        # fill in your API keys
cp config_demo.yaml config.yaml

# Frontend
cd next-finance-dashboard
npm install
cp .env.example .env.local

# Run
uvicorn backend.main:app --reload --port 8000   # backend
npm run dev                                      # frontend (from next-finance-dashboard/)
```

## Before opening a PR

1. Run the full verification locally:
   ```bash
   # frontend
   cd next-finance-dashboard && npm run lint && npx tsc --noEmit && npm run build

   # backend
   pytest -q
   ```
2. Do NOT commit secrets, real `config.yaml`, paper drafts under `docs/paper_*.md`, or files under `data/raw_filings/`.
3. Keep commits atomic. One logical change per commit. Clean message format:
   `feat|fix|docs|chore|refactor|test|ci(scope): short imperative description`
4. For UI changes, match the Courthouse Archive design tokens in `theme.ts` and `globals.css`. Don't introduce gradients, neumorphism, or dark-mode-era tokens.

## What we love

- Regression tests for bugs you're fixing
- Clean separation between extraction, storage, and presentation
- Provenance preserved end-to-end (`accession_number` / `rcept_no` / `source_url`)
- Bilingual UX labels (EN primary, KR secondary)

## What we push back on

- Feature creep without a clear comparable/research use case
- Vendored large data
- Silent failure modes (especially in the LLM extraction path)
- UI that hides live vs fallback data state

## Questions

Open an issue with the `question` label, or a Discussion if the repo has them enabled.
