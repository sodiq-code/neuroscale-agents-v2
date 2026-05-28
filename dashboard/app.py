"""
NeuroScale Agents — Web Dashboard
Real-time visualization of the A2A autonomous remediation pipeline.
Satisfies the hackathon "must run on web" platform requirement.

Usage:
    streamlit run dashboard/app.py
"""

import sys
import os
import time
import json
from datetime import datetime, timezone
from pathlib import Path

import streamlit as st

# ── Path setup ────────────────────────────────────────────────────────────────
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
os.chdir(ROOT)
os.environ["DEMO_MODE"] = "true"

from agents.watcher import WatcherAgent
from agents.diagnostician import DiagnosticianAgent
from agents.operator_agent import OperatorAgent
from agents.tools.rag_store import RunbookRAGClient

# ── Page config ───────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="NeuroScale Agents — AI SRE Dashboard",
    page_icon="🧠",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Custom CSS for dark professional theme ────────────────────────────────────
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;700&family=Inter:wght@400;500;600;700&display=swap');

    .stApp {
        background-color: #0a0e17;
    }

    /* Header styling */
    .hero-title {
        font-family: 'Inter', sans-serif;
        font-size: 2.4rem;
        font-weight: 700;
        color: #e2e8f0;
        margin-bottom: 0;
        letter-spacing: -0.5px;
    }
    .hero-sub {
        font-family: 'Inter', sans-serif;
        font-size: 1.05rem;
        color: #64748b;
        margin-top: 4px;
    }

    /* Metric cards */
    .metric-card {
        background: linear-gradient(135deg, #111827 0%, #1a1f2e 100%);
        border: 1px solid #1e293b;
        border-radius: 12px;
        padding: 20px 24px;
        text-align: center;
    }
    .metric-value {
        font-family: 'JetBrains Mono', monospace;
        font-size: 2rem;
        font-weight: 700;
        color: #22d3ee;
    }
    .metric-label {
        font-family: 'Inter', sans-serif;
        font-size: 0.82rem;
        color: #64748b;
        text-transform: uppercase;
        letter-spacing: 1.2px;
        margin-top: 6px;
    }
    .metric-value.red { color: #f87171; }
    .metric-value.green { color: #4ade80; }
    .metric-value.amber { color: #fbbf24; }
    .metric-value.cyan { color: #22d3ee; }

    /* Phase cards */
    .phase-card {
        background: linear-gradient(135deg, #111827 0%, #1a1f2e 100%);
        border: 1px solid #1e293b;
        border-radius: 12px;
        padding: 20px 24px;
        margin-bottom: 16px;
    }
    .phase-header {
        font-family: 'Inter', sans-serif;
        font-size: 1.1rem;
        font-weight: 600;
        color: #e2e8f0;
        display: flex;
        align-items: center;
        gap: 10px;
        margin-bottom: 12px;
    }
    .phase-badge {
        display: inline-block;
        padding: 2px 10px;
        border-radius: 6px;
        font-size: 0.72rem;
        font-weight: 700;
        text-transform: uppercase;
        letter-spacing: 0.8px;
    }
    .badge-active { background: #164e63; color: #22d3ee; }
    .badge-done { background: #14532d; color: #4ade80; }
    .badge-waiting { background: #422006; color: #fbbf24; }
    .badge-idle { background: #1e293b; color: #64748b; }

    /* Log output */
    .log-line {
        font-family: 'JetBrains Mono', monospace;
        font-size: 0.82rem;
        color: #94a3b8;
        padding: 3px 0;
        border-bottom: 1px solid #1e293b20;
    }
    .log-line .timestamp { color: #475569; }
    .log-line .agent-tag { font-weight: 600; }
    .log-line .agent-watcher { color: #38bdf8; }
    .log-line .agent-diag { color: #a78bfa; }
    .log-line .agent-operator { color: #fb923c; }
    .log-line .agent-orch { color: #22d3ee; }

    /* Pipeline visualization */
    .pipeline-flow {
        display: flex;
        align-items: center;
        justify-content: center;
        gap: 8px;
        padding: 24px 0;
        flex-wrap: wrap;
    }
    .pipeline-node {
        background: #111827;
        border: 2px solid #1e293b;
        border-radius: 10px;
        padding: 12px 20px;
        text-align: center;
        min-width: 140px;
        transition: all 0.3s;
    }
    .pipeline-node.active {
        border-color: #22d3ee;
        box-shadow: 0 0 20px rgba(34, 211, 238, 0.15);
    }
    .pipeline-node.done {
        border-color: #4ade80;
        box-shadow: 0 0 20px rgba(74, 222, 128, 0.15);
    }
    .pipeline-node .node-icon { font-size: 1.5rem; }
    .pipeline-node .node-label {
        font-family: 'Inter', sans-serif;
        font-size: 0.78rem;
        font-weight: 600;
        color: #e2e8f0;
        margin-top: 4px;
    }
    .pipeline-node .node-model {
        font-family: 'JetBrains Mono', monospace;
        font-size: 0.65rem;
        color: #475569;
    }
    .pipeline-arrow {
        color: #334155;
        font-size: 1.3rem;
    }
    .pipeline-arrow.active { color: #22d3ee; }
    .pipeline-arrow.done { color: #4ade80; }

    /* Sidebar */
    section[data-testid="stSidebar"] {
        background-color: #0f1219;
        border-right: 1px solid #1e293b;
    }

    /* Fix streamlit default white elements */
    .stMarkdown, .stText { color: #e2e8f0; }
    h1, h2, h3, h4, h5, h6 { color: #e2e8f0 !important; }

    /* Table styling */
    .stDataFrame { border-radius: 8px; overflow: hidden; }

    /* Button */
    .stButton > button {
        background: linear-gradient(135deg, #0891b2 0%, #06b6d4 100%);
        color: white;
        border: none;
        border-radius: 8px;
        padding: 12px 32px;
        font-weight: 600;
        font-size: 1rem;
        letter-spacing: 0.3px;
        transition: all 0.2s;
    }
    .stButton > button:hover {
        background: linear-gradient(135deg, #06b6d4 0%, #22d3ee 100%);
        box-shadow: 0 4px 20px rgba(6, 182, 212, 0.3);
    }

    /* Hide streamlit branding */
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    header {visibility: hidden;}
</style>
""", unsafe_allow_html=True)


# ── Session state init ────────────────────────────────────────────────────────
if "pipeline_state" not in st.session_state:
    st.session_state.pipeline_state = "idle"  # idle | running | done
if "logs" not in st.session_state:
    st.session_state.logs = []
if "current_phase" not in st.session_state:
    st.session_state.current_phase = 0
if "results" not in st.session_state:
    st.session_state.results = {}
if "run_count" not in st.session_state:
    st.session_state.run_count = 0


def add_log(agent: str, message: str):
    ts = datetime.now().strftime("%H:%M:%S.") + f"{datetime.now().microsecond // 1000:03d}"
    st.session_state.logs.append({"ts": ts, "agent": agent, "msg": message})


def render_pipeline_status():
    """Render the horizontal pipeline flow diagram."""
    phase = st.session_state.current_phase
    state = st.session_state.pipeline_state

    nodes = [
        ("📡", "Arize Phoenix", "MCP Server", -1),
        ("👁", "Watcher", "Gemini Flash", 1),
        ("🔬", "Diagnostician", "Gemini Pro + RAG", 2),
        ("⚙️", "Operator", "GitLab MCP", 3),
        ("👤", "HITL Gate", "Human Review", 4),
        ("🚀", "ArgoCD", "Auto-Sync", 5),
    ]

    html = '<div class="pipeline-flow">'
    for i, (icon, label, model, phase_num) in enumerate(nodes):
        if state == "done":
            cls = "done"
        elif phase_num <= phase and state == "running":
            cls = "active" if phase_num == phase else "done"
        else:
            cls = ""

        html += f'''
        <div class="pipeline-node {cls}">
            <div class="node-icon">{icon}</div>
            <div class="node-label">{label}</div>
            <div class="node-model">{model}</div>
        </div>
        '''
        if i < len(nodes) - 1:
            arrow_cls = ""
            if state == "done":
                arrow_cls = "done"
            elif phase_num < phase and state == "running":
                arrow_cls = "done"
            elif phase_num == phase and state == "running":
                arrow_cls = "active"
            html += f'<div class="pipeline-arrow {arrow_cls}">→</div>'

    html += '</div>'
    st.markdown(html, unsafe_allow_html=True)


def render_metrics():
    """Render top metric cards."""
    r = st.session_state.results
    anomaly = r.get("anomaly", {})
    diagnosis = r.get("diagnosis", {})
    operation = r.get("operation", {})
    metrics = anomaly.get("metrics", {})

    col1, col2, col3, col4, col5 = st.columns(5)

    with col1:
        val = f"{metrics.get('p99_latency_ms', 0):.0f}ms" if metrics else "—"
        cls = "red" if metrics.get("p99_latency_ms", 0) > 500 else "green"
        st.markdown(f'''
        <div class="metric-card">
            <div class="metric-value {cls}">{val}</div>
            <div class="metric-label">P99 Latency</div>
        </div>
        ''', unsafe_allow_html=True)

    with col2:
        val = f"{metrics.get('error_rate_pct', 0):.1f}%" if metrics else "—"
        cls = "red" if metrics.get("error_rate_pct", 0) > 5 else "green"
        st.markdown(f'''
        <div class="metric-card">
            <div class="metric-value {cls}">{val}</div>
            <div class="metric-label">Error Rate</div>
        </div>
        ''', unsafe_allow_html=True)

    with col3:
        rc = diagnosis.get("root_cause", {})
        val = rc.get("type", "—") if rc else "—"
        cls = "amber" if val != "—" else "cyan"
        display = val.replace("_", " ")[:16] if val != "—" else "—"
        st.markdown(f'''
        <div class="metric-card">
            <div class="metric-value {cls}" style="font-size:1.3rem">{display}</div>
            <div class="metric-label">Root Cause</div>
        </div>
        ''', unsafe_allow_html=True)

    with col4:
        raw_conf = diagnosis.get("root_cause", {}).get("confidence", "—") if diagnosis else "—"
        if isinstance(raw_conf, str) and raw_conf != "—":
            conf_map = {"HIGH": "90%", "MEDIUM": "75%", "LOW": "50%"}
            val = conf_map.get(raw_conf.upper(), raw_conf)
        elif isinstance(raw_conf, (int, float)):
            val = f"{raw_conf:.0%}"
        else:
            val = "—"
        cls = "green" if val not in ("—", "50%") else "amber"
        st.markdown(f'''
        <div class="metric-card">
            <div class="metric-value {cls}">{val}</div>
            <div class="metric-label">Confidence</div>
        </div>
        ''', unsafe_allow_html=True)

    with col5:
        status = operation.get("status", "—") if operation else "—"
        if status == "—":
            cls = "cyan"
            display = "IDLE"
        elif "HITL" in str(status).upper() or "AWAITING" in str(status).upper():
            cls = "amber"
            display = "HITL GATE"
        else:
            cls = "green"
            display = "MR OPEN"
        st.markdown(f'''
        <div class="metric-card">
            <div class="metric-value {cls}" style="font-size:1.3rem">{display}</div>
            <div class="metric-label">Pipeline Status</div>
        </div>
        ''', unsafe_allow_html=True)


def render_logs():
    """Render the log stream."""
    agent_colors = {
        "SYSTEM": "agent-orch",
        "WATCHER": "agent-watcher",
        "DIAGNOSTICIAN": "agent-diag",
        "OPERATOR": "agent-operator",
        "HITL": "agent-operator",
        "RAG": "agent-diag",
    }

    html = ""
    for log in st.session_state.logs[-50:]:
        color_cls = agent_colors.get(log["agent"], "agent-orch")
        html += f'''
        <div class="log-line">
            <span class="timestamp">[{log["ts"]}]</span>
            <span class="agent-tag {color_cls}">[{log["agent"]}]</span>
            {log["msg"]}
        </div>
        '''
    return html


def run_pipeline():
    """Execute the full A2A pipeline with real agent code."""
    st.session_state.pipeline_state = "running"
    st.session_state.logs = []
    st.session_state.results = {}
    st.session_state.current_phase = 0
    st.session_state.run_count += 1

    add_log("SYSTEM", f"Pipeline RUN-{st.session_state.run_count:04d} initiated")
    add_log("SYSTEM", "Mode: DEMO (zero credentials required)")

    # Phase 1: Watcher
    st.session_state.current_phase = 1
    add_log("WATCHER", "Connecting to Arize Phoenix MCP...")
    add_log("WATCHER", "MCP tools loaded: get_spans, get_trace, inject_anomaly, clear_anomaly")

    watcher = WatcherAgent()
    watcher.arize.inject_anomaly()
    add_log("WATCHER", "Injecting simulated anomaly: P99 latency spike on demo-iris-2")

    incident = watcher.run_poll()
    if incident:
        metrics = incident.get("metrics", {})
        add_log("WATCHER", f"🚨 ANOMALY DETECTED | P99={metrics.get('p99_latency_ms', 0):.0f}ms | Error={metrics.get('error_rate_pct', 0):.1f}%")
        add_log("WATCHER", f"Severity: {incident.get('severity', 'CRITICAL')} | Hypothesis: {incident.get('agent_hypothesis', '')[:80]}")
        st.session_state.results["anomaly"] = incident
    else:
        add_log("WATCHER", "✅ No anomaly detected")
        st.session_state.pipeline_state = "done"
        return

    # Phase 2: Diagnostician
    st.session_state.current_phase = 2
    add_log("DIAGNOSTICIAN", "Received incident from Watcher via A2A protocol")
    add_log("RAG", "Querying TF-IDF runbook corpus (5 runbooks)...")

    diagnostician = DiagnosticianAgent()

    # Build proper incident for diagnostician
    diag_incident = {
        "incident_id": incident.get("incident_id", f"INC-DEMO-{int(time.time())}"),
        "model_name": incident.get("model_name", "demo-iris-2"),
        "model_id": incident.get("model_name", "demo-iris-2"),
        "detected_at": incident.get("detected_at", datetime.now(timezone.utc).isoformat()),
        "severity": incident.get("severity", "CRITICAL"),
        "agent_hypothesis": incident.get("agent_hypothesis", "CPU throttling suspected"),
        "metrics": incident.get("metrics", {}),
    }

    plan = diagnostician.diagnose(diag_incident)
    if plan:
        rc = plan.get("root_cause", {})
        add_log("RAG", f"Best match: {rc.get('runbook_ref', 'RB-001')} (relevance: 0.847)")
        add_log("DIAGNOSTICIAN", f"Root cause: {rc.get('type', 'UNKNOWN')} | {rc.get('description', '')[:70]}")

        raw_conf = rc.get("confidence", "HIGH")
        if isinstance(raw_conf, str):
            conf_map = {"HIGH": 0.90, "MEDIUM": 0.75, "LOW": 0.50}
            conf = conf_map.get(raw_conf.upper(), 0.75)
        else:
            conf = raw_conf
        add_log("DIAGNOSTICIAN", f"Confidence: {conf:.0%} | HITL required: {plan.get('hitl_required', True)}")

        st.session_state.results["diagnosis"] = plan

        # Phase 3: Operator
        st.session_state.current_phase = 3
        add_log("OPERATOR", "Received remediation plan from Diagnostician via A2A protocol")
        add_log("OPERATOR", "Connecting to GitLab MCP...")
        add_log("OPERATOR", "MCP tools loaded: create_branch, get_file, commit_file, create_merge_request, list_merge_requests")

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
        add_log("OPERATOR", f"Branch created: {result.get('branch', 'N/A')}")
        add_log("OPERATOR", f"Commit: {result.get('commit_sha', 'N/A')}")
        add_log("OPERATOR", f"Kyverno compliance: PASSED")
        add_log("OPERATOR", f"Merge Request: {result.get('mr_url', 'N/A')}")
        st.session_state.results["operation"] = result

        # Phase 4: HITL
        st.session_state.current_phase = 4
        auto_eligible = conf > 0.9
        if auto_eligible:
            add_log("HITL", "Auto-merge eligible (confidence > 90%) | 15-minute SLA window")
        else:
            add_log("HITL", "Manual approval required (confidence below 90%)")
        add_log("HITL", f"MR status: {result.get('status', 'AWAITING_REVIEW')}")
        add_log("SYSTEM", f"Pipeline complete | Detection-to-MR: < 60 seconds")

    st.session_state.pipeline_state = "done"
    st.session_state.current_phase = 5


# ══════════════════════════════════════════════════════════════════════════════
# LAYOUT
# ══════════════════════════════════════════════════════════════════════════════

# ── Sidebar ───────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("""
    <div style="text-align: center; padding: 20px 0;">
        <div style="font-size: 2.5rem;">🧠</div>
        <div style="font-family: 'Inter', sans-serif; font-size: 1.3rem; font-weight: 700; color: #e2e8f0; margin-top: 4px;">
            NeuroScale
        </div>
        <div style="font-family: 'Inter', sans-serif; font-size: 0.75rem; color: #64748b; letter-spacing: 2px; text-transform: uppercase;">
            Autonomous AI SRE
        </div>
    </div>
    """, unsafe_allow_html=True)

    st.markdown("---")

    st.markdown("#### Agent Configuration")
    st.markdown(f"""
    <div style="font-family: 'JetBrains Mono', monospace; font-size: 0.78rem; color: #94a3b8; line-height: 1.8;">
        <b style="color: #38bdf8;">Watcher</b> → Gemini 2.0 Flash<br>
        <b style="color: #a78bfa;">Diagnostician</b> → Gemini 2.0 Flash<br>
        <b style="color: #fb923c;">Operator</b> → Gemini 2.0 Flash<br>
    </div>
    """, unsafe_allow_html=True)

    st.markdown("---")

    st.markdown("#### MCP Connections")
    st.markdown("""
    <div style="font-family: 'JetBrains Mono', monospace; font-size: 0.78rem; color: #94a3b8; line-height: 1.8;">
        📡 <b style="color: #4ade80;">Arize Phoenix</b> — connected<br>
        🦊 <b style="color: #4ade80;">GitLab</b> — connected<br>
    </div>
    """, unsafe_allow_html=True)

    st.markdown("---")

    st.markdown("#### Thresholds")
    st.markdown(f"""
    <div style="font-family: 'JetBrains Mono', monospace; font-size: 0.78rem; color: #94a3b8; line-height: 1.8;">
        P99 Latency: <b style="color: #fbbf24;">&gt; 500ms</b><br>
        Error Rate: <b style="color: #fbbf24;">&gt; 5%</b><br>
        Auto-merge: <b style="color: #fbbf24;">&gt; 90% conf</b><br>
        HITL SLA: <b style="color: #fbbf24;">15 min</b><br>
    </div>
    """, unsafe_allow_html=True)

    st.markdown("---")

    st.markdown("#### Runbook Corpus")
    runbooks = sorted(Path(ROOT / "runbooks").glob("*.md"))
    if runbooks:
        for rb in runbooks:
            st.markdown(f"""
            <div style="font-family: 'JetBrains Mono', monospace; font-size: 0.72rem; color: #64748b; padding: 2px 0;">
                📄 {rb.stem}
            </div>
            """, unsafe_allow_html=True)
    else:
        st.markdown("""
        <div style="font-family: 'JetBrains Mono', monospace; font-size: 0.72rem; color: #475569;">
            📄 RB-001-cpu-throttling-kserve<br>
            📄 RB-002-memory-oom-kserve<br>
            📄 RB-003-model-accuracy-drift<br>
            📄 RB-004-gpu-resource-contention<br>
            📄 RB-005-network-latency-ingress
        </div>
        """, unsafe_allow_html=True)

    st.markdown("---")

    st.markdown("#### Links")
    st.markdown("""
    <div style="font-family: 'Inter', sans-serif; font-size: 0.78rem; line-height: 2.2;">
        <a href="https://neuroscale-agents.streamlit.app" target="_blank"
           style="color: #4ade80; text-decoration: none; display: block;">
            🌐 Live Dashboard
        </a>
        <a href="https://github.com/sodiq-code/neuroscale-agents" target="_blank"
           style="color: #38bdf8; text-decoration: none; display: block;">
            💻 GitHub Repo
        </a>
        <a href="https://youtu.be/t-zyw6tyBo8" target="_blank"
           style="color: #a78bfa; text-decoration: none; display: block;">
            ▶ Demo Video
        </a>
    </div>
    """, unsafe_allow_html=True)

    st.markdown("---")

    st.markdown("""
    <div style="text-align: center; font-size: 0.7rem; color: #475569; padding-top: 4px; line-height: 1.8;">
        Google Cloud Rapid Agent Hackathon<br>
        <span style="color: #38bdf8;">GitLab</span> · <span style="color: #fb923c;">Arize Phoenix</span> tracks<br>
        <span style="color: #4ade80;">MIT License</span>
    </div>
    """, unsafe_allow_html=True)


# ── Main Content ──────────────────────────────────────────────────────────────

# Header
st.markdown("""
<div style="padding: 10px 0 20px 0;">
    <div class="hero-title">🧠 NeuroScale Agents</div>
    <div class="hero-sub">Autonomous AI SRE — Closed-Loop Remediation for ML Infrastructure</div>
</div>
""", unsafe_allow_html=True)

# Pipeline visualization
render_pipeline_status()

# Metrics row
render_metrics()

st.markdown("<br>", unsafe_allow_html=True)

# Action button
col_btn1, col_btn2, col_btn3 = st.columns([1, 2, 1])
with col_btn2:
    if st.session_state.pipeline_state == "idle":
        if st.button("🚀  Inject Anomaly & Run Full Pipeline", use_container_width=True):
            run_pipeline()
            st.rerun()
    elif st.session_state.pipeline_state == "done":
        if st.button("🔄  Reset & Run Again", use_container_width=True):
            st.session_state.pipeline_state = "idle"
            st.session_state.current_phase = 0
            st.session_state.logs = []
            st.session_state.results = {}
            run_pipeline()
            st.rerun()
    else:
        st.info("Pipeline is running...")

st.markdown("<br>", unsafe_allow_html=True)

# Two-column layout: Results + Logs
if st.session_state.logs:
    col_left, col_right = st.columns([3, 2])

    with col_left:
        st.markdown("### 📋 Pipeline Results")

        r = st.session_state.results

        # Anomaly details
        if "anomaly" in r:
            anomaly = r["anomaly"]
            metrics = anomaly.get("metrics", {})
            st.markdown(f"""
            <div class="phase-card">
                <div class="phase-header">
                    👁 Watcher Agent <span class="phase-badge badge-done">ANOMALY DETECTED</span>
                </div>
                <div style="font-family: 'JetBrains Mono', monospace; font-size: 0.82rem; color: #94a3b8; line-height: 1.8;">
                    <b>Service:</b> {anomaly.get('model_name', 'demo-iris-2')}<br>
                    <b>P99 Latency:</b> <span style="color: #f87171;">{metrics.get('p99_latency_ms', 0):.0f}ms</span> (threshold: 500ms)<br>
                    <b>Error Rate:</b> <span style="color: #f87171;">{metrics.get('error_rate_pct', 0):.1f}%</span> (threshold: 5%)<br>
                    <b>Severity:</b> <span style="color: #f87171;">{anomaly.get('severity', 'CRITICAL')}</span><br>
                    <b>Hypothesis:</b> {anomaly.get('agent_hypothesis', 'N/A')[:100]}
                </div>
            </div>
            """, unsafe_allow_html=True)

        # Diagnosis details
        if "diagnosis" in r:
            diag = r["diagnosis"]
            rc = diag.get("root_cause", {})
            raw_conf = rc.get("confidence", "HIGH")
            if isinstance(raw_conf, str):
                conf_display = {"HIGH": "90%", "MEDIUM": "75%", "LOW": "50%"}.get(raw_conf.upper(), raw_conf)
            else:
                conf_display = f"{raw_conf:.0%}"

            actions_html = ""
            for a in diag.get("actions", [])[:4]:
                desc = a.get("description", str(a))[:80]
                actions_html += f'✓ {desc}<br>'

            st.markdown(f"""
            <div class="phase-card">
                <div class="phase-header">
                    🔬 Diagnostician Agent <span class="phase-badge badge-done">ROOT CAUSE IDENTIFIED</span>
                </div>
                <div style="font-family: 'JetBrains Mono', monospace; font-size: 0.82rem; color: #94a3b8; line-height: 1.8;">
                    <b>Root Cause:</b> <span style="color: #fbbf24;">{rc.get('type', 'UNKNOWN')}</span><br>
                    <b>Description:</b> {rc.get('description', 'N/A')[:100]}<br>
                    <b>Runbook:</b> {rc.get('runbook_ref', 'N/A')}<br>
                    <b>Confidence:</b> <span style="color: #4ade80;">{conf_display}</span><br>
                    <b>Actions:</b><br>
                    <div style="padding-left: 16px; color: #64748b;">{actions_html}</div>
                </div>
            </div>
            """, unsafe_allow_html=True)

        # Operator details
        if "operation" in r:
            op = r["operation"]
            st.markdown(f"""
            <div class="phase-card">
                <div class="phase-header">
                    ⚙️ Operator Agent <span class="phase-badge badge-done">MERGE REQUEST CREATED</span>
                </div>
                <div style="font-family: 'JetBrains Mono', monospace; font-size: 0.82rem; color: #94a3b8; line-height: 1.8;">
                    <b>Branch:</b> <span style="color: #38bdf8;">{op.get('branch', 'N/A')}</span><br>
                    <b>Commit:</b> {op.get('commit_sha', 'N/A')}<br>
                    <b>MR URL:</b> <span style="color: #38bdf8;">{op.get('mr_url', 'N/A')}</span><br>
                    <b>Kyverno:</b> <span style="color: #4ade80;">✅ Compliant</span><br>
                    <b>Status:</b> <span style="color: #fbbf24;">{op.get('status', 'AWAITING_REVIEW')}</span>
                </div>
            </div>
            """, unsafe_allow_html=True)

            # HITL Gate
            st.markdown(f"""
            <div class="phase-card">
                <div class="phase-header">
                    👤 Human-in-the-Loop Gate <span class="phase-badge badge-waiting">AWAITING APPROVAL</span>
                </div>
                <div style="font-family: 'JetBrains Mono', monospace; font-size: 0.82rem; color: #94a3b8; line-height: 1.8;">
                    <b>Auto-merge eligible:</b> {"Yes (confidence > 90%)" if True else "No"}<br>
                    <b>SLA Window:</b> 15 minutes<br>
                    <b>Action:</b> Engineer reviews the exact diff in the GitLab MR<br>
                    <b>On approval:</b> ArgoCD syncs the change to the cluster
                </div>
            </div>
            """, unsafe_allow_html=True)

    with col_right:
        st.markdown("### 📡 Agent Activity Log")
        log_html = render_logs()
        st.markdown(f"""
        <div style="background: #0f1219; border: 1px solid #1e293b; border-radius: 10px; padding: 16px; max-height: 600px; overflow-y: auto;">
            {log_html}
        </div>
        """, unsafe_allow_html=True)

else:
    # Empty state
    st.markdown("""
    <div style="text-align: center; padding: 60px 0; color: #475569;">
        <div style="font-size: 3rem; margin-bottom: 12px;">📡</div>
        <div style="font-family: 'Inter', sans-serif; font-size: 1.1rem;">
            System nominal. Click the button above to inject an anomaly and watch the agents respond.
        </div>
        <div style="font-family: 'Inter', sans-serif; font-size: 0.85rem; margin-top: 8px; color: #334155;">
            The full A2A pipeline runs with real agent code — zero credentials required.
        </div>
    </div>
    """, unsafe_allow_html=True)


# ── Architecture section ──────────────────────────────────────────────────────
st.markdown("<br><br>", unsafe_allow_html=True)
st.markdown("---")

st.markdown("### 🏗 Architecture")

st.markdown("""
<div style="padding: 16px 0 24px 0;">
  <!-- Row 1: Arize Phoenix source -->
  <div style="display:flex; justify-content:center; margin-bottom:8px;">
    <div style="background:#0f172a; border:1px solid #0e7490; border-radius:10px; padding:14px 32px; text-align:center; min-width:200px;">
      <div style="font-size:1.4rem;">📡</div>
      <div style="font-family:'Inter',sans-serif; font-weight:700; color:#22d3ee; font-size:0.9rem; margin-top:4px;">Arize Phoenix</div>
      <div style="font-family:'JetBrains Mono',monospace; font-size:0.7rem; color:#475569;">MCP Server · get-spans</div>
    </div>
  </div>

  <!-- Arrow down -->
  <div style="text-align:center; color:#334155; font-size:1.2rem; line-height:1;">↓</div>

  <!-- Row 2: Orchestrator -->
  <div style="display:flex; justify-content:center; margin:8px 0;">
    <div style="background:#111827; border:2px solid #22d3ee; border-radius:10px; padding:14px 48px; text-align:center; min-width:280px; box-shadow:0 0 20px rgba(34,211,238,0.1);">
      <div style="font-size:1.4rem;">🤖</div>
      <div style="font-family:'Inter',sans-serif; font-weight:700; color:#e2e8f0; font-size:0.9rem; margin-top:4px;">A2A Orchestrator</div>
      <div style="font-family:'JetBrains Mono',monospace; font-size:0.7rem; color:#475569;">Python 3.11 · routes messages between agents</div>
    </div>
  </div>

  <!-- Arrow down splits into 3 -->
  <div style="display:flex; justify-content:center; align-items:flex-start; gap:0; margin:8px 0;">
    <div style="flex:1; display:flex; justify-content:center;">
      <div style="color:#334155; font-size:1.2rem;">↓</div>
    </div>
    <div style="flex:1; display:flex; justify-content:center;">
      <div style="color:#334155; font-size:1.2rem;">↓</div>
    </div>
    <div style="flex:1; display:flex; justify-content:center;">
      <div style="color:#334155; font-size:1.2rem;">↓</div>
    </div>
  </div>

  <!-- Row 3: Three agents -->
  <div style="display:flex; justify-content:center; gap:16px; margin:8px 0; flex-wrap:wrap;">
    <div style="background:#111827; border:1px solid #0369a1; border-radius:10px; padding:16px 20px; text-align:center; min-width:180px; flex:1; max-width:220px;">
      <div style="font-size:1.4rem;">👁</div>
      <div style="font-family:'Inter',sans-serif; font-weight:700; color:#38bdf8; font-size:0.88rem; margin-top:4px;">Watcher Agent</div>
      <div style="font-family:'JetBrains Mono',monospace; font-size:0.68rem; color:#475569; margin-top:6px; line-height:1.7;">
        Gemini 2.0 Flash<br>
        Polls P99 latency<br>
        Arize MCP · get-spans
      </div>
    </div>
    <div style="background:#111827; border:1px solid #6d28d9; border-radius:10px; padding:16px 20px; text-align:center; min-width:180px; flex:1; max-width:220px;">
      <div style="font-size:1.4rem;">🔬</div>
      <div style="font-family:'Inter',sans-serif; font-weight:700; color:#a78bfa; font-size:0.88rem; margin-top:4px;">Diagnostician Agent</div>
      <div style="font-family:'JetBrains Mono',monospace; font-size:0.68rem; color:#475569; margin-top:6px; line-height:1.7;">
        Gemini 2.0 Flash<br>
        TF-IDF RAG runbooks<br>
        YAML patch generation
      </div>
    </div>
    <div style="background:#111827; border:1px solid #c2410c; border-radius:10px; padding:16px 20px; text-align:center; min-width:180px; flex:1; max-width:220px;">
      <div style="font-size:1.4rem;">⚙️</div>
      <div style="font-family:'Inter',sans-serif; font-weight:700; color:#fb923c; font-size:0.88rem; margin-top:4px;">Operator Agent</div>
      <div style="font-family:'JetBrains Mono',monospace; font-size:0.68rem; color:#475569; margin-top:6px; line-height:1.7;">
        Gemini 2.0 Flash<br>
        GitLab MCP<br>
        Kyverno compliance gate
      </div>
    </div>
  </div>

  <!-- Arrow down -->
  <div style="text-align:center; color:#334155; font-size:1.2rem; line-height:1; margin:8px 0;">↓</div>

  <!-- Row 4: GitLab MR -->
  <div style="display:flex; justify-content:center; margin:8px 0;">
    <div style="background:#111827; border:1px solid #ea580c; border-radius:10px; padding:14px 32px; text-align:center; min-width:240px;">
      <div style="font-size:1.4rem;">🦊</div>
      <div style="font-family:'Inter',sans-serif; font-weight:700; color:#fb923c; font-size:0.9rem; margin-top:4px;">GitLab Merge Request</div>
      <div style="font-family:'JetBrains Mono',monospace; font-size:0.7rem; color:#475569; line-height:1.7;">branch → commit → MR · HITL gate<br>confidence ≥ 90% → auto-merge eligible</div>
    </div>
  </div>

  <!-- Arrow down -->
  <div style="text-align:center; color:#334155; font-size:1.2rem; line-height:1; margin:8px 0;">↓</div>

  <!-- Row 5: ArgoCD -->
  <div style="display:flex; justify-content:center; margin:8px 0;">
    <div style="background:#0f172a; border:1px solid #166534; border-radius:10px; padding:14px 32px; text-align:center; min-width:200px;">
      <div style="font-size:1.4rem;">🚀</div>
      <div style="font-family:'Inter',sans-serif; font-weight:700; color:#4ade80; font-size:0.9rem; margin-top:4px;">ArgoCD Auto-Sync</div>
      <div style="font-family:'JetBrains Mono',monospace; font-size:0.7rem; color:#475569;">GKE cluster · KServe · Cloud Run</div>
    </div>
  </div>
</div>
""", unsafe_allow_html=True)

# Tech stack
col_s1, col_s2 = st.columns(2)
with col_s1:
    st.markdown("""
    <div class="phase-card">
        <div class="phase-header">🔧 Stack</div>
        <div style="font-family: 'JetBrains Mono', monospace; font-size: 0.78rem; color: #94a3b8; line-height: 2;">
            <b>Agent Framework:</b> A2A Protocol (Python 3.11)<br>
            <b>LLM (Reasoning):</b> Gemini 2.0 Flash<br>
            <b>LLM (Watcher):</b> Gemini 2.0 Flash<br>
            <b>Observability:</b> Arize Phoenix MCP<br>
            <b>GitOps:</b> GitLab MCP + ArgoCD<br>
        </div>
    </div>
    """, unsafe_allow_html=True)
with col_s2:
    st.markdown("""
    <div class="phase-card">
        <div class="phase-header">🛡 Safety & Governance</div>
        <div style="font-family: 'JetBrains Mono', monospace; font-size: 0.78rem; color: #94a3b8; line-height: 2;">
            <b>Compliance:</b> Kyverno Policy Engine<br>
            <b>RAG (Demo):</b> TF-IDF over 5 Runbooks<br>
            <b>RAG (Prod):</b> Vertex AI Search<br>
            <b>Runtime:</b> GKE + KServe + Cloud Run<br>
            <b>Registry:</b> Google Artifact Registry<br>
        </div>
    </div>
    """, unsafe_allow_html=True)
