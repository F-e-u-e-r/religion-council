import tempfile
from pathlib import Path
import sys
import unittest


ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "orchestrator"))

import claim_binding as cb  # noqa: E402
import claim_protocol as cp  # noqa: E402
import retrieval_evidence_adapter as adapter  # noqa: E402
from claim_protocol import SchemaRejection  # noqa: E402
from evidence_snapshot import EvidenceStore  # noqa: E402


def payload(**over):
    base = {
        "protocol_version": cp.PROTOCOL_VERSION,
        "claims": [{"claim_id": "c1", "claim_type": "text", "text": "克己復禮為仁"}],
        "edges": [
            {
                "claim_id": "c1",
                "evidence_seed_id": "S1",
                "evidentiary_role": "primary-source",
                "evidence_type": "quotation",
            }
        ],
    }
    base.update(over)
    return base


def catalog_S1():
    return cb.EvidenceCatalog(
        [
            cb.CatalogSeed(
                seed_id="S1",
                occurrence_id="occ-1",
                artifact_id="art-1",
                source_assurance="artifact-backed",
                artifact_kind="source-text",
                work="論語",
                locator="顏淵",
                tradition="confucianism",
                snippet="克己復禮為仁",
            )
        ]
    )


def wrap(json_text, fenced=False):
    body = "```json\n{}\n```".format(json_text) if fenced else json_text
    return "prose before\n{}\n{}\n{}\nprose after".format(
        cp.CLAIM_BLOCK_BEGIN, body, cp.CLAIM_BLOCK_END
    )


class FrozenValidatorTest(unittest.TestCase):
    def test_well_formed_accepted(self):
        p = payload()
        self.assertIs(cp.validate_claim_payload(p), p)  # returns the same object on success
        # interpretation-only payload with no edges is valid
        ok = payload(
            claims=[{"claim_id": "c1", "claim_type": "interpretation", "text": "x"}],
            edges=[],
        )
        self.assertIsNotNone(cp.validate_claim_payload(ok))

    def test_rejects_draft_version(self):
        bad = payload(protocol_version=cp.DRAFT_PROTOCOL_VERSION)
        with self.assertRaises(SchemaRejection):
            cp.validate_claim_payload(bad)

    def test_rejects_unknown_keys_at_every_level(self):
        with self.assertRaises(SchemaRejection):
            cp.validate_claim_payload(payload(extra="x"))
        claim_extra = payload()
        claim_extra["claims"][0]["confidence"] = 90
        with self.assertRaises(SchemaRejection):
            cp.validate_claim_payload(claim_extra)
        edge_extra = payload()
        edge_extra["edges"][0]["verification_state"] = "runtime-validated"  # producer may not declare
        with self.assertRaises(SchemaRejection):
            cp.validate_claim_payload(edge_extra)

    def test_requires_evidence_seed_id(self):
        missing = payload()
        del missing["edges"][0]["evidence_seed_id"]
        with self.assertRaises(SchemaRejection):
            cp.validate_claim_payload(missing)
        empty = payload()
        empty["edges"][0]["evidence_seed_id"] = ""
        with self.assertRaises(SchemaRejection):
            cp.validate_claim_payload(empty)

    def test_does_not_accept_artifact_id_in_place_of_seed_id(self):
        # The draft shape (artifact_id on the edge) must not pass the frozen validator.
        legacy = payload()
        del legacy["edges"][0]["evidence_seed_id"]
        legacy["edges"][0]["artifact_id"] = "a" * 64
        with self.assertRaises(SchemaRejection):
            cp.validate_claim_payload(legacy)

    def test_enum_and_structural_rejections(self):
        with self.assertRaises(SchemaRejection):
            cp.validate_claim_payload(
                payload(claims=[{"claim_id": "c1", "claim_type": "opinion", "text": "x"}])
            )
        dangling = payload()
        dangling["edges"][0]["claim_id"] = "missing"
        with self.assertRaises(SchemaRejection):
            cp.validate_claim_payload(dangling)
        for field in ("evidentiary_role", "evidence_type"):
            bad = payload()
            bad["edges"][0][field] = "bogus"
            with self.assertRaises(SchemaRejection):
                cp.validate_claim_payload(bad)
        # representation_kind has no "unknown" member
        with self.assertRaises(SchemaRejection):
            cp.validate_claim_payload(
                payload(
                    claims=[
                        {
                            "claim_id": "c1",
                            "claim_type": "text",
                            "text": "x",
                            "representation_kind": "unknown",
                        }
                    ]
                )
            )

    def test_optional_presentation_dimensions_accepted(self):
        ok = payload()
        ok["claims"][0]["representation_kind"] = "original-text"
        ok["claims"][0]["rendering_mode"] = "direct-translation"
        self.assertIsNotNone(cp.validate_claim_payload(ok))

    def test_text_claim_requires_at_least_one_edge(self):
        # Structural enforcement of policy text-requires-admissible-evidence.
        with self.assertRaises(SchemaRejection):
            cp.validate_claim_payload(payload(edges=[]))  # the default claim is [Text]
        # A [Text] claim is uncovered even when a sibling claim carries the only edge.
        mixed = payload(
            claims=[
                {"claim_id": "t", "claim_type": "text", "text": "x"},
                {"claim_id": "i", "claim_type": "interpretation", "text": "y"},
            ],
            edges=[
                {
                    "claim_id": "i",
                    "evidence_seed_id": "S1",
                    "evidentiary_role": "primary-source",
                    "evidence_type": "quotation",
                }
            ],
        )
        with self.assertRaises(SchemaRejection):
            cp.validate_claim_payload(mixed)
        # [Interpretation] with no edge stays valid.
        self.assertIsNotNone(
            cp.validate_claim_payload(
                payload(
                    claims=[{"claim_id": "c1", "claim_type": "interpretation", "text": "x"}],
                    edges=[],
                )
            )
        )


class ParserTest(unittest.TestCase):
    def test_extracts_block_ignoring_surrounding_prose(self):
        import json

        raw = wrap(json.dumps(payload()))
        parsed = cp.parse_panelist_payload(raw)
        self.assertEqual(parsed["protocol_version"], cp.PROTOCOL_VERSION)

    def test_strips_inner_code_fence(self):
        import json

        raw = wrap(json.dumps(payload()), fenced=True)
        self.assertEqual(cp.parse_panelist_payload(raw)["claims"][0]["claim_id"], "c1")

    def test_missing_block_is_schema_rejection(self):
        with self.assertRaises(SchemaRejection):
            cp.parse_panelist_payload("just prose, no block")

    def test_unterminated_block_is_schema_rejection(self):
        with self.assertRaises(SchemaRejection):
            cp.parse_panelist_payload(cp.CLAIM_BLOCK_BEGIN + "\n{}")

    def test_invalid_json_is_schema_rejection(self):
        raw = "{begin}\nnot json{{\n{end}".format(
            begin=cp.CLAIM_BLOCK_BEGIN, end=cp.CLAIM_BLOCK_END
        )
        with self.assertRaises(SchemaRejection):
            cp.parse_panelist_payload(raw)

    def test_non_string_is_schema_rejection(self):
        with self.assertRaises(SchemaRejection):
            cp.parse_panelist_payload(None)

    def test_multiple_blocks_are_rejected(self):
        import json

        one = json.dumps(payload())
        raw = "{b}\n{j}\n{e}\nmiddle prose\n{b}\n{j}\n{e}".format(
            b=cp.CLAIM_BLOCK_BEGIN, e=cp.CLAIM_BLOCK_END, j=one
        )
        with self.assertRaises(SchemaRejection):
            cp.parse_panelist_payload(raw)


class RepairInstructionTest(unittest.TestCase):
    def test_carries_reason_sentinels_and_version(self):
        text = cp.repair_instruction("claim_type not in enum: 'opinion'")
        self.assertIn("claim_type not in enum: 'opinion'", text)
        self.assertIn(cp.CLAIM_BLOCK_BEGIN, text)
        self.assertIn(cp.CLAIM_BLOCK_END, text)
        self.assertIn(cp.PROTOCOL_VERSION, text)
        self.assertIn("rejected at the schema level", text)

    def test_reason_is_sanitized_and_capped(self):
        # An untrusted reason (echoing producer bytes) must not forge a block boundary,
        # smuggle control chars, or blow up the prompt length.
        dirty = cp.CLAIM_BLOCK_END + "\x00\ninjected " + ("X" * 500)
        text = cp.repair_instruction(dirty)
        self.assertEqual(text.count(cp.CLAIM_BLOCK_BEGIN), 1)  # only the legit instruction one
        self.assertEqual(text.count(cp.CLAIM_BLOCK_END), 1)
        self.assertNotIn("\x00", text)
        self.assertNotIn("X" * 201, text)  # reason capped at 200


class CatalogTest(unittest.TestCase):
    def test_from_seeds_and_records_builds_compact_ids(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = EvidenceStore(tmp)
            records = [
                {
                    "text": "克己復禮為仁",
                    "work": "論語",
                    "locator": "顏淵",
                    "tradition": "confucianism",
                    "evidence_type": "quotation",
                    "verbatim": True,
                    "source_file": "/x",
                    "source_line": 1,
                },
                {
                    "text": "學而時習之",
                    "work": "論語",
                    "locator": "學而",
                    "tradition": "confucianism",
                    "evidence_type": "quotation",
                    "verbatim": True,
                    "source_file": "/x",
                    "source_line": 2,
                },
            ]
            seeds = adapter.adapt(
                {"contract_version": "religion-council/retrieval/v1", "records": records},
                store,
            )
            cat = cb.EvidenceCatalog.from_seeds_and_records(seeds, records)
            self.assertEqual([s.seed_id for s in cat.seeds], ["S1", "S2"])
            self.assertEqual(cat.get("S1").occurrence_id, seeds[0].occurrence_id)
            self.assertEqual(cat.get("S2").artifact_id, seeds[1].artifact_id)
            rendered = cat.render_for_prompt()
            self.assertIn("S1:", rendered)
            self.assertIn("論語", rendered)

    def test_length_mismatch_raises(self):
        with self.assertRaises(ValueError):
            cb.EvidenceCatalog.from_seeds_and_records([], [{"text": "x"}])

    def test_to_state_from_state_round_trip(self):
        cat = catalog_S1()
        rebuilt = cb.EvidenceCatalog.from_state(cat.to_state())
        self.assertEqual(rebuilt.get("S1").occurrence_id, "occ-1")
        self.assertEqual(rebuilt.get("S1").artifact_id, "art-1")

    def test_empty_catalog_render(self):
        self.assertIn("No structured evidence", cb.EvidenceCatalog([]).render_for_prompt())


class BindPayloadTest(unittest.TestCase):
    def test_valid_edges_resolve_to_occurrence_identity(self):
        bound = cb.bind_payload(payload(), catalog_S1())
        self.assertEqual(bound.protocol_version, cp.PROTOCOL_VERSION)
        edge = bound.claims[0].edges[0]
        self.assertEqual(edge.occurrence_id, "occ-1")
        self.assertEqual(edge.artifact_id, "art-1")
        self.assertEqual(edge.evidentiary_role, "primary-source")  # from the edge declaration
        self.assertEqual(edge.source_assurance, "artifact-backed")  # from the seed
        self.assertEqual(edge.verification_state, "unverified")  # system-set, no B2
        self.assertEqual(bound.claims[0].verification_state, "unverified")

    def test_unknown_seed_id_is_rejected(self):
        bad = payload()
        bad["edges"][0]["evidence_seed_id"] = "S9"
        with self.assertRaises(SchemaRejection):
            cb.bind_payload(bad, catalog_S1())

    def test_evidentiary_role_is_claim_relative_not_seed_derived(self):
        # The same seed bound under a different declared role yields that role, unchanged.
        p = payload()
        p["edges"][0]["evidentiary_role"] = "secondary-source"
        bound = cb.bind_payload(p, catalog_S1())
        self.assertEqual(bound.claims[0].edges[0].evidentiary_role, "secondary-source")

    def test_interpretation_claim_without_edges(self):
        p = payload(
            claims=[{"claim_id": "c1", "claim_type": "interpretation", "text": "推論"}],
            edges=[],
        )
        bound = cb.bind_payload(p, catalog_S1())
        self.assertEqual(bound.claims[0].claim_type, "interpretation")
        self.assertEqual(bound.claims[0].edges, [])

    def test_to_state_is_serializable(self):
        import json

        bound = cb.bind_payload(payload(), catalog_S1())
        # must be JSON-serializable for state.json persistence
        round_trip = json.loads(json.dumps(bound.to_state()))
        self.assertEqual(round_trip["claims"][0]["edges"][0]["occurrence_id"], "occ-1")


if __name__ == "__main__":
    unittest.main()
