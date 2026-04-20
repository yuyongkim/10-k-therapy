# Cleanup Runbook (AI Collaboration Debt)

## Phase 1: Safety First
1. Backup dry-run
```powershell
python ops\ai_cleanup\phase1_bootstrap.py `
  --source F:\SEC\License `
  --output-dir F:\SEC\ops\outputs `
  --backup-dry-run
```
2. Review:
- `ops/outputs/backup_summary.json`
- `ops/outputs/project_inventory_report.md`

3. Real backup (after validation)
```powershell
python ops\ai_cleanup\backup_projects.py `
  --source F:\SEC\License `
  --backup-root D:\Backups
```

## Phase 2: Per-Project Reorganization
1. Create plan (dry-run):
```powershell
python ops\ai_cleanup\reorganize_project.py `
  --project-path F:\SEC\License\sec-license-extraction `
  --plan-json F:\SEC\ops\outputs\sec_reorg_plan.json
```
2. Manually review `sec_reorg_plan.json`.
3. Apply only when reviewed:
```powershell
python ops\ai_cleanup\reorganize_project.py `
  --project-path F:\SEC\License\sec-license-extraction `
  --plan-json F:\SEC\ops\outputs\sec_reorg_plan_apply.json `
  --apply
```

## Phase 3: Documentation + Git Baseline
1. Generate docs (safe default: skip existing files):
```powershell
python ops\ai_cleanup\generate_project_docs.py `
  --project-path F:\SEC\License\sec-license-extraction `
  --project-name "SEC License Extraction" `
  --track "Track 3 (B2B SaaS)"
```

2. Reinitialize Git (safe, no commit):
```powershell
python ops\ai_cleanup\git_reinit.py `
  --project-path F:\SEC\License\sec-license-extraction
```

3. Create initial commit when ready:
```powershell
python ops\ai_cleanup\git_reinit.py `
  --project-path F:\SEC\License\sec-license-extraction `
  --commit
```

## Non-Developer Checkpoints
- Backup artifacts exist and sizes are non-zero.
- Inventory report lists all expected projects.
- Reorg plan reviewed before apply.
- README/AGENTS exist and reflect current architecture.
- `git status` is clean before first production push.

