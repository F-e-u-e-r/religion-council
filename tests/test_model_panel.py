"""Tests for the retrieval-v1 model-panel evidence tooling (ADR 0007 §9).

Covers the generalized judge-template validator (human OR model), the committed Claude/Opus filled
panel pass (which must equal the fixture's model-judge-claude labels — one source of truth, no drift),
and the pairwise Cohen's κ panel-agreement script (which must surface same- vs cross-provider pairs).
"""
import ast
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
VALIDATOR = ROOT / "scripts" / "validate_human_judge_template.py"
PANEL_SCRIPT = ROOT / "scripts" / "compute_panel_agreement.py"
FIXTURE = ROOT / "docs" / "benchmarks" / "judgments" / "retrieval-v1.json"
CLAUDE = ROOT / "docs" / "benchmarks" / "judgments" / "panel" / "retrieval-v1-model-judge-claude-opus.json"
NETWORK_MODULES = {"socket", "urllib", "http", "ftplib", "asyncio", "requests", "httpx", "aiohttp"}


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _key(item):
    return (item["query_id"], item["tradition"], item["work"], item["locator"])


class ModelPanelValidatorTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.v = _load("rc_validate_panel", VALIDATOR)
        cls.claude = json.loads(CLAUDE.read_text("utf-8"))
        cls.fixture_keys = cls.v.fixture_pool_keys()

    def test_model_judge_type_is_accepted(self):
        self.assertIn("model", self.v.ALLOWED_JUDGE_TYPES)
        self.assertEqual(self.v.validate(self.claude, self.fixture_keys, filled=True), [])

    def test_unknown_judge_type_is_rejected(self):
        bad = json.loads(CLAUDE.read_text("utf-8"))
        bad["judge"]["judge_type"] = "robot"
        self.assertTrue(self.v.validate(bad, self.fixture_keys, filled=True))

    def test_claude_panel_is_blind_and_disclosed(self):
        judge = self.claude["judge"]
        self.assertEqual(judge["judge_type"], "model")
        for field in ("id", "provider", "model", "date", "prompt", "blind_to"):
            self.assertTrue(judge.get(field), field)
        for item in self.claude["pool"]:
            self.assertNotIn("labels", item)          # no multi-rater leak
            self.assertNotIn("curator-1", item)
            self.assertIn(item["label"], (0, 1, 2))

    def test_cli_filled_returns_zero(self):
        self.assertEqual(self.v.main([str(CLAUDE), "--filled"]), 0)


class ClaudePanelMatchesFixtureTest(unittest.TestCase):
    """One source of truth: the Claude panel file == the committed model-judge-claude pass."""

    def test_labels_match_fixture_model_judge(self):
        claude = {(_key(i)): i["label"] for i in json.loads(CLAUDE.read_text("utf-8"))["pool"]}
        pool = json.loads(FIXTURE.read_text("utf-8"))["judging"]["iaa"]["pool"]
        fixture = {_key(i): i["labels"]["model-judge-claude"] for i in pool}
        self.assertEqual(claude, fixture)
        self.assertEqual(len(claude), 110)


class PanelAgreementTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.p = _load("rc_panel", PANEL_SCRIPT)

    def test_curator_vs_claude_matches_committed_kappa(self):
        pairs = self.p.pairwise(self.p.build_raters([str(CLAUDE)]))
        self.assertEqual(len(pairs), 1)
        pair = pairs[0]
        self.assertEqual(set(pair["judges"]), {"curator-1", "model-judge-claude-opus"})
        self.assertEqual(pair["kappa"], 0.4436)
        self.assertEqual(pair["n"], 110)
        self.assertEqual(pair["relation"], "cross-provider")

    def test_pairwise_tags_same_vs_cross_provider(self):
        raters = [
            ("curator-1", "human", {("q", "t", "w", "1"): 2, ("q", "t", "w", "2"): 1}),
            ("claude-a", "anthropic", {("q", "t", "w", "1"): 2, ("q", "t", "w", "2"): 0}),
            ("claude-b", "anthropic", {("q", "t", "w", "1"): 2, ("q", "t", "w", "2"): 1}),
            ("gpt", "openai", {("q", "t", "w", "1"): 1, ("q", "t", "w", "2"): 1}),
        ]
        pairs = {tuple(p["judges"]): p for p in self.p.pairwise(raters)}
        self.assertEqual(pairs[("claude-a", "claude-b")]["relation"], "same-provider")
        self.assertEqual(pairs[("claude-a", "gpt")]["relation"], "cross-provider")
        self.assertEqual(len(pairs), 6)  # C(4,2)

    def test_panel_rater_reads_filled_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "f.json"
            path.write_text(json.dumps({
                "judge": {"id": "gemini", "provider": "google"},
                "pool": [{"query_id": "q1", "tradition": "t", "work": "w", "locator": "1", "label": 2}],
            }), encoding="utf-8")
            jid, provider, labels = self.p.panel_rater(path)
            self.assertEqual((jid, provider), ("gemini", "google"))
            self.assertEqual(labels[("q1", "t", "w", "1")], 2)

    def test_cli_runs(self):
        self.assertEqual(self.p.main([str(CLAUDE)]), 0)
        self.assertEqual(self.p.main([str(CLAUDE), "--json"]), 0)

    def test_panel_script_imports_no_network_modules(self):
        tree = ast.parse(PANEL_SCRIPT.read_text(encoding="utf-8"))
        imported = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported.update(alias.name.split(".")[0] for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imported.add(node.module.split(".")[0])
        self.assertEqual(imported & NETWORK_MODULES, set())


if __name__ == "__main__":
    unittest.main()
