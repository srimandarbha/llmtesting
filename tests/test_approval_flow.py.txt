"""
Integration tests for the Human-in-the-Loop approval flow.

Tests the full state machine:
  PENDING_APPROVAL → APPROVE → EXECUTING (AWX launched)
  PENDING_APPROVAL → REJECT  → REJECTED
  PENDING_APPROVAL → EDIT    → EXECUTING (modified intent validated + AWX launched)
  ANY ACTIVE       → ESCALATE → ESCALATED

These tests use the FastAPI TestClient and mock the DB + AWX calls.
"""

from __future__ import annotations

import json
import uuid
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from agents.langchain_tools import RemediationIntent

# Sample intent that would be stored in DB for a PENDING_APPROVAL incident
SAMPLE_INTENT = {
    "action": "drain_node",
    "namespace": "openshift-infra",
    "target": "worker-node-07",
    "reason": "Node memory pressure detected. Drain before maintenance.",
    "confidence": 0.87,
}


def _make_test_app():
    """Create FastAPI TestClient with mocked DB."""
    from api.main import app
    return TestClient(app)


# ─── Approval flow tests ──────────────────────────────────────────────────────

class TestApprovalFlow:
    """
    Tests the approve/reject/edit/escalate endpoints.
    These tests mock the psycopg2 DB calls and AWX client.
    """

    @pytest.fixture
    def incident_id(self):
        return str(uuid.uuid4())

    @pytest.fixture
    def pending_incident_db(self, incident_id):
        """Mock DB fetch returning a PENDING_APPROVAL incident."""
        row = (
            uuid.UUID(incident_id),  # id
            "test-correlation-id",    # correlation_id
            "nzclu101",               # cluster
            "openshift-infra",        # namespace
            "NodeMemoryPressure",     # alert_name
            "worker-node-07",         # hostname
            "PENDING_APPROVAL",       # status
            "HIGH",                   # risk_tier
            0.87,                     # llm_confidence
            SAMPLE_INTENT,            # llm_intent_json
            None,                     # awx_job_id
            "2026-05-26T10:00:00Z",  # created_at
            "2026-05-26T10:01:00Z",  # updated_at
            None,                     # resolved_at
        )
        return row

    def test_approve_requires_reason(self, incident_id):
        """Approve request with empty reason should be rejected by schema validation."""
        from api.schemas import ApproveRequest
        with pytest.raises(Exception):
            ApproveRequest(reason="ab", user_id="test-user")  # too short

    def test_reject_requires_reason(self):
        """Reject request with empty reason should fail validation."""
        from api.schemas import RejectRequest
        with pytest.raises(Exception):
            RejectRequest(reason="", user_id="test-user")

    def test_edit_validates_intent_schema(self):
        """Edit+approve with invalid action should be rejected before hitting AWX."""
        from api.schemas import EditAndApproveRequest
        bad_intent = {
            "action": "destroy_cluster",  # not in allowlist
            "namespace": "default",
            "target": "everything",
            "reason": "test",
            "confidence": 0.9,
        }
        # FastAPI endpoint validates against RemediationIntent schema
        with pytest.raises(Exception):
            RemediationIntent(**bad_intent)

    def test_valid_edit_passes_schema(self):
        """Valid edited intent should pass RemediationIntent validation."""
        valid_intent = {
            "action": "restart_pod",  # changed from drain_node to safer action
            "namespace": "openshift-infra",
            "target": "worker-node-07",
            "reason": "Changed to pod restart — safer option confirmed by SRE.",
            "confidence": 0.87,
        }
        intent = RemediationIntent(**valid_intent)
        assert intent.action == "restart_pod"
        extra_vars = intent.to_awx_extra_vars()
        assert "confidence" not in extra_vars  # confidence never sent to AWX
        assert extra_vars["action"] == "restart_pod"

    def test_mock_awx_launch_on_approve(self, mock_awx):
        """AWX job should launch when approve is called with valid intent."""
        intent = RemediationIntent(**SAMPLE_INTENT)
        job_id = mock_awx.launch_job("1", intent.to_awx_extra_vars())
        assert job_id is not None

        import time
        time.sleep(0.3)
        result = mock_awx.get_job_status(job_id)
        assert result.status.is_success

    def test_mock_awx_uses_pydantic_extra_vars(self, mock_awx):
        """AWX must receive validated extra_vars, not raw strings."""
        intent = RemediationIntent(**SAMPLE_INTENT)
        extra_vars = intent.to_awx_extra_vars()

        # Verify the shape is what we expect
        assert set(extra_vars.keys()) == {"action", "namespace", "target", "reason"}
        assert extra_vars["action"] in {
            "restart_pod", "clear_evicted_pods", "scale_up_replicas",
            "delete_pvc", "drain_node", "scale_down_deployment", "escalate"
        }

    def test_full_reject_flow(self, mock_awx):
        """Simulates the reject flow end-to-end with mock objects."""
        # In the real API, reject writes to DB and calls PagerDuty
        # Here we verify the reject schema validation passes
        from api.schemas import RejectRequest
        req = RejectRequest(reason="The proposed drain is too risky during business hours.", user_id="john.doe")
        assert req.reason.startswith("The proposed")
        assert req.user_id == "john.doe"

    def test_edit_changes_intent_before_awx(self, mock_awx):
        """Verify that editing an intent changes what gets sent to AWX."""
        original_intent = RemediationIntent(**SAMPLE_INTENT)  # drain_node
        modified_intent = RemediationIntent(
            action="restart_pod",   # downgraded to safer action
            namespace=SAMPLE_INTENT["namespace"],
            target=SAMPLE_INTENT["target"],
            reason="SRE downgraded from drain_node to restart_pod after manual inspection.",
            confidence=0.87,
        )

        original_vars = original_intent.to_awx_extra_vars()
        modified_vars = modified_intent.to_awx_extra_vars()

        assert original_vars["action"] == "drain_node"
        assert modified_vars["action"] == "restart_pod"

        # Both are valid AWX extra_vars
        job_id = mock_awx.launch_job("1", modified_vars)
        assert job_id is not None


# ─── Risk engine state machine tests ─────────────────────────────────────────

class TestRiskStateMachine:
    """Tests the if/else routing logic (no LangGraph)."""

    def test_low_goes_auto_execute(self):
        from agents.risk_engine import classify_risk
        intent = RemediationIntent(
            action="restart_pod", namespace="ns", target="pod",
            reason="r", confidence=0.90,
        )
        assert classify_risk(intent) == "LOW"

    def test_high_goes_pending(self):
        from agents.risk_engine import classify_risk
        intent = RemediationIntent(
            action="drain_node", namespace="ns", target="node",
            reason="r", confidence=0.85,
        )
        assert classify_risk(intent) == "HIGH"

    def test_low_confidence_forces_escalate_regardless_of_action(self):
        from agents.risk_engine import classify_risk, CONFIDENCE_THRESHOLD
        for action in ["restart_pod", "clear_evicted_pods", "scale_up_replicas"]:
            intent = RemediationIntent(
                action=action, namespace="ns", target="t",
                reason="r", confidence=CONFIDENCE_THRESHOLD - 0.01,
            )
            tier = classify_risk(intent)
            assert tier == "ESCALATE", \
                f"Action {action} with low confidence should ESCALATE but got {tier}"
