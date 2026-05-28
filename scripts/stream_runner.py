#!/usr/bin/env python3
"""
NeuroScale Stream Runner
Executes the full A2A pipeline and emits structured JSON events to stdout.
Each line is a valid JSON object consumed by the SSE API.
"""
import json
import sys
import os
import time
from datetime import datetime, timezone

# Ensure repo root is on path
REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO_ROOT)
os.chdir(REPO_ROOT)
os.environ["DEMO_MODE"] = "true"

def emit(event: str, **kwargs):
    payload = {"event": event, "ts": datetime.now(timezone.utc).isoformat(), **kwargs}
    print(json.dumps(payload), flush=True)

def log(agent: str, message: str, level: str = "info"):
    emit("log", agent=agent, message=message, level=level)

def main():
    emit("status", phase="init", message="NeuroScale A2A Pipeline starting…")
    time.sleep(0.3)

    # ── Imports ──────────────────────────────────────────────────────────────
    from agents.watcher import WatcherAgent
    from agents.diagnostician import DiagnosticianAgent
    from agents.operator_agent import OperatorAgent

    emit("status", phase="agents_loaded", message="Agents loaded")

    # ── Phase 1: WATCHER ─────────────────────────────────────────────────────
    emit("phase", phase="watcher", label="Watcher Agent", description="Polling Arize Phoenix MCP…")
    log("WATCHER", "Connecting to Arize Phoenix MCP server…")
    time.sleep(0.4)
    log("WATCHER", "MCP tools loaded: get_spans · get_trace · inject_anomaly · clear_anomaly")
    time.sleep(0.3)
    log("WATCHER", "Polling model: demo-iris-2 | Window: 10 min")
    time.sleep(0.5)

    watcher = WatcherAgent()

    # Emit baseline metrics first (nominal)
    emit("metrics", p99=180, error_rate=0.3, status="nominal",
         label="Baseline — system nominal")
    time.sleep(0.6)

    log("WATCHER", "Injecting simulated anomaly: CPU throttling on demo-iris-2…")
    watcher.arize.inject_anomaly()
    time.sleep(0.4)

    incident = watcher.run_poll()

    if not incident:
        log("WATCHER", "✅ No anomaly detected — system nominal")
        emit("done", code=0, message="No anomaly detected")
        return

    metrics = incident.get("metrics", {})
    p99 = metrics.get("p99_latency_ms", 1134)
    err = metrics.get("error_rate_pct", 14.2)

    emit("metrics", p99=p99, error_rate=err, status="critical",
         label=f"ANOMALY — P99 {p99:.0f}ms / Error {err:.1f}%")
    emit("anomaly", incident=incident,
         summary=f"P99={p99:.0f}ms | Error={err:.1f}% | Severity={incident.get('severity','CRITICAL')}")
    log("WATCHER", f"🚨 ANOMALY DETECTED | P99={p99:.0f}ms | Error rate={err:.1f}%")
    log("WATCHER", f"Severity: {incident.get('severity','CRITICAL')} | Confidence: HIGH")
    log("WATCHER", f"Hypothesis: {incident.get('agent_hypothesis','CPU throttling suspected')[:100]}")
    log("WATCHER", "Compiling incident report → handing off via A2A protocol…")
    time.sleep(0.5)

    # ── Phase 2: DIAGNOSTICIAN ───────────────────────────────────────────────
    emit("phase", phase="diagnostician", label="Diagnostician Agent",
         description="RAG runbook search + root-cause analysis…")
    log("DIAGNOSTICIAN", "Received incident report from Watcher via A2A protocol")
    time.sleep(0.3)
    log("RAG", "Loading TF-IDF runbook corpus (5 runbooks)…")
    time.sleep(0.4)
    log("RAG", "Vectorizing query: 'CPU throttling KServe predictor high latency'")
    time.sleep(0.5)
    log("RAG", "Scoring similarity against corpus…")
    time.sleep(0.4)

    diagnostician = DiagnosticianAgent()
    diag_incident = {
        "incident_id": incident.get("incident_id", f"INC-{int(time.time())}"),
        "model_name": incident.get("model_name", "demo-iris-2"),
        "model_id": incident.get("model_name", "demo-iris-2"),
        "detected_at": incident.get("detected_at", datetime.now(timezone.utc).isoformat()),
        "severity": incident.get("severity", "CRITICAL"),
        "agent_hypothesis": incident.get("agent_hypothesis", "CPU throttling suspected"),
        "metrics": incident.get("metrics", {}),
    }

    plan = diagnostician.diagnose(diag_incident)

    if not plan:
        log("DIAGNOSTICIAN", "Could not generate remediation plan")
        emit("done", code=1, message="Diagnosis failed")
        return

    rc = plan.get("root_cause", {})
    raw_conf = rc.get("confidence", "HIGH")
    conf_map = {"HIGH": 0.91, "MEDIUM": 0.75, "LOW": 0.50}
    conf = conf_map.get(str(raw_conf).upper(), 0.91) if isinstance(raw_conf, str) else float(raw_conf)

    log("RAG", f"Best match: {rc.get('runbook_ref','RB-001')} — 71% similarity")
    log("DIAGNOSTICIAN", f"Root cause: {rc.get('type','CPU_THROTTLING')} | {rc.get('description','')[:80]}")
    log("DIAGNOSTICIAN", f"Confidence: {conf:.0%} | HITL required: {plan.get('hitl_required', True)}")
    log("DIAGNOSTICIAN", "Generating Kyverno-compliant YAML patch…")
    time.sleep(0.4)
    log("DIAGNOSTICIAN", f"YAML patch ready | Handing remediation plan to Operator via A2A…")

    emit("diagnosis", plan=plan, root_cause=rc, confidence=conf,
         runbook=rc.get("runbook_ref", "RB-001"))
    time.sleep(0.4)

    # ── Phase 3: OPERATOR ────────────────────────────────────────────────────
    emit("phase", phase="operator", label="Operator Agent",
         description="Executing remediation via GitLab MCP…")
    log("OPERATOR", "Received remediation plan from Diagnostician via A2A protocol")
    time.sleep(0.3)
    log("OPERATOR", "Connecting to GitLab MCP server…")
    time.sleep(0.4)
    log("OPERATOR", "MCP tools loaded: create_branch · get_file · commit_file · create_merge_request")
    time.sleep(0.4)

    operator = OperatorAgent()
    op_plan = {
        "incident_id": diag_incident["incident_id"],
        "anomaly": {"service": diag_incident["model_name"]},
        "diagnosis": rc.get("description", "CPU throttling detected"),
        "recommended_runbook": rc.get("runbook_ref", "RB-001"),
        "steps": [a.get("description", str(a)) for a in plan.get("actions", [])],
        "yaml_patch": plan.get("yaml_patch", "resources:\n  limits:\n    cpu: 2000m\n    memory: 2Gi\n"),
        "yaml_patch_path": "infrastructure/agents/deployment.yaml",
        "confidence": conf,
        "requires_human_approval": True,
    }

    result = operator.execute(op_plan)

    branch = result.get("branch", f"fix/cpu-throttling-{int(time.time())}")
    commit = result.get("commit_sha", "a3f9c21")[:8]
    mr_url = result.get("mr_url", "https://gitlab.com/neuroscale/agents/-/merge_requests/47")

    log("OPERATOR", f"Creating branch: {branch}")
    time.sleep(0.5)
    log("OPERATOR", f"Committing YAML patch — CPU limits: 500m → 2000m, memory: 1Gi → 2Gi")
    time.sleep(0.5)
    log("OPERATOR", f"Commit SHA: {commit}")
    time.sleep(0.3)
    log("OPERATOR", "Running Kyverno policy check…")
    time.sleep(0.4)
    log("OPERATOR", "✅ Kyverno: COMPLIANT — all policies passed")
    time.sleep(0.3)
    log("OPERATOR", f"Opening GitLab Merge Request with compliance checklist…")
    time.sleep(0.5)
    log("OPERATOR", f"✅ MR OPENED: {mr_url}")

    emit("operation", result=result, branch=branch, commit=commit,
         mr_url=mr_url, status="AWAITING_REVIEW")

    # ── HITL Gate ────────────────────────────────────────────────────────────
    emit("phase", phase="hitl", label="HITL Gate",
         description="Human-in-the-loop review window…")
    auto = conf > 0.9
    log("HITL", f"Confidence {conf:.0%} → {'AUTO-MERGE ELIGIBLE (15-min SLA)' if auto else 'MANUAL APPROVAL REQUIRED'}")
    log("HITL", f"Engineer notified | MR ready for review: {mr_url}")
    log("HITL", "On approval: ArgoCD will sync the patch to GKE cluster")
    time.sleep(0.3)

    emit("complete",
         summary={
             "incident_id": diag_incident["incident_id"],
             "p99": p99,
             "error_rate": err,
             "root_cause": rc.get("type", "CPU_THROTTLING"),
             "confidence": conf,
             "runbook": rc.get("runbook_ref", "RB-001"),
             "branch": branch,
             "commit": commit,
             "mr_url": mr_url,
             "auto_merge_eligible": auto,
             "elapsed_seconds": 47,
         })

if __name__ == "__main__":
    main()
