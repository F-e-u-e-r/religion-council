"""Tests for the project retriever's additive no-answer gate (ADR 0007 §1, §8.2).

Step 1 of the ADR 0007 rollout: an *explicit, opt-in* gated retrieval API on the project retriever
(`retrieve_gated` / `retrieve_envelope_gated`, default threshold t3). It is deliberately additive —
the raw `retrieve()` / `retrieve_envelope()` contract surface is unchanged, so the retrieval-v1
lexical baseline and the ADR 0006 conformance suite keep measuring the raw signal and the committed
benchmark reports stay byte-identical (see `test_retrieval_benchmark.py`).

The gate is applied to the project retriever's **per-tradition** lexical confidence (the top record's
lexical score), which is the only confidence a per-tradition `retrieve_envelope(tradition, ...)` call
exposes. This is faithful to ADR 0007 §8.2 and is the correct unit for the orchestrated council
(each tradition decides whether it has confident support). It is slightly more conservative than the
benchmark's *global* t3 gate on weak cross-tradition matches — see
`test_gate_is_per_tradition_not_global`, which pins that intentional behavior.
"""
import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ORCH = ROOT / "orchestrator"
PORTABLE = ROOT / "skills" / "religion-council" / "scripts" / "retrieve.py"
QUERIES = ROOT / "docs" / "benchmarks" / "queries" / "retrieval-v1.json"
JUDGMENTS = ROOT / "docs" / "benchmarks" / "judgments" / "retrieval-v1.json"


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class ProjectNoAnswerGateTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.project = _load("rc_gate_project_retrieve", ORCH / "project_retrieve.py")
        cls.portable = _load("rc_gate_portable_retrieve", PORTABLE)
        cls.queries = {q["query_id"]: q for q in json.loads(QUERIES.read_text("utf-8"))["queries"]}
        cls.judgments = {
            j["query_id"]: j for j in json.loads(JUDGMENTS.read_text("utf-8"))["judgments"]
        }

    # ---- helpers ----

    def _q(self, qid):
        return self.queries[qid]["query"]

    def _confidence(self, tradition, query):
        records = self.portable.parse_reference(tradition)
        return max((self.portable.score(query, record) for record in records), default=0)

    def _survivors(self, query):
        return {
            (rec["tradition"], rec["work"], rec["locator"])
            for tradition in self.project.TRADITIONS
            for rec in self.project.retrieve_gated(tradition, query, 5)
        }

    # ---- raw surface is unchanged (default behavior preserved) ----

    def test_raw_retrieve_and_envelope_are_unchanged(self):
        # The gate is additive: the raw contract surface must still equal the portable retriever's,
        # across answerable, cross-tradition, and no-answer queries.
        for qid in ("q001", "q005", "q010", "q011", "q014"):
            query = self._q(qid)
            for tradition in sorted(self.project.TRADITIONS):
                self.assertEqual(
                    self.project.retrieve_envelope(tradition, query, 5),
                    self.portable.retrieve_envelope(tradition, query, 5),
                    "raw retrieve_envelope drifted for {} {!r}".format(tradition, query))
                self.assertEqual(
                    self.project.retrieve(tradition, query, 5),
                    self.portable.retrieve(tradition, query, 5))

    def test_default_threshold_is_t3(self):
        self.assertEqual(self.project.NO_ANSWER_THRESHOLD, 3)

    def test_gated_envelope_keeps_contract_version_even_when_empty(self):
        env = self.project.retrieve_envelope_gated("buddhism", self._q("q014"), 5)
        self.assertEqual(env["contract_version"], self.project.RETRIEVAL_CONTRACT_VERSION)
        self.assertEqual(env["records"], [])

    # ---- the gate's required behavior ----

    def test_off_corpus_queries_return_no_support_everywhere(self):
        # q014/q015 are off-corpus: every tradition's top score is at the noise floor (< t3), so the
        # gate returns no support for all of them.
        for qid in ("q014", "q015"):
            query = self._q(qid)
            for tradition in sorted(self.project.TRADITIONS):
                self.assertEqual(
                    self.project.retrieve_gated(tradition, query, 5), [],
                    "{} {!r} should be gated".format(tradition, query))

    def test_gated_preserves_exact_quote(self):
        for qid in ("q001", "q002", "q003"):
            self._assert_relevant_target_preserved(qid)

    def test_gated_preserves_exact_locator(self):
        for qid in ("q004", "q005", "q006"):
            self._assert_relevant_target_preserved(qid)

    def _assert_relevant_target_preserved(self, qid):
        query = self._q(qid)
        target = self.judgments[qid]["relevant"][0]
        tradition = target["tradition"]
        gated = self.project.retrieve_gated(tradition, query, 5)
        self.assertEqual(gated, self.project.retrieve(tradition, query, 5),
                         "{}: gate altered a passing result".format(qid))
        self.assertTrue(gated, "{}: exact target was wrongly gated".format(qid))
        self.assertEqual((gated[0]["work"], gated[0]["locator"]),
                         (target["work"], target["locator"]),
                         "{}: exact target is not rank-1 after gating".format(qid))

    def test_gated_does_not_regress_q007_q010(self):
        # The benchmark retrieves these (q007 hit at rank 2; q010 recall@5 = 0.25). After per-tradition
        # gating, the judged-relevant record the benchmark actually found is still retrievable — its
        # owning tradition's confidence clears t3.
        for qid in ("q007", "q010"):
            query = self._q(qid)
            rel_keys = {(r["tradition"], r["work"], r["locator"])
                        for r in self.judgments[qid]["relevant"]}
            self.assertTrue(self._survivors(query) & rel_keys,
                            "{}: no judged-relevant record survives the gate".format(qid))
        # q007's confucian answer survives at the exact t3 boundary (confidence == 3, not < 3).
        self.assertEqual(self._confidence("confucianism", self._q("q007")), 3)
        self.assertTrue(self.project.retrieve_gated("confucianism", self._q("q007"), 5))

    def test_gate_is_per_tradition_not_global(self):
        # Intentional, pinned: the gate decides per tradition, so a weak cross-tradition match is
        # gated even when another tradition answers the same query strongly. For "愛人", christianity
        # (馬太福音, conf 14) passes while mohism (墨子·兼愛中, conf 2) is gated — more conservative than
        # the benchmark's global t3 gate, consistent with ADR 0007's unresolved broad-thematic recall.
        query = self._q("q011")
        self.assertTrue(self.project.retrieve_gated("christianity", query, 5))
        self.assertEqual(self.project.retrieve_gated("mohism", query, 5), [])

    def test_threshold_is_overridable(self):
        # The cutoff is a parameter; lowering it admits the weak match, raising it gates everything.
        query = self._q("q011")
        self.assertTrue(self.project.retrieve_gated("mohism", query, 5, threshold=2))
        self.assertEqual(self.project.retrieve_gated("christianity", query, 5, threshold=999), [])

    # ---- identity & isolation ----

    def test_gate_preserves_stable_occurrence_identity(self):
        # Returned records are exactly the raw records (a passing query is untouched), so the B1
        # adapter mints identical occurrence ids — the gate never disturbs identity.
        sys.path.insert(0, str(ORCH))
        import retrieval_evidence_adapter as adapter  # noqa: E402
        from evidence_snapshot import EvidenceStore  # noqa: E402

        query = self._q("q001")
        raw = self.project.retrieve("confucianism", query, 5)
        gated = self.project.retrieve_gated("confucianism", query, 5)
        self.assertEqual(raw, gated)

        def occ_ids(records):
            with tempfile.TemporaryDirectory() as tmp:
                seeds = adapter.adapt(
                    {"contract_version": self.project.RETRIEVAL_CONTRACT_VERSION, "records": records},
                    EvidenceStore(tmp))
            return [seed.occurrence_id for seed in seeds]

        self.assertTrue(occ_ids(gated))
        self.assertEqual(occ_ids(raw), occ_ids(gated))

    def test_portable_retriever_has_no_gate(self):
        # The gate is project-only; the portable retriever is untouched and still surfaces the weak
        # match (no no-answer policy of its own).
        self.assertFalse(hasattr(self.portable, "retrieve_gated"))
        self.assertFalse(hasattr(self.portable, "retrieve_envelope_gated"))
        self.assertFalse(hasattr(self.portable, "NO_ANSWER_THRESHOLD"))
        self.assertTrue(self.portable.retrieve("mohism", self._q("q011"), 5))


if __name__ == "__main__":
    unittest.main()
