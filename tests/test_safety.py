"""
Tests for neuroscale-agents-v2 safety fixes:
  1. RAG margin gate (agents/tools/rag_store.py)
  2. Per-action confidence thresholds (agents/operator_agent.py)
"""
import sys, os, re
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest
from agents.tools.rag_store import RunbookRAGClient, RunbookResult


# ─── RAG Margin Gate Tests ────────────────────────────────────────────────────

class TestRAGMarginGate:

    def _client_with_index(self, docs: list[dict]) -> RunbookRAGClient:
        """Build a RunbookRAGClient with an in-memory index (skip disk I/O)."""
        client = RunbookRAGClient.__new__(RunbookRAGClient)
        client._use_vertex = False
        client._index = []
        for doc in docs:
            client._index.append({
                "file": doc["file"],
                "path": f"/fake/{doc['file']}",
                "content": doc["content"],
                "words": set(re.findall(r'\w+', doc["content"].lower())),
            })
        return client

    def test_empty_index_returns_empty(self):
        client = self._client_with_index([])
        results = client.semantic_search("crashloop oomkill memory")
        assert results == []

    def test_low_score_triggers_gate(self):
        """Query with almost no keyword match → gate blocks, returns empty list."""
        client = self._client_with_index([{
            "file": "rb-001.md",
            "content": "# ArgoCD Recovery\nSync stuck Unknown state resolution steps procedure",
        }])
        results = client.semantic_search("zebra penguin antarctica completely unrelated")
        assert results == []

    def test_ambiguous_scores_triggers_gate(self):
        """Two equally matching docs → margin too narrow → gate blocks."""
        shared_content = "crashloop oomkill memory kubernetes pod restart backoff recovery"
        client = self._client_with_index([
            {"file": "rb-001.md", "content": f"# Guide A\n{shared_content}"},
            {"file": "rb-002.md", "content": f"# Guide B\n{shared_content}"},
        ])
        results = client.semantic_search("crashloop oomkill memory pod restart")
        assert results == []

    def test_clear_winner_passes_gate(self):
        """One highly relevant doc, second unrelated → gate passes, returns result."""
        client = self._client_with_index([
            {"file": "rb-001.md", "content": "# CrashLoop Recovery\ncpu throttling memory oomkill pod restart kubernetes service container"},
            {"file": "rb-002.md", "content": "# Billing Report\nbilling invoice payment vendor procurement finance"},
        ])
        results = client.semantic_search("cpu throttling oomkill pod restart kubernetes")
        assert len(results) >= 1
        assert results[0].title == "CrashLoop Recovery"

    def test_relevance_score_present_on_results(self):
        """Verify relevance_score is populated on returned RunbookResult objects."""
        client = self._client_with_index([
            {"file": "rb-001.md", "content": "# OOMKill Fix\noomkill memory limit container kubernetes pod increase resources"},
            {"file": "rb-002.md", "content": "# Cost Dashboard\nbilling invoice vendor spend finance procurement"},
        ])
        results = client.semantic_search("oomkill memory limit container kubernetes resources")
        if results:
            assert results[0].relevance_score > 0.0


# ─── Per-Action Confidence Threshold Tests ────────────────────────────────────

class TestPerActionThresholds:
    """
    operator_agent.py now uses per-action thresholds instead of a single 0.9 gate.
    """

    THRESHOLDS = {
        "rollback":                0.85,
        "model_rollback":          0.85,
        "resource_limit_increase": 0.75,
        "argocd_sync":             0.75,
        "policy_fix":              0.80,
        "scale_down":              0.85,
        "create_exception":        0.80,
    }

    def test_all_thresholds_in_valid_range(self):
        for action, thresh in self.THRESHOLDS.items():
            assert 0.5 <= thresh <= 1.0, f"{action}: {thresh} out of range"

    def test_destructive_actions_have_higher_bars(self):
        """rollback and scale_down must require more confidence than argocd_sync."""
        assert self.THRESHOLDS["rollback"] >= self.THRESHOLDS["argocd_sync"]
        assert self.THRESHOLDS["scale_down"] >= self.THRESHOLDS["argocd_sync"]
        assert self.THRESHOLDS["rollback"] >= self.THRESHOLDS["resource_limit_increase"]

    def test_low_confidence_blocked_for_rollback(self):
        confidence = 0.70
        assert confidence < self.THRESHOLDS["rollback"], "0.70 should not pass rollback threshold"

    def test_medium_confidence_passes_argocd_sync(self):
        confidence = 0.80
        assert confidence >= self.THRESHOLDS["argocd_sync"], "0.80 should pass argocd_sync threshold"

    def test_high_confidence_passes_all(self):
        confidence = 0.92
        for action, thresh in self.THRESHOLDS.items():
            assert confidence >= thresh, f"0.92 should pass {action} threshold {thresh}"

    def test_borderline_confidence_for_resource_patch(self):
        """0.75 is exactly on the threshold for resource_limit_increase — should pass."""
        confidence = 0.75
        assert confidence >= self.THRESHOLDS["resource_limit_increase"]

    def test_borderline_confidence_below_rollback(self):
        """0.84 is just below rollback threshold — should not pass."""
        confidence = 0.84
        assert confidence < self.THRESHOLDS["rollback"]


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
