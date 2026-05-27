"""
Risk tier classification engine.

NON-NEGOTIABLE: LLM NEVER decides risk tier.
Risk tier is determined ONLY by this rule engine based on action type and confidence.
"""

from __future__ import annotations

from typing import Literal

from agents.langchain_tools import RemediationIntent

# ---------------------------------------------------------------------------
# Allowlists — single source of truth for all risk tiers
# ---------------------------------------------------------------------------

LOW_RISK_ACTIONS: frozenset[str] = frozenset(
    {"restart_pod", "clear_evicted_pods", "scale_up_replicas"}
)

HIGH_RISK_ACTIONS: frozenset[str] = frozenset(
    {"delete_pvc", "drain_node", "scale_down_deployment"}
)

# Any action NOT in LOW or HIGH → ESCALATE
# Explicit set for documentation purposes
KNOWN_ACTIONS: frozenset[str] = LOW_RISK_ACTIONS | HIGH_RISK_ACTIONS

CONFIDENCE_THRESHOLD = 0.75  # Below this → ESCALATE immediately, no approval prompt

RiskTier = Literal["LOW", "HIGH", "ESCALATE"]


def classify_risk(intent: RemediationIntent) -> RiskTier:
    """
    Classify the risk tier for a remediation intent.

    Rules (evaluated in order):
    1. Confidence < CONFIDENCE_THRESHOLD → ESCALATE (page oncall, no human prompt)
    2. Action in LOW_RISK_ACTIONS → LOW (auto-execute via AWX)
    3. Action in HIGH_RISK_ACTIONS → HIGH (pause, write PENDING_APPROVAL, wait for human)
    4. Unknown action → ESCALATE

    Returns one of: "LOW", "HIGH", "ESCALATE"
    """
    if intent.confidence < CONFIDENCE_THRESHOLD:
        return "ESCALATE"

    if intent.action in LOW_RISK_ACTIONS:
        return "LOW"

    if intent.action in HIGH_RISK_ACTIONS:
        return "HIGH"

    # Unknown action — never execute
    return "ESCALATE"


def get_risk_reasoning(intent: RemediationIntent, tier: RiskTier) -> str:
    """Return a human-readable explanation of the risk decision."""
    if intent.confidence < CONFIDENCE_THRESHOLD:
        return (
            f"Confidence score {intent.confidence:.2%} is below the "
            f"{CONFIDENCE_THRESHOLD:.0%} threshold. Escalating to oncall "
            f"without human approval prompt."
        )
    if tier == "LOW":
        return (
            f"Action '{intent.action}' is classified as LOW risk. "
            f"Proceeding with automatic AWX execution."
        )
    if tier == "HIGH":
        return (
            f"Action '{intent.action}' is classified as HIGH risk. "
            f"Pausing for human approval before AWX execution."
        )
    return (
        f"Action '{intent.action}' is not in the known action allowlist. "
        f"Escalating to oncall."
    )


def is_action_allowed(action: str) -> bool:
    """Returns True if the action is in the known allowlist."""
    return action in KNOWN_ACTIONS
