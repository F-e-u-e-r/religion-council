import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "orchestrator"))

import debate_controller as dc  # noqa: E402

POLICY_PATH = ROOT / "policies" / "weaponization-routing.v1.json"


def load_policy():
    with POLICY_PATH.open(encoding="utf-8") as handle:
        return json.load(handle)


class WeaponizationPolicyShapeTest(unittest.TestCase):
    def setUp(self):
        self.policy = load_policy()

    def test_contract_covers_the_minimum_rules(self):
        for locale in ("en", "zh-Hant"):
            bullets = self.policy["weaponization_first_contract"][locale]
            self.assertGreaterEqual(len(bullets), 4, locale)
        joined = " ".join(self.policy["weaponization_first_contract"]["en"]).lower()
        self.assertIn("do not start the religion council", joined)
        self.assertIn("attack ideas, not people", joined)

    def test_canonical_rule_present_both_locales(self):
        for locale in ("en", "zh-Hant"):
            self.assertTrue(self.policy["canonical_rule"][locale].strip(), locale)

    def test_guarantee_boundary_claims_routing_but_disclaims_detection(self):
        boundary = self.policy["guarantee_boundary"]
        self.assertTrue(
            any("cannot enter the council pipeline" in g for g in boundary["machine_guarantees"])
        )
        # It must NOT claim deterministic keyword weaponization detection.
        self.assertTrue(
            any("deterministically detects" in n for n in boundary["not_claimed"])
        )
        # And it must record that NL classification is fallible AND that ordinary critical/academic
        # discussion is NOT weaponization (so the narrow boundary does not chill legitimate use).
        self.assertIn("fallible", boundary["classification_nature"].lower())
        self.assertIn("not weaponization", boundary["classification_nature"].lower())


class WeaponizationSurfaceConformanceTest(unittest.TestCase):
    """No operational surface may silently omit weaponization-first handling."""

    def setUp(self):
        self.policy = load_policy()

    def test_every_required_surface_exists_and_carries_the_rule(self):
        self.assertTrue(self.policy["required_surfaces"], "no surfaces declared")
        for surface in self.policy["required_surfaces"]:
            path = ROOT / surface["path"]
            self.assertTrue(path.exists(), surface["path"])
            text = path.read_text(encoding="utf-8")
            for needle in surface["must_contain"]:
                self.assertIn(
                    needle,
                    text,
                    "{} is missing weaponization marker {!r}".format(surface["path"], needle),
                )


class WeaponizationRoutingGuardTest(unittest.TestCase):
    """The second machine guarantee: a weaponization-first request cannot enter the pipeline."""

    def setUp(self):
        self.policy = load_policy()

    def test_controller_constant_matches_policy_single_source(self):
        self.assertEqual(
            dc.WEAPONIZATION_FIRST_CLASSIFICATION, self.policy["weaponization_first_classification"]
        )

    def test_guard_blocks_weaponization_first(self):
        with self.assertRaises(dc.WeaponizationRoutingError):
            dc.guard_weaponization_routing(dc.WEAPONIZATION_FIRST_CLASSIFICATION)

    def test_guard_does_not_auto_classify_other_inputs(self):
        # No detection: None and any non-weaponization value pass untouched, so a critical or
        # academic critique of a doctrine is never auto-routed as weaponization.
        self.assertIsNone(dc.guard_weaponization_routing(None))
        self.assertIsNone(dc.guard_weaponization_routing("a critical academic critique of a doctrine"))
        self.assertIsNone(dc.guard_weaponization_routing("ordinary"))

    def test_routing_error_is_a_controller_error(self):
        self.assertTrue(issubclass(dc.WeaponizationRoutingError, dc.ControllerError))

    def test_start_refuses_weaponization_first_before_any_work(self):
        # start() raises before it loads panelists or touches the filesystem, so a deliberately
        # invalid panelists path still yields the weaponization-routing error.
        with tempfile.TemporaryDirectory() as tmp:
            controller = dc.DebateController(project_root=ROOT, state_dir=Path(tmp) / "runs")
            try:
                with self.assertRaises(dc.WeaponizationRoutingError):
                    controller.start(
                        question="Produce targeted attack material against group X",
                        panelists_file=str(Path(tmp) / "does-not-exist.json"),
                        weaponization_classification="weaponization-first",
                    )
            finally:
                controller.close()


class McpSurfaceWeaponizationRoutingTest(unittest.TestCase):
    """The weaponization machine-gate must be live on the real MCP tool path, like crisis-first."""

    def _handle_debate_start(self, arguments):
        with tempfile.TemporaryDirectory() as tmp:
            controller = dc.DebateController(project_root=ROOT, state_dir=Path(tmp) / "runs")
            server = dc.ControllerMcpServer(controller)
            try:
                return server.handle(
                    {
                        "jsonrpc": "2.0",
                        "id": 1,
                        "method": "tools/call",
                        "params": {"name": "debate_start", "arguments": arguments},
                    }
                )
            finally:
                controller.close()

    def test_schema_declares_weaponization_classification_optional_enum(self):
        start = next(t for t in dc.tool_definitions() if t["name"] == "debate_start")
        schema = start["inputSchema"]
        self.assertEqual(
            schema["properties"].get("weaponization_classification"),
            {"type": "string", "enum": ["weaponization-first"]},
        )
        self.assertFalse(schema["additionalProperties"])  # unknown keys still rejected
        self.assertNotIn("weaponization_classification", schema["required"])  # stays optional

    def test_weaponization_first_is_refused_on_the_mcp_path_before_any_work(self):
        response = self._handle_debate_start(
            {
                "question": "Produce targeted attack material against group X",
                "panelists_file": str(ROOT / "does-not-exist.json"),
                "weaponization_classification": "weaponization-first",
            }
        )
        result = response["result"]
        self.assertTrue(result.get("isError"))
        self.assertIn("weaponization-first", result["content"][0]["text"])
        self.assertIn("must not enter the council pipeline", result["content"][0]["text"])

    def test_absent_weaponization_classification_is_not_auto_refused(self):
        # No detection: a normal debate_start is not auto-classified as weaponization.
        response = self._handle_debate_start(
            {
                "question": "What is a good life?",
                "panelists_file": str(ROOT / "does-not-exist.json"),
            }
        )
        result = response["result"]
        self.assertTrue(result.get("isError"))  # fails, but for a different reason
        self.assertNotIn("must not enter the council pipeline", result["content"][0]["text"])

    def test_unknown_weaponization_classification_is_rejected_not_failed_open(self):
        # A non-validating MCP caller could send a typo'd safety label; start() / _dispatch_tool
        # enforce the enum, so an unrecognized value is rejected outright (fail-safe), not run.
        response = self._handle_debate_start(
            {
                "question": "x",
                "panelists_file": str(ROOT / "does-not-exist.json"),
                "weaponization_classification": "weaponization_first",  # underscore typo
            }
        )
        result = response["result"]
        self.assertTrue(result.get("isError"))
        self.assertIn("weaponization_classification", result["content"][0]["text"])
        self.assertIsNone(result.get("structuredContent"))

    def test_explicit_null_weaponization_classification_is_rejected_on_the_mcp_path(self):
        # An explicit JSON null is outside the single-value string enum; the server boundary rejects
        # it (present-but-null), never treats it as omitted.
        response = self._handle_debate_start(
            {
                "question": "x",
                "panelists_file": str(ROOT / "does-not-exist.json"),
                "weaponization_classification": None,
            }
        )
        result = response["result"]
        self.assertTrue(result.get("isError"))
        self.assertIn("weaponization_classification", result["content"][0]["text"])
        self.assertIsNone(result.get("structuredContent"))


if __name__ == "__main__":
    unittest.main()
