import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "orchestrator"))

import claim_protocol  # noqa: E402
import response_boundary as rb  # noqa: E402


def result_with(claims, protocol=claim_protocol.PROTOCOL_VERSION):
    return {"claim_verification": {"protocol_version": protocol, "claims": claims}}


def claim(claim_id, claim_type, verification_state):
    return {
        "claim_id": claim_id,
        "claim_type": claim_type,
        "verification_state": verification_state,
    }


class AdmitTest(unittest.TestCase):
    def test_runtime_validated_text_admitted_as_text(self):
        decision = rb.gate_response(result_with([claim("c1", "text", "runtime-validated")]))
        self.assertTrue(decision["admitted"])
        self.assertEqual(decision["claims"][0], {"claim_id": "c1", "decision": "admit", "render_as": "text"})
        self.assertEqual(decision["admitted_count"], 1)
        self.assertEqual(decision["denied_count"], 0)

    def test_interpretation_admitted(self):
        d = rb.gate_response(result_with([claim("c1", "interpretation", "unverified")]))
        self.assertEqual(d["claims"][0]["decision"], "admit")
        self.assertEqual(d["claims"][0]["render_as"], "interpretation")

    def test_unverified_citation_admitted_as_non_supporting(self):
        # A failed [Text] that B2 downgraded is retained, but only as non-supporting.
        d = rb.gate_response(result_with([claim("c1", "unverified-citation", "failed")]))
        self.assertEqual(d["claims"][0]["decision"], "admit")
        self.assertEqual(d["claims"][0]["render_as"], "non-supporting")


class DefaultDenyTest(unittest.TestCase):
    def test_text_without_runtime_validation_is_unstructured_bypass(self):
        d = rb.gate_response(result_with([claim("c1", "text", "unverified")]))
        self.assertEqual(d["claims"][0]["decision"], "deny")
        self.assertEqual(d["claims"][0]["reason"], "unstructured-evidence-bypass")
        self.assertEqual(d["admitted_count"], 0)

    def test_unknown_claim_type_denied(self):
        d = rb.gate_response(result_with([claim("c1", "opinion", "runtime-validated")]))
        self.assertEqual(d["claims"][0]["decision"], "deny")
        self.assertEqual(d["claims"][0]["reason"], "unknown-claim-type")

    def test_missing_verification_is_renderer_bypass(self):
        d = rb.gate_response({})  # no claim_verification at all
        self.assertFalse(d["admitted"])
        self.assertEqual(d["response_denial"], "renderer-bypass")

    def test_unsupported_protocol_denies_response(self):
        d = rb.gate_response(result_with([claim("c1", "text", "runtime-validated")], protocol="religion-council/claim/v9"))
        self.assertFalse(d["admitted"])
        self.assertEqual(d["response_denial"], "unsupported-protocol")


class MixedTest(unittest.TestCase):
    def test_partial_admit_keeps_response_admitted_with_counts(self):
        d = rb.gate_response(
            result_with(
                [
                    claim("c1", "text", "runtime-validated"),  # admit
                    claim("c2", "text", "unverified"),  # deny (bypass)
                    claim("c3", "interpretation", "unverified"),  # admit
                ]
            )
        )
        self.assertTrue(d["admitted"])  # response-level checks passed
        self.assertEqual(d["admitted_count"], 2)
        self.assertEqual(d["denied_count"], 1)
        decisions = {c["claim_id"]: c["decision"] for c in d["claims"]}
        self.assertEqual(decisions, {"c1": "admit", "c2": "deny", "c3": "admit"})

    def test_distinct_from_b1b_and_b2_vocabularies(self):
        # The three rejections stay distinct (ADR 0002 §5): B3 uses decision/reason, never
        # B1b's schema_status or B2's verification_state vocabulary.
        d = rb.gate_response(result_with([claim("c1", "text", "unverified")]))
        denied = d["claims"][0]
        self.assertIn("decision", denied)
        self.assertNotIn("schema_status", denied)
        self.assertNotIn("verification_state", denied)


if __name__ == "__main__":
    unittest.main()
