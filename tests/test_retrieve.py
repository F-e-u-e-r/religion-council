import importlib.util
from pathlib import Path
import unittest


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
