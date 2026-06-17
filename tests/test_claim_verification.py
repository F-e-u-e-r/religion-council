import tempfile
from pathlib import Path
import sys
import unittest


ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "orchestrator"))

import claim_binding as cb  # noqa: E402
import claim_verification as cv  # noqa: E402
from evidence_snapshot import EvidenceStore, EvidenceStoreError  # noqa: E402


def bound_state(text, evidence_type, artifact_id, claim_type="text"):
    """A B1b BoundClaims.to_state() with one claim + one edge pointing at artifact_id."""
    seed = cb.CatalogSeed(
        seed_id="S1",
        occurrence_id="occ-1",
        artifact_id=artifact_id,
        source_assurance="artifact-backed",
        artifact_kind="source-text",
    )
    catalog = cb.EvidenceCatalog([seed])
    payload = {
        "protocol_version": "religion-council/claim/v1",
        "claims": [{"claim_id": "c1", "claim_type": claim_type, "text": text}],
        "edges": (
            []
            if claim_type != "text"
            else [
                {
                    "claim_id": "c1",
                    "evidence_seed_id": "S1",
                    "evidentiary_role": "primary-source",
                    "evidence_type": evidence_type,
                }
            ]
        ),
    }
    return cb.bind_payload(payload, catalog).to_state()


class ReadSnapshotTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.store = EvidenceStore(self.tmp.name)

    def test_round_trips_canonical_bytes(self):
        aid, _ = self.store.put_snapshot("學而時習之")
        self.assertEqual(self.store.read_snapshot(aid).decode("utf-8"), "學而時習之")

    def test_missing_snapshot_raises(self):
        with self.assertRaises(EvidenceStoreError):
            self.store.read_snapshot("a" * 64)

    def test_non_hex_id_rejected_no_traversal(self):
        for bad in ("../etc/passwd", "x" * 64, "abc", "A" * 64):
            with self.assertRaises(EvidenceStoreError):
                self.store.read_snapshot(bad)


class VerifyQuotationTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.store = EvidenceStore(self.tmp.name)

    def test_verbatim_quotation_runtime_validated_with_curated_tier(self):
        aid, _ = self.store.put_snapshot("學而時習之不亦說乎")
        verified = cv.verify_bound_claims(
            bound_state("學而時習之", "quotation", aid), self.store.read_snapshot
        )
        claim = verified["claims"][0]
        self.assertEqual(claim["verification_state"], "runtime-validated")
        self.assertEqual(claim["span_assurance_tier"], "curated-snapshot-span-verified")
        edge = claim["edges"][0]
        self.assertEqual(edge["verification_state"], "runtime-validated")
        self.assertEqual(edge["span"], {"byte_offset": 0, "byte_length": len("學而時習之".encode())})
        self.assertNotIn("removed_edges", claim)

    def test_quotation_not_in_snapshot_fails_and_downgrades(self):
        aid, _ = self.store.put_snapshot("學而時習之不亦說乎")
        verified = cv.verify_bound_claims(
            bound_state("我從未說過這句話", "quotation", aid), self.store.read_snapshot
        )
        claim = verified["claims"][0]
        self.assertEqual(claim["verification_state"], "failed")
        self.assertEqual(claim["claim_type"], "unverified-citation")  # never [Interpretation]
        self.assertEqual(claim["downgraded_from"], "text")
        self.assertEqual(claim["edges"], [])  # failed support edge removed
        self.assertEqual(len(claim["removed_edges"]), 1)  # retained for audit
        self.assertNotIn("span_assurance_tier", claim)

    def test_unreadable_snapshot_fails_edge(self):
        verified = cv.verify_bound_claims(
            bound_state("x", "quotation", "b" * 64), self.store.read_snapshot
        )
        claim = verified["claims"][0]
        self.assertEqual(claim["verification_state"], "failed")
        self.assertIn("unreadable", claim["removed_edges"][0]["verification_detail"])


class VerifySummaryTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.store = EvidenceStore(self.tmp.name)

    def test_summary_validates_without_span_tier(self):
        aid, _ = self.store.put_snapshot("學而時習之不亦說乎")
        verified = cv.verify_bound_claims(
            bound_state("孔子論學習與複習之樂", "source-bound-summary", aid),
            self.store.read_snapshot,
        )
        claim = verified["claims"][0]
        self.assertEqual(claim["verification_state"], "runtime-validated")
        self.assertNotIn("span_assurance_tier", claim)  # paraphrase: no verbatim span
        self.assertNotIn("span", claim["edges"][0])


class B1bOutputUntouchedTest(unittest.TestCase):
    def test_verification_does_not_mutate_input_bindings(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = EvidenceStore(tmp)
            aid, _ = store.put_snapshot("學而時習之")
            bindings = bound_state("學而時習之", "quotation", aid)
            # the initial B1b state: unverified, no span/tier
            self.assertEqual(bindings["claims"][0]["edges"][0]["verification_state"], "unverified")
            cv.verify_bound_claims(bindings, store.read_snapshot)
            # input is unchanged (B2 is additive; B1b's unverified result is preserved)
            self.assertEqual(bindings["claims"][0]["edges"][0]["verification_state"], "unverified")
            self.assertNotIn("span", bindings["claims"][0]["edges"][0])


class NonTextCarriedForwardTest(unittest.TestCase):
    def test_non_text_claim_with_edge_is_not_verified_or_modified(self):
        # B2 validates [Text] only. An [Interpretation] (or unverified-citation) that carries an
        # edge must be carried forward UNCHANGED — its edge is never verified or removed.
        with tempfile.TemporaryDirectory() as tmp:
            store = EvidenceStore(tmp)
            aid, _ = store.put_snapshot("學而時習之")  # does NOT contain the claim text below
            seed = cb.CatalogSeed(
                seed_id="S1",
                occurrence_id="occ",
                artifact_id=aid,
                source_assurance="artifact-backed",
                artifact_kind="source-text",
            )
            catalog = cb.EvidenceCatalog([seed])
            payload = {
                "protocol_version": "religion-council/claim/v1",
                "claims": [{"claim_id": "c1", "claim_type": "interpretation", "text": "我的推論"}],
                "edges": [
                    {
                        "claim_id": "c1",
                        "evidence_seed_id": "S1",
                        "evidentiary_role": "secondary-source",
                        "evidence_type": "quotation",
                    }
                ],
            }
            bound = cb.bind_payload(payload, catalog).to_state()
            verified = cv.verify_bound_claims(bound, store.read_snapshot)
            claim = verified["claims"][0]
            self.assertEqual(claim["claim_type"], "interpretation")  # not downgraded
            self.assertEqual(claim["verification_state"], "unverified")  # not verified
            self.assertEqual(len(claim["edges"]), 1)  # edge NOT removed despite no span match
            self.assertNotIn("removed_edges", claim)
            self.assertNotIn("span_assurance_tier", claim)
            self.assertEqual(cv.verification_summary(verified)["runtime_validated"], 0)


class VerificationSummaryTest(unittest.TestCase):
    def test_counts(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = EvidenceStore(tmp)
            aid, _ = store.put_snapshot("學而時習之")
            ok = cv.verify_bound_claims(bound_state("學而時習之", "quotation", aid), store.read_snapshot)
            self.assertEqual(
                cv.verification_summary(ok),
                {"claims": 1, "runtime_validated": 1, "failed": 0, "downgraded": 0},
            )
            bad = cv.verify_bound_claims(bound_state("無此句", "quotation", aid), store.read_snapshot)
            self.assertEqual(
                cv.verification_summary(bad),
                {"claims": 1, "runtime_validated": 0, "failed": 1, "downgraded": 1},
            )


if __name__ == "__main__":
    unittest.main()
