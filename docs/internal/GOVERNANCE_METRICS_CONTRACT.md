# Governance Metrics Contract (AI Developer Controllability)

## Purpose
Define how the project continuously produces control metrics so the dashboard reflects:
- process transparency
- objective controllability
- human-in-the-loop governance effectiveness

## Event Ingest Contract
Endpoint:
- `POST /api/governance/event`

Supported event `type` values:
- `objective_set`
- `plan_committed`
- `task_started`
- `task_completed`
- `task_stopped`
- `gate_passed`
- `gate_failed`
- `human_review_requested`
- `human_review_resolved`
- `decision_logged`
- `rollback`
- `auth_prompted`
- `auth_approved`
- `auth_denied`
- `action_confirmed`
- `action_skipped`
- `action_stopped`

Event payload fields:
- required: `type`, `message`
- optional: `actor`, `severity`, `objective_id`, `task_id`, `request_id`, `gate`, `result`
- optional AI/human interaction correlation: `workflow_id`, `run_id`, `step_id`, `interaction_id`, `decision`, `channel`, `target`, `duration_ms`
- optional project routing: `project_id`, `project_name`, `project_path`

Storage:
- `${project_root}/.ivx/data/governance_events.jsonl`

## Governance KPIs (computed)
The dashboard computes governance KPIs in `pipeline_metrics.governance`:
- `decision_logs_24h`
- `gate_pass_rate_percent`
- `human_response_sla_percent`
- `review_requests_24h`
- `unresolved_human_reviews`
- `traceability_coverage_percent`
- `transparency_score`
- `controllability_score`
- `objective_defined`
- `events_24h`
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

### KPI Intent (AI behavior and human interaction)
- `ai_task_*`: throughput and interruption observability for autonomous execution.
- `human_authorization_*`: permission prompt volume and operator trust/approval behavior.
- `pending_authorization_requests_24h`: unclosed prompts indicating governance lag.
- `human_confirmations_24h` / `human_skips_24h` / `human_stops_24h`: direct intervention profile.
- `human_interaction_rate_percent`: how often execution required human intervention.

## Read APIs
- `GET /api/progress`
  - includes all governance KPIs under `pipeline_metrics.governance`
- `GET /api/governance`
  - governance-focused projection for audits and controls
- `POST /api/collect`
  - force immediate signal refresh

## Recommended AI Workflow Emission
At minimum, AI/editor should emit:
1. objective declaration
2. plan commit
3. task start
4. gate pass/fail
5. auth prompt and auth outcome (`auth_prompted` -> `auth_approved|auth_denied`)
6. confirmation outcome for risky operations (`action_confirmed|action_skipped|action_stopped`)
7. human review requested/resolved
8. decision log for major trade-offs

This keeps controllability and transparency scores meaningful.
