# IVX Plan

## 1. Context
This file is the rolling execution plan for IVX.

Use it to track current and next implementation work that realizes ROADMAP phase goals.

## 2. Scope
In scope:
- near-term execution items (1-4 weeks)
- task-level ownership and validation
- dependency order and done criteria

Out of scope:
- long-term strategy statements
- release notes content

## 3. Decision or Plan
### Plan Usage Rule (Canonical)
- This file is the single active execution tracker for cross-session delivery.
- Every session must update status, owner/session, and last update for touched tasks.
- Do not create parallel task trackers unless this file becomes structurally insufficient.
- Other sessions should start here to pick the next task.

### Current Window (Next 4 Weeks)
1. Reliability and data baseline
- service availability checks and port hygiene
- stale telemetry refresh correctness
- health diagnostics for raw file state and recovery state

2. Governance event quality
- event semantic normalization
- correlation IDs and traceability field coverage
- compatibility-safe validation tightening

3. Action-loop dashboard
- intervention queue action fields (owner, priority, due, status)
- recommendation mapping from risk signal to next action

4. Cross-project adoption pilot
- onboard a second project via non-invasive Level 1 integration
- verify reproducible metrics with CI artifacts and API push
- run weekly trend validation to confirm cross-project signals stay stable over repeated pilot runs
- run weekly-trend from workflow entrypoint on a fixed cadence (daily/weekly) for longitudinal evidence

### Execution Rule
- one scoped task per session
- focused validation before widening scope
- mandatory handoff summary with coverage/changes/validation/risks/lessons

### Session Self-Check Gate (Strict, pass-before-close)
Before marking a task done, all checks below must be explicitly answered.

1. Requirement closure check
- Is requested scope fully covered without silent omission?
- Is out-of-scope explicitly stated?

2. Validation closure check
- Did focused validation run against changed behavior (not only generic tests)?
- Are exact commands and pass/fail results recorded?

3. Git closure check
- Is local `HEAD` commit present and message task-scoped?
- Is residual working tree listed (`git status --short`) and intentionally excluded or planned?
- Is local vs remote state explicit (committed locally only vs pushed)?

4. Dashboard closure check
- Are event metrics and task fields interpreted by contract, not assumption?
- Confirmed distinction:
	- `task` drives Current Task
	- `next_milestone` drives the milestone line
	- commit events update `recent_events`/`commits_today`, not `task` by default

5. Reviewer clarity check
- Can a reviewer answer in under 2 minutes:
	- what changed
	- how it was validated
	- what remains uncommitted or risky

Close rule:
- If any answer above is "no" or "unclear", status remains `in-progress`.

### Ownership, Commit, and Review Rule
- Whoever takes a task is responsible for implementation, focused validation, and the task commit.
- A task should not be marked `done` until validation evidence is recorded here.
- Push to shared remote or production-facing branch requires review after the commit is prepared.
- Recommended flow:
	1. pick task from this file
	2. set `Status` to `in-progress` and claim `Owner/Session`
	3. implement and validate
	4. commit with task-scoped changes
	5. request review before push/merge
	6. after review and acceptance, update status/handoff record

### Task Status Board (Editable)
Status values:
- `todo`: not started
- `in-progress`: actively owned by one session
- `blocked`: waiting on dependency/decision
- `done`: merged and validated

| Task | Priority | Status | Owner/Session | Last Update | Blocker | Validation Evidence |
|---|---|---|---|---|---|---|
| A1 Runtime availability and connection-refused diagnostics | P0 | done | current-session | 2026-05-29 | none | `python -m pytest tests/test_service_contract.py` |
| A2 Testing telemetry stale refresh safeguards | P0 | done | current-session | 2026-06-01 | none | `e:/YanXin/ivx/.venv-release-test/Scripts/python.exe -m pytest tests/test_telemetry.py -q` |
| B1 Governance event semantic validation | P1 | done | current-session | 2026-05-31 | none | `e:/YanXin/ivx/.venv-release-test/Scripts/python.exe -m pytest tests/test_governance.py -q` |
| C1 Intervention queue action model | P1 | done | current-session | 2026-05-31 | none | `e:/YanXin/ivx/.venv-release-test/Scripts/python.exe -m pytest tests/test_service_contract.py -q` |
| D1 Second-project onboarding pilot | P2 | done | current-session | 2026-05-31 | none | `e:/YanXin/ivx/.venv-release-test/Scripts/python.exe scripts/second_project_pilot.py --host 127.0.0.1 --port 8793` |
| D2 Multi-project weekly trend baseline | P2 | done | current-session | 2026-06-01 | none | `e:/YanXin/ivx/.venv-release-test/Scripts/python.exe scripts/weekly_trend_validation.py --samples 2 --port-start 8810 --interval-seconds 0` |
| D3 Weekly-trend workflow scheduling readiness | P2 | done | current-session | 2026-06-01 | none | `e:/YanXin/ivx/.venv-release-test/Scripts/python.exe scripts/workflow.py weekly-trend --samples 1 --port-start 8820 --interval-seconds 0` |

### Session Handoff Contract (Required)
When a session closes a task update, append one short record under "Recent Handoffs" using this format:
- Date:
- Task:
- Status change:
- Files changed:
- Validation summary:
- Risk and rollback:
- Next suggested task:

### Recent Handoffs
- 2026-05-29: Plan tracker initialized (status board + handoff contract).
- Date: 2026-05-29
- Task: A1 Runtime availability and connection-refused diagnostics
- Status change: in-progress -> done
- Files changed: `src/ivx/server/service.py`, `tests/test_service_contract.py`, `docs/internal/PLAN.md`
- Validation summary: `python -m pytest tests/test_service_contract.py` passed (5 tests); changed files also passed static error check.
- Risk and rollback: listener hint relies on platform tools such as `netstat`/`lsof`; rollback is to remove `_format_bind_error` branch and restore pre-bind collector startup order only if startup regression appears.
- Next suggested task: A2 Testing telemetry stale refresh safeguards
- Date: 2026-05-29
- Task: A2 Testing telemetry stale refresh safeguards
- Status change: todo -> in-progress (implemented + validated, pending review/merge)
- Files changed: `tests/test_telemetry.py`, `docs/internal/PLAN.md`
- Validation summary: `e:/YanXin/ivx/.venv-release-test/Scripts/python.exe -m unittest tests.test_telemetry -v` passed (8 tests).
- Risk and rollback: scope is test-only with no runtime behavior change; rollback is reverting the two new A2 safeguard tests if they prove too strict.
- Next suggested task: B1 Governance event semantic validation
- Date: 2026-05-30
- Task: Session review discipline hardening (cross-session self-check tightening)
- Status change: governance/process update recorded
- Files changed: `docs/internal/PLAN.md`
- Validation summary: checklist reviewed against recent session outcomes (commit visibility mismatch, residual uncommitted files, dashboard field interpretation mismatch) and converted to explicit closure gates.
- Risk and rollback: risk is over-strict process slowing small tasks; rollback is to downgrade strict gate to advisory-only for low-risk docs-only tasks.
- Next suggested task: apply this gate to current active task before next push/merge action.
- Date: 2026-05-31
- Task: B1 Governance event semantic validation
- Status change: todo -> done
- Files changed: `src/ivx/server/governance.py`, `tests/test_governance.py`
- Validation summary: `e:/YanXin/ivx/.venv-release-test/Scripts/python.exe -m pytest tests/test_governance.py -q` passed (4 tests).
- Risk and rollback: alias normalization may change event-type labeling in downstream consumers; rollback is `git revert --no-edit b876524`.
- Next suggested task: C1 Intervention queue action model.
- Date: 2026-05-31
- Task: C1 Intervention queue action model
- Status change: todo -> done
- Files changed: `src/ivx/server/service.py`, `tests/test_service_contract.py`
- Validation summary: `e:/YanXin/ivx/.venv-release-test/Scripts/python.exe -m pytest tests/test_service_contract.py -q` passed (6 tests at delivery).
- Risk and rollback: due-time policy is priority-based and may require calibration; rollback is `git revert --no-edit 895f814`.
- Next suggested task: D1 Second-project onboarding pilot.
- Date: 2026-05-31
- Task: D1 Second-project onboarding pilot
- Status change: todo -> done
- Files changed: `scripts/second_project_pilot.py`, `tests/test_service_contract.py`
- Validation summary: `e:/YanXin/ivx/.venv-release-test/Scripts/python.exe -m pytest tests/test_service_contract.py -q` passed (7 tests) and `e:/YanXin/ivx/.venv-release-test/Scripts/python.exe scripts/second_project_pilot.py --host 127.0.0.1 --port 8793` passed with report generated.
- Risk and rollback: pilot script launches ephemeral server/data and assumes free port; rollback is `git revert --no-edit b6f025b`.
- Next suggested task: close A2 review/merge, then start weekly trend validation for multi-project evidence.
- Date: 2026-06-01
- Task: A2 Testing telemetry stale refresh safeguards
- Status change: in-progress -> done
- Files changed: `tests/test_telemetry.py`, `docs/internal/PLAN.md`
- Validation summary: `e:/YanXin/ivx/.venv-release-test/Scripts/python.exe -m pytest tests/test_telemetry.py -q` passed (8 tests).
- Risk and rollback: scope remains test/telemetry safeguards; rollback is `git revert --no-edit <A2-commit-sha>` for the corresponding A2 implementation commit.
- Next suggested task: start weekly trend validation for multi-project evidence using D1 pilot script.
- Date: 2026-06-01
- Task: D2 Multi-project weekly trend baseline
- Status change: new -> done
- Files changed: `scripts/weekly_trend_validation.py`, `tests/test_weekly_trend_validation.py`, `docs/internal/PLAN.md`
- Validation summary: `e:/YanXin/ivx/.venv-release-test/Scripts/python.exe -m pytest tests/test_weekly_trend_validation.py -q` passed (2 tests) and `e:/YanXin/ivx/.venv-release-test/Scripts/python.exe scripts/weekly_trend_validation.py --samples 2 --port-start 8810 --interval-seconds 0` passed with JSON/Markdown reports generated under `.ivx/data`.
- Risk and rollback: repeated pilot runs consume temporary ports and can fail if port range is occupied; rollback is `git revert --no-edit <D2-commit-sha>` for this addition.
- Next suggested task: raise sample count and schedule periodic execution (daily/weekly) to collect longitudinal evidence.
- Date: 2026-06-01
- Task: D3 Weekly-trend workflow scheduling readiness
- Status change: new -> done
- Files changed: `scripts/workflow.py`, `scripts/workflow.bat`, `scripts/workflow.sh`, `WORKFLOW.md`, `docs/internal/PLAN.md`
- Validation summary: `e:/YanXin/ivx/.venv-release-test/Scripts/python.exe scripts/workflow.py weekly-trend --samples 1 --port-start 8820 --interval-seconds 0` passed and generated trend artifacts under `.ivx/data`.
- Risk and rollback: wrapper usage text changes are low risk; workflow weekly-trend command depends on available local ports and pilot script stability. Rollback: `git revert --no-edit <D3-commit-sha>`.
- Next suggested task: wire this command into CI schedule or OS scheduled task with weekly cadence.

## 4. Acceptance Criteria
- Plan is actionable without creating extra planning documents.
- Priority queue maps clearly to roadmap phases.
- Each active task has validation evidence before closure.

## 5. Risks and Rollback
Risk 1: sessions diverge on execution direction.
- Rollback: treat this file as active plan source of truth and update at handoff.

Risk 2: plan contains stale completed tasks.
- Rollback: prune or mark status on every weekly sync.

## 6. Owner and Date
- Owner: IVX engineering owner
- Date: 2026-05-29
