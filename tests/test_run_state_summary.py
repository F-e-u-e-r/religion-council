import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import run_state_summary as rss  # noqa: E402


def _write_run(runs_dir, run_id, state):
    run_dir = runs_dir / run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    (run_dir / "state.json").write_text(json.dumps(state, ensure_ascii=False), encoding="utf-8")


PROSE_OK = {
    "run_id": "run-prose-ok",
    "profile": None,
    "structured_claims": False,
    "verify_claims": False,
    "fail_closed": False,
    "finalization_required": False,
    "rounds": {
        "1": {
            "status": "complete",
            "results": {
                "p1": {"thread_id": "t1", "content": "opening:p1"},
                "p2": {"thread_id": "t2", "content": "opening:p2"},
            },
        }
    },
}

STRICT_MIXED = {
    "run_id": "run-strict-mixed",
    "profile": "strict",
    "structured_claims": True,
    "verify_claims": True,
    "fail_closed": True,
    "finalization_required": True,
    "rounds": {
        "1": {
            "status": "complete",
            "finalized": True,
            "results": {
                "admitted": {
                    "schema_status": "ok",
                    "boundary_decision": {
                        "admitted": True,
                        "response_denial": None,
                        "claims": [
                            {"claim_id": "c1", "decision": "admit", "render_as": "text"},
                            {"claim_id": "c2", "decision": "deny", "reason": "unknown-claim-type"},
                        ],
                        "admitted_count": 1,
                        "denied_count": 1,
                    },
                    "verification_summary": {
                        "claims": 2,
                        "runtime_validated": 1,
                        "failed": 0,
                        "downgraded": 1,
                    },
                },
                "denied": {
                    "schema_status": "schema_failed",
                    "boundary_decision": {
                        "admitted": False,
                        "response_denial": "renderer-bypass",
                        "admitted_count": 0,
                        "denied_count": 0,
                    },
                    "claim_verification": {"protocol_version": "religion-council/claim/v1", "claims": []},
                },
            },
        }
    },
}

PROSE_FAILED = {
    "run_id": "run-prose-failed",
    "profile": None,
    "structured_claims": False,
    "verify_claims": False,
    "fail_closed": False,
    "finalization_required": False,
    "rounds": {
        "1": {
            "status": "failed",
            "results": {"p1": {"error": "Codex MCP error", "attempts": 1}},
        }
    },
}


class SummarizeTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.runs = Path(self.temp.name)
        _write_run(self.runs, "run-prose-ok", PROSE_OK)
        _write_run(self.runs, "run-strict-mixed", STRICT_MIXED)
        _write_run(self.runs, "run-prose-failed", PROSE_FAILED)
        # An unreadable state file must be counted, not fatal.
        bad = self.runs / "run-bad"
        bad.mkdir()
        (bad / "state.json").write_text("{ this is not json", encoding="utf-8")
        # A directory without a state.json is simply ignored (not globbed).
        (self.runs / "run-empty").mkdir()
        self.summary = rss.summarize(self.runs)

    def tearDown(self):
        self.temp.cleanup()

    def test_run_counts_and_modes(self):
        runs = self.summary["runs"]
        self.assertEqual(runs["total"], 3)
        self.assertEqual(runs["unreadable"], 1)
        self.assertEqual(runs["by_profile"], {"strict": 1, "none": 2})
        self.assertEqual(
            runs["modes"], {"structured_claims": 1, "verify_claims": 1, "fail_closed": 1}
        )
        self.assertEqual(runs["finalization_required"], 1)
        self.assertEqual(runs["finalized_rounds"], 1)

    def test_enforcement_mode_uses_the_canonical_ladder(self):
        # instruction-enforced for the two prose runs, structured-fail-closed for the strict one.
        self.assertEqual(
            self.summary["runs"]["enforcement_mode"],
            {"instruction-enforced": 2, "structured-fail-closed": 1},
        )

    def test_round_and_result_counts(self):
        self.assertEqual(self.summary["rounds"]["total"], 3)
        self.assertEqual(self.summary["rounds"]["by_status"], {"complete": 2, "failed": 1})
        res = self.summary["results"]
        self.assertEqual(res["total"], 5)
        self.assertEqual(res["schema_status"], {"none": 3, "ok": 1, "schema_failed": 1})
        self.assertEqual(res["errored"], 1)

    def test_verification_and_boundary(self):
        res = self.summary["results"]
        self.assertEqual(
            res["verification"],
            {"claims": 2, "runtime_validated": 1, "failed": 0, "downgraded": 1},
        )
        boundary = res["boundary"]
        self.assertEqual(boundary["with_decision"], 2)
        self.assertEqual(boundary["admitted"], 1)
        self.assertEqual(boundary["denied"], 1)
        self.assertEqual(boundary["response_denial_reasons"], {"renderer-bypass": 1})
        # Claim-level denials are surfaced even inside a response-admitted boundary decision.
        self.assertEqual(boundary["claims_admitted"], 1)
        self.assertEqual(boundary["claims_denied"], 1)
        self.assertEqual(boundary["claim_denial_reasons"], {"unknown-claim-type": 1})
        # Round-level finalization IS persisted (finalized_rounds); per-result finalization detail
        # is not, so the summary must not invent a per-result finalization section.
        self.assertNotIn("finalization", res)
        self.assertEqual(self.summary["runs"]["finalized_rounds"], 1)

    def test_summary_is_json_serializable_and_renders(self):
        json.dumps(self.summary)  # must not raise (Counters converted to plain dicts)
        text = rss.render_text(self.summary)
        self.assertIn("Run-state summary", text)
        self.assertIn("renderer-bypass", text)
        self.assertIn("structured-fail-closed", text)

    def test_malformed_round_is_tolerated_not_fatal(self):
        # A readable but malformed structured state (a round whose `results` is not a dict) makes
        # _enforcement_mode raise; the report must classify the mode as "unknown" and keep going,
        # never abort — the diagnostic's tolerance promise.
        with tempfile.TemporaryDirectory() as tmp:
            runs = Path(tmp)
            _write_run(runs, "run-ok", PROSE_OK)
            _write_run(
                runs,
                "run-malformed",
                {
                    "run_id": "run-malformed",
                    "profile": "strict",
                    "structured_claims": True,
                    "verify_claims": True,
                    "fail_closed": True,
                    "finalization_required": True,
                    "rounds": {"1": {"status": "complete", "results": ["not", "a", "dict"]}},
                },
            )
            summary = rss.summarize(runs)
        self.assertEqual(summary["runs"]["total"], 2)
        self.assertEqual(summary["runs"]["unreadable"], 0)  # it IS readable, just malformed
        self.assertEqual(summary["runs"]["enforcement_mode"].get("unknown"), 1)
        self.assertEqual(summary["results"]["total"], 2)  # malformed round contributes no results

    def test_stage_crash_errors_are_counted(self):
        # B2/B3 graceful-degradation crashes persist verification_error / boundary_error and NO
        # verification_summary / boundary_decision, so the report must surface them as stage crashes
        # rather than silently showing zero B2/B3 activity (the failure operators need to see).
        with tempfile.TemporaryDirectory() as tmp:
            runs = Path(tmp)
            _write_run(
                runs,
                "run-crash",
                {
                    "run_id": "run-crash",
                    "profile": "strict",
                    "structured_claims": True,
                    "verify_claims": True,
                    "fail_closed": True,
                    "finalization_required": True,
                    "rounds": {
                        "1": {
                            "status": "complete",
                            "results": {
                                "p1": {"schema_status": "ok", "verification_error": "boom in B2"},
                                "p2": {"schema_status": "ok", "boundary_error": "boom in B3"},
                            },
                        }
                    },
                },
            )
            summary = rss.summarize(runs)
        stage = summary["results"]["stage_errors"]
        self.assertEqual(stage["verification_error"], 1)
        self.assertEqual(stage["boundary_error"], 1)
        # The crash must not read as B2/B3 success: no summary / decision was persisted.
        self.assertEqual(summary["results"]["verification"], {})
        self.assertEqual(summary["results"]["boundary"]["with_decision"], 0)
        self.assertIn("verification_error=1", rss.render_text(summary))

    def test_missing_directory_is_empty_not_fatal(self):
        summary = rss.summarize(self.runs / "does-not-exist")
        self.assertEqual(summary["runs"]["total"], 0)
        self.assertEqual(summary["runs"]["unreadable"], 0)
        self.assertEqual(summary["results"]["total"], 0)


if __name__ == "__main__":
    unittest.main()
