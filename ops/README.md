# AI Debt Cleanup Toolkit

Scripts in `ops/ai_cleanup/` standardize cleanup and documentation for mixed AI-collaboration projects.
Full execution checklist: `ops/ai_cleanup/CLEANUP_RUNBOOK.md`.

## Scripts
- `backup_projects.py`: 3-layer backup (`FULL_BACKUP`, `CRITICAL_ASSETS`, `DATABASES`)
- `audit_projects.py`: inventory JSON + markdown report
- `reorganize_project.py`: standard-structure reorganization (`dry-run` default)
- `generate_project_docs.py`: auto-generate `README.md` and `AGENTS.md`
- `git_reinit.py`: safe Git re-initialization
- `phase1_bootstrap.py`: run backup + inventory in one command

## Quick Commands

```powershell
# 1) Phase-1 bootstrap (safe: backup dry-run)
python ops\ai_cleanup\phase1_bootstrap.py `
  --source F:\SEC\License `
  --output-dir F:\SEC\ops\outputs `
  --backup-dry-run

# 2) Detailed inventory only
python ops\ai_cleanup\audit_projects.py `
  --root F:\SEC\License `
  --output-json F:\SEC\ops\outputs\project_inventory.json `
  --output-md F:\SEC\ops\outputs\project_inventory_report.md

# 3) Reorganization preview for one project
python ops\ai_cleanup\reorganize_project.py `
  --project-path F:\SEC\License\sec-license-extraction `
  --plan-json F:\SEC\ops\outputs\sec_reorg_plan.json

# 4) Generate README/AGENTS for a project
python ops\ai_cleanup\generate_project_docs.py `
  --project-path F:\SEC\License\sec-license-extraction `
  --project-name "SEC License Extraction" `
  --track "Track 3 (B2B SaaS)"
```

## Safety Defaults
- `reorganize_project.py`: no changes unless `--apply`.
- `phase1_bootstrap.py`: use `--backup-dry-run` to validate before heavy copy.
- `git_reinit.py`: existing `.git` is backed up by default.
