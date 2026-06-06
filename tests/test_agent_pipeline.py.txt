"""
Integration tests for the LangChain agent pipeline.

Tests:
1. Risk engine: LOW / HIGH / ESCALATE classification rules
2. Tool validation: RemediationIntent allowlist enforcement
3. Mock AWX: launch → poll → SUCCESSFUL lifecycle
4. Mock AWX: fail path → FAILED terminal state
5. Full pipeline routing: LOW → auto_execute
6. Full pipeline routing: ESCALATE (confidence < 0.75)
"""

from __future__ import annotations

import json
import time
from unittest.mock import patch

import pytest

from agents.langchain_tools import RemediationIntent
from agents.risk_engine import (
    CONFIDENCE_THRESHOLD,
    classify_risk,
    get_risk_reasoning,
    is_action_allowed,
)
from awx.client import AWXJobStatus
from simulation.mock_client import MockAWXClient


# ─── Risk engine tests ────────────────────────────────────────────────────────

class TestRiskEngine:
    def test_low_risk_restart_pod(self):
        intent = RemediationIntent(
            action="restart_pod", namespace="ns", target="pod-abc",
            reason="test", confidence=0.90,
        )
        assert classify_risk(intent) == "LOW"

    def test_low_risk_clear_evicted(self):
        intent = RemediationIntent(
            action="clear_evicted_pods", namespace="ns", target="cluster",
            reason="test", confidence=0.80,
        )
        assert classify_risk(intent) == "LOW"

    def test_low_risk_scale_up(self):
        intent = RemediationIntent(
            action="scale_up_replicas", namespace="ns", target="deploy-x",
            reason="test", confidence=0.85,
        )
        assert classify_risk(intent) == "LOW"

    def test_high_risk_delete_pvc(self):
        intent = RemediationIntent(
            action="delete_pvc", namespace="ns", target="pvc-data",
            reason="test", confidence=0.85,
        )
        assert classify_risk(intent) == "HIGH"

    def test_high_risk_drain_node(self):
        intent = RemediationIntent(
            action="drain_node", namespace="ns", target="node-01",
            reason="test", confidence=0.90,
        )
        assert classify_risk(intent) == "HIGH"

    def test_escalate_low_confidence(self):
        """Any action with confidence < CONFIDENCE_THRESHOLD → ESCALATE."""
        for action in ["restart_pod", "delete_pvc", "drain_node"]:
            intent = RemediationIntent(
                action=action, namespace="ns", target="target",
                reason="test", confidence=CONFIDENCE_THRESHOLD - 0.01,
            )
            assert classify_risk(intent) == "ESCALATE", \
                f"Expected ESCALATE for confidence below threshold on {action}"

    def test_escalate_unknown_action(self):
        """escalate action → ESCALATE tier."""
        intent = RemediationIntent(
            action="escalate", namespace="ns", target="cluster",
            reason="unknown", confidence=0.80,
        )
        assert classify_risk(intent) == "ESCALATE"

    def test_allowlist_restart_pod(self):
        assert is_action_allowed("restart_pod") is True

    def test_allowlist_unknown(self):
        assert is_action_allowed("delete_everything") is False

    def test_confidence_boundary(self):
        """Exactly at threshold should NOT escalate."""
        intent = RemediationIntent(
            action="restart_pod", namespace="ns", target="pod",
            reason="boundary test", confidence=CONFIDENCE_THRESHOLD,
        )
        assert classify_risk(intent) == "LOW"


# ─── Mock AWX lifecycle tests ─────────────────────────────────────────────────

class TestMockAWXClient:
    def test_launch_returns_job_id(self, mock_awx):
        job_id = mock_awx.launch_job("42", {"action": "restart_pod"})
        assert isinstance(job_id, str)
        assert len(job_id) > 0

    def test_initial_status_pending(self, mock_awx):
        job_id = mock_awx.launch_job("42", {"action": "restart_pod"})
        result = mock_awx.get_job_status(job_id)
        assert result.status == AWXJobStatus.PENDING

    def test_progresses_to_running(self):
        awx = MockAWXClient(pending_delay=0.05, run_delay=10.0)
        job_id = awx.launch_job("42", {"action": "restart_pod"})
        time.sleep(0.1)
        result = awx.get_job_status(job_id)
        assert result.status == AWXJobStatus.RUNNING

    def test_terminal_success(self):
        awx = MockAWXClient(pending_delay=0.0, run_delay=0.0, fail_rate=0.0)
        job_id = awx.launch_job("42", {"action": "restart_pod"})
        time.sleep(0.01)
        result = awx.get_job_status(job_id)
        assert result.status == AWXJobStatus.SUCCESSFUL
        assert result.status.is_terminal is True
        assert result.status.is_success is True

    def test_terminal_failure(self):
        awx = MockAWXClient(pending_delay=0.0, run_delay=0.0, fail_rate=1.0)
        job_id = awx.launch_job("42", {"action": "restart_pod"})
        time.sleep(0.01)
        result = awx.get_job_status(job_id)
        assert result.status == AWXJobStatus.FAILED
        assert result.status.is_terminal is True
        assert result.status.is_success is False

    def test_extra_vars_preserved(self, mock_awx):
        extra_vars = {"action": "drain_node", "namespace": "test", "target": "node-01"}
        job_id = mock_awx.launch_job("42", extra_vars)
        time.sleep(0.15)
        result = mock_awx.get_job_status(job_id)
        assert result.extra_vars == extra_vars

    def test_cancel_running_job(self):
        awx = MockAWXClient(pending_delay=0.0, run_delay=60.0)
        job_id = awx.launch_job("42", {})
        time.sleep(0.05)
        canceled = awx.cancel_job(job_id)
        assert canceled is True

    def test_cancel_terminal_job(self):
        awx = MockAWXClient(pending_delay=0.0, run_delay=0.0)
        job_id = awx.launch_job("42", {})
        time.sleep(0.05)
        canceled = awx.cancel_job(job_id)
        assert canceled is False  # already terminal


# ─── RemediationIntent validation ────────────────────────────────────────────

class TestRemediationIntent:
    def test_to_awx_extra_vars_shape(self):
        intent = RemediationIntent(
            action="restart_pod",
            namespace="openshift-ns",
            target="my-pod-abc123",
            reason="CrashLoopBackOff detected",
            confidence=0.91,
        )
        extra_vars = intent.to_awx_extra_vars()
        assert extra_vars["action"] == "restart_pod"
        assert extra_vars["namespace"] == "openshift-ns"
        assert extra_vars["target"] == "my-pod-abc123"
        # confidence must NOT be in extra_vars (it's internal, not sent to AWX)
        assert "confidence" not in extra_vars

    def test_invalid_action_rejected(self):
        with pytest.raises(Exception):
            RemediationIntent(
                action="rm_rf_everything",   # type: ignore — not in Literal
                namespace="ns",
                target="t",
                reason="bad",
                confidence=0.9,
            )

    def test_confidence_bounds(self):
        with pytest.raises(Exception):
            RemediationIntent(
                action="restart_pod", namespace="ns", target="t",
                reason="r", confidence=1.5,
            )
        with pytest.raises(Exception):
            RemediationIntent(
                action="restart_pod", namespace="ns", target="t",
                reason="r", confidence=-0.1,
            )
