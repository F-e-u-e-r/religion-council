import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "orchestrator"))

import debate_controller as dc  # noqa: E402

POLICY_PATH = ROOT / "policies" / "safety-routing.v1.json"


def load_policy():
    with POLICY_PATH.open(encoding="utf-8") as handle:
        return json.load(handle)


class PolicyShapeTest(unittest.TestCase):
    def setUp(self):
        self.policy = load_policy()

    def test_contract_covers_the_minimum_crisis_first_rules(self):
        # The plan's minimum contract, single-sourced here, must be present in both locales.
        for locale in ("en", "zh-Hant"):
            bullets = self.policy["crisis_first_contract"][locale]
            self.assertGreaterEqual(len(bullets), 6, locale)
        joined = " ".join(self.policy["crisis_first_contract"]["en"]).lower()
        self.assertIn("do not start the religion council", joined)
        self.assertIn("immediate safety", joined)
        self.assertIn("secondary supplement", joined)

    def test_canonical_rule_present_both_locales(self):
        for locale in ("en", "zh-Hant"):
            self.assertTrue(self.policy["canonical_rule"][locale].strip(), locale)

    def test_guarantee_boundary_claims_routing_but_disclaims_detection(self):
        boundary = self.policy["guarantee_boundary"]
        self.assertTrue(
            any("cannot enter the council pipeline" in g for g in boundary["machine_guarantees"])
        )
        # It must NOT claim deterministic keyword crisis detection.
        self.assertTrue(
            any("deterministically detects" in n for n in boundary["not_claimed"])
        )
        # And it must record that NL classification is a distinct, fallible boundary so that
        # ordinary academic discussion is not treated as a confirmed live crisis.
        self.assertIn("fallible", boundary["classification_nature"].lower())
        self.assertIn("not", boundary["classification_nature"].lower())


class SurfaceConformanceTest(unittest.TestCase):
    """No distribution surface may silently omit crisis-first handling."""

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
                    "{} is missing crisis-first marker {!r}".format(surface["path"], needle),
                )

    def test_the_canonical_distribution_surfaces_are_all_covered(self):
        # Guards against a surface being quietly dropped from the registry.
        covered = {s["path"] for s in self.policy["required_surfaces"]}
        for expected in (
            "DISCLAIMER.md",
            "README.md",
            "skills/religion-council/SKILL.md",
            ".claude/skills/religion-council/SKILL.md",
            ".claude/agents/council-moderator.md",
        ):
            self.assertIn(expected, covered)


class RoutingGuardTest(unittest.TestCase):
    """The one machine guarantee: a crisis-first request cannot enter the pipeline."""

    def setUp(self):
        self.policy = load_policy()

    def test_controller_constant_matches_policy_single_source(self):
        self.assertEqual(
            dc.CRISIS_FIRST_CLASSIFICATION, self.policy["crisis_first_classification"]
        )

    def test_guard_blocks_crisis_first(self):
        with self.assertRaises(dc.CrisisRoutingError):
            dc.guard_crisis_routing(dc.CRISIS_FIRST_CLASSIFICATION)

    def test_guard_does_not_auto_classify_other_inputs(self):
        # No detection: None and any non-crisis-first classification pass untouched, so a normal
        # academic question (even one mentioning self-harm) is never auto-routed as a live crisis.
        self.assertIsNone(dc.guard_crisis_routing(None))
        self.assertIsNone(dc.guard_crisis_routing("a question that mentions self-harm academically"))
        self.assertIsNone(dc.guard_crisis_routing("ordinary"))

    def test_crisis_routing_error_is_a_controller_error(self):
        # Existing `except ControllerError` handlers still fail closed on crisis routing.
        self.assertTrue(issubclass(dc.CrisisRoutingError, dc.ControllerError))

    def test_start_refuses_crisis_first_before_any_work(self):
        # Integration: start() raises before it ever loads panelists or touches the filesystem,
        # so a deliberately invalid panelists path still yields the crisis-routing error.
        with tempfile.TemporaryDirectory() as tmp:
            controller = dc.DebateController(project_root=ROOT, state_dir=Path(tmp) / "runs")
            try:
                with self.assertRaises(dc.CrisisRoutingError):
                    controller.start(
                        question="I am in danger right now",
                        panelists_file=str(Path(tmp) / "does-not-exist.json"),
                        crisis_classification="crisis-first",
                    )
            finally:
                controller.close()


class McpSurfaceCrisisRoutingTest(unittest.TestCase):
    """The crisis machine-gate must be live on the real MCP tool path, not only via a direct
    Python start(). These drive ControllerMcpServer.handle(tools/call) end to end (R1)."""

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

    def test_schema_declares_crisis_classification_optional_enum(self):
        start = next(t for t in dc.tool_definitions() if t["name"] == "debate_start")
        schema = start["inputSchema"]
        self.assertEqual(
            schema["properties"].get("crisis_classification"),
            {"type": "string", "enum": ["crisis-first"]},
        )
        self.assertFalse(schema["additionalProperties"])  # unknown keys still rejected
        self.assertNotIn("crisis_classification", schema["required"])  # stays optional

    def test_crisis_first_is_refused_on_the_mcp_path_before_any_work(self):
        # A crisis-first debate_start must be refused via the real dispatch path, before any
        # panelist / run-dir / snapshot work — proving the guarantee is machine-enforced on the
        # tool surface, not only in a direct Python call. The panelists_file deliberately does not
        # exist: the guard fires first (start() calls guard_crisis_routing before any work), so we
        # never reach it.
        response = self._handle_debate_start(
            {
                "question": "I am in danger right now",
                "panelists_file": str(ROOT / "does-not-exist.json"),
                "crisis_classification": "crisis-first",
            }
        )
        result = response["result"]
        self.assertTrue(result.get("isError"))
        self.assertIn("crisis-first", result["content"][0]["text"])
        self.assertIn("must not enter the council pipeline", result["content"][0]["text"])

    def test_absent_crisis_classification_is_not_auto_refused(self):
        # No detection: a normal debate_start is not auto-classified. It passes the guard and here
        # fails later on the missing panelists file, so the error is NOT the crisis refusal.
        response = self._handle_debate_start(
            {
                "question": "What is a good life?",
                "panelists_file": str(ROOT / "does-not-exist.json"),
            }
        )
        result = response["result"]
        self.assertTrue(result.get("isError"))  # fails, but for a different reason
        self.assertNotIn("must not enter the council pipeline", result["content"][0]["text"])

    def test_unknown_crisis_classification_is_rejected_not_failed_open(self):
        # A non-validating MCP caller could send a typo'd safety label; the inputSchema enum is only
        # advisory on the host. start() enforces it server-side, so an unrecognized value is rejected
        # outright (fail-safe) — it must NOT start a run as if it were a non-crisis request.
        response = self._handle_debate_start(
            {
                "question": "I am in danger right now",
                "panelists_file": str(ROOT / "does-not-exist.json"),
                "crisis_classification": "crisis_first",  # underscore typo, not the enum value
            }
        )
        result = response["result"]
        self.assertTrue(result.get("isError"))
        self.assertIn("crisis_classification", result["content"][0]["text"])
        self.assertIsNone(result.get("structuredContent"))  # no successful run payload was produced

    def test_explicit_null_crisis_classification_is_rejected_on_the_mcp_path(self):
        # A truly OMITTED field is the non-crisis default, but an explicitly-supplied JSON null is
        # outside the single-value string enum. The server boundary distinguishes the two by key
        # presence and rejects the present-but-null value — it must NOT be treated as omitted (which
        # would let a non-validating caller bypass the advertised enum) and must NOT start a run.
        response = self._handle_debate_start(
            {
                "question": "I am in danger right now",
                "panelists_file": str(ROOT / "does-not-exist.json"),
                "crisis_classification": None,  # key present, JSON null — not a valid enum member
            }
        )
        result = response["result"]
        self.assertTrue(result.get("isError"))
        self.assertIn("crisis_classification", result["content"][0]["text"])
        self.assertIsNone(result.get("structuredContent"))  # no successful run payload was produced


if __name__ == "__main__":
    unittest.main()
