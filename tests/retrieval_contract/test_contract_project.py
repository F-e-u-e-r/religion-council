"""Run the shared retrieval-contract battery against the project retriever (ADR 0006).

The project retriever passes the *same* battery as the portable one (proving the two
implementations share one contract), plus an explicit semantic-equivalence check against the
portable retriever (ADR 0006 §4.2).
"""
import sys
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))  # for `import contract_assertions`

import contract_assertions as ca  # noqa: E402

sys.path.insert(0, str(ca.ROOT / "orchestrator"))  # for `import project_retrieve`
import project_retrieve  # noqa: E402


class ProjectContractTest(ca.RetrievalContractMixin, unittest.TestCase):
    STDLIB_ONLY = False  # the project retriever MAY import project code (ADR 0006 §4.4)
    EXPECTED_RETRIEVER_KIND = "project-file"

    def load_retriever(self):
        return project_retrieve

    def test_semantically_equivalent_to_portable(self):
        # ADR 0006 §4.2: the same query against the same corpus yields semantically equivalent
        # envelopes across retrievers. Today the project retriever wraps the portable one, so
        # equivalence is exact equality; a future index backend that reorders would relax this to
        # set/identity-equivalence (same artifacts + same stable occurrence ids), never weaker.
        portable = ca.load_module_from_path("rc_portable_retriever", ca.PORTABLE_RETRIEVER)
        for tradition in sorted(project_retrieve.TRADITIONS):
            for query in ca.SAMPLE_QUERIES:
                self.assertEqual(
                    project_retrieve.retrieve_envelope(tradition, query, 3),
                    portable.retrieve_envelope(tradition, query, 3),
                    "project/portable envelope divergence for {} {!r}".format(tradition, query),
                )


if __name__ == "__main__":
    unittest.main()
