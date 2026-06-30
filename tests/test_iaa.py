"""Tests for the inter-annotator-agreement (Cohen's κ) infrastructure (ADR 0007 §9 gate).

These cover the standard-library κ math (scripts/compute_iaa.py) against hand-computed values, the
additive ``judging.iaa`` pool wiring, and the benchmark runner surfacing the computed figure. They
also pin the committed fixture's disclosed model-judge κ state — a guard so a second judge's labels
are never silently committed without provenance, limitations, and a freshly computed figure (the
figure must be earned, not fabricated).
"""
import ast
import importlib.util
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
IAA_PATH = ROOT / "scripts" / "compute_iaa.py"
RUNNER_PATH = ROOT / "scripts" / "run_retrieval_benchmark.py"
NETWORK_MODULES = {"socket", "urllib", "http", "ftplib", "asyncio", "requests", "httpx", "aiohttp"}


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _pool(*rows):
    """Build an iaa pool from (curator-1 label, judge-2 label) rows."""
    pool = []
    for i, (a, b) in enumerate(rows):
        pool.append({
            "query_id": "q{:03d}".format(i),
            "tradition": "t", "work": "w", "locator": "l{}".format(i),
            "labels": {"curator-1": a, "judge-2": b},
        })
    return {"judges": [{"id": "curator-1", "independent": False},
                       {"id": "judge-2", "independent": True}],
            "independent_judge_count": 2, "agreement_method": "cohen_kappa",
            "iaa": {"label_set": [0, 1, 2], "pool": pool}}


class CohenKappaMathTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.iaa = _load("rc_iaa_math", IAA_PATH)

    def test_perfect_agreement_is_one(self):
        self.assertEqual(self.iaa.cohen_kappa([2, 1, 0, 1], [2, 1, 0, 1]), 1.0)

    def test_total_disagreement_is_minus_one(self):
        self.assertEqual(self.iaa.cohen_kappa([1, 0, 1, 0], [0, 1, 0, 1]), -1.0)

    def test_known_binary_example(self):
        # Hand-computed: po=0.6, pe=0.5 -> κ = (0.6-0.5)/(1-0.5) = 0.2.
        a = [1, 1, 1, 1, 1, 0, 0, 0, 0, 0]
        b = [1, 1, 1, 0, 0, 1, 1, 0, 0, 0]
        self.assertAlmostEqual(self.iaa.cohen_kappa(a, b), 0.2, places=10)

    def test_known_three_category_example(self):
        # Hand-computed: po=0.6, pe=0.4 -> κ = 0.2/0.6 = 0.3333...
        a = [2, 2, 2, 1, 1]
        b = [2, 2, 1, 1, 0]
        self.assertAlmostEqual(self.iaa.cohen_kappa(a, b), 1 / 3, places=10)

    def test_empty_is_none_not_zero(self):
        self.assertIsNone(self.iaa.cohen_kappa([], []))

    def test_degenerate_single_category_is_none(self):
        # Both raters used one identical category throughout -> pe == 1, κ undefined (not 1.0).
        self.assertIsNone(self.iaa.cohen_kappa([1, 1, 1], [1, 1, 1]))

    def test_misaligned_lengths_raise(self):
        with self.assertRaises(ValueError):
            self.iaa.cohen_kappa([1, 2], [1])


class IaaPoolTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.iaa = _load("rc_iaa_pool", IAA_PATH)

    def test_overall_kappa_from_pool(self):
        judging = _pool((2, 2), (2, 2), (2, 1), (1, 1), (1, 0))
        self.assertEqual(self.iaa.overall_kappa(judging), 0.3333)

    def test_pairwise_structure(self):
        summary = self.iaa.pairwise_kappa(_pool((2, 2), (2, 1), (1, 1)))
        self.assertEqual(summary["judges"], ["curator-1", "judge-2"])
        self.assertEqual(summary["pool_size"], 3)
        self.assertEqual(len(summary["pairs"]), 1)
        self.assertEqual(summary["pairs"][0]["judges"], ["curator-1", "judge-2"])
        self.assertEqual(summary["pairs"][0]["n"], 3)

    def test_single_judge_pool_is_none(self):
        judging = {"iaa": {"pool": [{"query_id": "q1", "labels": {"curator-1": 2}}]}}
        self.assertIsNone(self.iaa.pairwise_kappa(judging))
        self.assertIsNone(self.iaa.overall_kappa(judging))

    def test_no_pool_is_none(self):
        self.assertIsNone(self.iaa.overall_kappa({"judges": [], "inter_annotator_agreement": None}))

    def test_report_for_two_judges_is_computed(self):
        data = self.iaa.report(_pool((2, 2), (2, 1), (1, 1), (1, 0)))
        self.assertEqual(data["status"], "computed")
        self.assertEqual(data["independent_judge_count"], 2)
        self.assertEqual(data["method"], "cohen_kappa")
        self.assertIsNotNone(data["inter_annotator_agreement"])


class CommittedFixtureModelJudgeTest(unittest.TestCase):
    """Pin the committed retrieval-v1 fixture's *disclosed model-judge* κ state (ADR 0007 §9).

    The second judge is an explicitly disclosed model judge (claude-opus-4-8). The declared κ must
    equal the κ freshly computed from the pool (no drift, no hand-written figure), the model judge
    must never be labeled human, and every pooled record must be a real corpus record.
    """

    @classmethod
    def setUpClass(cls):
        cls.iaa = _load("rc_iaa_fixture", IAA_PATH)
        cls.judging = cls.iaa.load_judging()

    def test_two_disclosed_judges_with_computed_kappa(self):
        data = self.iaa.report(self.judging)
        self.assertEqual(data["status"], "computed")
        self.assertEqual(data["independent_judge_count"], 2)
        self.assertEqual(data["method"], "cohen_kappa")
        self.assertIsInstance(data["inter_annotator_agreement"], float)

    def test_declared_kappa_matches_pool_computation(self):
        # the fixture's declared figure must equal what compute_iaa derives from the pool — never a
        # hand-written number that can silently drift from the labels.
        self.assertEqual(self.judging["inter_annotator_agreement"],
                         self.iaa.overall_kappa(self.judging))

    def test_second_judge_is_disclosed_as_model_not_human(self):
        model = [j for j in self.judging["judges"] if j.get("judge_type") == "model"]
        self.assertEqual(len(model), 1)
        self.assertNotEqual(model[0].get("judge_type"), "human")
        self.assertTrue(model[0].get("limitation"))
        self.assertTrue(model[0].get("independence_note"))
        self.assertIn("model", self.judging["disclosure"].lower())

    def test_pool_records_exist_in_corpus(self):
        # every pooled (tradition, work, locator) must be a real corpus record — no phantom items.
        portable = _load(
            "rc_portable_pool", ROOT / "skills" / "religion-council" / "scripts" / "retrieve.py")
        corpus = set()
        for tradition in portable.TRADITIONS:
            for rec in portable.parse_reference(tradition):
                corpus.add((rec["tradition"], rec["work"], rec["locator"]))
        for item in self.judging["iaa"]["pool"]:
            self.assertIn((item["tradition"], item["work"], item["locator"]), corpus)

    def test_cli_runs_offline_and_returns_zero(self):
        self.assertEqual(self.iaa.main([]), 0)
        self.assertEqual(self.iaa.main(["--json"]), 0)

    def test_compute_iaa_imports_no_network_modules(self):
        tree = ast.parse(IAA_PATH.read_text(encoding="utf-8"))
        imported = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported.update(alias.name.split(".")[0] for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imported.add(node.module.split(".")[0])
        self.assertEqual(imported & NETWORK_MODULES, set())


class RunnerSurfacesKappaTest(unittest.TestCase):
    """The benchmark runner computes κ from the pool when ≥2 judges exist, n/a otherwise."""

    @classmethod
    def setUpClass(cls):
        cls.bm = _load("rc_runner_iaa", RUNNER_PATH)

    def test_disclosure_surfaces_computed_kappa(self):
        doc = {"judging": _pool((2, 2), (2, 2), (2, 1), (1, 1), (1, 0))}
        disclosure = self.bm.judging_disclosure(doc)
        self.assertEqual(disclosure["inter_annotator_agreement"], 0.3333)
        self.assertEqual(disclosure["independent_judge_count"], 2)
        self.assertEqual(disclosure["agreement_method"], "cohen_kappa")

    def test_disclosure_stays_na_without_pool(self):
        doc = {"judging": {"judges": [{"id": "curator-1"}], "independent_judge_count": 1,
                           "inter_annotator_agreement": None, "agreement_method": "cohen_kappa"}}
        disclosure = self.bm.judging_disclosure(doc)
        self.assertIsNone(disclosure["inter_annotator_agreement"])
        self.assertEqual(disclosure["independent_judge_count"], 1)


if __name__ == "__main__":
    unittest.main()
