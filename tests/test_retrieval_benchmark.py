"""Tests for the retrieval-v1 benchmark fixtures and runner (scripts/run_retrieval_benchmark.py).

These validate the fixture schemas, the runner's determinism and contract handling, and that the
committed baseline report is reproducible. They deliberately do NOT assert that retrieval scores are
high — the benchmark measures the lexical baseline, it does not require good quality (see
docs/benchmarks/retrieval-v1.md). They DO fail if the runner crashes, a fixture is malformed,
identity is unstable, required metadata is missing, or the report format/baseline drifts.
"""
import ast
import importlib.util
import json
import types
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RUNNER_PATH = ROOT / "scripts" / "run_retrieval_benchmark.py"
RESULT_JSON = ROOT / "docs" / "benchmarks" / "results" / "retrieval-v1-lexical-baseline.json"
NETWORK_MODULES = {"socket", "urllib", "http", "ftplib", "asyncio", "requests", "httpx", "aiohttp"}


def load_runner():
    spec = importlib.util.spec_from_file_location("rc_benchmark_runner", RUNNER_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class RetrievalBenchmarkTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.bm = load_runner()
        cls.queries_doc = cls.bm.load_json(cls.bm.QUERIES_PATH)
        cls.judgments_doc = cls.bm.load_json(cls.bm.JUDGMENTS_PATH)
        cls.result = cls.bm.run_benchmark("project", cls.bm.DEFAULT_KS)

    # ---- fixtures ----

    def test_check_fixtures_passes_for_both_retrievers(self):
        self.assertEqual(self.bm.validate_fixtures("project"), [])
        self.assertEqual(self.bm.validate_fixtures("portable"), [])

    def test_no_duplicate_query_ids(self):
        ids = [q["query_id"] for q in self.queries_doc["queries"]]
        self.assertEqual(len(ids), len(set(ids)))

    def test_query_schema_is_valid(self):
        declared = set(self.queries_doc["categories"])
        for query in self.queries_doc["queries"]:
            for field in ("query_id", "category", "query", "traditions"):
                self.assertIn(field, query)
            self.assertIn(query["category"], declared)
            self.assertIsInstance(query["traditions"], list)

    def test_judgment_schema_is_valid(self):
        query_ids = {q["query_id"] for q in self.queries_doc["queries"]}
        for judgment in self.judgments_doc["judgments"]:
            self.assertIn(judgment["query_id"], query_ids)  # references an existing query
            for entry in judgment.get("relevant", []):
                for field in ("tradition", "work", "locator", "relevance"):
                    self.assertIn(field, entry)
                self.assertIn(entry["relevance"], (0, 1, 2))

    def test_every_positive_judgment_has_rationale(self):
        for judgment in self.judgments_doc["judgments"]:
            for entry in judgment.get("relevant", []):
                if entry["relevance"] >= self.bm.RELEVANT_THRESHOLD:
                    self.assertTrue(str(entry.get("rationale", "")).strip(), judgment["query_id"])

    def test_judgments_reference_existing_records(self):
        retriever = self.bm.get_retriever("project")
        corpus_keys = {self.bm.record_key(r) for r in self.bm.corpus_records(retriever)}
        for judgment in self.judgments_doc["judgments"]:
            for entry in judgment.get("relevant", []):
                key = (entry["tradition"], entry["work"], entry["locator"])
                self.assertIn(key, corpus_keys, "judgment {} -> {}".format(judgment["query_id"], key))

    def test_no_answer_queries_are_explicit(self):
        no_answer = [j for j in self.judgments_doc["judgments"] if j.get("no_answer")]
        self.assertTrue(no_answer, "expected at least one no_answer judgment")
        for judgment in no_answer:
            self.assertEqual(judgment.get("relevant", []), [])  # no record is direct support
        # and the runner classifies every no_answer query explicitly
        for entry in self.result["per_query"]:
            if entry["no_answer"]:
                self.assertIn(entry["outcome"], ("no_answer_ok", "false_support"))

    # ---- runner ----

    def test_runner_is_deterministic(self):
        again = self.bm.run_benchmark("project", self.bm.DEFAULT_KS)
        self.assertEqual(
            self.bm.reproducible_view(self.result), self.bm.reproducible_view(again)
        )
        self.assertTrue(self.result["contract"]["deterministic_repeat"])

    def test_json_has_required_metric_keys(self):
        summary = self.result["summary"]
        for key in ("recall_at_k", "precision_at_k", "ndcg_at_k", "mrr",
                    "exact_span_hit_rate", "no_answer_correct_rate", "false_support_rate"):
            self.assertIn(key, summary)
        for k in ("1", "3", "5"):
            self.assertIn(k, summary["recall_at_k"])
        contract = self.result["contract"]
        for key in ("stable_occurrence_identity_present", "deterministic_repeat",
                    "occurrence_scheme_counts", "required_envelope_fields_present",
                    "citation_fidelity", "span_assurance"):
            self.assertIn(key, contract)

    def test_identity_is_stable_not_position_scoped(self):
        contract = self.result["contract"]
        self.assertTrue(contract["stable_occurrence_identity_present"])
        self.assertTrue(contract["required_envelope_fields_present"])
        # The whole corpus is file-based, so every retrieved record uses the corpus-stable scheme —
        # never the order-scoped index-fallback (ADR 0005).
        self.assertEqual(list(contract["occurrence_scheme_counts"]), ["occ/v1-corpus-stable"])

    def test_citation_fidelity_is_measured_and_perfect(self):
        # Measured, not assumed: occurrence ids of returned+relevant records must agree across two
        # runs AND a reordering of the result list (the spec's enforcement-critical metric).
        cf = self.result["contract"]["citation_fidelity"]
        self.assertGreater(cf["records"], 0)
        self.assertEqual(cf["stable_records"], cf["records"])
        self.assertEqual(cf["fidelity"], 1.0)
        self.assertTrue(cf["reproducible_across_two_runs_and_reorder"])
        self.assertEqual(cf["unstable"], [])

    def test_span_assurance_status_is_concrete(self):
        # A concrete status, not a prose note: retrieval mints no span tier; the artifact-backed
        # source_assurance floor is reported, and edition-backed is explicitly false (A2-only).
        sa = self.result["contract"]["span_assurance"]
        self.assertIsNone(sa["tier_at_retrieval"])
        self.assertEqual(sa["span_tiers_minted_at_retrieval"], [])
        self.assertFalse(sa["edition_backed_span_verified"])
        self.assertEqual(sa["source_assurance_floor"], "artifact-backed")
        self.assertTrue(sa["all_records_artifact_backed"])

    def test_search_needs_only_the_contract_surface(self):
        # The runner must measure through the contract: search() may use only TRADITIONS,
        # retrieve_envelope(), and the lexical score() signal — never parse_reference() or any other
        # internal. A proxy exposing ONLY the contract surface must produce the identical ranking.
        retriever = self.bm.get_retriever("project")
        proxy = types.SimpleNamespace(
            TRADITIONS=retriever.TRADITIONS,
            retrieve_envelope=retriever.retrieve_envelope,
            score=retriever.score,
        )
        self.assertFalse(hasattr(proxy, "parse_reference"))
        for query in ("道", "愛人", "約翰福音 3:16"):
            self.assertEqual(
                [self.bm.record_key(r) for r, _ in self.bm.search(proxy, query, 5)],
                [self.bm.record_key(r) for r, _ in self.bm.search(retriever, query, 5)],
            )

    def test_non_lexical_backend_is_refused_not_mismeasured(self):
        # A future backend that satisfies the retrieval contract but is not the lexical file baseline
        # must be refused with a clear error, never silently measured by the score() ranking.
        stub = types.SimpleNamespace(
            capabilities=lambda: {
                "retriever_kind": "project-index",
                "contract_version": "religion-council/retrieval/v1",
            },
            TRADITIONS={"x"},
            score=lambda q, r: 0,
        )
        with self.assertRaises(ValueError):
            self.bm._require_lexical_baseline(stub)
        # The real baselines pass the guard.
        for kind in ("project", "portable"):
            self.bm._require_lexical_baseline(self.bm.get_retriever(kind))

    def test_judging_provenance_is_disclosed(self):
        j = self.result["judging"]
        self.assertEqual(j["independent_judge_count"], 1)
        self.assertIsNone(j["inter_annotator_agreement"])  # single-curator baseline: n/a, not faked
        self.assertTrue(str(j.get("disclosure", "")).strip())
        self.assertTrue(j.get("judges"))

    def test_invalid_k_is_rejected_not_crashed(self):
        # --k 0 used to raise ZeroDivisionError; it must now be a clean CLI error.
        for bad in ("0", "-3"):
            with self.assertRaises(SystemExit):
                self.bm.main(["--retriever", "project", "--k", bad])

    def test_project_and_portable_are_equivalent(self):
        # The project retriever wraps the portable one, so the measured baseline is identical except
        # for the declared retriever_kind (ADR 0006 §4.2).
        project = self.bm.reproducible_view(self.result)
        portable = self.bm.reproducible_view(self.bm.run_benchmark("portable", self.bm.DEFAULT_KS))
        project.pop("retriever_kind")
        portable.pop("retriever_kind")
        self.assertEqual(project, portable)

    def test_runner_imports_no_network_modules(self):
        # "Benchmark can run offline": the runner imports only stdlib + the project's own modules.
        tree = ast.parse(RUNNER_PATH.read_text(encoding="utf-8"))
        imported = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported.update(alias.name.split(".")[0] for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imported.add(node.module.split(".")[0])
        self.assertEqual(imported & NETWORK_MODULES, set())

    # ---- committed baseline ----

    def test_committed_baseline_report_is_reproducible(self):
        committed = json.loads(RESULT_JSON.read_text(encoding="utf-8"))
        fresh = self.bm.reproducible_view(self.result)
        self.assertEqual(
            committed,
            fresh,
            "committed baseline is stale — regenerate it with:\n"
            "  python scripts/run_retrieval_benchmark.py --retriever project --k 1 --k 3 --k 5 \\\n"
            "    --json-out docs/benchmarks/results/retrieval-v1-lexical-baseline.json \\\n"
            "    --md-out docs/benchmarks/results/retrieval-v1-lexical-baseline.md",
        )


if __name__ == "__main__":
    unittest.main()
