# IVX Session Task Pack (2026-05-29)

## 1. Context
This task pack enables independent sessions to execute concrete work from the same product strategy and development plan without repeated clarification.

Use with:
- docs/internal/PRODUCT_STRATEGY_20260529.md
- docs/internal/DEVELOPMENT_PLAN_20260529.md

## 2. Scope
In scope:
- executable tasks with explicit target files
- per-task validation commands
- handoff output template for cross-session continuity

Out of scope:
- implementation details beyond each task boundary
- replacing architecture or release governance contracts

## 3. Decision or Plan
### 3.1 Execution Rule
Pick one task at a time. Finish with focused validation, then provide handoff summary in the fixed output template.

### 3.2 Task List
Task A1: Runtime availability and port hygiene
- Goal: eliminate stale-listener and connection-refused operational failures.
- Target files: app.py, server.py, src/ivx/server/service.py, HANDOVER.md references if behavior changes.
- Validation:
  - ivx serve --host 127.0.0.1 --port 8789
  - GET /api/health returns service_ok with diagnostics
- Done when: service can be started predictably with clear conflict diagnostics.

Task A2: Testing telemetry refresh correctness
- Goal: prevent stale testing metrics when source priority changes.
- Target files: src/ivx/server/telemetry.py and related tests.
- Validation:
  - run targeted telemetry tests
  - run scripts\\workflow.bat local
- Done when: xml/pytest_cache/unittest probe source transitions refresh persisted metrics correctly.

Task B1: Governance event semantic validation
- Goal: ensure governance events carry stable semantics and correlation fields.
- Target files: src/ivx/server/governance.py, docs/internal/GOVERNANCE_METRICS_CONTRACT.md, tests for event ingest.
- Validation:
  - governance API payload tests
  - compatibility tests for accepted historical payloads
- Done when: low-semantic/noise events are filtered or down-scored without breaking required event types.

Task C1: Intervention queue action model
- Goal: convert queue items into executable action cards.
- Target files: web/index.html and/or src/ivx/web/index.html, related API shaping in service layer.
- Validation:
  - UI renders owner/priority/due/status/action recommendation
  - no regression in existing progress panels
- Done when: each intervention item has enough fields for assignment and closure tracking.

Task D1: Second-project adoption pilot
- Goal: prove non-invasive onboarding in a second repository.
- Target files: docs/internal/DASHBOARD_METRICS_ADOPTION_GUIDE.md, docs/internal pilot notes.
- Validation:
  - collect junit/coverage artifacts
  - push progress to /api/progress
  - verify dashboard metrics update reproducibly
- Done when: second project can onboard in one day with reproducible metrics.

### 3.3 Suggested Task Order
1. A1
2. A2
3. B1
4. C1
5. D1

### 3.4 Handoff Output Template (Required)
Coverage:
- requirement addressed:
- out-of-scope kept intact:

Changes:
- files changed:
- contract impact:

Validation:
- commands run:
- pass/fail summary:

Risks/Rollback:
- residual risk:
- immediate rollback path:

Lessons Learned:
- what worked:
- pitfall and guardrail:
- follow-up task:

## 4. Acceptance Criteria
- At least five independent tasks are executable without additional planning.
- Each task has clear target files and objective done criteria.
- Validation commands are explicit and align with current workflow contract.
- A fixed handoff format enables cross-session continuity.

## 5. Risks and Rollback
Risk 1: parallel sessions overlap and conflict in the same file scope.
- Rollback: enforce one-task lock ownership and rebase before merge.

Risk 2: sessions skip validation for speed.
- Rollback: reject handoff without validation evidence.

Risk 3: task pack drifts from strategy/plan.
- Rollback: weekly sync update of this file and linked strategy/plan docs.

## 6. Owner and Date
- Owner: IVX session coordinator
- Date: 2026-05-29
