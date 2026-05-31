"""
pytest fixtures for integration tests.

Provides:
- mock_llm_response: patches the LLM API with a canned RemediationIntent
- mock_awx_client: injects MockAWXClient
- test_db_conn: psycopg2 connection to a test database (uses env vars)
"""

from __future__ import annotations

import json
import os
import uuid
from unittest.mock import MagicMock, patch

import psycopg2
import pytest
import respx
import httpx

from agents.langchain_tools import RemediationIntent


# ─── Canned LLM response (restart_pod, HIGH risk → PENDING_APPROVAL) ─────────

CANNED_INTENT = RemediationIntent(
    action="restart_pod",
    namespace="openshift-virtualization-operator",
    target="virt-controller-7d9b4f",
    reason="Pod is in CrashLoopBackOff — restart is the standard first action.",
    confidence=0.88,
)

CANNED_INTENT_LOW = RemediationIntent(
    action="restart_pod",     # restart_pod is LOW risk
    namespace="test-ns",
    target="test-pod",
    reason="Test auto-execute path.",
    confidence=0.90,
)


@pytest.fixture
def sample_alert():
    return {
        "alert_name": "SSPOperatorDown",
        "namespace": "openshift-virtualization-operator",
        "cluster": "nzclu101",
        "hostname": "nzclu101.prod.openshift.com",
        "correlation_id": f"nzclu101-test-{uuid.uuid4().hex[:8]}",
    }


@pytest.fixture
def mock_awx():
    """Returns a MockAWXClient with 0% failure rate."""
    from simulation.mock_client import MockAWXClient
    return MockAWXClient(fail_rate=0.0, pending_delay=0.1, run_delay=0.2)


@pytest.fixture
def mock_failing_awx():
    """Returns a MockAWXClient that always fails."""
    from simulation.mock_client import MockAWXClient
    return MockAWXClient(fail_rate=1.0, pending_delay=0.1, run_delay=0.2)


@pytest.fixture
def mock_rag_tools():
    """Patches all DB-hitting tools to return canned responses."""
    with patch("agents.langchain_tools.lookup_runbook") as rl, \
         patch("agents.langchain_tools.get_incident_history") as ih, \
         patch("agents.langchain_tools.get_pod_status") as ps, \
         patch("agents.langchain_tools.query_prometheus") as pq:

        rl.invoke.return_value = json.dumps({
            "alert_name": "SSPOperatorDown",
            "runbook_hits": 1,
            "results": [{"source_id": "RB-001", "excerpt": "Restart the SSP operator pod."}],
        })
        ih.invoke.return_value = json.dumps({
            "cluster": "nzclu101",
            "alert_name": "SSPOperatorDown",
            "weekly_occurrences": 2,
            "reopen_count": 0,
            "resolution_quality_score": 95.0,
        })
        ps.invoke.return_value = json.dumps({
            "pod": "virt-controller",
            "namespace": "openshift-virtualization-operator",
            "phase": "Running",
            "container_statuses": [],
        })
        pq.invoke.return_value = json.dumps({
            "query": "ALERTS{...}",
            "result_count": 1,
            "results": [{"metric": {}, "value": [1, "1"]}],
        })
        yield {"runbook": rl, "history": ih, "pod": ps, "prometheus": pq}


@pytest.fixture
def mock_llm_classify():
    """Patches classify_action to return the canned HIGH-risk intent."""
    with patch("agents.langchain_tools.classify_action") as ca:
        ca.invoke.return_value = CANNED_INTENT.model_dump_json()
        yield ca
