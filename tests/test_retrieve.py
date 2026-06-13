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
    def test_all_traditions_return_contract_records(self):
        module = load_retriever(
            ROOT / "skills" / "religion-council" / "scripts" / "retrieve.py"
        )
        required = {
            "text",
            "tradition",
            "school",
            "work",
            "locator",
            "language",
            "version",
            "category",
        }
        for tradition in module.TRADITIONS:
            records = module.retrieve(tradition, "人生意義", 2)
            self.assertTrue(records, tradition)
            self.assertTrue(required.issubset(records[0]), tradition)

    def test_relevant_buddhist_entry_ranks_first(self):
        module = load_retriever(
            ROOT / "skills" / "religion-council" / "scripts" / "retrieve.py"
        )
        records = module.retrieve("buddhism", "空", 1)
        self.assertEqual(records[0]["work"], "般若波羅蜜多心經")


if __name__ == "__main__":
    unittest.main()
