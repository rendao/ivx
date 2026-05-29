# IVX 0.2.0 Release Checklist

## Scope Freeze
- [x] 0.2.0 scope aligned to stability baseline.
- [x] Input validation, atomic writes, recovery, and `/api/health` implemented.
- [x] Non-invasive behavior recordability output kept under `.ivx/data`.

## Validation Evidence
- [x] `python -m unittest tests.test_service_contract -v`
- [x] `python -m unittest discover -s tests -v`
- [x] `scripts\\workflow.bat local`
- [x] `python scripts\\release_smoke_0_2_0.py`

## Release Docs
- [x] `README.md` updated to 0.2.0 baseline.
- [x] `README_ZH.md` updated to 0.2.0 baseline.
- [x] `HANDOVER.md` updated with 0.2.0 release notes.
- [x] `docs/releases/RELEASE_NOTES_0.2.0.md` created.

## Packaging and Installability
- [x] `pyproject.toml` version set to `0.2.0`.
- [x] Build distribution artifacts.
- [x] Validate install path equivalent to `pip install ivx==0.2.0`.

## Release Execution
- [ ] Assign Product owner.
- [ ] Assign Tech owner.
- [ ] Assign Release owner.
- [ ] Create tag `v0.2.0`.
- [ ] Publish release package.
- [ ] Monitor first 24h runtime window.

## Rollback Readiness
- [x] State recovery uses rotating `.backups/` snapshots.
- [x] Release notes include rollback summary.
- [ ] Confirm release operator keeps previous install/version rollback command at hand.