"""Run the shared retrieval-contract battery against the portable retriever (ADR 0006)."""
import importlib.util
import sys
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))  # so `import contract_assertions` works under direct execution too

import contract_assertions as ca  # noqa: E402

PORTABLE_RETRIEVER = (
    ca.ROOT / "skills" / "religion-council" / "scripts" / "retrieve.py"
)


def _load(path):
    spec = importlib.util.spec_from_file_location("rc_portable_retriever", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class PortableContractTest(ca.RetrievalContractMixin, unittest.TestCase):
    STDLIB_ONLY = True
    EXPECTED_RETRIEVER_KIND = "portable-file"

    def load_retriever(self):
        return _load(PORTABLE_RETRIEVER)

    def retriever_source_path(self):
        return PORTABLE_RETRIEVER


if __name__ == "__main__":
    unittest.main()
