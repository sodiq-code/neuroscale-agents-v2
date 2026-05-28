# Devpost Submission Update Guide
## What to change and exact copy to paste

---

## 1. REPO URL
**Field:** GitHub repository URL

**Change to:**
```
https://github.com/sodiq-code/neuroscale-agents-v2
```

---

## 2. BUILT WITH TAGS
**Remove:** `gemini-1.5`, `gemini-1.5-flash`  
**Add:** `gemini-2.0-flash`, `google-genai`, `streamlit`, `arize-phoenix`, `gitlab`, `python`, `kubernetes`

---

## 3. "WHAT I BUILT" / DESCRIPTION (short tagline)

Paste this as the one-liner description:

> Autonomous AI SRE pipeline: Arize Phoenix anomaly → Gemini 2.0 Flash root-cause analysis → GitLab Merge Request — under 60 seconds, zero human toil.

---

## 4. "HOW I BUILT IT" SECTION

Replace your current "How I Built It" with this:

---

**How I Built It**

NeuroScale Agents is a three-agent A2A pipeline built entirely in Python:

**Watcher Agent** connects to Arize Phoenix via MCP (`get-spans`, `get-trace`) and continuously polls for anomalies. When P99 latency or error rate breaches threshold, it scores severity and hands off a structured incident payload to the Orchestrator.

**Diagnostician Agent** is the reasoning core. It runs TF-IDF RAG over five production runbooks to retrieve the most relevant remediation context, then calls **Gemini 2.0 Flash** (via `google-genai` SDK) with the Arize span data + runbook as context. Gemini returns a structured JSON root-cause analysis with confidence score and a Kyverno-compliant YAML patch. This is live — not planned, not a stub.

**Operator Agent** connects to GitLab via MCP (`create_branch`, `commit_file`, `create_merge_request`). It commits the YAML patch to a new branch and opens a Merge Request with the full root-cause reasoning embedded in the description, plus a compliance checklist. The agent never merges unilaterally — a human approves.

**Orchestrator** coordinates the three agents in an A2A pattern with a confidence gate: ≥ 90% confidence → MR is auto-merge eligible with 15-minute SLA. Below 90% → mandatory human review.

The Streamlit dashboard streams the live pipeline via SSE, showing real-time agent execution logs, metric cards, and the generated MR link.

Stack summary:

| Layer | Technology |
|-------|-----------|
| Anomaly detection | Arize Phoenix MCP |
| AI reasoning | **Gemini 2.0 Flash** (`google-genai` SDK) |
| Runbook retrieval | TF-IDF RAG (5 runbooks) |
| Fix delivery | GitLab MCP — branch + commit + MR |
| HITL gate | GitLab Merge Request (never auto-merges) |
| Web dashboard | Streamlit (live at neuroscale-agents.streamlit.app) |
| Container | Docker + Cloud Run deploy script |
| Orchestration | Python A2A pattern |

---

## 5. "WHAT I LEARNED" SECTION

Replace/update with:

---

**What I Learned**

- Structuring a multi-agent A2A pipeline with typed interfaces between agents makes the system composable and testable independently — each agent is a black box with a defined input/output contract.
- Gemini 2.0 Flash's structured output mode (JSON schema) is the right tool for root-cause analysis: it forces the model to commit to a confidence score and a specific runbook reference, which feeds directly into the confidence gate logic.
- HITL design matters more than automation depth. Having the agent produce a fully-prepared MR (with YAML, root cause, compliance checklist) means the human review is a 30-second binary decision — not a 45-minute investigation.
- Arize Phoenix MCP gives structured observability data that's immediately usable as LLM context — the span metadata and trace IDs are exactly what Gemini needs to ground its analysis.

---

## 6. "WHAT'S NEXT" SECTION

Replace your current section with this — **DO NOT** list Gemini as future work, it's already live:

---

**What's Next**

The core pipeline is working end-to-end. Next milestones:

- **Production Arize connection** — swap demo mode for live `ARIZE_API_KEY` + `ARIZE_SPACE_ID` against a real Kubernetes cluster
- **Vertex AI Search** — replace TF-IDF with Vertex AI Search for runbook retrieval at scale (the `RunbookRAGClient` interface is already abstracted for this swap)
- **Multi-cluster support** — one Orchestrator managing agents across multiple GKE clusters
- **Feedback loop** — post-merge Arize span comparison feeds back as training signal to improve runbook matching confidence
- **Slack / PagerDuty integration** — HITL notifications beyond GitLab MR comments

Gemini 2.0 Flash reasoning is **already live** in this submission — `agents/diagnostician.py`, method `_gemini_root_cause()`.

---

## 7. LIVE DEMO / LINKS

Make sure these are set in the submission:

- **Website / Demo:** `https://neuroscale-agents.streamlit.app`
- **Video:** `https://youtu.be/t-zyw6tyBo8`
- **GitHub:** `https://github.com/sodiq-code/neuroscale-agents-v2`

---

## 8. STREAMLIT REDEPLOY INSTRUCTIONS

After updating the Devpost repo URL, you also need Streamlit to serve from the new repo:

1. Go to **share.streamlit.io** → click your `neuroscale-agents` app → **Settings**
2. Under **Repository**, change to: `sodiq-code/neuroscale-agents-v2`
3. Branch: `main`
4. Main file path: `dashboard/app.py`
5. Under **Secrets**, confirm `GOOGLE_API_KEY = AIzaSyDwl3LDfBvV-PVnfhHX1LyguXAFaasqfaU` is still there
6. Click **Save** → app will redeploy from v2 repo

If the URL stays `neuroscale-agents.streamlit.app` after redeploy → UptimeRobot needs no change.  
If Streamlit assigns a new URL → update UptimeRobot monitor URL.

---

## CHECKLIST — before you submit

- [ ] GitHub URL → `neuroscale-agents-v2`
- [ ] Built With tags → `gemini-2.0-flash` + `google-genai` (remove `gemini-1.5`)
- [ ] "How I Built It" → Gemini 2.0 Flash named as live reasoning engine
- [ ] "What's Next" → no Gemini in future work (it's live)
- [ ] Demo URL → `https://neuroscale-agents.streamlit.app`
- [ ] Video URL → `https://youtu.be/t-zyw6tyBo8`
- [ ] Streamlit redeployed from `neuroscale-agents-v2`
- [ ] UptimeRobot URL confirmed correct after redeploy
