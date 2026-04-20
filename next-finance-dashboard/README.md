# Next Finance Dashboard

Next.js frontend for SEC license analytics, styled as a financial dashboard.

## Run locally

```bash
npm install
npm run sync:data
npm run dev -- --port=3007
```

Open `http://localhost:3007`.

## Pages

- `/`: SEC Dashboard
- `/sec/prototype`: SEC Prototype Lab
- `/dart`: DART Prototype
- `/dart/license`: DART License Prototype

## Data source

API routes:
- `src/app/api/licenses/route.ts`
- `src/app/api/dart/route.ts`

Server reads `license_summary.json` from:
1. `LICENSE_SUMMARY_PATH` env var (if set)
2. `next-finance-dashboard/license_summary.json`
3. `../license_summary.json` (parent folder fallback)

## Build check

```bash
npm run deploy:check
```

This command validates:
- data sync (`license_summary.json` copied into Next project root)
- lint
- production build

## Deploy

### Option A: Vercel (recommended for Next.js)

1. Push this folder to GitHub (including `license_summary.json`, ~29MB).
2. Import repo in Vercel.
3. If this is a monorepo, set **Root Directory** to `next-finance-dashboard`.
4. Build command: `npm run build` (prebuild auto-runs data sync).
5. Deploy.

If you do not commit `license_summary.json` in this folder, set `LICENSE_SUMMARY_PATH` to a valid path available at build/runtime.

### Option B: Docker / Self-hosted Node

1. Build with `npm run build`
2. Start with `npm run start`
3. Ensure `license_summary.json` is present at one of the supported paths.
