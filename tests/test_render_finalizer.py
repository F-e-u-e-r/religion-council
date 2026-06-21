import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "orchestrator"))

import claim_binding as cb  # noqa: E402
import render_finalizer as rf  # noqa: E402
from evidence_snapshot import EvidenceStore  # noqa: E402
from render_types import (  # noqa: E402
    AuthorityRenderUnit,
    FinalizationError,
    RenderError,
)

SNAPSHOT = "學而時習之不亦說乎"
QUOTE = "學而時習之"


def make_env():
    """A store + catalog seed (curated published-translation + meaning-rendering) + helpers."""
    store = EvidenceStore(tempfile.mkdtemp())
    artifact_id, _ = store.put_snapshot(SNAPSHOT)
    span = {"byte_offset": 0, "byte_length": len(QUOTE.encode("utf-8"))}
    seed = cb.CatalogSeed(
        seed_id="S1",
        occurrence_id="occ",
        artifact_id=artifact_id,
        source_assurance="artifact-backed",
        artifact_kind="source-text",
        work="論語",
        locator="學而",
        representation_kind="published-translation",
        rendering_mode="meaning-rendering",
        provenance={"translator": "X"},
        rights="short excerpt; test fixture",
    )
    return store, artifact_id, span, cb.EvidenceCatalog([seed])


def make_result(
    *,
    claim_text=QUOTE,
    claim_type="text",
    evidence_type="quotation",
    verification_state="runtime-validated",
    admit=True,
    artifact_id=None,
    span=None,
    declared_representation=None,
    boundary_admitted=True,
    response_denial=None,
):
    edge = {
        "claim_id": "c1",
        "evidence_seed_id": "S1",
        "occurrence_id": "occ",
        "artifact_id": artifact_id,
        "evidentiary_role": "primary-source",
        "evidence_type": evidence_type,
        "verification_state": verification_state,
    }
    if evidence_type == "quotation" and span is not None:
        edge["span"] = span
        edge["span_assurance_tier"] = "curated-snapshot-span-verified"
    claim = {
        "claim_id": "c1",
        "claim_type": claim_type,
        "text": claim_text,
        "verification_state": verification_state,
        "edges": [edge] if claim_type == "text" else [],
    }
    if declared_representation is not None:
        claim["representation_kind"] = declared_representation
    return {
        "claim_verification": {"protocol_version": "religion-council/claim/v1", "claims": [claim]},
        "boundary_decision": {
            "admitted": boundary_admitted,
            "response_denial": response_denial,
            "claims": [{"claim_id": "c1", "decision": "admit" if admit else "deny", "render_as": "text"}],
        },
    }


class MintGuardTest(unittest.TestCase):
    def test_no_supported_public_path_mints_authority_from_raw_prose(self):
        # Negative invariant (capability-shaped API guard, not a sandbox): no SUPPORTED public
        # construction path mints an authority unit from raw text — direct construction without
        # the builder's token raises.
        with self.assertRaises(RenderError):
            AuthorityRenderUnit(
                claim_id="x", render_as="quotation", text="raw prose", attribution="a"
            )

    def test_only_finalizer_produces_authority_units(self):
        # render_finalizer exposes no function that turns arbitrary text into an authority unit;
        # the only producer is _build_authority_unit, which consumes a structured claim.
        store, artifact_id, span, catalog = make_env()
        result = make_result(artifact_id=artifact_id, span=span)
        units = rf.finalize(result, catalog, store.read_snapshot).answer.authority_units
        self.assertEqual(len(units), 1)
        self.assertIsInstance(units[0], AuthorityRenderUnit)


class SurfaceATest(unittest.TestCase):
    def test_quotation_text_is_sourced_from_snapshot_not_producer(self):
        store, artifact_id, span, catalog = make_env()
        # producer text is WRONG; the authority surface must use the snapshot span regardless.
        result = make_result(claim_text="PRODUCER FABRICATION", artifact_id=artifact_id, span=span)
        finalized = rf.finalize(result, catalog, store.read_snapshot)
        unit = finalized.answer.authority_units[0]
        self.assertEqual(unit.text, QUOTE)  # from snapshot span, not "PRODUCER FABRICATION"
        self.assertNotIn("PRODUCER FABRICATION", finalized.surface_a)
        self.assertEqual(unit.span_assurance_tier, "curated-snapshot-span-verified")

    def test_system_authoritative_representation_and_marker(self):
        store, artifact_id, span, catalog = make_env()
        finalized = rf.finalize(make_result(artifact_id=artifact_id, span=span), catalog, store.read_snapshot)
        unit = finalized.answer.authority_units[0]
        self.assertEqual(unit.representation_kind, "published-translation")
        self.assertEqual(unit.rendering_marker, "meaning-rendering")
        self.assertIn("[meaning-rendering]", finalized.surface_a)


class SurfaceBTest(unittest.TestCase):
    def test_interpretation_goes_to_surface_b_not_a(self):
        store, artifact_id, span, catalog = make_env()
        result = make_result(claim_type="interpretation", verification_state="unverified")
        finalized = rf.finalize(result, catalog, store.read_snapshot)
        self.assertEqual(finalized.answer.authority_units, ())
        self.assertEqual(len(finalized.answer.interpretation_units), 1)
        self.assertEqual(finalized.surface_a, "")  # no authority text

    def test_unverified_citation_is_non_supporting_surface_b(self):
        store, artifact_id, span, catalog = make_env()
        result = make_result(claim_type="unverified-citation", verification_state="failed")
        finalized = rf.finalize(result, catalog, store.read_snapshot)
        self.assertEqual(finalized.answer.authority_units, ())
        self.assertEqual(finalized.answer.interpretation_units[0].kind, "unverified-citation")


class RepresentationRuleTest(unittest.TestCase):
    def test_producer_self_downgrade_to_generated_rendering_is_honored(self):
        # No curated metadata on the seed; producer self-labels generated-rendering -> honored + marker.
        store = EvidenceStore(tempfile.mkdtemp())
        artifact_id, _ = store.put_snapshot(SNAPSHOT)
        span = {"byte_offset": 0, "byte_length": len(QUOTE.encode("utf-8"))}
        seed = cb.CatalogSeed(seed_id="S1", occurrence_id="occ", artifact_id=artifact_id,
                              source_assurance="artifact-backed", artifact_kind="source-text", work="論語")
        catalog = cb.EvidenceCatalog([seed])
        result = make_result(artifact_id=artifact_id, span=span, declared_representation="generated-rendering")
        unit = rf.finalize(result, catalog, store.read_snapshot).answer.authority_units[0]
        self.assertEqual(unit.representation_kind, "generated-rendering")
        self.assertEqual(unit.rendering_marker, "generated-rendering")

    def test_producer_self_raise_to_published_translation_is_not_granted(self):
        # No curated metadata; producer claims published-translation -> NOT granted (dropped to None).
        store = EvidenceStore(tempfile.mkdtemp())
        artifact_id, _ = store.put_snapshot(SNAPSHOT)
        span = {"byte_offset": 0, "byte_length": len(QUOTE.encode("utf-8"))}
        seed = cb.CatalogSeed(seed_id="S1", occurrence_id="occ", artifact_id=artifact_id,
                              source_assurance="artifact-backed", artifact_kind="source-text", work="論語")
        catalog = cb.EvidenceCatalog([seed])
        result = make_result(artifact_id=artifact_id, span=span, declared_representation="published-translation")
        unit = rf.finalize(result, catalog, store.read_snapshot).answer.authority_units[0]
        self.assertIsNone(unit.representation_kind)  # producer cannot self-raise authority

    def test_representation_mismatch_against_curated_fails_atomically(self):
        store, artifact_id, span, catalog = make_env()  # seed curated published-translation
        result = make_result(artifact_id=artifact_id, span=span, declared_representation="original-text")
        with self.assertRaises(FinalizationError) as ctx:
            rf.finalize(result, catalog, store.read_snapshot)
        self.assertEqual(ctx.exception.reason, "trace-representation-mismatch")

    def test_invalid_system_representation_metadata_fails_atomically(self):
        store, artifact_id, span, _ = make_env()
        seed = cb.CatalogSeed(
            seed_id="S1",
            occurrence_id="occ",
            artifact_id=artifact_id,
            source_assurance="artifact-backed",
            artifact_kind="source-text",
            work="論語",
            representation_kind="bogus",
            rendering_mode="meaning-rendering",
            rights="short excerpt; test fixture",
        )
        catalog = cb.EvidenceCatalog([seed])
        with self.assertRaises(FinalizationError) as ctx:
            rf.finalize(make_result(artifact_id=artifact_id, span=span), catalog, store.read_snapshot)
        self.assertEqual(ctx.exception.reason, "trace-representation-mismatch")

    def test_curated_presentation_without_rights_is_blocked(self):
        store, artifact_id, span, _ = make_env()
        seed = cb.CatalogSeed(
            seed_id="S1",
            occurrence_id="occ",
            artifact_id=artifact_id,
            source_assurance="artifact-backed",
            artifact_kind="source-text",
            work="論語",
            representation_kind="published-translation",
            rendering_mode="meaning-rendering",
        )
        catalog = cb.EvidenceCatalog([seed])
        with self.assertRaises(FinalizationError) as ctx:
            rf.finalize(make_result(artifact_id=artifact_id, span=span), catalog, store.read_snapshot)
        self.assertEqual(ctx.exception.reason, "trace-rights-blocked")


class DenyAndAtomicityTest(unittest.TestCase):
    def test_denied_claim_goes_to_audit_not_surface_a(self):
        store, artifact_id, span, catalog = make_env()
        result = make_result(artifact_id=artifact_id, span=span, admit=False)
        finalized = rf.finalize(result, catalog, store.read_snapshot)
        self.assertEqual(finalized.answer.authority_units, ())
        self.assertIn("c1", finalized.audit.summary.rejected_claim_ids)

    def test_missing_verification_or_boundary_fails(self):
        store, artifact_id, span, catalog = make_env()
        with self.assertRaises(FinalizationError):
            rf.finalize({"claim_verification": {"claims": []}}, catalog, store.read_snapshot)  # no boundary
        with self.assertRaises(FinalizationError):
            rf.finalize({"boundary_decision": {"admitted": True, "claims": []}}, catalog, store.read_snapshot)  # no verification

    def test_response_level_deny_yields_empty_surface_a(self):
        store, artifact_id, span, catalog = make_env()
        result = make_result(artifact_id=artifact_id, span=span)
        result["boundary_decision"] = {"admitted": False, "response_denial": "renderer-bypass", "claims": []}
        finalized = rf.finalize(result, catalog, store.read_snapshot)
        self.assertEqual(finalized.surface_a, "")
        self.assertIn("renderer-bypass", finalized.audit.summary.reason_codes)

    def test_admitted_text_without_canonical_span_fails_atomically(self):
        store, artifact_id, span, catalog = make_env()
        result = make_result(artifact_id=artifact_id, span=None)  # quotation edge with NO span
        with self.assertRaises(FinalizationError) as ctx:
            rf.finalize(result, catalog, store.read_snapshot)
        self.assertEqual(ctx.exception.reason, "trace-text-not-canonical")

    def test_forged_boundary_render_as_cannot_upgrade_to_authority(self):
        store, artifact_id, span, catalog = make_env()
        result = make_result(artifact_id=artifact_id, span=span)
        result["boundary_decision"]["claims"][0]["render_as"] = "non-supporting"
        with self.assertRaises(FinalizationError) as ctx:
            rf.finalize(result, catalog, store.read_snapshot)
        self.assertEqual(ctx.exception.reason, "trace-render-as-disallowed")

    def test_forged_unvalidated_text_claim_cannot_enter_authority(self):
        store, artifact_id, span, catalog = make_env()
        result = make_result(
            artifact_id=artifact_id,
            span=span,
            verification_state="failed",
        )
        # Hostile persisted artifact: boundary says admit despite failed verification.
        result["boundary_decision"]["claims"][0]["decision"] = "admit"
        with self.assertRaises(FinalizationError) as ctx:
            rf.finalize(result, catalog, store.read_snapshot)
        self.assertEqual(ctx.exception.reason, "trace-claim-not-admitted")

    def test_one_bad_claim_aborts_the_whole_finalization(self):
        # Atomicity: a good claim must not be partially produced when a sibling claim bypasses.
        store, artifact_id, span, catalog = make_env()
        result = make_result(artifact_id=artifact_id, span=span)  # c1 is good
        result["claim_verification"]["claims"].append(
            {
                "claim_id": "c2",
                "claim_type": "text",
                "text": "x",
                "verification_state": "runtime-validated",
                "edges": [
                    {
                        "claim_id": "c2",
                        "evidence_seed_id": "S1",
                        "artifact_id": artifact_id,
                        "evidentiary_role": "primary-source",
                        "evidence_type": "quotation",
                        "verification_state": "runtime-validated",
                    }  # no span -> uncanonicalizable
                ],
            }
        )
        result["boundary_decision"]["claims"].append(
            {"claim_id": "c2", "decision": "admit", "render_as": "text"}
        )
        with self.assertRaises(FinalizationError):
            rf.finalize(result, catalog, store.read_snapshot)

    def test_surface_b_frame_is_constant(self):
        from render_types import INTERPRETATION_FRAME

        store, artifact_id, span, catalog = make_env()
        finalized = rf.finalize(
            make_result(claim_type="interpretation", verification_state="unverified"),
            catalog,
            store.read_snapshot,
        )
        self.assertEqual(finalized.surface_b_frame, INTERPRETATION_FRAME)


class TraceValidatorTest(unittest.TestCase):
    """The real renderer-bypass: re-derive each authority unit and compare; never scan prose."""

    def _legit_unit_and_inputs(self):
        store, artifact_id, span, catalog = make_env()
        result = make_result(artifact_id=artifact_id, span=span)
        finalized = rf.finalize(result, catalog, store.read_snapshot)
        return finalized.answer, result["claim_verification"], result["boundary_decision"], catalog, store

    def test_hostile_request_to_serialize_denied_claim_is_rejected(self):
        answer, verified, boundary, catalog, store = self._legit_unit_and_inputs()
        denied_decisions = {"c1": {"claim_id": "c1", "decision": "deny", "reason": "x"}}
        with self.assertRaises(FinalizationError) as ctx:
            rf.validate_answer_input(answer, verified, denied_decisions, catalog, store.read_snapshot)
        self.assertEqual(ctx.exception.reason, "trace-claim-not-admitted")

    def test_forged_claim_id_is_rejected(self):
        answer, verified, boundary, catalog, store = self._legit_unit_and_inputs()
        verified_no_claim = {"protocol_version": "religion-council/claim/v1", "claims": []}
        decisions = {"c1": {"claim_id": "c1", "decision": "admit"}}
        with self.assertRaises(FinalizationError) as ctx:
            rf.validate_answer_input(answer, verified_no_claim, decisions, catalog, store.read_snapshot)
        self.assertEqual(ctx.exception.reason, "trace-unknown-claim")


class CanonicalUnicodeTest(unittest.TestCase):
    def test_quotation_text_is_canonical_nfc_from_snapshot(self):
        # Serializer and trace validator share ONE source (the snapshot via the same builder), so
        # normalization cannot diverge. The snapshot is canonicalized (NFC); Surface A text is NFC.
        import unicodedata

        store = EvidenceStore(tempfile.mkdtemp())
        decomposed = unicodedata.normalize("NFD", "café試")
        composed = unicodedata.normalize("NFC", decomposed)
        self.assertNotEqual(decomposed, composed)  # the example actually differs by normalization
        artifact_id, _ = store.put_snapshot(decomposed)  # store canonicalizes to NFC
        span = {"byte_offset": 0, "byte_length": len(composed.encode("utf-8"))}
        seed = cb.CatalogSeed(
            seed_id="S1", occurrence_id="o", artifact_id=artifact_id,
            source_assurance="artifact-backed", artifact_kind="source-text", work="W",
        )
        catalog = cb.EvidenceCatalog([seed])
        result = make_result(claim_text="ignored-producer-text", artifact_id=artifact_id, span=span)
        unit = rf.finalize(result, catalog, store.read_snapshot).answer.authority_units[0]
        self.assertEqual(unit.text, composed)  # NFC, sourced from the snapshot span


class SerializerExitTest(unittest.TestCase):
    def test_serializer_only_consumes_authority_units(self):
        # No path turns a plain dict / raw string into a provenance-bearing Surface A line: the
        # serializer reads authority-unit attributes, so a masquerading dict cannot pass.
        from render_types import AnswerRenderInput

        answer = AnswerRenderInput(authority_units=({"render_as": "quotation", "text": "x"},))
        with self.assertRaises(AttributeError):
            rf.serialize_surface_a(answer)


class SurfaceBFrameStateTest(unittest.TestCase):
    def test_finalized_to_state_always_carries_surface_b_frame(self):
        from render_types import INTERPRETATION_FRAME

        store, artifact_id, span, catalog = make_env()
        # denied claim -> empty Surface A, but the non-authoritative frame must still be present
        finalized = rf.finalize(
            make_result(artifact_id=artifact_id, span=span, admit=False), catalog, store.read_snapshot
        )
        state = rf.finalized_to_state(finalized)
        self.assertEqual(state["surface_b_frame"], INTERPRETATION_FRAME)
        self.assertEqual(state["surface_a"], "")  # no verified-looking authority heading
        self.assertNotIn("mint", str(state))  # capability token never serialized


class StrictConfigTest(unittest.TestCase):
    def test_complete_strict_config_passes(self):
        self.assertEqual(
            rf.validate_strict_profile(
                {"structured_claims": True, "verify_claims": True, "fail_closed": True}
            ),
            {"structured_claims": True, "verify_claims": True, "fail_closed": True},
        )

    def test_incomplete_strict_config_fails_fast(self):
        with self.assertRaises(FinalizationError) as ctx:
            rf.validate_strict_profile({"structured_claims": True, "verify_claims": False, "fail_closed": False})
        self.assertEqual(ctx.exception.reason, "strict-config-incomplete")


if __name__ == "__main__":
    unittest.main()
