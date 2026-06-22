"""Run the shared retrieval-contract battery against the portable retriever (ADR 0006)."""
import sys
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))  # so `import contract_assertions` works under direct execution too

import contract_assertions as ca  # noqa: E402


class PortableContractTest(ca.RetrievalContractMixin, unittest.TestCase):
    STDLIB_ONLY = True
    EXPECTED_RETRIEVER_KIND = "portable-file"

    def load_retriever(self):
        return ca.load_module_from_path("rc_portable_retriever", ca.PORTABLE_RETRIEVER)

    def retriever_source_path(self):
        return ca.PORTABLE_RETRIEVER


if __name__ == "__main__":
    unittest.main()
