# WORKFLOW

## Purpose
This file is the first-read execution contract for all collaborators (human or AI).

Goal:
- develop first, then consolidate and document
- keep delivery stable through mandatory checks
- keep process evidence and metrics auditable

## First-Read Order
1. `WORKFLOW.md` (this file)
2. `ARCHITECTURE_QUICK_READ.md`
3. `HANDOVER.md`
4. `README.md` or `README_ZH.md`

## Execution Principle
1. Start from a clear requirement and acceptance criteria.
2. Implement fast in small, verifiable increments.
3. Run local required checks before PR.
4. The session that implements a task is responsible for validation and commit quality.
5. Open PR or review request with evidence and rollback plan before push/merge to shared remote.
6. Merge only after required CI checks pass and review is completed.
7. Record handover items for the next owner.

## Task Ownership and Commit Rule
- Active task pickup should start from `docs/internal/PLAN.md`.
- One task should have one active owner/session at a time.
- Whoever implements a task is responsible for:
	- scoped code changes
	- focused validation
	- updating `docs/internal/PLAN.md`
	- creating the commit for that task when the scope is clean
- Push to shared remote, merge, or release should not happen without review.
- Recommended split:
	- task owner: implement, validate, commit
	- reviewer: review, approve/reject, then allow push/merge

## Mandatory Local Checks
Use one command:
- Windows: `scripts\\workflow.bat local`
- Linux/macOS: `sh scripts/workflow.sh local`

Weekly trend validation command:
- Windows: `scripts\\workflow.bat weekly-trend --samples 3`
- Linux/macOS: `sh scripts/workflow.sh weekly-trend --samples 3`

Trend artifacts:
- `.ivx/data/multi-project-weekly-trend.json`
- `.ivx/data/multi-project-weekly-trend.md`

Trend command must return non-zero on failure so it can be scheduled in CI or cron-like jobs.

Equivalent checks include:
- unit tests
- integration tests (if applicable)
- behavior recordability check
- lint (when configured)

## Mandatory PR Evidence
- what changed
- why needed
- validation result
- risk and rollback plan
- metrics impact

PR template:
- `.github/PULL_REQUEST_TEMPLATE.md`

## CI and Metrics Rule
CI must produce a metrics artifact (`metrics-summary.json`) to keep trend data reproducible.

Reference guides:
- `docs/internal/GITHUB_WORKFLOW_METRICS_GUIDE.md`
- `docs/internal/WORKFLOW_UNIVERSAL_GUIDE.md`

## Release Rule
No release without:
- required checks green
- metrics artifact available and parseable
- explicit risk owner decision

## Decision Rule: Develop First, Then Organize
If blocked by documentation structure debates:
1. proceed with a minimal executable implementation first
2. ensure tests/checks are green
3. then consolidate docs and structure in a follow-up PR
