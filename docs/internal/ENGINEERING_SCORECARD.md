# Engineering Scorecard (Internal)

## Purpose
Provide a multi-dimensional, evidence-based scorecard for AI-automated engineering projects.

This scorecard is designed to:
- reward standardized engineering behavior
- make process transparency measurable
- make objective progress controllable
- help teams improve operational discipline

## Dimensions
All scores are in range `0-100`.

### 1) Process Observability
Field: `pipeline_metrics.governance.process_observability_score`

Signals:
- transparency score
- event activity in recent 24h
- traceability coverage

Interpretation:
- `>= 80`: process evidence is rich and auditable
- `60-79`: acceptable, but event/traceability quality should improve
- `< 60`: evidence is weak, process visibility risk is high

### 2) Objective Progress
Field: `pipeline_metrics.governance.objective_progress_score`

Signals:
- task progress (done/planned)
- gate pass rate
- AI task completion rate

Interpretation:
- `>= 80`: objective progress is healthy and predictable
- `60-79`: progress exists but has friction
- `< 60`: objective alignment or execution throughput is weak

### 3) Human Collaboration Quality
Field: `pipeline_metrics.governance.human_collaboration_quality_score`

Signals:
- human response SLA
- authorization approval behavior
- confirmation behavior
- interaction traceability
- pending authorization pressure (penalty)

Interpretation:
- `>= 80`: human-in-the-loop is efficient and traceable
- `60-79`: collaboration works but has operational gaps
- `< 60`: interaction quality is unstable; governance friction is high

### 4) Risk Control
Field: `pipeline_metrics.governance.risk_control_score`

Signals:
- controllability score
- AI stop rate (inverse contribution)

Interpretation:
- `>= 80`: risks are actively controlled
- `60-79`: moderate risk pressure
- `< 60`: control breakdown likely

### 5) Overall Governance Score
Field: `pipeline_metrics.governance.overall_governance_score`

Composition:
- equal-weight blend of the four dimensions above

Interpretation:
- `>= 80`: ready as a reference implementation
- `65-79`: stable baseline, improvement required
- `< 65`: not suitable as external sample yet

## Data Quality Tier
Field: `pipeline_metrics.governance.data_quality_tier`
Values: `A`, `B`, `C`

Rules (current implementation):
- `A`: high event volume + high interaction traceability + sufficient decision logs
- `B`: medium event volume + medium interaction traceability
- `C`: low evidence quality

Usage:
- use `A/B` data for comparative benchmarking
- use `C` only for local diagnostics, not for external ranking

## Required Evidence for Reliable Scoring
- CI reports: junit xml + coverage xml
- governance event logs with real semantics
- interaction correlation fields: `request_id` or `interaction_id`

## Team Action Playbook
- if `process_observability_score < 60`: improve event emission and traceability tags
- if `objective_progress_score < 60`: review plan decomposition, gate criteria, and task closure discipline
- if `human_collaboration_quality_score < 60`: reduce pending prompts, improve response SLA, enforce interaction IDs
- if `risk_control_score < 60`: tighten review checkpoints and stop policy
- if `data_quality_tier == C`: fix evidence pipeline before discussing score changes

## Governance Principle
No evidence, no score authority.
