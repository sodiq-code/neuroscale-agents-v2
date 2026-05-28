# NeuroScale Agents — Architecture

## Overview

NeuroScale Agents is an **autonomous AI SRE layer** built with Python. Three specialised agents collaborate via an **A2A pipeline pattern** to detect, diagnose, and remediate Kubernetes ML platform incidents — opening a GitLab Merge Request in under 60 seconds.

All agents are stateless Python classes. The Orchestrator calls them sequentially, passing a shared `pipeline_context` dict between phases. In demo mode everything runs in-process with no live credentials.

---

## System Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                    NeuroScale Agents — Agent Layer                  │
│                                                                     │
│  ┌──────────────────────────────────────────────────────────────┐   │
│  │                  A2A Orchestrator                            │   │
│  │              (agents/orchestrator.py)                        │   │
│  └──────────────┬─────────────────┬──────────────┬─────────────┘   │
│                 │                 │              │                  │
│                 ▼                 ▼              ▼                  │
│  ┌──────────────────┐ ┌───────────────────┐ ┌──────────────────┐   │
│  │  Watcher Agent   │ │ Diagnostician     │ │ Operator Agent   │   │
│  │  watcher.py      │ │ Agent             │ │ operator_agent.py│   │
│  │                  │ │ diagnostician.py  │ │                  │   │
│  │  • Poll metrics  │ │ • Root-cause      │ │ • Create branch  │   │
│  │  • Detect anomaly│ │ • TF-IDF RAG      │ │ • Commit YAML    │   │
│  │  • Score severity│ │ • Build plan      │ │ • Open MR        │   │
│  └────────┬─────────┘ └────────┬──────────┘ └────────┬─────────┘   │
│           │                    │                     │              │
└───────────┼────────────────────┼─────────────────────┼─────────────┘
            │                    │                     │
            ▼                    ▼                     ▼
┌───────────────┐   ┌────────────────────┐   ┌─────────────────────┐
│ Arize Phoenix │   │  Runbook RAG Store │   │  GitLab MCP Layer   │
│ MCP Client    │   │  (TF-IDF local /   │   │  REST API v4        │
│ arize_mcp.py  │   │   Vertex AI prod)  │   │  gitlab_mcp.py      │
└───────────────┘   └────────────────────┘   └─────────────────────┘
        │                    │                         │
        ▼                    ▼                         ▼
┌───────────────┐   ┌────────────────────┐   ┌─────────────────────┐
│ Arize Phoenix │   │  /runbooks/*.md    │   │  GitLab.com         │
│ Observability │   │  RB-001…RB-009     │   │  Branch / MR / HITL │
└───────────────┘   └────────────────────┘   └─────────────────────┘
```

---

## Agent Descriptions

### 1. Watcher Agent (`agents/watcher.py`)

**Role:** Continuous anomaly detection  
**Trigger:** Orchestrator loop (configurable `POLL_INTERVAL_SECONDS`)  
**MCP tools used:** `get_spans`, `get_trace`

| Input | Output |
|-------|--------|
| Arize Phoenix span stream | `SpanMetrics` dataclass with `p99_latency_ms`, `error_rate_pct`, `total_spans`, `is_anomalous()` |

**Decision logic:**
- Reads spans from Arize Phoenix via `get_spans`
- Compares `p99_latency_ms` against `LATENCY_P99_THRESHOLD_MS` and `error_rate_pct` against `ERROR_RATE_THRESHOLD_PCT`
- Scores severity: `CRITICAL` / `WARNING` / `INFO`
- Returns empty anomaly list if system nominal (no-op pipeline)

---

### 2. Diagnostician Agent (`agents/diagnostician.py`)

**Role:** Root-cause analysis + remediation planning  
**Trigger:** Watcher output (anomaly report)  
**Tools used:** `RunbookRAGClient` (TF-IDF keyword search over `runbooks/*.md`)

| Input | Output |
|-------|--------|
| Incident dict from Watcher | `RemediationPlan` dict with `root_cause`, `runbook_ref`, `yaml_patch`, `kyverno_constraints`, `actions` |

**Decision logic:**
1. Builds search query from incident metrics and hypothesis
2. Queries `RunbookRAGClient.semantic_search()` — TF-IDF word-overlap scoring against local runbook files
3. Classifies root cause: `CPU_THROTTLING` / `MODEL_DRIFT` / `RESOURCE_EXHAUSTION`
4. Generates concrete Kyverno-compliant YAML patch
5. Sets `hitl_required: true` — agent never merges unilaterally

---

### 3. Operator Agent (`agents/operator_agent.py`)

**Role:** GitOps execution  
**Trigger:** Diagnostician output (remediation plan)  
**MCP tools used:** `create_branch`, `create_or_update_file`, `create_merge_request`, `list_merge_requests`

| Input | Output |
|-------|--------|
| `RemediationPlan` dict | Execution report with `branch`, `commit_sha`, `mr_url`, `status: AWAITING_APPROVAL` |

**Workflow:**
1. `create_branch` → `agent/fix-INC-{id}-{timestamp}`
2. `create_or_update_file` → commits YAML patch with Kyverno compliance metadata
3. `create_merge_request` → opens MR with root-cause analysis, confidence score, Kyverno checklist
4. HITL notification logged — on-call reviews a ready-to-merge fix, not a raw incident

---

## MCP Tool Registry

### Arize Phoenix MCP (`agents/tools/arize_mcp.py`)

| Tool | Description |
|------|-------------|
| `get_spans` | Fetch trace spans for a model; returns `SpanMetrics` with latency + error rate |
| `get_trace` | Get individual trace detail by trace ID |
| `inject_anomaly` | **Demo only** — inject synthetic latency spike for testing |
| `clear_anomaly` | **Demo only** — reset to healthy baseline |

> In production (`DEMO_MODE=false`): set `ARIZE_API_KEY` + `ARIZE_SPACE_ID` in env. Same `get_spans`/`get_trace` interface, real Phoenix API backing.

### GitLab MCP (`agents/tools/gitlab_mcp.py`)

Calls GitLab REST API v4 directly (mirrors `@zereight/mcp-gitlab` tool schema).

| Tool | Description |
|------|-------------|
| `create_branch` | Create feature branch from `main` |
| `create_or_update_file` | Commit file with message |
| `create_merge_request` | Open MR with title, description, labels |
| `list_merge_requests` | List open MRs for the project |

---

## RAG / Runbook Store (`agents/tools/rag_store.py`)

**Demo mode:** Local TF-IDF keyword overlap scoring over `runbooks/*.md`  
**Production:** Vertex AI Search (same `RunbookRAGClient` interface, swap backend via `rag_configured()`)

**How TF-IDF search works:**
1. Loads all `.md` files in `runbooks/` into memory at startup
2. For each query, computes word-set intersection between query tokens and document tokens
3. Scores = `|query_words ∩ doc_words| / |query_words|`
4. Returns top-k results as `RunbookResult` dataclasses

Runbook library:

| ID | Title | Triggers |
|----|-------|---------|
| RB-001 | CPU Throttling — KServe Predictor | `p99_latency_ms > threshold` + `cpu_throttl` hypothesis |
| RB-002 | Model Drift — Rollback Required | `drift` in hypothesis or runbook tags |
| RB-005 | KServe InferenceService Not Ready | OOMKill / readiness failure |
| RB-007 | ArgoCD Sync Recovery | Sync stuck / Unknown state |
| RB-009 | Kyverno Policy Debugging | Policy deny events |

---

## A2A Pipeline Pattern

Agents are stateless Python classes called sequentially by the Orchestrator. No external messaging bus or SDK — state lives in `pipeline_context`.

```python
# agents/orchestrator.py — simplified

orchestrator = NeuroScaleOrchestrator()
watcher      = WatcherAgent()
diagnostician = DiagnosticianAgent()
operator     = OperatorAgent()

# Phase 1
metrics = watcher.watch(model_name)

# Phase 2 (only if anomaly detected)
if metrics.is_anomalous():
    incident = metrics.to_incident_report()
    plan = diagnostician.diagnose(incident)

    # Phase 3
    result = operator.execute(plan)
```

**Pipeline context** (passed through all phases):
```json
{
  "run_id": "RUN-0001-1748188800",
  "started_at": "2026-05-27T10:00:00Z",
  "anomalies": [...],
  "diagnoses": [...],
  "operations": [...],
  "errors": [],
  "status": "REMEDIATED"
}
```

> In production: each agent can be a separate Cloud Run service behind an HTTP endpoint. The orchestrator POSTs to each agent's `/run` endpoint. Same interface, distributed execution.

---

## HITL (Human-in-the-Loop) Gate

The Operator Agent **always** opens a Merge Request and **never** merges unilaterally.

- `hitl_required: true` is set on every remediation plan
- If `confidence >= 0.90` → MR is flagged as auto-merge eligible (15-min review window)
- If `confidence < 0.90` → MR requires mandatory human review before merge
- On-call engineer reviews a fully-prepared fix with root-cause analysis, YAML diff, and compliance checklist

---

## Kyverno-Compliant YAML Generation

Every YAML patch generated by the Diagnostician Agent is built to satisfy the following Kyverno policy constraints (checked in `_check_policy_constraints()`):

| Policy | Constraint |
|--------|-----------|
| `require-standard-labels-inferenceservice` | `owner` + `cost-center` labels mandatory |
| `require-resource-requests-limits` | `cpu`/`memory` requests + limits required |
| `disallow-latest-image-tag` | `:latest` image tag forbidden |
| `disallow-root-containers` | `runAsNonRoot: true` required |
| Namespace ResourceQuota | Total CPU requests ≤ 4 cores, memory ≤ 8Gi |

The MR description includes a full compliance checklist so the human reviewer can verify at a glance.

---

## Configuration (`agents/config.py`)

| Variable | Default | Description |
|----------|---------|-------------|
| `DEMO_MODE` | `true` | Run without live credentials — all API calls simulated |
| `ARIZE_API_KEY` | — | Arize Phoenix API key |
| `ARIZE_SPACE_ID` | — | Arize space ID |
| `GITLAB_TOKEN` | — | GitLab personal access token |
| `GITLAB_PROJECT_ID` | — | Target GitLab project ID |
| `GITLAB_PROJECT_URL` | — | GitLab project web URL |
| `HITL_WEBHOOK_URL` | — | Slack/PagerDuty webhook for on-call notification |
| `POLL_INTERVAL_SECONDS` | `30` | Watcher poll frequency |
| `LATENCY_P99_THRESHOLD_MS` | `500` | P99 latency SLO threshold |
| `ERROR_RATE_THRESHOLD_PCT` | `5.0` | Error rate SLO threshold |
| `CONFIDENCE_GATE` | `0.90` | Auto-merge-eligible confidence floor |

---

## Technology Stack

| Layer | Technology |
|-------|-----------|
| Agent pipeline | Python 3.11 — A2A pattern (Watcher → Diagnostician → Operator) |
| ML observability | Arize Phoenix — `get_spans`, `get_trace` via MCP client |
| GitOps automation | GitLab REST API v4 — `create_branch`, `create_merge_request` |
| Policy compliance | Kyverno — Kyverno-compliant YAML generation + MR checklist |
| RAG (demo) | scikit-learn TF-IDF keyword search over local runbook files |
| RAG (production) | Vertex AI Search (same `RunbookRAGClient` interface) |
| Web dashboard | Streamlit — live at [neuroscale-agents.streamlit.app](https://neuroscale-agents.streamlit.app) |
| Container | Docker / Cloud Run (`deploy/cloud-run.sh`) |
| Kubernetes runtime | GKE + KServe inference serving |
| GitOps deployment | ArgoCD |
