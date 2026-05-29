# Architecture Quick Read Playbook

## Purpose
This playbook turns architecture understanding into an executable routine.

Target outcome in one pass:
- know where behavior is decided
- know where quality is enforced
- know where metrics are produced and consumed
- know what can be changed safely first

Primary execution contract remains: `WORKFLOW.md`.

## 10-Minute First Pass
1. Read `WORKFLOW.md` to lock delivery rules and required gates.
2. Read `HANDOVER.md` to identify active risks and unfinished decisions.
3. Read `README.md` or `README_ZH.md` for runtime entry and user-facing scope.
4. Open `.github/workflows/ci.yml` to see blocking quality gates.
5. Open `.github/scripts/build_metrics_summary.py` to see CI metrics schema source.
6. Open `src/ivx/server/service.py` to see API contracts and payload merge logic.
7. Open `scripts/workflow.py` to see local check parity with CI.

If only 10 minutes are available, stop here and start implementation with small reversible changes.

## 30-Minute Deepening (By Control Surface)

### 1) Runtime Control Surface
Read:
- `server.py`
- `app.py`
- `src/ivx/server/service.py`
- `src/ivx/server/governance.py`

Answer:
- Which endpoint updates progress state?
- Which endpoint records governance events?
- Which payload fields are merged vs replaced?

### 2) Delivery Control Surface
Read:
- `.github/workflows/ci.yml`
- `scripts/workflow.py`
- `pyproject.toml`

Answer:
- Which checks are blocking merge?
- Which local command gives closest CI parity?
- Which failures are expected to fail-fast?

### 3) Metrics Control Surface
Read:
- `.github/scripts/build_metrics_summary.py`
- `.github/scripts/push_metrics_summary.py`
- `docs/internal/GOVERNANCE_METRICS_CONTRACT.md`

Answer:
- How `pipeline_metrics.testing.*` is computed?
- How `pipeline_metrics.ci.*` is computed?
- Which governance events drive controllability/traceability metrics?

### 4) UI and Data Surface
Read:
- `web/index.html` or `src/ivx/web/index.html`
- `data/live_progress.json`
- `data/dashboard_state.json`

Answer:
- Which data the UI expects as stable contract?
- Which fields are critical for operations view?

## Architecture Decision Ladder (Change Priority)
Use this order to reduce risk:
1. Additive changes to docs/templates/scripts.
2. Additive API payload fields (backward compatible).
3. CI workflow refinements that do not relax required gates.
4. Metrics schema extensions with default-safe values.
5. Behavior-changing server merge logic.

For levels 4-5, require explicit rollback note in PR.

## Best-Practice Baseline (Cross-Source Synthesis)

### GitHub Actions Design
- Keep workflow triggers explicit; avoid accidental broad triggers.
- Use `needs` to express gate dependency graph clearly.
- Keep workflow lean: fewer, blocking, high-signal checks.
- Use `concurrency` to cancel stale runs on same branch.

### GitHub Actions Security
- Principle of least privilege for `GITHUB_TOKEN` permissions.
- Pin third-party actions to immutable versions (prefer full SHA).
- Treat all external input as untrusted in scripts.
- Prefer action inputs or intermediate env variables to avoid script injection.
- Use secrets for sensitive values, never plaintext in workflow YAML.

### Test Portfolio and Feedback Speed
- Follow test pyramid intent: many fast low-level checks, few high-level checks.
- Push checks downward when possible to reduce flakiness and cycle time.
- Keep early pipeline stages fast for quick failure feedback.
- Avoid duplicated checks across layers unless confidence increases materially.

### Service Architecture Hygiene (12-Factor aligned)
- Config in environment, not hardcoded in codepaths.
- Keep dev/prod behavior parity as high as practical.
- Treat logs/events as streams that can be aggregated and audited.
- Separate build/release/run concerns in CI and runtime operations.

## IVX-Specific Execution Rules
1. Local required checks use one command:
   - Windows: `scripts\\workflow.bat local`
   - Linux/macOS: `sh scripts/workflow.sh local`
2. CI must produce `metrics-summary.json` artifact each run.
3. Governance-relevant actions should emit events via `/api/governance/event`.
4. Progress and metrics updates should stay compatible with `/api/progress` merge contract.
5. Never remove a required gate unless replacement gives equal or better signal.

## Standard Delivery SOP (Per Task)
Apply this sequence for every implementation task:
1. Clarify requirement and acceptance criteria (done means what, out-of-scope what).
2. Identify the nearest owning file/symbol that directly controls behavior.
3. Propose minimal change plan (smallest reversible increment first).
4. Implement with compatibility and rollback awareness.
5. Run focused validation first (cheapest falsifiable check), then related checks.
6. Produce final delivery summary in fixed format.
7. Capture lessons learned for future runs.

Notes:
- Do not broaden scope before first focused validation.
- Prefer one stable recommended path over multiple optional paths.

## Standard Completion Output (Per Task)
Use this fixed structure in final response:
1. Requirement coverage: what was requested and what was delivered.
2. Change summary: key implementation and affected contracts.
3. Validation: commands/checks run and pass/fail result.
4. Risk and rollback: residual risk plus immediate rollback path.
5. Experience summary: lessons learned and what will be reused next time.

### Auto-Run Policy (Default)
- Do not wait for repeated prompts.
- After implementation, automatically run focused validation.
- If validation passes, automatically run commit-readiness checks (`git status`, staged diff review).
- If commit scope is clean and task is complete, proceed with commit directly.
- Only pause for confirmation when: scope is ambiguous, validation fails, or commit risk is unclear.

Recommended short template:
- Coverage:
- Changes:
- Validation:
- Risks/Rollback:
- Lessons Learned:

## Lessons-Learned Capture Rule
After each completed task, capture at least:
1. One thing that worked and should be repeated.
2. One failure mode or pitfall and its guardrail.
3. One concrete update to workflow/docs/scripts/tests (if needed).

Priority for recording:
1. Repository memory (`/memories/repo/`) for codebase-specific lessons.
2. Root/internal docs when behavior contract changed.
3. Session notes for temporary investigation context.

## Fast Architecture Q&A Template (for next handover)
When opening a new task, answer these first:
1. Which file directly decides the behavior?
2. Which test/check can falsify my hypothesis cheapest?
3. Which metric will move if this change is correct?
4. Which rollback step restores previous safe state?

If these four are unclear, do not widen scope. Read one nearby owning file and decide.

## Context Bloat Response (Fast Architecture Practice)
When input context starts growing too fast, compress it before adding more:
1. Keep only four anchors: goal, confirmed facts, open questions, next action.
2. Preserve file paths, symbols, commands, errors, and test names; drop repeated narration.
3. Add only deltas from the last turn: new failure, changed file, latest log, updated decision.
4. Externalize long history into a short handover note, diff, or checklist instead of the prompt.
5. Start a fresh thread when the current one has a stable summary and the next step is local.

Recommended prompt shape:
- Goal:
- Confirmed:
- Open:
- Next:

Rule of thumb: if you cannot state one falsifiable local hypothesis and one cheap check, the context is already too wide.

## Definition of "Architecture Understood"
You can claim architecture is understood only if you can state:
- one request path from trigger to persisted state
- one gate path from local checks to CI required checks
- one metrics path from raw test output to dashboard field
- one safe rollback path for your planned edit

## References
- GitHub Actions overview: https://docs.github.com/en/actions/learn-github-actions/understanding-github-actions
- Workflow syntax: https://docs.github.com/en/actions/using-workflows/workflow-syntax-for-github-actions
- Security hardening: https://docs.github.com/en/actions/security-for-github-actions/security-guides/security-hardening-for-github-actions
- Test pyramid (practical): https://martinfowler.com/articles/practical-test-pyramid.html
- Twelve-Factor App: https://12factor.net/