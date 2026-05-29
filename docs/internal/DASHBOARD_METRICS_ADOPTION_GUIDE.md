# Dashboard Metrics Adoption Guide (Non-Invasive)

## Goal
Help project developers make their projects compatible with IVX dashboard metrics with minimal intrusion.

This guide prioritizes:
- no mandatory repository layout changes
- no mandatory .ivx/data writes in the target project
- reuse of existing CI and test outputs
- progressive adoption by maturity level

CI workflow naming/path recommendation:
- use neutral directories such as `artifacts/ci` or `reports/ci`
- avoid tool-specific paths (for example `.ivx/...`) in shared project workflows

## Core Principle
Treat dashboard integration as an external observability adapter, not an internal project framework requirement.

Recommended order:
1. reuse existing artifacts
2. map artifacts to dashboard contract fields
3. push summarized metrics via API from CI
4. add governance events only where meaningful

## Data Source Priority
For testing and quality signals, use this priority:
1. junit xml + coverage xml (highest confidence)
2. pytest cache (fallback)
3. test command probe output (last fallback)

Implication:
- `.pytest_cache` is optional, not required
- if xml reports exist, dashboard metrics are stable and auditable

## Non-Invasive Integration Levels

### Level 0: Zero Project Changes
Use dashboard auto collection only.

What you get:
- baseline commit and test signals when discoverable
- quick visibility with no project changes

Trade-off:
- lower confidence when only fallback signals are available

### Level 1: CI Artifact Mapping (Recommended Baseline)
Keep project code unchanged. Add CI commands that produce standard test artifacts.

Minimum artifacts:
- junit xml
- coverage xml

Recommended CI command example:
- `pytest -m "not integration" --junitxml=./junit.xml --cov=src --cov-report=xml:./coverage.xml`

Then either:
- let dashboard collect from project path automatically, or
- upload a summary to dashboard with `POST /api/progress`

### Level 2: Governance Event Emission
Emit control events for process transparency and controllability.

Endpoint:
- `POST /api/governance/event`

Useful event types:
- `objective_set`
- `plan_committed`
- `task_started`
- `task_completed`
- `task_stopped`
- `gate_passed` / `gate_failed`
- `human_review_requested` / `human_review_resolved`
- `decision_logged`
- `auth_prompted` / `auth_approved` / `auth_denied`
- `action_confirmed` / `action_skipped` / `action_stopped`

Only emit events that already exist in your workflow. Do not invent ceremony.

Recommended interaction fields:
- `request_id` or `interaction_id` to correlate prompt and response
- `run_id` and `step_id` to map to AI execution step
- `decision`, `channel`, `target` for human action context
- `duration_ms` for prompt-to-response latency tracking

## Contract Mapping Reference

### Testing
Map to `pipeline_metrics.testing`:
- `tests_passed`
- `tests_failed`
- `coverage_percent`
- `regressions`

### CI
Map to `pipeline_metrics.ci`:
- `last_build_status`
- `build_success_rate`
- `deploy_success_rate`

### Delivery and Review
Map to `pipeline_metrics.commit`:
- `commits_today`
- `prs_open`
- `review_pending`

### AI Behavior and Human Interaction
Map to `pipeline_metrics.governance`:
- `ai_task_started_24h`
- `ai_task_completed_24h`
- `ai_task_stopped_24h`
- `ai_task_stop_rate_percent`
- `human_authorization_requests_24h`
- `human_authorization_approved_24h`
- `human_authorization_denied_24h`
- `pending_authorization_requests_24h`
- `authorization_approval_rate_percent`
- `human_confirmations_24h`
- `human_skips_24h`
- `human_stops_24h`
- `human_confirmation_rate_percent`
- `human_interactions_24h`
- `human_interaction_rate_percent`

## API-First Push Pattern (No Repo Layout Dependency)
If you want strict non-intrusive integration, compute metrics in CI and push summary payload directly.

Endpoint:
- `POST /api/progress`

Minimal payload example:

```json
{
  "project": "your-project",
  "phase": "Phase 2 - Delivery",
  "task": "CI validation",
  "progress_percent": 70,
  "status": "yellow",
  "risk_level": "medium",
  "pipeline_metrics": {
    "testing": {
      "tests_passed": 120,
      "tests_failed": 2,
      "coverage_percent": 78,
      "regressions": 2
    },
    "ci": {
      "last_build_status": "running"
    }
  }
}
```

Benefits:
- no special path conventions required in project repository
- easy to integrate with any CI provider
- explicit and auditable metric ownership

## Practical Adoption Checklist
1. Start with Level 1, not Level 2.
2. Ensure junit xml and coverage xml are generated in CI.
3. Verify dashboard testing metrics are sourced from report artifacts.
4. Add integration tests as a separate stage (`-m integration`).
5. Introduce governance events only for real decision points.
6. For AI-assisted execution, always log permission prompts and outcomes.
7. Track stop/skip/confirm outcomes for risky or irreversible actions.

## Anti-Patterns to Avoid
- forcing project code to depend on dashboard internals
- treating `.pytest_cache` as primary source of truth
- mixing operational telemetry with private developer notes
- emitting governance events without real workflow semantics

## Success Criteria
Integration is considered successful when:
- dashboard metrics are reproducible from CI outputs
- data confidence is report-driven, not fallback-driven
- adoption does not require major changes to project layout
- teams can opt in incrementally without breaking delivery speed

## Internal Scorecard Reference
For multi-dimensional governance evaluation and sample-project readiness criteria, see:
- `docs/internal/ENGINEERING_SCORECARD.md`