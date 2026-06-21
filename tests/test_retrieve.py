import importlib.util
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def load_retriever(path):
    spec = importlib.util.spec_from_file_location("religion_retrieve", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class RetrieveTest(unittest.TestCase):
    def setUp(self):
        self.portable_path = (
            ROOT / "skills" / "religion-council" / "scripts" / "retrieve.py"
        )
        self.claude_path = (
            ROOT / ".claude" / "skills" / "religion-council" / "scripts" / "retrieve.py"
        )
        self.module = load_retriever(self.portable_path)

    def test_retriever_distributions_are_byte_identical(self):
        # Byte parity is an A0-A1 invariant. At A2 the project-integrated copy
        # forks to an index/RAG backend while the portable copy stays file-based,
        # and this parity check is replaced by a shared contract-conformance suite
        # over retrieve_envelope()'s contract_version. See ADR 0002 / docs/CORPUS.md.
        self.assertEqual(
            self.portable_path.read_bytes(),
            self.claude_path.read_bytes(),
        )

    def test_presentation_sidecars_are_byte_identical(self):
        # Both retriever copies load their LOCAL sidecar, so the two sidecars must match too.
        portable = self.portable_path.parent.parent / "references" / "presentation.json"
        claude = self.claude_path.parent.parent / "references" / "presentation.json"
        self.assertEqual(portable.read_bytes(), claude.read_bytes())

    def test_wrong_typed_sidecar_values_are_dropped_at_merge(self):
        # A malformed sidecar (valid JSON, wrong value types) must not inject garbage: each
        # wrong-typed field is dropped; a correctly-typed sibling field still merges.
        sample = self.module.parse_reference("confucianism")[0]
        key = ("confucianism", sample["work"], sample["locator"])
        original = dict(self.module.PRESENTATION)
        self.module.PRESENTATION[key] = {
            "work": sample["work"],
            "locator": sample["locator"],
            "representation_kind": 123,            # wrong type -> dropped
            "rendering_mode": "meaning-rendering",  # str -> carried
            "provenance": "not-a-dict",            # wrong type -> dropped
            "rights": None,                         # wrong type -> dropped
        }
        try:
            merged = next(
                r
                for r in self.module.parse_reference("confucianism")
                if r["work"] == sample["work"] and r["locator"] == sample["locator"]
            )
        finally:
            self.module.PRESENTATION.clear()
            self.module.PRESENTATION.update(original)
        self.assertNotIn("representation_kind", merged)
        self.assertNotIn("provenance", merged)
        self.assertNotIn("rights", merged)
        self.assertEqual(merged["rendering_mode"], "meaning-rendering")

    def test_retrieve_envelope_wraps_records_with_contract_version(self):
        envelope = self.module.retrieve_envelope("buddhism", "空", 1)
        self.assertEqual(
            envelope["contract_version"], self.module.RETRIEVAL_CONTRACT_VERSION
        )
        self.assertEqual(envelope["contract_version"], "religion-council/retrieval/v1")
        # The envelope is additive: records is exactly the legacy retrieve() list,
        # so existing callers of retrieve() are unaffected.
        self.assertEqual(envelope["records"], self.module.retrieve("buddhism", "空", 1))
        self.assertIsInstance(envelope["records"], list)

    def test_all_traditions_return_contract_records(self):
        required = {
            "text",
            "tradition",
            "school",
            "work",
            "locator",
            "language",
            "version",
            "category",
            "label",
            "evidence_type",
            "verbatim",
        }
        for tradition in self.module.TRADITIONS:
            records = self.module.retrieve(tradition, "人生意義", 2)
            self.assertTrue(records, tradition)
            self.assertTrue(required.issubset(records[0]), tradition)

    def test_relevant_buddhist_entry_ranks_first(self):
        records = self.module.retrieve("buddhism", "空", 1)
        self.assertEqual(records[0]["work"], "般若波羅蜜多心經")

    def test_parenthetical_note_does_not_become_school(self):
        records = self.module.parse_reference("islam")
        loyalty = next(record for record in records if record["locator"] == "112:1-4(忠誠章)")
        self.assertEqual(loyalty["school"], "伊斯蘭教")

    def test_known_school_marker_is_extracted_from_mixed_note(self):
        records = self.module.retrieve("buddhism", "四諦", 1)
        self.assertEqual(records[0]["work"], "轉法輪經")
        self.assertEqual(records[0]["locator"], "(初轉法輪,南傳)")
        self.assertEqual(records[0]["school"], "南傳")

    def test_presentation_sidecar_merges_onto_renderings(self):
        # A1: curated presentation/provenance is merged onto the matching Qur'an renderings.
        records = self.module.parse_reference("islam")
        rendering = next(
            r for r in records if r["work"] == "古蘭經" and r["locator"] == "51:56"
        )
        self.assertEqual(rendering["representation_kind"], "published-translation")
        self.assertEqual(rendering["rendering_mode"], "meaning-rendering")
        self.assertEqual(rendering["provenance"]["translator"], "馬堅")
        self.assertIn("copyright", rendering["rights"])

    def test_uncurated_records_have_no_presentation_fields(self):
        # The summary entry (not curated) and a whole non-curated tradition stay untouched.
        islam = self.module.parse_reference("islam")
        summary = next(r for r in islam if not r["verbatim"])
        for field in self.module.PRESENTATION_FIELDS:
            self.assertNotIn(field, summary)
        for record in self.module.parse_reference("confucianism"):
            for field in self.module.PRESENTATION_FIELDS:
                self.assertNotIn(field, record)

    def test_presentation_sidecar_is_additive_to_core_contract(self):
        # Merging presentation does not change the core return shape every persona relies on.
        record = next(
            r
            for r in self.module.parse_reference("islam")
            if r.get("representation_kind")
        )
        self.assertTrue({"text", "tradition", "work", "locator", "evidence_type"} <= set(record))

    def test_source_bound_summary_is_text_but_not_verbatim(self):
        records = self.module.retrieve("buddhism", "四諦", 1)
        self.assertEqual(records[0]["label"], "Text")
        self.assertEqual(records[0]["evidence_type"], "source-bound-summary")
        self.assertFalse(records[0]["verbatim"])

        quotation = self.module.retrieve("buddhism", "空", 1)[0]
        self.assertEqual(quotation["evidence_type"], "quotation")
        self.assertTrue(quotation["verbatim"])


if __name__ == "__main__":
    unittest.main()
