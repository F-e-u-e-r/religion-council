import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "orchestrator"))

import policy_enums  # noqa: E402
import retrieval_evidence_adapter as adapter  # noqa: E402
from claim_protocol import (  # noqa: E402
    DRAFT_PROTOCOL_VERSION,
    SchemaRejection,
    validate_claim_payload_draft,
)
from evidence_snapshot import (  # noqa: E402
    EvidenceStore,
    EvidenceStoreError,
    artifact_id,
    canonical_bytes,
)


def make_record(**overrides):
    record = {
        "text": "克己復禮為仁",
        "tradition": "confucianism",
        "school": "儒家",
        "work": "論語",
        "locator": "顏淵",
        "language": "zh-Hant",
        "version": "curated-reference-v0.1",
        "category": "哲學思想著作",
        "label": "Text",
        "evidence_type": "quotation",
        "verbatim": True,
        "topic": "仁與禮",
        "source_file": "/repo/references/07-儒家.md",
        "source_line": 12,
    }
    record.update(overrides)
    return record


def envelope(records):
    return {"contract_version": "religion-council/retrieval/v1", "records": records}


class CanonicalizationTest(unittest.TestCase):
    def test_no_trailing_newline_added_or_stripped(self):
        self.assertEqual(canonical_bytes("abc"), b"abc")
        self.assertEqual(canonical_bytes("abc\n"), b"abc\n")
        self.assertNotEqual(artifact_id("abc"), artifact_id("abc\n"))

    def test_newlines_normalized_to_lf(self):
        self.assertEqual(canonical_bytes("a\r\nb"), b"a\nb")
        self.assertEqual(canonical_bytes("a\rb"), b"a\nb")
        self.assertEqual(artifact_id("a\r\nb"), artifact_id("a\nb"))
        self.assertEqual(artifact_id("a\rb"), artifact_id("a\nb"))

    def test_nfc_equivalence(self):
        self.assertEqual(artifact_id("é"), artifact_id("é"))

    def test_non_string_rejected_not_coerced(self):
        for value in (None, 123, ["x"], {"a": 1}):
            with self.assertRaises(TypeError):
                canonical_bytes(value)


class ArtifactKindTest(unittest.TestCase):
    def test_kind_from_evidence_type_and_verbatim(self):
        self.assertEqual(
            adapter.artifact_kind_of({"evidence_type": "quotation", "verbatim": True}),
            "source-text",
        )
        self.assertEqual(
            adapter.artifact_kind_of({"evidence_type": "source-bound-summary", "verbatim": False}),
            "reference-summary",
        )

    def test_kind_is_unknown_on_mismatch_or_missing(self):
        self.assertEqual(
            adapter.artifact_kind_of({"evidence_type": "quotation", "verbatim": False}),
            "unknown",
        )
        self.assertEqual(
            adapter.artifact_kind_of({"evidence_type": None, "verbatim": True}),
            "unknown",
        )
        self.assertEqual(adapter.artifact_kind_of({}), "unknown")

    def test_category_does_not_drive_kind(self):
        # 宗教經典 + source-bound-summary must still be reference-summary, not source-text.
        record = {"category": "宗教經典", "evidence_type": "source-bound-summary", "verbatim": False}
        self.assertEqual(adapter.artifact_kind_of(record), "reference-summary")


class OccurrenceIdTest(unittest.TestCase):
    def test_excludes_rank_and_is_not_artifact_id(self):
        record = make_record()
        aid = artifact_id(record["text"])
        first = adapter.occurrence_id(record, aid, 0)
        later = adapter.occurrence_id(record, aid, 7)
        self.assertEqual(first, later)  # record index / rank not part of identity
        self.assertNotEqual(first, aid)  # never the artifact_id alone

    def test_same_bytes_different_locator_distinct_occurrence(self):
        aid = artifact_id("克己復禮為仁")
        one = adapter.occurrence_id(make_record(source_line=12, locator="顏淵"), aid, 0)
        two = adapter.occurrence_id(make_record(source_line=99, locator="里仁"), aid, 0)
        self.assertNotEqual(one, two)

    def test_fallback_when_origin_missing_is_retrieval_scoped(self):
        # Without source_file/source_line the id is retrieval-order scoped: index matters.
        record = make_record(source_file=None, source_line=None)
        aid = artifact_id(record["text"])
        first = adapter.occurrence_id(record, aid, 0)
        second = adapter.occurrence_id(record, aid, 1)
        self.assertNotEqual(first, aid)
        self.assertNotEqual(first, second)  # index disambiguates absent origin hints


class EvidenceStoreTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.store = EvidenceStore(self.temp.name)
        self.dir = Path(self.temp.name)

    def test_put_snapshot_idempotent_by_content(self):
        aid1, length1 = self.store.put_snapshot("hello")
        aid2, length2 = self.store.put_snapshot("hello")
        self.assertEqual(aid1, aid2)
        self.assertEqual(length1, length2)
        self.assertTrue((self.dir / aid1).exists())
        self.assertTrue((self.dir / (aid1 + ".meta.json")).exists())

    def test_exclusive_create_refuses_to_overwrite_different_bytes(self):
        aid, _ = self.store.put_snapshot("hello")
        (self.dir / aid).write_bytes(b"tampered")  # simulate corruption
        with self.assertRaises(EvidenceStoreError):
            self.store.put_snapshot("hello")

    def test_meta_is_content_derived_only(self):
        aid, length = self.store.put_snapshot("hello")
        meta = json.loads((self.dir / (aid + ".meta.json")).read_text(encoding="utf-8"))
        self.assertEqual(
            set(meta),
            {"artifact_id", "sha256", "byte_length", "encoding", "normalization", "newline"},
        )
        self.assertEqual(meta["byte_length"], length)
        self.assertEqual(meta["newline"], "LF")

    def test_origins_are_append_only_and_may_duplicate(self):
        self.store.append_origin({"artifact_id": "a", "locator": "x"})
        self.store.append_origin({"artifact_id": "a", "locator": "x"})
        lines = (self.dir / "origins.jsonl").read_text(encoding="utf-8").splitlines()
        self.assertEqual(len(lines), 2)


class AdapterTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.store = EvidenceStore(self.temp.name)
        self.dir = Path(self.temp.name)

    def _snapshot_files(self):
        return [p for p in self.dir.iterdir() if len(p.name) == 64]

    def test_valid_envelope_yields_unverified_seeds(self):
        seeds = adapter.adapt(envelope([make_record()]), self.store)
        self.assertEqual(len(seeds), 1)
        seed = seeds[0]
        self.assertEqual(seed.verification_state, "unverified")
        self.assertEqual(seed.source_assurance, "artifact-backed")
        self.assertEqual(seed.acquisition_origin, "bundled")
        self.assertEqual(seed.retrieval_path, "retrieved-via-seam")
        self.assertEqual(seed.artifact_kind, "source-text")
        self.assertEqual(seed.byte_offset, 0)

    def test_seed_carries_curated_representation_dimensions(self):
        # A1: representation_kind / rendering_mode are never inferred — None on an uncurated
        # record, carried (declared, not trusted) when the record supplies them. The attrs use
        # the declared_ prefix; there is no bare representation_kind on the seed.
        plain = adapter.adapt(envelope([make_record()]), self.store)[0]
        self.assertIsNone(plain.declared_representation_kind)
        self.assertIsNone(plain.declared_rendering_mode)
        self.assertIsNone(plain.provenance)
        self.assertIsNone(plain.rights)
        self.assertFalse(hasattr(plain, "representation_kind"))
        curated = adapter.adapt(
            envelope(
                [
                    make_record(
                        representation_kind="published-translation",
                        rendering_mode="meaning-rendering",
                        provenance={"translator": "馬堅"},
                        rights="short excerpt; verify before redistribution",
                    )
                ]
            ),
            self.store,
        )[0]
        self.assertEqual(curated.declared_representation_kind, "published-translation")
        self.assertEqual(curated.declared_rendering_mode, "meaning-rendering")
        self.assertEqual(curated.provenance, {"translator": "馬堅"})
        self.assertEqual(curated.rights, "short excerpt; verify before redistribution")

    def test_producer_metadata_is_carried(self):
        seed = adapter.adapt(envelope([make_record()]), self.store)[0]
        self.assertEqual(seed.declared_label, "Text")
        self.assertEqual(seed.declared_evidence_type, "quotation")
        self.assertIs(seed.declared_verbatim, True)

    def test_no_claim_or_verification_result_object(self):
        seed = adapter.adapt(envelope([make_record()]), self.store)[0]
        self.assertEqual(type(seed).__name__, "EvidenceSeed")
        self.assertIsInstance(seed.verification_state, str)
        self.assertFalse(hasattr(seed, "evidentiary_role"))  # claim-relative -> B1b

    def test_same_bytes_one_artifact_many_seeds(self):
        seeds = adapter.adapt(
            envelope([make_record(source_line=12, locator="顏淵"),
                      make_record(source_line=99, locator="里仁")]),
            self.store,
        )
        self.assertEqual(len({s.artifact_id for s in seeds}), 1)  # artifact deduped
        self.assertEqual(len({s.occurrence_id for s in seeds}), 2)  # seeds are not
        self.assertEqual(len(self._snapshot_files()), 1)
        origins = (self.dir / "origins.jsonl").read_text(encoding="utf-8").splitlines()
        self.assertEqual(len(origins), 2)

    def test_whitespace_only_text_is_accepted(self):
        seeds = adapter.adapt(envelope([make_record(text=" ")]), self.store)
        self.assertEqual(len(seeds), 1)
        self.assertTrue((self.dir / artifact_id(" ")).exists())

    def test_rejects_bad_text_without_writing_artifact(self):
        for bad in (None, 123, ["x"], {"a": 1}, ""):
            with self.subTest(bad=bad):
                with self.assertRaises(SchemaRejection):
                    adapter.adapt(envelope([make_record(text=bad)]), self.store)
        missing = make_record()
        del missing["text"]
        with self.assertRaises(SchemaRejection):
            adapter.adapt(envelope([missing]), self.store)
        self.assertEqual(self._snapshot_files(), [])

    def test_invalid_record_leaves_store_empty(self):
        # Preflight: a later invalid record must not leave the earlier one persisted.
        with self.assertRaises(SchemaRejection):
            adapter.adapt(envelope([make_record(), make_record(text="")]), self.store)
        self.assertEqual(self._snapshot_files(), [])
        self.assertFalse((self.dir / "origins.jsonl").exists())

    def test_rejects_bad_envelope(self):
        with self.assertRaises(SchemaRejection):
            adapter.adapt({"contract_version": "wrong", "records": []}, self.store)
        with self.assertRaises(SchemaRejection):
            adapter.adapt({"records": []}, self.store)
        with self.assertRaises(SchemaRejection):
            adapter.adapt({"contract_version": "religion-council/retrieval/v1", "records": "no"}, self.store)
        with self.assertRaises(SchemaRejection):
            adapter.adapt(envelope(["not-an-object"]), self.store)

    def test_empty_records_is_valid(self):
        self.assertEqual(adapter.adapt(envelope([]), self.store), [])


class ClaimProtocolDraftDormantTest(unittest.TestCase):
    def _payload(self, **claim_over):
        claim = {"claim_id": "c1", "claim_type": "text", "text": "克己復禮為仁"}
        claim.update(claim_over)
        return {
            "protocol_version": DRAFT_PROTOCOL_VERSION,
            "claims": [claim],
            "edges": [
                {
                    "claim_id": "c1",
                    "artifact_id": "a" * 64,
                    "evidentiary_role": "primary-source",
                    "evidence_type": "quotation",
                    "source_assurance": "artifact-backed",
                    "verification_state": "unverified",
                }
            ],
        }

    def test_well_formed_payload_accepted(self):
        self.assertIsNotNone(validate_claim_payload_draft(self._payload()))
        self.assertIsNotNone(
            validate_claim_payload_draft(self._payload(representation_kind="original-text"))
        )

    def test_version_is_draft_not_frozen_v1(self):
        self.assertTrue(DRAFT_PROTOCOL_VERSION.endswith("-draft"))
        frozen = self._payload()
        frozen["protocol_version"] = "religion-council/claim/v1"
        with self.assertRaises(SchemaRejection):
            validate_claim_payload_draft(frozen)

    def test_rejections(self):
        bad_version = self._payload()
        bad_version["protocol_version"] = "religion-council/claim/v0"
        with self.assertRaises(SchemaRejection):
            validate_claim_payload_draft(bad_version)

        no_claims = self._payload()
        no_claims["claims"] = []
        with self.assertRaises(SchemaRejection):
            validate_claim_payload_draft(no_claims)

        with self.assertRaises(SchemaRejection):
            validate_claim_payload_draft(self._payload(claim_type="opinion"))

        # representation_kind has no "unknown" member -> must be rejected.
        with self.assertRaises(SchemaRejection):
            validate_claim_payload_draft(self._payload(representation_kind="unknown"))

        dangling = self._payload()
        dangling["edges"][0]["claim_id"] = "missing"
        with self.assertRaises(SchemaRejection):
            validate_claim_payload_draft(dangling)

        bad_edge_enum = self._payload()
        bad_edge_enum["edges"][0]["evidence_type"] = "rumor"
        with self.assertRaises(SchemaRejection):
            validate_claim_payload_draft(bad_edge_enum)

    def test_frozen_v1_wired_but_draft_stays_dormant(self):
        # B1b wires the FROZEN v1 path (claim_protocol + claim_binding + the adapter) into
        # the controller. The B1a DRAFT validator stays dormant: nothing in the controller
        # references it, so the draft remains a library exercised only by these tests.
        source = (ROOT / "orchestrator" / "debate_controller.py").read_text(encoding="utf-8")
        self.assertIn("claim_protocol", source)
        self.assertIn("claim_binding", source)
        self.assertIn("retrieval_evidence_adapter", source)
        self.assertNotIn("validate_claim_payload_draft", source)
        self.assertNotIn("DRAFT_PROTOCOL_VERSION", source)
        self.assertNotIn("v1-draft", source)


class EnumConformanceTest(unittest.TestCase):
    ENUM_NAMES = (
        "CLAIM_TYPES",
        "EVIDENCE_TYPES",
        "REPRESENTATION_KINDS",
        "RENDERING_MODES",
        "EVIDENTIARY_ROLES",
        "ARTIFACT_KINDS",
        "ACQUISITION_ORIGINS",
        "RETRIEVAL_PATHS",
        "SOURCE_ASSURANCES",
        "SPAN_ASSURANCE_TIERS",
        "VERIFICATION_STATES",
        "RESPONSE_ENFORCEMENT_MODES",
        "BOUNDARY_DENIAL_REASONS",
    )

    def test_adapter_emitted_values_are_in_policy(self):
        self.assertLessEqual(
            {"source-text", "reference-summary", "unknown"}, policy_enums.ARTIFACT_KINDS
        )
        self.assertIn("bundled", policy_enums.ACQUISITION_ORIGINS)
        self.assertIn("retrieved-via-seam", policy_enums.RETRIEVAL_PATHS)
        self.assertIn("artifact-backed", policy_enums.SOURCE_ASSURANCES)
        self.assertIn("unverified", policy_enums.VERIFICATION_STATES)

    def test_representation_kinds_has_no_unknown(self):
        self.assertNotIn("unknown", policy_enums.REPRESENTATION_KINDS)

    def test_all_enum_sets_non_empty(self):
        # Guards the fail-fast loader: a renamed manifest key must not yield a silent
        # empty enum.
        for name in self.ENUM_NAMES:
            self.assertTrue(getattr(policy_enums, name), name)


if __name__ == "__main__":
    unittest.main()
