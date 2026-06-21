import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "orchestrator"))

import assurance_footer as af  # noqa: E402
import claim_binding as cb  # noqa: E402
import policy_enums  # noqa: E402
import render_finalizer as rf  # noqa: E402
from evidence_snapshot import EvidenceStore  # noqa: E402

CURATED = af.CURATED_SNAPSHOT_TIER
EDITION = af.EDITION_BACKED_TIER


def quotation_unit(tier=CURATED, representation="published-translation"):
    return {
        "claim_id": "c",
        "render_as": "quotation",
        "text": "…",
        "attribution": "W",
        "representation_kind": representation,
        "rendering_marker": None,
        "span_assurance_tier": tier,
        "provenance": None,
    }


def summary_unit():
    return {
        "claim_id": "s",
        "render_as": "source-bound-summary",
        "text": "paraphrase",
        "attribution": "W",
        "representation_kind": None,
        "rendering_marker": None,
        "span_assurance_tier": None,
        "provenance": None,
    }


def make_state(authority=(), interpretation=(), rejected=(), reason_codes=()):
    return {
        "surface_a": "",
        "surface_b_frame": "Council interpretation — not source text",
        "answer": {
            "authority_units": list(authority),
            "interpretation_units": [
                {"speaker_id": "p", "content": c, "based_on_claim_ids": [], "kind": "interpretation"}
                for c in interpretation
            ],
        },
        "audit": {"rejected_claim_ids": list(rejected), "reason_codes": list(reason_codes)},
    }


class TierConstantsTest(unittest.TestCase):
    def test_tier_ids_are_canonical_policy_enums(self):
        # Drift guard: the footer's tier ids must be the manifest's span_assurance_tiers.
        self.assertIn(CURATED, policy_enums.SPAN_ASSURANCE_TIERS)
        self.assertIn(EDITION, policy_enums.SPAN_ASSURANCE_TIERS)


class CountInvariantTest(unittest.TestCase):
    def test_buckets_are_exhaustive_over_authority_units(self):
        state = make_state(
            authority=[quotation_unit(CURATED), quotation_unit(EDITION), quotation_unit(None), summary_unit()]
        )
        c = af.summarize_finalized(state)
        self.assertEqual(
            c["curated_snapshot_span_verified"]
            + c["edition_backed_span_verified"]
            + c["span_unverified_quotation"]
            + c["source_bound_summaries"],
            c["textual_claims_rendered"],
        )


class ConciseFooterTest(unittest.TestCase):
    def test_zero_authority_units(self):
        footer = af.render_assurance_footer(make_state(interpretation=["only analysis"]))
        self.assertIn("Textual claims rendered: 0", footer)
        self.assertIn("Curated snapshot-span verified: 0", footer)
        self.assertIn("Source-bound summaries: 0", footer)
        self.assertIn("Denied claims: 0", footer)

    def test_one_authority_unit(self):
        footer = af.render_assurance_footer(make_state(authority=[quotation_unit(CURATED)]))
        self.assertIn("Textual claims rendered: 1", footer)
        self.assertIn("Curated snapshot-span verified: 1", footer)

    def test_multiple_units_matches_plan_example_shape(self):
        state = make_state(
            authority=[quotation_unit(CURATED), quotation_unit(CURATED), summary_unit()],
            rejected=["d1", "d2"],
        )
        footer = af.render_assurance_footer(state)
        self.assertIn("Textual claims rendered: 3", footer)
        self.assertIn("Curated snapshot-span verified: 2", footer)
        self.assertIn("Source-bound summaries: 1", footer)
        self.assertIn("Denied claims: 2", footer)

    def test_all_denied_case(self):
        footer = af.render_assurance_footer(make_state(rejected=["c1", "c2", "c3"]))
        self.assertIn("Textual claims rendered: 0", footer)
        self.assertIn("Denied claims: 3", footer)

    def test_interpretation_limitation_always_visible(self):
        # Present even when there is nothing else to say.
        for state in (make_state(), make_state(authority=[quotation_unit()]), make_state(rejected=["x"])):
            self.assertIn(
                "Interpretation: non-authoritative / instruction-bounded",
                af.render_assurance_footer(state),
            )

    def test_mode_line_present(self):
        self.assertIn("Mode: strict-finalized", af.render_assurance_footer(make_state()))


class NoAccidentalEditionBackedTest(unittest.TestCase):
    def test_curated_unit_is_never_labeled_edition_backed(self):
        footer = af.render_assurance_footer(make_state(authority=[quotation_unit(CURATED)]))
        self.assertNotIn("Edition-backed", footer)
        self.assertIn("Curated snapshot-span verified: 1", footer)

    def test_edition_line_appears_only_when_present(self):
        absent = af.render_assurance_footer(make_state(authority=[quotation_unit(CURATED)]))
        self.assertNotIn("Edition-backed span verified", absent)
        present = af.render_assurance_footer(make_state(authority=[quotation_unit(EDITION)]))
        self.assertIn("Edition-backed span verified: 1", present)

    def test_anomalous_untiered_quotation_is_not_counted_as_verified(self):
        footer = af.render_assurance_footer(make_state(authority=[quotation_unit(None)]))
        self.assertIn("Curated snapshot-span verified: 0", footer)
        self.assertIn("Quotation span not verified: 1", footer)


class DeterminismTest(unittest.TestCase):
    def test_output_is_stable(self):
        state = make_state(
            authority=[quotation_unit(CURATED), summary_unit()], rejected=["d"], reason_codes=["renderer-bypass"]
        )
        self.assertEqual(
            af.render_assurance_footer(state, expanded=True),
            af.render_assurance_footer(state, expanded=True),
        )

    def test_representation_breakdown_is_sorted(self):
        state = make_state(
            authority=[quotation_unit(CURATED, "published-translation"), quotation_unit(CURATED, "original-text")]
        )
        expanded = af.render_assurance_footer(state, expanded=True)
        self.assertIn("representation kinds: original-text=1, published-translation=1", expanded)


class ExpandedViewTest(unittest.TestCase):
    def test_expanded_shows_reason_codes_but_concise_does_not(self):
        state = make_state(reason_codes=["renderer-bypass"])
        self.assertNotIn("renderer-bypass", af.render_assurance_footer(state))
        self.assertIn("renderer-bypass", af.render_assurance_footer(state, expanded=True))


class EndToEndTest(unittest.TestCase):
    """Footer must consume the real finalizer output, not just hand-built dicts."""

    def _finalized_state(self, **kwargs):
        store = EvidenceStore(tempfile.mkdtemp())
        snapshot, quote = "學而時習之不亦說乎", "學而時習之"
        artifact_id, _ = store.put_snapshot(snapshot)
        span = {"byte_offset": 0, "byte_length": len(quote.encode("utf-8"))}
        seed = cb.CatalogSeed(
            seed_id="S1", occurrence_id="occ", artifact_id=artifact_id,
            source_assurance="artifact-backed", artifact_kind="source-text", work="論語", locator="學而",
            representation_kind="published-translation", rendering_mode="meaning-rendering",
            provenance={"translator": "X"}, rights="short excerpt; test fixture",
        )
        catalog = cb.EvidenceCatalog([seed])
        edge = {
            "claim_id": "c1", "evidence_seed_id": "S1", "occurrence_id": "occ", "artifact_id": artifact_id,
            "evidentiary_role": "primary-source", "evidence_type": "quotation",
            "verification_state": "runtime-validated", "span": span,
            "span_assurance_tier": "curated-snapshot-span-verified",
        }
        claim = {
            "claim_id": "c1", "claim_type": "text", "text": "學而時習之",
            "verification_state": "runtime-validated", "edges": [edge],
        }
        result = {
            "claim_verification": {"protocol_version": "religion-council/claim/v1", "claims": [claim]},
            "boundary_decision": {
                "admitted": kwargs.get("admitted", True),
                "response_denial": kwargs.get("response_denial"),
                "claims": [{"claim_id": "c1", "decision": kwargs.get("decision", "admit"), "render_as": "text"}],
            },
        }
        finalized = rf.finalize(result, catalog, store.read_snapshot)
        return rf.finalized_to_state(finalized)

    def test_real_admitted_finalized_state(self):
        footer = af.render_assurance_footer(self._finalized_state())
        self.assertIn("Textual claims rendered: 1", footer)
        self.assertIn("Curated snapshot-span verified: 1", footer)
        # B2 only ever mints the curated-snapshot tier, so a real finalized unit is never
        # shown as edition-backed.
        self.assertNotIn("Edition-backed span verified", footer)

    def test_real_denied_finalized_state(self):
        state = self._finalized_state(decision="deny")
        footer = af.render_assurance_footer(state)
        self.assertIn("Textual claims rendered: 0", footer)
        self.assertIn("Denied claims: 1", footer)


if __name__ == "__main__":
    unittest.main()
