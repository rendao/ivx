# Architecture Quick Read Playbook (Template)

## Purpose
This file is a reusable architecture quick-read template for other project teams.

Target outcome in one pass:
- know where behavior is decided
- know where quality is enforced
- know where metrics are produced and consumed
- know what can be changed safely first

## Usage Boundary (Mandatory)
This playbook is a distilled sample from IVX practice, designed for cross-project adoption.

It is not the authoritative execution contract for IVX internal implementation.

For IVX internal execution, always follow:
- `WORKFLOW.md`
- `HANDOVER.md`
- `docs/internal/ROADMAP.md`
- `docs/internal/PLAN.md`
- release and internal docs under `docs/`

## 10-Minute First Pass (Generic)
1. Read the target project's workflow contract (for example `WORKFLOW.md`).
2. Read handover/open risks document (for example `HANDOVER.md`).
3. Read project README for runtime entry and user-facing scope.
4. Open CI workflow file to see blocking quality gates.
5. Open metrics build script to identify schema source.
6. Open backend service entry to identify API contract and persistence path.
7. Open local workflow script to align local checks with CI checks.

If only 10 minutes are available, stop here and start implementation with small reversible changes.

## 30-Minute Deepening (By Control Surface)

### 1) Runtime Control Surface
Read:
- service entry
- API service module
- governance or audit module

Answer:
- Which endpoint updates progress state?
- Which endpoint records governance events?
- Which payload fields are merged vs replaced?

### 2) Delivery Control Surface
Read:
- CI workflow
- local workflow wrapper
- package/build config

Answer:
- Which checks are blocking merge?
- Which local command gives closest CI parity?
- Which failures are expected to fail-fast?

### 3) Metrics Control Surface
Read:
- metrics summary builder
- metrics push/uploader
- governance metrics contract doc

Answer:
- How `pipeline_metrics.testing.*` is computed?
- How `pipeline_metrics.ci.*` is computed?
- Which events drive controllability and traceability metrics?

### 4) UI and Data Surface
Read:
- dashboard page or frontend module
- runtime progress state file
- runtime dashboard state file

Answer:
- Which data the UI expects as stable contract?
- Which fields are critical for operations view?

## Architecture Decision Ladder (Change Priority)
Use this order to reduce risk:
1. Additive changes to docs/templates/scripts.
2. Additive API payload fields (backward compatible).
3. CI workflow refinements that do not relax required gates.
4. Metrics schema extensions with default-safe values.
5. Behavior-changing merge/persistence logic.

For levels 4-5, require explicit rollback note in PR.

## Best-Practice Baseline

### CI Design
- Keep workflow triggers explicit; avoid accidental broad triggers.
- Use `needs` to express gate dependency graph clearly.
- Keep workflow lean: fewer, blocking, high-signal checks.
- Use `concurrency` to cancel stale runs on the same branch.

### CI Security
- Principle of least privilege for token permissions.
- Pin third-party actions to immutable versions where possible.
- Treat all external input as untrusted.
- Use secrets for sensitive values, never plaintext in workflow YAML.

### Test Portfolio
- Keep fast tests in early stages for quick failure feedback.
- Avoid duplicated checks across layers unless confidence gain is material.

### Service Hygiene
- Config in environment, not hardcoded in codepaths.
- Keep dev/prod behavior parity as high as practical.
- Treat logs/events as streams that can be audited.

## Standard Delivery SOP (Per Task)
Apply this sequence for every implementation task:
1. Clarify requirement and acceptance criteria.
2. Identify the nearest owning file/symbol.
3. Propose minimal reversible change.
4. Implement with compatibility and rollback awareness.
5. Run focused validation first, then related checks.
6. Produce fixed-format delivery summary.
7. Capture lessons learned.

## Standard Completion Output (Per Task)
Use this fixed structure:
1. Requirement coverage
2. Change summary
3. Validation
4. Risk and rollback
5. Lessons learned

## Fast Architecture Q&A Template
Answer these first before coding:
1. Which file directly decides behavior?
2. Which test/check can falsify the hypothesis cheapest?
3. Which metric should move if the change is correct?
4. Which rollback step restores previous safe state?

If these four are unclear, do not widen scope.

## Definition of "Architecture Understood"
Architecture is understood only if you can state:
- one request path from trigger to persisted state
- one gate path from local checks to required CI checks
- one metrics path from raw output to dashboard field
- one safe rollback path for the planned edit

## References
- GitHub Actions overview: https://docs.github.com/en/actions/learn-github-actions/understanding-github-actions
- Workflow syntax: https://docs.github.com/en/actions/using-workflows/workflow-syntax-for-github-actions
- Security hardening: https://docs.github.com/en/actions/security-for-github-actions/security-guides/security-hardening-for-github-actions
- Test pyramid (practical): https://martinfowler.com/articles/practical-test-pyramid.html
- Twelve-Factor App: https://12factor.net/