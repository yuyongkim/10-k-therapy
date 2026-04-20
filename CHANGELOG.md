# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres loosely to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- `.github/workflows/ci.yml` — GitHub Actions CI (Next.js lint/typecheck/build + pytest)
- `next-finance-dashboard/.env.example` — frontend env template
- `CONTRIBUTING.md`, `SECURITY.md`

### Fixed
- `.gitignore`: anchor `/src/` to root so `next-finance-dashboard/src/` isn't silently ignored
- `ui.tsx`, `assistant/page.tsx`: split `border` shorthand to silence React's "conflicting property" warning
- `app/page.tsx`: move `new Date().toLocaleString("ko-KR")` out of initial render into `useEffect` to fix hydration mismatch
- `backend/main.py`: add `http://localhost:3400` to CORS `allow_origins` (default dev port)

## [0.1.0] — 2026-04-20

### Added
- Initial public release as `10-k-therapy`.
- Backend: FastAPI with `contracts`, `stats`, `comparison`, `assistant`, `dart`, `annotation` routers.
- Frontend: Next.js 16 + React 19 Courthouse Archive design system.
  - 4 dashboard variations (Evidence Ledger · Comparables Grid · Split Provenance · Assistant-first).
  - Source Serif 4 + Inter + JetBrains Mono.
  - Oxblood accent (configurable hue) + paper/ink OKLCH tokens.
  - Provenance-first primitives: `SourceChip` (SEC accession_number / DART rcept_no).
  - Tweaks panel (accent · density · variation), keyboard 1–4 cycle.
- Data pipeline: SEC EDGAR crawler + DART orchestrator + unified schema parser.
- Litigation: CourtListener royalty verdict parsing.
- Valuation: DCF + comparable-based technology valuation engine.
- Analysis: SQLite DB + schema_quality report.
- Annotation: paper-quality validation queue UI.

### Data scale at release
- 38,114 raw extractions → 19,054 clean agreements
- 2,186 companies
- 1,546 royalty observations
- 79.3% real-license rate (LLM-as-judge)
