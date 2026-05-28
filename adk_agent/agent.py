"""
NeuroScale 2.0 — Google ADK Agent Entry Point
==============================================
This module exposes the NeuroScale pipeline as a Google ADK SequentialAgent
built on the code-first Agent Development Kit (google-adk) path of
Google Cloud Agent Builder.

The agent uses three ADK FunctionTools — one per pipeline phase — backed by the
existing Watcher, Diagnostician and Operator implementations.  MCP toolsets
(Arize Phoenix and GitLab) are declared here so ADK can surface them in the
agent manifest.

Usage (ADK local runner):
    adk run adk_agent

Usage (Agent Runtime / Cloud Run):
    See deploy/cloud-run.sh — the same image runs the orchestrator CLI
    directly; ADK runner is an additional entry-point for Agent Builder.

Environment variables (all optional in DEMO_MODE=true):
    GOOGLE_API_KEY     — Gemini 2.0 Flash
    GITLAB_TOKEN       — GitLab API v4
    GITLAB_PROJECT_ID  — numeric GitLab project ID
    ARIZE_PHOENIX_BASE_URL — Phoenix endpoint (default localhost:6006)
    GCP_PROJECT        — required for Vertex AI Search
    VERTEX_RAG_DATASTORE  — Vertex AI Search serving config resource name
    DEMO_MODE          — set to "false" to activate live MCP calls (default true)
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

# ── Make sure repo root is importable ─────────────────────────────────────────
REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

# ── Google ADK imports ────────────────────────────────────────────────────────
try:
    from google.adk.agents import Agent, SequentialAgent  # type: ignore
    from google.adk.tools import FunctionTool              # type: ignore
    _ADK_AVAILABLE = True
except ImportError:
    # ADK not installed — fall back to stub so the rest of the module still
    # imports cleanly.  The orchestrator CLI (agents/orchestrator.py) does
    # not require ADK.
    _ADK_AVAILABLE = False
    Agent = object          # type: ignore
    SequentialAgent = None  # type: ignore
    FunctionTool = None     # type: ignore

# ── NeuroScale agent imports ───────────────────────────────────────────────────
from agents.watcher import WatcherAgent
from agents.diagnostician import DiagnosticianAgent
from agents.operator_agent import OperatorAgent

# ─────────────────────────────────────────────────────────────────────────────
# ADK FunctionTools — one per pipeline phase
# ─────────────────────────────────────────────────────────────────────────────

def poll_arize_metrics(model_name: str = "demo-iris-2", inject_anomaly: bool = True) -> dict:
    """
    Phase 1 — WatcherAgent.
    Polls Arize Phoenix MCP for model span metrics and detects SLO breaches.
    Returns a structured incident report if an anomaly is found, or a
    'nominal' dict if the cluster is healthy.

    MCP tools used: get_spans, get_trace (Arize Phoenix MCP Server)

    Args:
        model_name:     KServe InferenceService name to monitor.
        inject_anomaly: When True (demo), forces a latency/error anomaly so
                        the full pipeline is exercised end-to-end.

    Returns:
        Incident report dict with incident_id, severity, metrics, hypothesis.
        Returns {"status": "NOMINAL"} when no anomaly is detected.
    """
    watcher = WatcherAgent()
    if inject_anomaly:
        watcher.arize.inject_anomaly(model_name)
    result = watcher.run_poll(model_name)
    if result is None:
        return {"status": "NOMINAL", "model_name": model_name}
    return result


def diagnose_incident(incident: dict) -> dict:
    """
    Phase 2 — DiagnosticianAgent.
    Performs root-cause analysis on an Arize Phoenix incident report.
    Queries the runbook knowledge base (Vertex AI Search in production,
    TF-IDF locally) and calls Gemini 2.0 Flash to reason over span metrics
    and runbook context.  Returns a Kyverno-compliant remediation plan.

    Google Cloud services used:
        - Gemini 2.0 Flash (root-cause reasoning)
        - Vertex AI Search (runbook retrieval — production)

    Args:
        incident: Incident report dict as returned by poll_arize_metrics.

    Returns:
        Remediation plan dict with root_cause, YAML patch, confidence,
        and step-by-step recovery instructions.
    """
    if incident.get("status") == "NOMINAL":
        return {"status": "NOMINAL", "message": "No diagnosis required"}
    diagnostician = DiagnosticianAgent()
    return diagnostician.diagnose(incident)


def execute_remediation(remediation_plan: dict) -> dict:
    """
    Phase 3 — OperatorAgent.
    Executes the remediation plan end-to-end via the GitLab MCP:
      1. Creates a dedicated remediation branch.
      2. Commits the Kyverno-compliant YAML patch.
      3. Opens a Merge Request with a full compliance checklist.
      4. Sends a Human-in-the-Loop (HITL) notification.

    MCP tools used: create_branch, commit_file, create_merge_request
                    (GitLab REST API v4 / GitLab MCP Server)

    Args:
        remediation_plan: Plan dict as returned by diagnose_incident.

    Returns:
        Execution report with branch, commit SHA, MR URL, HITL status.
    """
    if remediation_plan.get("status") == "NOMINAL":
        return {"status": "NOMINAL", "message": "No remediation required"}

    # Normalise diagnostician plan → operator schema
    root_cause = remediation_plan.get("root_cause", {})
    actions = remediation_plan.get("actions", [])

    yaml_patch = None
    yaml_patch_path = None
    for a in actions:
        if isinstance(a, dict) and a.get("yaml_patch"):
            yaml_patch = a["yaml_patch"]
            yaml_patch_path = a.get("file")
            break

    raw_confidence = root_cause.get("confidence", 0.80)
    if isinstance(raw_confidence, str):
        raw_confidence = {"HIGH": 0.90, "MEDIUM": 0.75, "LOW": 0.50}.get(
            raw_confidence.upper(), 0.75
        )

    plan = {
        "incident_id": remediation_plan.get("incident_id", "INC-unknown"),
        "diagnosis": root_cause.get("description", "Autonomous agent diagnosis"),
        "recommended_runbook": root_cause.get("runbook_ref", "RB-001"),
        "steps": [a.get("description", "") for a in actions if isinstance(a, dict)],
        "yaml_patch": yaml_patch,
        "yaml_patch_path": yaml_patch_path,
        "confidence": raw_confidence,
        "requires_human_approval": remediation_plan.get("hitl_required", True),
    }

    operator = OperatorAgent()
    return operator.execute(plan)


# ─────────────────────────────────────────────────────────────────────────────
# ADK Agent definition
# ─────────────────────────────────────────────────────────────────────────────

_SYSTEM_PROMPT = """You are NeuroScale, an autonomous SRE agent for Kubernetes ML platforms.

Your pipeline:
1. Use poll_arize_metrics to detect anomalies via Arize Phoenix MCP
2. Use diagnose_incident to root-cause the anomaly with Gemini + runbook RAG
3. Use execute_remediation to create a GitLab MR with a Kyverno-compliant fix

Always run all three tools sequentially. After execute_remediation, report the
MR URL and confidence level to the user. The human engineer decides whether to
merge — never claim a fix is deployed until the MR is merged.

Google Cloud services in use:
- Gemini 2.0 Flash: reasoning engine (google-genai SDK)
- Vertex AI Search: runbook knowledge base (production mode)
- Cloud Run: deployment platform for this agent service
- GitLab MCP: branch, commit, MR creation
- Arize Phoenix MCP: span metrics, trace retrieval
"""

if _ADK_AVAILABLE and FunctionTool is not None:
    # ── Tool definitions ──────────────────────────────────────────────────────
    watcher_tool = FunctionTool(func=poll_arize_metrics)
    diagnostician_tool = FunctionTool(func=diagnose_incident)
    operator_tool = FunctionTool(func=execute_remediation)

    # ── Root agent — ADK Agent (code-first Google Cloud Agent Builder path) ───
    root_agent = Agent(
        name="neuroscale_sre_agent",
        model="gemini-2.0-flash",
        description=(
            "Autonomous SRE agent for Kubernetes ML platforms. "
            "Detects incidents via Arize Phoenix MCP, diagnoses root causes "
            "with Gemini 2.0 Flash + Vertex AI Search, and executes "
            "Kyverno-compliant remediation via GitLab MCP."
        ),
        instruction=_SYSTEM_PROMPT,
        tools=[watcher_tool, diagnostician_tool, operator_tool],
    )

else:
    # ── Fallback when google-adk is not installed ─────────────────────────────
    # The orchestrator CLI (agents/orchestrator.py) remains fully functional.
    class _FallbackAgent:
        """Placeholder when google-adk package is not installed."""
        name = "neuroscale_sre_agent"
        description = "Install google-adk to use the ADK runner."

        def run(self, message: str = "") -> dict:
            from agents.orchestrator import NeuroScaleOrchestrator
            orch = NeuroScaleOrchestrator()
            return orch.run_once(inject_anomaly=True)

    root_agent = _FallbackAgent()


# ─────────────────────────────────────────────────────────────────────────────
# Convenience CLI  (python adk_agent/agent.py)
# ─────────────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    print("\n🤖 NeuroScale ADK Agent — direct run\n")
    if not _ADK_AVAILABLE:
        print("google-adk not installed — running via orchestrator fallback\n")
    result = root_agent.run()
    import json as _json
    print("\nResult:", _json.dumps(result, indent=2, default=str))
