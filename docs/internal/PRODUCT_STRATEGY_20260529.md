# IVX Product Strategy (2026-05-29)

Snapshot note:
- This file is a time-stamped strategy snapshot.
- Active updates should go to `docs/internal/ROADMAP.md` and `docs/internal/PLAN.md`.

## 1. Context
IVX is a standalone live board for AI-driven software delivery. The current baseline (0.2.0) has completed stability foundations: health diagnostics, atomic writes, state recovery, and strict payload validation.

The next phase should shift from "stable display" to "operational decision system" with two constraints:
- keep integration non-invasive for project teams
- keep governance evidence auditable for management

## 2. Scope
In scope:
- product design direction for the next 1-2 quarters
- value proposition for developers and managers
- north-star metrics and design principles
- execution alignment with current runtime and API contracts

Out of scope:
- major architecture rewrite
- multi-tenant permission system implementation
- SDK expansion for non-Python ecosystems

## 3. Decision or Plan
### 3.1 Product Positioning
IVX is an operations cockpit for AI collaboration, not only a dashboard.

It must continuously answer three questions:
1. Are we healthy now?
2. What is the next best action?
3. Is the process auditable and controllable?

### 3.2 Core User Value
For developers:
- reduce context switching by unifying progress, CI/testing, blockers, and interventions
- provide action-first intervention queue instead of status-only display
- preserve low-friction onboarding through CI artifact mapping and API-first push

For managers:
- provide evidence-based governance rather than report-based governance
- expose process observability, objective controllability, and human-in-the-loop quality
- support cross-project comparability using the same metric contract

### 3.3 Product Design Principles
1. Data trust first: no confidence, no decision.
2. Actionability over decoration: every risk item maps to owner/action/deadline.
3. Progressive adoption: Level 1 artifact mapping before Level 2 governance events.
4. Backward compatibility by default for payload and metrics contracts.
5. Governance as product behavior, not post-hoc documentation.

### 3.4 North-Star and Guardrail Metrics
North-star (operational effectiveness):
- intervention resolution lead time
- unresolved intervention backlog
- gate pass rate trend

Guardrails (quality and governance):
- governance traceability coverage
- human response SLA
- data quality tier (A/B/C)
- API payload validation failure rate

### 3.5 Roadmap Direction (Single Recommended Path)
Phase A: Data trust hardening
- enforce required event semantics and correlation identifiers
- improve source-priority confidence (xml reports first, fallback second)

Phase B: Action-loop productization
- evolve intervention queue into executable task flow
- attach recommendation rules for common risk patterns

Phase C: Multi-project operating model
- portfolio-level comparison views and baseline benchmarks
- standard runbook-driven response for recurring governance risks

## 4. Acceptance Criteria
- Product strategy is explicit about user value for developers and managers.
- North-star and guardrail metrics are defined and usable by release planning.
- A single recommended roadmap path is documented with phase boundaries.
- Follow-up development planning can map work items to this strategy without reinterpretation.

## 5. Risks and Rollback
Risk 1: over-expansion of scope before data quality baseline is reliable.
- Rollback: freeze to Phase A only; reject features that do not improve data trust.

Risk 2: event noise reduces governance score usefulness.
- Rollback: whitelist high-semantic event types; gate non-semantic events.

Risk 3: high process burden for developers.
- Rollback: keep Level 1 artifact-first integration as default path.

## 6. Owner and Date
- Owner: IVX product/tech owner
- Date: 2026-05-29
