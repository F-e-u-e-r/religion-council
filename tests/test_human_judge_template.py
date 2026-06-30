"""Tests for the retrieval-v1 human blind-judge template + validator (ADR 0007 §9 gate package).

The committed template must stay BLIND (no curator-1 / model-judge answers), complete (its pool keys
match the fixture's ``judging.iaa.pool`` exactly), and unfilled (all labels null). The validator must
accept a well-formed filled pass and reject leaks, bad labels, and pool drift.
"""
import ast
import copy
import importlib.util
import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
VALIDATOR = ROOT / "scripts" / "validate_human_judge_template.py"
TEMPLATE = ROOT / "docs" / "benchmarks" / "judgments" / "templates" / "retrieval-v1-human-blind-template.json"
FIXTURE = ROOT / "docs" / "benchmarks" / "judgments" / "retrieval-v1.json"
NETWORK_MODULES = {"socket", "urllib", "http", "ftplib", "asyncio", "requests", "httpx", "aiohttp"}


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class HumanJudgeTemplateTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.v = _load("rc_validate_human", VALIDATOR)
        cls.template = json.loads(TEMPLATE.read_text("utf-8"))
        cls.fixture_keys = cls.v.fixture_pool_keys()

    def _filled(self):
        """A valid filled copy of the committed template."""
        t = copy.deepcopy(self.template)
        t["judge"]["id"] = "human-judge-1"
        for item in t["pool"]:
            item["label"] = 1
        return t

    # ---- committed blank template ----

    def test_committed_template_is_valid_blank(self):
        self.assertEqual(self.v.validate(self.template, self.fixture_keys, filled=False), [])

    def test_committed_template_is_blind(self):
        # no item may carry an existing judge's answer, and every label is unset.
        for item in self.template["pool"]:
            self.assertNotIn("labels", item)
            self.assertNotIn("curator-1", item)
            self.assertNotIn("model-judge-claude", item)
            self.assertIsNone(item["label"])
        self.assertEqual(self.template["judge"]["judge_type"], "human")
        self.assertTrue(self.template["judge"]["blind_to"])

    def test_template_pool_matches_fixture_exactly(self):
        keys = {(i["query_id"], i["tradition"], i["work"], i["locator"]) for i in self.template["pool"]}
        self.assertEqual(keys, self.fixture_keys)
        self.assertEqual(len(self.template["pool"]), len(self.fixture_keys))

    def test_template_items_carry_content_for_blind_judging(self):
        # a human must be able to judge from the file alone: query + the record's own text.
        for item in self.template["pool"]:
            self.assertTrue(item["query"].strip())
            self.assertTrue(item["text"].strip() or item["topic"].strip())

    # ---- validator behavior ----

    def test_filled_template_validates(self):
        self.assertEqual(self.v.validate(self._filled(), self.fixture_keys, filled=True), [])

    def test_filled_blank_mode_mismatch_is_rejected(self):
        self.assertTrue(self.v.validate(self._filled(), self.fixture_keys, filled=False))
        # ...and a blank template fails --filled.
        self.assertTrue(self.v.validate(self.template, self.fixture_keys, filled=True))

    def test_bad_label_is_rejected(self):
        t = self._filled()
        t["pool"][0]["label"] = 3
        self.assertTrue(self.v.validate(t, self.fixture_keys, filled=True))

    def test_missing_judge_id_is_rejected_when_filled(self):
        t = self._filled()
        t["judge"]["id"] = ""
        self.assertTrue(self.v.validate(t, self.fixture_keys, filled=True))

    def test_leaked_label_is_rejected(self):
        t = self._filled()
        t["pool"][0]["labels"] = {"curator-1": 2}  # blindness violation
        self.assertTrue(self.v.validate(t, self.fixture_keys, filled=True))

    def test_pool_drift_is_rejected(self):
        t = self._filled()
        t["pool"].pop()  # missing item vs the fixture
        self.assertTrue(self.v.validate(t, self.fixture_keys, filled=True))

    def test_cli_blank_returns_zero(self):
        self.assertEqual(self.v.main([str(TEMPLATE), "--blank"]), 0)

    def test_validator_imports_no_network_modules(self):
        tree = ast.parse(VALIDATOR.read_text(encoding="utf-8"))
        imported = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported.update(alias.name.split(".")[0] for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imported.add(node.module.split(".")[0])
        self.assertEqual(imported & NETWORK_MODULES, set())


if __name__ == "__main__":
    unittest.main()
