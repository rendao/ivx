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

### Execution Rule
- one scoped task per session
- focused validation before widening scope
- mandatory handoff summary with coverage/changes/validation/risks/lessons

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
| A2 Testing telemetry stale refresh safeguards | P0 | in-progress | current-session | 2026-05-29 | review required before push/merge | `e:/YanXin/ivx/.venv-release-test/Scripts/python.exe -m unittest tests.test_telemetry -v` |
| B1 Governance event semantic validation | P1 | todo | unassigned | 2026-05-29 | dependency: A1/A2 baseline | pending |
| C1 Intervention queue action model | P1 | todo | unassigned | 2026-05-29 | dependency: A1 baseline | pending |
| D1 Second-project onboarding pilot | P2 | todo | unassigned | 2026-05-29 | dependency: B1/C1 baseline | pending |

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
