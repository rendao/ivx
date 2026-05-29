# IVX 0.2.0 Release Notes

## Summary
- Stabilized the dashboard service for local release use.
- Added strict progress validation, atomic writes, backup recovery, and `/api/health`.
- Added governance, telemetry, and behavior recordability coverage.
- Added a minimal smoke script for startup, push, and readback verification.

## Key Changes
- `src/ivx/server/service.py`: strict `/api/progress` validation, health snapshot, and atomic state recovery.
- `src/ivx/server/governance.py`: AI / Human / System behavior split and governance KPIs.
- `src/ivx/server/telemetry.py`: git/test activity collection with report and fallback support.
- `scripts/release_smoke_0_2_0.py`: end-to-end local smoke check.
- `tools/behavior_recordability_check.py`: behavior recordability report output kept under `.ivx/data` by default.

## Validation
- `python -m unittest tests.test_service_contract -v`
- `python -m unittest discover -s tests -v`
- `scripts\\workflow.bat local`

## Rollback
- Revert the 0.2.0 release commit set.
- Restore the previous `pyproject.toml` version if needed.
- Recover state files from `.backups/` if a runtime file needs rollback.

## Smoke Path
1. Start the service.
2. Push progress, collaborator, CI, and governance updates.
3. Read back `/api/progress` and `/api/health`.
4. Confirm the smoke report is written to `.ivx/data/release-smoke-0.2.0.md`.