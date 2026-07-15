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

    def test_portable_distribution_copies_are_byte_identical(self):
        # NARROW same-artifact check (ADR 0006): the two PORTABLE copies are the same file shipped
        # to two install locations, so they must stay byte-identical. This is no longer the
        # retriever seam's cross-implementation guarantee — that is the shared contract suite in
        # tests/retrieval_contract/, which both the portable AND the project retriever pass. The
        # project retriever (orchestrator/project_retrieve.py) is a separate implementation and is
        # deliberately NOT byte-checked against the portable one. See ADR 0006 / docs/CORPUS.md.
        self.assertEqual(
            self.portable_path.read_bytes(),
            self.claude_path.read_bytes(),
        )

    def test_project_retriever_shares_the_contract_not_bytes(self):
        # ADR 0006 migration phase 4: byte-parity is retired as the cross-implementation invariant.
        # The project retriever is bound by the retrieval-envelope contract, not by byte-parity with
        # the portable copy: it re-exports the same contract_version and reports its own kind.
        project_path = ROOT / "orchestrator" / "project_retrieve.py"
        self.assertTrue(project_path.is_file())
        project = load_retriever(project_path)
        self.assertEqual(
            project.capabilities()["contract_version"], self.module.RETRIEVAL_CONTRACT_VERSION
        )
        self.assertEqual(project.capabilities()["retriever_kind"], "project-file")
        self.assertEqual(
            project.retrieve_envelope("buddhism", "空", 1)["contract_version"],
            self.module.RETRIEVAL_CONTRACT_VERSION,
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
        # A record with no sidecar entry stays untouched: an uncurated Buddhist source-bound summary
        # (轉法輪經), and a baseline Confucian quotation whose chapter-in-work key (論語·顏淵) is not
        # curated. (The islam《古蘭經》多處 summary is now curated interpretation_only, so it is no
        # longer a valid uncurated example — see test_corpus_curation.)
        buddhism = self.module.parse_reference("buddhism")
        summary = next(r for r in buddhism if r["work"] == "轉法輪經" and not r["verbatim"])
        confucian = self.module.parse_reference("confucianism")
        baseline = next(r for r in confucian if r["work"] == "論語·顏淵")  # 己所不欲, not curated
        for record in (summary, baseline):
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
