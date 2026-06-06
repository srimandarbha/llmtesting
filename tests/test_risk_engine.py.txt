import unittest
from agents.risk_engine import classify_risk, is_action_allowed
from agents.langchain_tools import RemediationIntent

class TestRiskEngine(unittest.TestCase):
    def test_is_action_allowed(self):
        self.assertTrue(is_action_allowed("restart_pod"))
        self.assertTrue(is_action_allowed("scale_deployment"))
        self.assertFalse(is_action_allowed("delete_pvc"))
        self.assertFalse(is_action_allowed("escalate"))

    def test_risk_classification_low_risk(self):
        intent = RemediationIntent(
            action="restart_pod",
            namespace="openshift-monitoring",
            target="prometheus-k8s-0",
            reason="Test",
            confidence=0.95
        )
        self.assertEqual(classify_risk(intent), "LOW")

    def test_risk_classification_high_risk_action(self):
        intent = RemediationIntent(
            action="rollout_restart",
            namespace="default",
            target="my-app",
            reason="Test",
            confidence=0.90
        )
        self.assertEqual(classify_risk(intent), "HIGH")

    def test_risk_classification_low_confidence_escalates(self):
        intent = RemediationIntent(
            action="restart_pod",
            namespace="openshift-monitoring",
            target="prometheus-k8s-0",
            reason="Not sure",
            confidence=0.74
        )
        self.assertEqual(classify_risk(intent), "ESCALATE")

    def test_risk_classification_escalate_action_escalates(self):
        intent = RemediationIntent(
            action="escalate",
            namespace="openshift-monitoring",
            target="prometheus-k8s-0",
            reason="Escalating directly",
            confidence=0.95
        )
        self.assertEqual(classify_risk(intent), "ESCALATE")

    def test_remediation_intent_validation(self):
        # Valid
        intent = RemediationIntent.model_validate_json(
            '{"action": "restart_pod", "namespace": "test", "target": "pod", "reason": "why", "confidence": 0.8}'
        )
        self.assertEqual(intent.action, "restart_pod")

        # Missing fields should raise validation error
        with self.assertRaises(ValueError):
            RemediationIntent.model_validate_json('{"action": "restart_pod"}')

        # Invalid confidence type
        with self.assertRaises(ValueError):
            RemediationIntent.model_validate_json(
                '{"action": "restart_pod", "namespace": "test", "target": "pod", "reason": "why", "confidence": "high"}'
            )

if __name__ == '__main__':
    unittest.main()

