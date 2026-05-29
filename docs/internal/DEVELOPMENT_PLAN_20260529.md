# IVX Development Plan (2026-05-29)

Snapshot note:
- This file is a time-stamped plan snapshot.
- Active updates should go to `docs/internal/PLAN.md` (execution) and `docs/internal/ROADMAP.md` (phase direction).

## 1. Context
The product direction is set to "data trust -> action loop -> multi-project replication". This document converts that direction into executable development work for upcoming sessions.

Current baseline includes:
- runtime service and dashboard UI
- progress and governance APIs
- governance metric contract
- release stability baseline 0.2.0

## 2. Scope
In scope:
- 4-week implementation plan
- workstream breakdown and dependencies
- validation and release readiness gates
- session-ready ownership structure

Out of scope:
- long-horizon roadmap beyond initial replication baseline
- org-level process policy changes outside repository contracts

## 3. Decision or Plan
### 3.1 Timeline (4 Weeks)
Week 1: Reliability and data baseline
- verify service availability and port hygiene
- harden data source confidence and stale-metric refresh behavior
- confirm health diagnostics isolate raw-state faults

Week 2: Governance event quality
- normalize event semantic usage and correlation IDs
- separate operational warning events from governance control events
- reduce ambiguous events and improve traceability coverage

Week 3: Action-loop UX and API contract
- redesign intervention queue data model to action-oriented fields
- add recommendation mapping from risk signal to next action
- validate backward compatibility for existing payload producers

Week 4: Cross-project adoption pilot
- onboard a second project using non-invasive Level 1 integration
- run one full operational cycle and compare baseline metrics
- produce replication checklist and rollout readiness report

### 3.2 Workstreams
WS-A Runtime reliability
- owners: backend/runtime
- key files: src/ivx/server/service.py, src/ivx/server/telemetry.py, server.py
- output: reliability notes, failing-case tests, recovery diagnostics

WS-B Governance semantics
- owners: backend/governance
- key files: src/ivx/server/governance.py, docs/internal/GOVERNANCE_METRICS_CONTRACT.md
- output: semantic event guidance and validation updates

WS-C Actionable dashboard
- owners: frontend + API
- key files: web/index.html, src/ivx/web/index.html, service contracts
- output: actionable intervention queue and recommendation rendering

WS-D Adoption and operations
- owners: docs + integration
- key files: docs/internal/DASHBOARD_METRICS_ADOPTION_GUIDE.md, handover docs
- output: second-project onboarding and operation runbook

### 3.3 Dependency Order
1. WS-A before WS-C (stability before UX action loop)
2. WS-B before WS-D (clean governance semantics before replication)
3. WS-C and WS-D can run in parallel after WS-A/B baseline completion

### 3.4 Delivery Cadence
- each session should close one scoped task with focused validation
- merge only with evidence: change, validation, risk/rollback
- mandatory local parity command on task completion:
  - Windows: scripts\\workflow.bat local
  - Linux/macOS: sh scripts/workflow.sh local

## 4. Acceptance Criteria
- Week-level milestones are mapped to concrete workstreams and owning files.
- Dependencies are explicit and prevent unstable parallelization.
- Validation gates are clear for each merged task.
- Plan is directly consumable by other sessions without extra planning artifacts.

## 5. Risks and Rollback
Risk 1: breaking existing push scripts due to stricter event semantics.
- Rollback: keep compatibility parser and warn-first strategy before strict fail.

Risk 2: UI changes outrun backend contract stability.
- Rollback: freeze UI changes to additive fields only until API contract is finalized.

Risk 3: adoption pilot blocked by project-specific CI differences.
- Rollback: default to API-first push pattern while preserving artifact mapping target.

## 6. Owner and Date
- Owner: IVX engineering owner
- Date: 2026-05-29
