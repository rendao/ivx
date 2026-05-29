from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict

EVENT_LOG_RELATIVE = Path(".ivx") / "data" / "governance_events.jsonl"
DEFAULT_REVIEW_SLA_MINUTES = 30


def now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def parse_iso(value: str) -> datetime | None:
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            return parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc)
    except Exception:
        return None


def governance_event_log_path(project_root: Path) -> Path:
    return (project_root / EVENT_LOG_RELATIVE).resolve()


def normalize_governance_event(event: Dict[str, Any]) -> Dict[str, Any]:
    event_type = str(event.get("type") or "decision_logged").strip().lower()
    severity = str(event.get("severity") or "info").strip().lower()
    if severity not in {"info", "warning", "critical"}:
        severity = "info"

    normalized: Dict[str, Any] = {
        "time": str(event.get("time") or now_iso()),
        "type": event_type,
        "actor": str(event.get("actor") or "ai-editor"),
        "message": str(event.get("message") or ""),
        "severity": severity,
    }

    for key in (
        "objective_id",
        "task_id",
        "request_id",
        "gate",
        "result",
        "workflow_id",
        "run_id",
        "step_id",
        "interaction_id",
        "decision",
        "channel",
        "target",
    ):
        value = str(event.get(key) or "").strip()
        if value:
            normalized[key] = value

    duration_ms = event.get("duration_ms")
    if duration_ms is not None:
        try:
            normalized["duration_ms"] = max(0, int(duration_ms))
        except Exception:
            pass

    return normalized


def append_governance_event(project_root: Path, event: Dict[str, Any]) -> Dict[str, Any]:
    log_file = governance_event_log_path(project_root)
    log_file.parent.mkdir(parents=True, exist_ok=True)
    normalized = normalize_governance_event(event)
    with log_file.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(normalized, ensure_ascii=False) + "\n")
    return normalized


def load_governance_events(project_root: Path, limit: int = 500) -> list[Dict[str, Any]]:
    log_file = governance_event_log_path(project_root)
    if not log_file.exists():
        return []

    lines = log_file.read_text(encoding="utf-8").splitlines()
    selected = lines[-max(1, limit):]
    result: list[Dict[str, Any]] = []
    for line in selected:
        try:
            raw = json.loads(line)
            if isinstance(raw, dict):
                result.append(normalize_governance_event(raw))
        except Exception:
            continue

    result.sort(key=lambda item: item.get("time", ""), reverse=True)
    return result


def _events_in_window(events: list[Dict[str, Any]], hours: int = 24) -> list[Dict[str, Any]]:
    threshold = datetime.now(timezone.utc) - timedelta(hours=hours)
    filtered: list[Dict[str, Any]] = []
    for item in events:
        ts = parse_iso(str(item.get("time") or ""))
        if ts is None:
            continue
        if ts >= threshold:
            filtered.append(item)
    return filtered


def _build_review_pairs(events: list[Dict[str, Any]]) -> tuple[int, int, int]:
    pending_by_id: Dict[str, datetime] = {}
    unresolved_without_id: list[datetime] = []
    resolved_within_sla = 0
    resolved_total = 0

    ordered = sorted(events, key=lambda item: item.get("time", ""))
    for event in ordered:
        event_type = str(event.get("type") or "")
        ts = parse_iso(str(event.get("time") or ""))
        if ts is None:
            continue

        request_id = str(event.get("request_id") or "").strip()

        if event_type == "human_review_requested":
            if request_id:
                pending_by_id[request_id] = ts
            else:
                unresolved_without_id.append(ts)
            continue

        if event_type != "human_review_resolved":
            continue

        request_at: datetime | None = None
        if request_id and request_id in pending_by_id:
            request_at = pending_by_id.pop(request_id)
        elif unresolved_without_id:
            request_at = unresolved_without_id.pop(0)

        if request_at is None:
            continue

        resolved_total += 1
        latency_minutes = max(0, int((ts - request_at).total_seconds() // 60))
        if latency_minutes <= DEFAULT_REVIEW_SLA_MINUTES:
            resolved_within_sla += 1

    unresolved = len(pending_by_id) + len(unresolved_without_id)
    return resolved_within_sla, resolved_total, unresolved


def derive_governance_metrics(progress: Dict[str, Any], project_root: Path) -> Dict[str, Any]:
    events = load_governance_events(project_root)
    events_24h = _events_in_window(events, hours=24)

    gate_passed = 0
    gate_total = 0
    decision_logs_24h = 0
    task_completed_total = 0
    task_completed_with_objective = 0

    ai_task_started_24h = 0
    ai_task_completed_24h = 0
    ai_task_stopped_24h = 0
    human_authorization_requests_24h = 0
    human_authorization_approved_24h = 0
    human_authorization_denied_24h = 0
    human_confirmations_24h = 0
    human_skips_24h = 0
    human_stops_24h = 0

    ai_behavior_events_24h = 0
    human_behavior_events_24h = 0
    system_behavior_events_24h = 0
    ai_behavior_type_counts_24h: Dict[str, int] = {}
    human_behavior_type_counts_24h: Dict[str, int] = {}
    system_behavior_type_counts_24h: Dict[str, int] = {}

    decision_types = {
        "objective_set",
        "plan_committed",
        "decision_logged",
        "gate_passed",
        "gate_failed",
        "task_completed",
    }

    ai_event_types = {
        "objective_set",
        "plan_committed",
        "task_started",
        "task_completed",
        "task_stopped",
        "run_stopped",
        "agent_stopped",
        "decision_logged",
        "gate_passed",
        "gate_failed",
        "auth_prompted",
        "authorization_requested",
        "permission_prompted",
    }
    human_event_types = {
        "auth_approved",
        "authorization_approved",
        "permission_granted",
        "auth_denied",
        "authorization_denied",
        "permission_denied",
        "action_confirmed",
        "confirmed",
        "action_skipped",
        "skip",
        "action_stopped",
        "stop_requested",
        "agent_stopped_by_human",
        "human_review_requested",
        "human_review_resolved",
    }

    for event in events_24h:
        event_type = str(event.get("type") or "")
        actor = str(event.get("actor") or "").lower()

        behavior_owner = "system"
        if event_type in ai_event_types:
            behavior_owner = "ai"
        elif event_type in human_event_types:
            behavior_owner = "human"
        elif any(token in actor for token in {"human", "operator", "reviewer", "approver"}):
            behavior_owner = "human"
        elif any(token in actor for token in {"ai", "agent", "copilot", "assistant"}):
            behavior_owner = "ai"

        if behavior_owner == "ai":
            ai_behavior_events_24h += 1
            ai_behavior_type_counts_24h[event_type] = ai_behavior_type_counts_24h.get(event_type, 0) + 1
        elif behavior_owner == "human":
            human_behavior_events_24h += 1
            human_behavior_type_counts_24h[event_type] = human_behavior_type_counts_24h.get(event_type, 0) + 1
        else:
            system_behavior_events_24h += 1
            system_behavior_type_counts_24h[event_type] = system_behavior_type_counts_24h.get(event_type, 0) + 1

        if event_type in decision_types:
            decision_logs_24h += 1

        if event_type == "task_started":
            ai_task_started_24h += 1
        elif event_type == "task_completed":
            ai_task_completed_24h += 1
        elif event_type in {"task_stopped", "run_stopped", "agent_stopped"}:
            ai_task_stopped_24h += 1

        if event_type in {"auth_prompted", "authorization_requested", "permission_prompted"}:
            human_authorization_requests_24h += 1
        elif event_type in {"auth_approved", "authorization_approved", "permission_granted"}:
            human_authorization_approved_24h += 1
        elif event_type in {"auth_denied", "authorization_denied", "permission_denied"}:
            human_authorization_denied_24h += 1

        if event_type in {"action_confirmed", "confirmed"}:
            human_confirmations_24h += 1
        elif event_type in {"action_skipped", "skip"}:
            human_skips_24h += 1
        elif event_type in {"action_stopped", "stop_requested", "agent_stopped_by_human"}:
            human_stops_24h += 1

        if event_type == "gate_passed":
            gate_total += 1
            gate_passed += 1
        elif event_type == "gate_failed":
            gate_total += 1
        elif event_type == "gate":
            gate_total += 1
            if str(event.get("result") or "").strip().lower() == "passed":
                gate_passed += 1

    interaction_event_types = {
        "auth_prompted",
        "authorization_requested",
        "permission_prompted",
        "auth_approved",
        "authorization_approved",
        "permission_granted",
        "auth_denied",
        "authorization_denied",
        "permission_denied",
        "action_confirmed",
        "confirmed",
        "action_skipped",
        "skip",
        "action_stopped",
        "stop_requested",
        "agent_stopped_by_human",
    }
    correlated_interactions_24h = 0
    for event in events_24h:
        event_type = str(event.get("type") or "")
        if event_type not in interaction_event_types:
            continue
        if str(event.get("interaction_id") or "").strip() or str(event.get("request_id") or "").strip():
            correlated_interactions_24h += 1

    for event in events:
        if str(event.get("type") or "") != "task_completed":
            continue
        task_completed_total += 1
        if str(event.get("objective_id") or "").strip():
            task_completed_with_objective += 1

    gate_pass_rate = int(round((gate_passed / gate_total) * 100)) if gate_total > 0 else 100

    auth_decisions = human_authorization_approved_24h + human_authorization_denied_24h
    authorization_approval_rate_percent = int(round((human_authorization_approved_24h / auth_decisions) * 100)) if auth_decisions > 0 else 100
    pending_authorization_requests_24h = max(0, human_authorization_requests_24h - auth_decisions)

    confirmation_decisions = human_confirmations_24h + human_skips_24h
    human_confirmation_rate_percent = int(round((human_confirmations_24h / confirmation_decisions) * 100)) if confirmation_decisions > 0 else 100

    ai_task_events = ai_task_started_24h + ai_task_completed_24h + ai_task_stopped_24h
    human_interactions_24h = (
        human_authorization_requests_24h
        + human_authorization_approved_24h
        + human_authorization_denied_24h
        + human_confirmations_24h
        + human_skips_24h
        + human_stops_24h
    )
    human_interaction_rate_percent = int(round((human_interactions_24h / max(1, ai_task_events)) * 100)) if ai_task_events > 0 else 0
    ai_task_stop_rate_percent = int(round((ai_task_stopped_24h / max(1, ai_task_events)) * 100)) if ai_task_events > 0 else 0

    behavior_events_total_24h = ai_behavior_events_24h + human_behavior_events_24h + system_behavior_events_24h
    ai_behavior_ratio_percent = int(round((ai_behavior_events_24h / max(1, behavior_events_total_24h)) * 100)) if behavior_events_total_24h > 0 else 0
    human_behavior_ratio_percent = int(round((human_behavior_events_24h / max(1, behavior_events_total_24h)) * 100)) if behavior_events_total_24h > 0 else 0

    resolved_within_sla, resolved_total, unresolved_reviews = _build_review_pairs(events_24h)
    total_review_requests = len([e for e in events_24h if str(e.get("type") or "") == "human_review_requested"])
    if total_review_requests > 0:
        human_response_sla_percent = int(round((resolved_within_sla / total_review_requests) * 100))
    else:
        human_response_sla_percent = 100

    if task_completed_total > 0:
        traceability_coverage_percent = int(round((task_completed_with_objective / task_completed_total) * 100))
    else:
        traceability_coverage_percent = 100

    last_update = parse_iso(str(progress.get("last_update") or ""))
    freshness_penalty = 0
    if last_update is not None:
        stale_minutes = max(0, int((datetime.now(timezone.utc) - last_update).total_seconds() // 60))
        freshness_penalty = min(30, stale_minutes // 3)

    transparency_score = 100
    transparency_score -= freshness_penalty
    transparency_score -= max(0, 20 - min(20, decision_logs_24h * 4))
    transparency_score -= max(0, 20 - min(20, len(events_24h) * 2))
    transparency_score -= max(0, 20 - traceability_coverage_percent // 5)
    transparency_score = max(0, min(100, transparency_score))

    blockers = len(progress.get("blockers") or []) if isinstance(progress.get("blockers"), list) else 0
    failed_checks = int(progress.get("failed_checks", 0))
    regressions = 0
    pipeline = progress.get("pipeline_metrics") if isinstance(progress.get("pipeline_metrics"), dict) else {}
    testing = pipeline.get("testing") if isinstance(pipeline.get("testing"), dict) else {}
    regressions = int(testing.get("regressions", 0))

    controllability_score = 100
    controllability_score -= blockers * 10
    controllability_score -= failed_checks * 7
    controllability_score -= regressions * 8
    controllability_score -= unresolved_reviews * 6
    controllability_score -= max(0, (100 - gate_pass_rate) // 3)
    controllability_score = max(0, min(100, controllability_score))

    objective_defined = bool(str(progress.get("phase") or "").strip() and str(progress.get("task") or "").strip())

    interaction_traceability_percent = int(round((correlated_interactions_24h / max(1, human_interactions_24h)) * 100)) if human_interactions_24h > 0 else 100
    process_observability_score = int(
        round(
            transparency_score * 0.50
            + min(100, len(events_24h) * 5) * 0.20
            + traceability_coverage_percent * 0.30
        )
    )

    development = pipeline.get("development") if isinstance(pipeline.get("development"), dict) else {}
    tasks_planned = max(0, int(development.get("tasks_planned", 0)))
    tasks_done = max(0, int(development.get("tasks_done", 0)))
    tasks_progress_percent = int(round((tasks_done / tasks_planned) * 100)) if tasks_planned > 0 else (100 if objective_defined else 0)
    ai_completion_rate_percent = int(round((ai_task_completed_24h / max(1, ai_task_events)) * 100)) if ai_task_events > 0 else (100 if objective_defined else 0)
    objective_progress_score = int(
        round(
            tasks_progress_percent * 0.50
            + gate_pass_rate * 0.25
            + ai_completion_rate_percent * 0.25
        )
    )

    pending_authorization_penalty = min(20, pending_authorization_requests_24h * 5)
    human_collaboration_quality_score = int(
        round(
            human_response_sla_percent * 0.35
            + authorization_approval_rate_percent * 0.20
            + human_confirmation_rate_percent * 0.20
            + interaction_traceability_percent * 0.25
        )
    ) - pending_authorization_penalty
    human_collaboration_quality_score = max(0, min(100, human_collaboration_quality_score))

    risk_control_score = int(round(controllability_score * 0.70 + max(0, 100 - ai_task_stop_rate_percent) * 0.30))
    overall_governance_score = int(
        round(
            process_observability_score * 0.25
            + objective_progress_score * 0.25
            + human_collaboration_quality_score * 0.25
            + risk_control_score * 0.25
        )
    )

    data_quality_tier = "C"
    if len(events_24h) >= 20 and interaction_traceability_percent >= 80 and decision_logs_24h >= 5:
        data_quality_tier = "A"
    elif len(events_24h) >= 8 and interaction_traceability_percent >= 40:
        data_quality_tier = "B"

    governance_recommendations: list[Dict[str, Any]] = []
    if process_observability_score < 60:
        governance_recommendations.append(
            {
                "dimension": "process_observability",
                "priority": 90,
                "reason": "Process observability is low.",
                "action": "Increase semantic governance events and ensure objective/task traceability tags.",
            }
        )
    if objective_progress_score < 60:
        governance_recommendations.append(
            {
                "dimension": "objective_progress",
                "priority": 88,
                "reason": "Objective progress is weak.",
                "action": "Re-baseline tasks_planned/tasks_done and enforce gate criteria before closure.",
            }
        )
    if human_collaboration_quality_score < 60:
        governance_recommendations.append(
            {
                "dimension": "human_collaboration_quality",
                "priority": 92,
                "reason": "Human collaboration quality is below threshold.",
                "action": "Reduce pending authorization prompts and enforce interaction_id/request_id correlation.",
            }
        )
    if risk_control_score < 60:
        governance_recommendations.append(
            {
                "dimension": "risk_control",
                "priority": 95,
                "reason": "Risk control score is low.",
                "action": "Tighten stop policy and run explicit human review checkpoints for risky operations.",
            }
        )
    if data_quality_tier == "C":
        governance_recommendations.append(
            {
                "dimension": "data_quality",
                "priority": 85,
                "reason": "Evidence quality is insufficient for benchmarking.",
                "action": "Publish richer CI reports and governance interaction events before comparing scores.",
            }
        )

    governance_recommendations.sort(key=lambda item: int(item.get("priority", 0)), reverse=True)

    return {
        "decision_logs_24h": decision_logs_24h,
        "gate_pass_rate_percent": gate_pass_rate,
        "human_response_sla_percent": human_response_sla_percent,
        "review_requests_24h": total_review_requests,
        "unresolved_human_reviews": unresolved_reviews,
        "traceability_coverage_percent": traceability_coverage_percent,
        "transparency_score": transparency_score,
        "controllability_score": controllability_score,
        "objective_defined": objective_defined,
        "events_24h": len(events_24h),
        "ai_task_started_24h": ai_task_started_24h,
        "ai_task_completed_24h": ai_task_completed_24h,
        "ai_task_stopped_24h": ai_task_stopped_24h,
        "ai_task_stop_rate_percent": ai_task_stop_rate_percent,
        "human_authorization_requests_24h": human_authorization_requests_24h,
        "human_authorization_approved_24h": human_authorization_approved_24h,
        "human_authorization_denied_24h": human_authorization_denied_24h,
        "pending_authorization_requests_24h": pending_authorization_requests_24h,
        "authorization_approval_rate_percent": authorization_approval_rate_percent,
        "human_confirmations_24h": human_confirmations_24h,
        "human_skips_24h": human_skips_24h,
        "human_stops_24h": human_stops_24h,
        "human_confirmation_rate_percent": human_confirmation_rate_percent,
        "human_interactions_24h": human_interactions_24h,
        "human_interaction_rate_percent": max(0, min(100, human_interaction_rate_percent)),
        "ai_behavior_events_24h": ai_behavior_events_24h,
        "human_behavior_events_24h": human_behavior_events_24h,
        "system_behavior_events_24h": system_behavior_events_24h,
        "behavior_events_total_24h": behavior_events_total_24h,
        "ai_behavior_ratio_percent": max(0, min(100, ai_behavior_ratio_percent)),
        "human_behavior_ratio_percent": max(0, min(100, human_behavior_ratio_percent)),
        "ai_behavior_type_counts_24h": ai_behavior_type_counts_24h,
        "human_behavior_type_counts_24h": human_behavior_type_counts_24h,
        "system_behavior_type_counts_24h": system_behavior_type_counts_24h,
        "interaction_traceability_percent": max(0, min(100, interaction_traceability_percent)),
        "process_observability_score": max(0, min(100, process_observability_score)),
        "objective_progress_score": max(0, min(100, objective_progress_score)),
        "human_collaboration_quality_score": max(0, min(100, human_collaboration_quality_score)),
        "risk_control_score": max(0, min(100, risk_control_score)),
        "overall_governance_score": max(0, min(100, overall_governance_score)),
        "data_quality_tier": data_quality_tier,
        "governance_recommendations": governance_recommendations[:5],
        "events": events,
    }


def governance_recent_events(project_root: Path, limit: int = 6) -> list[Dict[str, Any]]:
    events = load_governance_events(project_root, limit=max(1, limit))
    return events[:limit]
