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


if __name__ == "__main__":
    unittest.main()
