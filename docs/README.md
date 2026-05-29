# Documentation Structure

This directory stores project documentation by purpose.

## Layout
- `releases/`: version plans, release notes, and release checklists.
- `internal/`: team internal standards and process conventions.

## Recommended Internal Guides
- `../ARCHITECTURE_QUICK_READ.md`: root-level architecture quick-read playbook for new collaborators.
- `internal/DASHBOARD_METRICS_ADOPTION_GUIDE.md`: non-invasive dashboard metrics adoption playbook.
- `internal/GOVERNANCE_METRICS_CONTRACT.md`: governance event contract and KPI definition.
- `internal/GITHUB_WORKFLOW_METRICS_GUIDE.md`: GitHub Actions workflow standard and metrics push guide.
- `internal/WORKFLOW_UNIVERSAL_GUIDE.md`: concise cross-project workflow baseline.

## Reusable Templates
- `.github/PULL_REQUEST_TEMPLATE.md`: one-page PR evidence template.
- `internal/templates/ci-metrics-template.yml`: portable CI + metrics artifact workflow template.

## Local Workflow Scripts
- `scripts/workflow.py`: unified local workflow check entry.
- `scripts/workflow.bat`: Windows wrapper.
- `scripts/workflow.sh`: Linux/macOS wrapper.

## Conventions
- Keep public and shareable documents in tracked files.
- Put sensitive notes and temporary drafts under `internal/private/` (gitignored).
- Use file names that are easy to search and sort, such as:
  - `RELEASE_PLAN_0.2.0.md`
  - `RELEASE_NOTES_0.2.0.md`
