import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "orchestrator"))

import claim_verification  # noqa: E402
import render_finalizer  # noqa: E402
from debate_controller import (  # noqa: E402
    ControllerError,
    DebateController,
    sanitize_contrast_proposition,
    tool_definitions,
)


def _envelope(text):
    return {
        "contract_version": "religion-council/retrieval/v1",
        "records": [
            {
                "text": text,
                "work": "論語",
                "locator": "顏淵",
                "tradition": "confucianism",
                "evidence_type": "quotation",
                "verbatim": True,
                "source_file": "/x",
                "source_line": 1,
            }
        ],
    }


def evidence_envelope():
    """One-record envelope whose snapshot text == the fake's quoted text (B2 will validate)."""
    return _envelope("克己復禮為仁")


def evidence_envelope_mismatch():
    """Snapshot text != the fake's quoted text, so B2 span verification fails (downgrade)."""
    return _envelope("學而時習之不亦說乎")


class DebateControllerTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.temp_path = Path(self.temp.name)
        panelists = {
            "panelists": [
                {
                    "id": "panelist_{:02d}".format(index),
                    "role": "role {}".format(index),
                    "priorities": ["independence"],
                }
                for index in range(1, 31)
            ]
        }
        self.panelists_file = self.temp_path / "panelists.json"
        self.panelists_file.write_text(json.dumps(panelists), encoding="utf-8")
        fake = ROOT / "tests" / "fake_codex_mcp.py"
        self.controller = DebateController(
            project_root=ROOT,
            state_dir=self.temp_path / "runs",
            codex_command="{} {}".format(sys.executable, fake),
        )

    def tearDown(self):
        self.controller.close()
        self.temp.cleanup()

    def test_thirty_persistent_panelists_across_two_rounds(self):
        opening = self.controller.start(
            question="Should the proposal proceed?",
            panelists_file=str(self.panelists_file),
            concurrency=10,
            timeout_seconds=30,
            retries=0,
        )
        self.assertEqual(opening["status"], "complete")
        self.assertEqual(opening["completed"], 30)
        run_id = opening["run_id"]

        first_batch = self.controller.collect(run_id, round_number=1, limit=50)
        opening_threads = {
            item["panelist_id"]: item["thread_id"] for item in first_batch["results"]
        }
        self.assertEqual(len(set(opening_threads.values())), 30)

        followup = self.controller.reply(
            run_id=run_id,
            issue_matrix="A majority favors proceeding; the strongest objection is risk.",
            concurrency=10,
            timeout_seconds=30,
            retries=0,
        )
        self.assertEqual(followup["status"], "complete")
        self.assertEqual(followup["completed"], 30)

        second_batch = self.controller.collect(run_id, round_number=2, limit=50)
        reply_threads = {
            item["panelist_id"]: item["thread_id"] for item in second_batch["results"]
        }
        self.assertEqual(opening_threads, reply_threads)

    def test_collect_is_paginated(self):
        opening = self.controller.start(
            question="Test pagination",
            panelists_file=str(self.panelists_file),
            concurrency=6,
            timeout_seconds=30,
            retries=0,
        )
        page = self.controller.collect(opening["run_id"], offset=5, limit=7)
        self.assertEqual(len(page["results"]), 7)
        self.assertEqual(page["next_offset"], 12)

    def test_round_barrier_and_failed_only_retry(self):
        opening = self.controller.start(
            question="Force one failure",
            panelists_file=str(self.panelists_file),
            concurrency=10,
            timeout_seconds=30,
            retries=0,
        )
        self.assertEqual(opening["status"], "failed")
        self.assertEqual(opening["failed_panelists"], ["panelist_30"])
        with self.assertRaises(ControllerError):
            self.controller.reply(
                run_id=opening["run_id"],
                issue_matrix="Round 2 must not start yet.",
                concurrency=10,
                timeout_seconds=30,
                retries=0,
            )
        retried = self.controller.retry(
            run_id=opening["run_id"],
            concurrency=10,
            timeout_seconds=30,
            retries=0,
        )
        self.assertEqual(retried["status"], "complete")
        self.assertEqual(retried["completed"], 30)

    def test_opening_prompt_requires_substantive_claim_collision(self):
        prompt = DebateController._opening_prompt(
            "Is pleasure sufficient for a good life?",
            "",
            {
                "id": "test",
                "role": "test perspective",
                "priorities": ["clarity"],
                "reference_text": "",
            },
            "tok-opening",
        )
        required = (
            "non-negotiable thesis",
            "anticipated rival proposition",
            "Weakest premise and cost",
            "Limited concession",
            "Do not lead with common ground",
            "remaining respectful toward persons",
            "reconstructed arguments and inferences as [Interpretation]",
        )
        normalized = " ".join(prompt.casefold().split())
        for phrase in required:
            self.assertIn(" ".join(phrase.casefold().split()), normalized)
        self.assertNotIn("Strongest objection to your own position", prompt)

    def test_followup_prompt_requires_claim_level_cross_examination(self):
        prompt = DebateController._followup_prompt(
            2,
            "C1 contradicts C2",
            {
                "id": "test",
                "role": "test perspective",
                "priorities": ["clarity"],
                "reference_text": "",
            },
            "tok-followup",
        )
        required = (
            "claim ID",
            "reject, partially concede, or accept",
            "weakest premise",
            "counterexample or internal contradiction",
            "pointed cross-examination question",
            "decisive crux",
            "upheld, narrowed, or withdrawn",
            "practical overlap is not consensus",
            "Do not invent an opponent",
        )
        normalized = " ".join(prompt.casefold().split())
        for phrase in required:
            self.assertIn(" ".join(phrase.casefold().split()), normalized)

    def test_debate_start_schema_includes_contrast_proposition(self):
        start = next(t for t in tool_definitions() if t["name"] == "debate_start")
        self.assertIn("contrast_proposition", start["inputSchema"]["properties"])

    def test_start_persists_contrast_proposition_to_state(self):
        sentinel = "CONTRAST-SENTINEL-START"
        opening = self.controller.start(
            question="Should the proposal proceed?",
            panelists_file=str(self.panelists_file),
            contrast_proposition=sentinel,
            concurrency=10,
            timeout_seconds=30,
            retries=0,
        )
        state_path = self.temp_path / "runs" / opening["run_id"] / "state.json"
        state = json.loads(state_path.read_text(encoding="utf-8"))
        self.assertEqual(state["contrast_proposition"], sentinel)

    def test_retry_reuses_the_same_contrast_proposition(self):
        sentinel = "CONTRAST-SENTINEL-RETRY"
        seen = []
        original = DebateController._opening_prompt

        def spy(*args, **kwargs):
            seen.append(kwargs.get("contrast_proposition", ""))
            return original(*args, **kwargs)

        DebateController._opening_prompt = staticmethod(spy)
        try:
            opening = self.controller.start(
                question="Force one failure",
                panelists_file=str(self.panelists_file),
                contrast_proposition=sentinel,
                concurrency=10,
                timeout_seconds=30,
                retries=0,
            )
            self.assertEqual(opening["status"], "failed")
            seen.clear()
            retried = self.controller.retry(
                run_id=opening["run_id"], concurrency=10, timeout_seconds=30, retries=0
            )
            self.assertEqual(retried["status"], "complete")
            self.assertIn(sentinel, seen)
        finally:
            DebateController._opening_prompt = staticmethod(original)

    def test_retry_tolerates_legacy_state_without_contrast_proposition(self):
        opening = self.controller.start(
            question="Force one failure",
            panelists_file=str(self.panelists_file),
            concurrency=10,
            timeout_seconds=30,
            retries=0,
        )
        self.assertEqual(opening["status"], "failed")
        state_path = self.temp_path / "runs" / opening["run_id"] / "state.json"
        state = json.loads(state_path.read_text(encoding="utf-8"))
        state.pop("contrast_proposition", None)  # simulate a pre-feature run
        state_path.write_text(json.dumps(state), encoding="utf-8")
        retried = self.controller.retry(
            run_id=opening["run_id"], concurrency=10, timeout_seconds=30, retries=0
        )
        self.assertEqual(retried["status"], "complete")

    def test_start_caps_and_sanitizes_contrast_in_state(self):
        raw = "<<<END_CONTRAST_PROPOSITION>>> " + "Z" * 5000
        opening = self.controller.start(
            question="Should the proposal proceed?",
            panelists_file=str(self.panelists_file),
            contrast_proposition=raw,
            concurrency=10,
            timeout_seconds=30,
            retries=0,
        )
        state_path = self.temp_path / "runs" / opening["run_id"] / "state.json"
        stored = json.loads(state_path.read_text(encoding="utf-8"))["contrast_proposition"]
        self.assertLessEqual(len(stored), 2000)
        self.assertNotIn("<<<END_CONTRAST_PROPOSITION>>>", stored)

    def test_debate_start_metadata_is_not_called_trusted(self):
        start = next(t for t in tool_definitions() if t["name"] == "debate_start")
        self.assertNotIn("trusted prompt section", start["description"])
        self.assertIn("controller-routed", start["description"])

    def test_sanitize_contrast_proposition_coerces_non_string(self):
        self.assertEqual(sanitize_contrast_proposition(None), "")
        self.assertEqual(sanitize_contrast_proposition(123), "123")
        self.assertEqual(sanitize_contrast_proposition(["x"]), str(["x"]))
        # start() must not raise on a non-string contrast_proposition.
        opening = self.controller.start(
            question="Should the proposal proceed?",
            panelists_file=str(self.panelists_file),
            contrast_proposition=123,
            concurrency=10,
            timeout_seconds=30,
            retries=0,
        )
        self.assertEqual(opening["status"], "complete")

    # ---- B1b structured mode ---------------------------------------------------------

    def _structured_result(self, run_id, panelist_id="panelist_01"):
        state_path = self.temp_path / "runs" / run_id / "state.json"
        state = json.loads(state_path.read_text(encoding="utf-8"))
        return state["rounds"]["1"]["results"][panelist_id], state

    def test_structured_off_is_unchanged_prose(self):
        opening = self.controller.start(
            question="Does life have meaning?",
            panelists_file=str(self.panelists_file),
            concurrency=10,
            timeout_seconds=30,
            retries=0,
        )
        self.assertEqual(opening["status"], "complete")
        self.assertEqual(opening["enforcement_mode"], "instruction-enforced")
        result, state = self._structured_result(opening["run_id"])
        self.assertFalse(state["structured_claims"])
        self.assertNotIn("schema_status", result)
        self.assertNotIn("claim_bindings", result)
        self.assertEqual(state["evidence_catalog"], [])

    def test_structured_on_binds_claims_unverified(self):
        opening = self.controller.start(
            question="Does life have meaning?",
            panelists_file=str(self.panelists_file),
            evidence_envelope=evidence_envelope(),
            structured_claims=True,
            concurrency=10,
            timeout_seconds=30,
            retries=0,
        )
        self.assertEqual(opening["status"], "complete")
        self.assertEqual(opening["enforcement_mode"], "structured-schema-enforced")
        result, state = self._structured_result(opening["run_id"])
        self.assertEqual(result["schema_status"], "ok")
        self.assertEqual(result["claim_payload_source"], "reply")
        edge = result["claim_bindings"]["claims"][0]["edges"][0]
        self.assertEqual(edge["evidence_seed_id"], "S1")
        self.assertTrue(edge["occurrence_id"])
        self.assertTrue(edge["artifact_id"])
        self.assertEqual(edge["verification_state"], "unverified")  # no B2
        # collect surfaces the same qualifier, never implying verification
        collected = self.controller.collect(opening["run_id"], limit=1)
        self.assertEqual(collected["enforcement_mode"], "structured-schema-enforced")

    def test_structured_repair_then_bind(self):
        opening = self.controller.start(
            question="STRUCTURED_REPAIR: does life have meaning?",
            panelists_file=str(self.panelists_file),
            evidence_envelope=evidence_envelope(),
            structured_claims=True,
            concurrency=10,
            timeout_seconds=30,
            retries=0,
        )
        self.assertEqual(opening["status"], "complete")  # barrier reached
        repaired, _ = self._structured_result(opening["run_id"], "panelist_30")
        self.assertEqual(repaired["schema_status"], "repaired")
        self.assertNotIn("error", repaired)
        self.assertEqual(
            repaired["claim_bindings"]["claims"][0]["edges"][0]["evidence_seed_id"], "S1"
        )
        # audit: original (malformed) reply kept as content; bindings sourced from the repair
        self.assertEqual(repaired["claim_payload_source"], "repair")
        self.assertIn("opening:panelist_30", repaired["content"])
        self.assertIn("repaired:", repaired["repair_content"])

    def test_structured_drop_keeps_prose_and_round_completes(self):
        opening = self.controller.start(
            question="STRUCTURED_DROP: does life have meaning?",
            panelists_file=str(self.panelists_file),
            evidence_envelope=evidence_envelope(),
            structured_claims=True,
            concurrency=10,
            timeout_seconds=30,
            retries=0,
        )
        self.assertEqual(opening["status"], "complete")  # NOT fail-closed
        dropped, _ = self._structured_result(opening["run_id"], "panelist_30")
        self.assertEqual(dropped["schema_status"], "schema_failed")
        self.assertNotIn("error", dropped)  # schema failure must not be a transport error
        self.assertNotIn("claim_bindings", dropped)
        self.assertTrue(dropped["content"])  # prose kept
        # other panelists still bound -> response-level qualifier remains structured
        self.assertEqual(opening["enforcement_mode"], "structured-schema-enforced")
        # barrier still reachable for round 2
        followup = self.controller.reply(
            run_id=opening["run_id"],
            issue_matrix="anonymized matrix",
            concurrency=10,
            timeout_seconds=30,
            retries=0,
        )
        self.assertEqual(followup["status"], "complete")

    def test_structured_mode_survives_failed_panelist_retry(self):
        # Finding #4: retry rebuilds prompts in its own path; structured mode must persist.
        opening = self.controller.start(
            question="Force one failure",
            panelists_file=str(self.panelists_file),
            evidence_envelope=evidence_envelope(),
            structured_claims=True,
            concurrency=10,
            timeout_seconds=30,
            retries=0,
        )
        self.assertEqual(opening["status"], "failed")
        self.assertEqual(opening["failed_panelists"], ["panelist_30"])
        retried = self.controller.retry(
            run_id=opening["run_id"], concurrency=10, timeout_seconds=30, retries=0
        )
        self.assertEqual(retried["status"], "complete")
        self.assertEqual(retried["enforcement_mode"], "structured-schema-enforced")
        result, _ = self._structured_result(opening["run_id"], "panelist_30")
        self.assertEqual(result["schema_status"], "ok")  # bound on retry, not dropped to prose
        self.assertEqual(
            result["claim_bindings"]["claims"][0]["edges"][0]["evidence_seed_id"], "S1"
        )

    def test_structured_threadid_reuse_and_second_round_binds(self):
        opening = self.controller.start(
            question="Does life have meaning?",
            panelists_file=str(self.panelists_file),
            evidence_envelope=evidence_envelope(),
            structured_claims=True,
            concurrency=10,
            timeout_seconds=30,
            retries=0,
        )
        run_id = opening["run_id"]
        first = self.controller.collect(run_id, round_number=1, limit=50)
        opening_threads = {r["panelist_id"]: r["thread_id"] for r in first["results"]}
        followup = self.controller.reply(
            run_id=run_id,
            issue_matrix="anonymized matrix",
            concurrency=10,
            timeout_seconds=30,
            retries=0,
        )
        self.assertEqual(followup["status"], "complete")
        self.assertEqual(followup["enforcement_mode"], "structured-schema-enforced")
        second = self.controller.collect(run_id, round_number=2, limit=50)
        reply_threads = {r["panelist_id"]: r["thread_id"] for r in second["results"]}
        self.assertEqual(opening_threads, reply_threads)  # threadId reuse preserved
        self.assertEqual(second["results"][0]["schema_status"], "ok")

    def test_malformed_evidence_envelope_is_rejected_at_start(self):
        with self.assertRaises(ControllerError):
            self.controller.start(
                question="Does life have meaning?",
                panelists_file=str(self.panelists_file),
                evidence_envelope={"contract_version": "wrong", "records": []},
                structured_claims=True,
                concurrency=10,
                timeout_seconds=30,
                retries=0,
            )

    def test_structured_requires_evidence_envelope(self):
        # B1b binds claims to seeds; structured mode without an evidence source is a no-op
        # and must fail fast rather than emit empty structured runs.
        with self.assertRaises(ControllerError):
            self.controller.start(
                question="Does life have meaning?",
                panelists_file=str(self.panelists_file),
                structured_claims=True,  # no evidence_envelope supplied
                concurrency=10,
                timeout_seconds=30,
                retries=0,
            )

    # ---- B2 claim-level verification --------------------------------------------------

    def test_verify_requires_structured(self):
        with self.assertRaises(ControllerError):
            self.controller.start(
                question="Does life have meaning?",
                panelists_file=str(self.panelists_file),
                verify_claims=True,  # without structured_claims
                concurrency=10,
                timeout_seconds=30,
                retries=0,
            )

    def test_verify_on_validates_against_curated_snapshot(self):
        opening = self.controller.start(
            question="Does life have meaning?",
            panelists_file=str(self.panelists_file),
            evidence_envelope=evidence_envelope(),  # snapshot == fake's quote -> validates
            structured_claims=True,
            verify_claims=True,
            concurrency=10,
            timeout_seconds=30,
            retries=0,
        )
        self.assertEqual(opening["status"], "complete")
        self.assertEqual(opening["enforcement_mode"], "structured-claim-validated")
        result, state = self._structured_result(opening["run_id"])
        self.assertTrue(state["verify_claims"])
        # B2 adds a separate verified structure...
        vclaim = result["claim_verification"]["claims"][0]
        self.assertEqual(vclaim["verification_state"], "runtime-validated")
        self.assertEqual(vclaim["span_assurance_tier"], "curated-snapshot-span-verified")
        self.assertEqual(result["verification_summary"]["runtime_validated"], 1)
        # ...while B1b's bindings stay unverified (ADR 0003 §3; B2 is additive).
        self.assertEqual(
            result["claim_bindings"]["claims"][0]["edges"][0]["verification_state"],
            "unverified",
        )

    def test_verify_off_stays_schema_enforced(self):
        opening = self.controller.start(
            question="Does life have meaning?",
            panelists_file=str(self.panelists_file),
            evidence_envelope=evidence_envelope(),
            structured_claims=True,  # no verify_claims
            concurrency=10,
            timeout_seconds=30,
            retries=0,
        )
        self.assertEqual(opening["enforcement_mode"], "structured-schema-enforced")
        result, state = self._structured_result(opening["run_id"])
        self.assertFalse(state["verify_claims"])
        self.assertNotIn("claim_verification", result)

    def test_verify_failed_quotation_downgrades_and_council_continues(self):
        opening = self.controller.start(
            question="Does life have meaning?",
            panelists_file=str(self.panelists_file),
            evidence_envelope=evidence_envelope_mismatch(),  # snapshot != quote -> fails
            structured_claims=True,
            verify_claims=True,
            concurrency=10,
            timeout_seconds=30,
            retries=0,
        )
        self.assertEqual(opening["status"], "complete")  # not fail-closed
        result, _ = self._structured_result(opening["run_id"])
        vclaim = result["claim_verification"]["claims"][0]
        self.assertEqual(vclaim["verification_state"], "failed")
        self.assertEqual(vclaim["claim_type"], "unverified-citation")  # downgraded, not [Interpretation]
        self.assertEqual(vclaim["downgraded_from"], "text")
        self.assertEqual(result["verification_summary"]["downgraded"], 1)

    def test_verify_applies_on_reply_round_two(self):
        # reply() goes through the shared _dispatch_jobs, so round 2 must verify too.
        opening = self.controller.start(
            question="Does life have meaning?",
            panelists_file=str(self.panelists_file),
            evidence_envelope=evidence_envelope(),
            structured_claims=True,
            verify_claims=True,
            concurrency=10,
            timeout_seconds=30,
            retries=0,
        )
        followup = self.controller.reply(
            run_id=opening["run_id"],
            issue_matrix="anonymized matrix",
            concurrency=10,
            timeout_seconds=30,
            retries=0,
        )
        self.assertEqual(followup["status"], "complete")
        self.assertEqual(followup["enforcement_mode"], "structured-claim-validated")
        state_path = self.temp_path / "runs" / opening["run_id"] / "state.json"
        state = json.loads(state_path.read_text(encoding="utf-8"))
        r2 = state["rounds"]["2"]["results"]["panelist_01"]
        self.assertEqual(
            r2["claim_verification"]["claims"][0]["verification_state"], "runtime-validated"
        )

    def test_verify_survives_failed_panelist_retry(self):
        # retry() also goes through _dispatch_jobs, so a retried panelist must be verified.
        opening = self.controller.start(
            question="Force one failure",
            panelists_file=str(self.panelists_file),
            evidence_envelope=evidence_envelope(),
            structured_claims=True,
            verify_claims=True,
            concurrency=10,
            timeout_seconds=30,
            retries=0,
        )
        self.assertEqual(opening["status"], "failed")
        retried = self.controller.retry(
            run_id=opening["run_id"], concurrency=10, timeout_seconds=30, retries=0
        )
        self.assertEqual(retried["status"], "complete")
        self.assertEqual(retried["enforcement_mode"], "structured-claim-validated")
        result, _ = self._structured_result(opening["run_id"], "panelist_30")
        self.assertEqual(
            result["claim_verification"]["claims"][0]["verification_state"], "runtime-validated"
        )

    # ---- B3 response-boundary fail-closed ---------------------------------------------

    def test_fail_closed_requires_verify_claims(self):
        with self.assertRaises(ControllerError):
            self.controller.start(
                question="Does life have meaning?",
                panelists_file=str(self.panelists_file),
                evidence_envelope=evidence_envelope(),
                structured_claims=True,
                fail_closed=True,  # without verify_claims
                concurrency=10,
                timeout_seconds=30,
                retries=0,
            )

    def test_fail_closed_admits_validated_claims(self):
        opening = self.controller.start(
            question="Does life have meaning?",
            panelists_file=str(self.panelists_file),
            evidence_envelope=evidence_envelope(),  # validates
            structured_claims=True,
            verify_claims=True,
            fail_closed=True,
            concurrency=10,
            timeout_seconds=30,
            retries=0,
        )
        self.assertEqual(opening["status"], "complete")  # boundary gate is pre-renderer, not a round fail
        self.assertEqual(opening["enforcement_mode"], "structured-fail-closed")
        result, state = self._structured_result(opening["run_id"])
        self.assertTrue(state["fail_closed"])
        decision = result["boundary_decision"]
        self.assertTrue(decision["admitted"])
        self.assertEqual(decision["claims"][0]["decision"], "admit")
        self.assertEqual(decision["claims"][0]["render_as"], "text")

    def test_fail_closed_admits_downgraded_claim_as_non_supporting(self):
        # B2 downgrades a failed [Text] to unverified-citation; B3 admits it, but non-supporting.
        opening = self.controller.start(
            question="Does life have meaning?",
            panelists_file=str(self.panelists_file),
            evidence_envelope=evidence_envelope_mismatch(),  # quotation not in snapshot -> fail
            structured_claims=True,
            verify_claims=True,
            fail_closed=True,
            concurrency=10,
            timeout_seconds=30,
            retries=0,
        )
        self.assertEqual(opening["status"], "complete")
        result, _ = self._structured_result(opening["run_id"])
        decision = result["boundary_decision"]
        self.assertEqual(decision["claims"][0]["decision"], "admit")
        self.assertEqual(decision["claims"][0]["render_as"], "non-supporting")

    def test_fail_closed_denies_schema_failed_response_as_renderer_bypass(self):
        # A schema_failed panelist has no claim_verification, so the fail-closed boundary
        # default-denies it (renderer-bypass) — yet the round still completes.
        opening = self.controller.start(
            question="STRUCTURED_DROP: does life have meaning?",
            panelists_file=str(self.panelists_file),
            evidence_envelope=evidence_envelope(),
            structured_claims=True,
            verify_claims=True,
            fail_closed=True,
            concurrency=10,
            timeout_seconds=30,
            retries=0,
        )
        self.assertEqual(opening["status"], "complete")
        dropped, _ = self._structured_result(opening["run_id"], "panelist_30")
        self.assertEqual(dropped["schema_status"], "schema_failed")
        self.assertFalse(dropped["boundary_decision"]["admitted"])
        self.assertEqual(dropped["boundary_decision"]["response_denial"], "renderer-bypass")

    def test_fail_closed_applies_on_reply_round_two(self):
        opening = self.controller.start(
            question="Does life have meaning?",
            panelists_file=str(self.panelists_file),
            evidence_envelope=evidence_envelope(),
            structured_claims=True,
            verify_claims=True,
            fail_closed=True,
            concurrency=10,
            timeout_seconds=30,
            retries=0,
        )
        followup = self.controller.reply(
            run_id=opening["run_id"],
            issue_matrix="anonymized matrix",
            concurrency=10,
            timeout_seconds=30,
            retries=0,
        )
        self.assertEqual(followup["status"], "complete")
        self.assertEqual(followup["enforcement_mode"], "structured-fail-closed")
        state_path = self.temp_path / "runs" / opening["run_id"] / "state.json"
        state = json.loads(state_path.read_text(encoding="utf-8"))
        r2 = state["rounds"]["2"]["results"]["panelist_01"]
        self.assertTrue(r2["boundary_decision"]["admitted"])
        self.assertEqual(r2["boundary_decision"]["claims"][0]["decision"], "admit")

    def test_boundary_error_degrades_gracefully(self):
        # An unexpected gate crash must record a flag and let the round/barrier complete.
        import response_boundary

        original = response_boundary.gate_response

        def boom(*args, **kwargs):
            raise RuntimeError("gate exploded")

        response_boundary.gate_response = boom
        try:
            opening = self.controller.start(
                question="Does life have meaning?",
                panelists_file=str(self.panelists_file),
                evidence_envelope=evidence_envelope(),
                structured_claims=True,
                verify_claims=True,
                fail_closed=True,
                concurrency=10,
                timeout_seconds=30,
                retries=0,
            )
        finally:
            response_boundary.gate_response = original
        self.assertEqual(opening["status"], "complete")  # barrier intact despite the crash
        result, _ = self._structured_result(opening["run_id"])
        self.assertIn("boundary_error", result)
        self.assertIn("gate exploded", result["boundary_error"])
        self.assertNotIn("error", result)

    # ---- Strict profile + debate_finalize --------------------------------------------

    def test_profile_strict_turns_on_full_graph(self):
        opening = self.controller.start(
            question="Does life have meaning?",
            panelists_file=str(self.panelists_file),
            evidence_envelope=evidence_envelope(),
            profile="strict",
            concurrency=10,
            timeout_seconds=30,
            retries=0,
        )
        self.assertEqual(opening["enforcement_mode"], "structured-fail-closed")
        _, state = self._structured_result(opening["run_id"])
        self.assertTrue(state["structured_claims"])
        self.assertTrue(state["verify_claims"])
        self.assertTrue(state["fail_closed"])
        self.assertEqual(state["profile"], "strict")

    def test_profile_strict_requires_evidence_envelope(self):
        with self.assertRaises(ControllerError):
            self.controller.start(
                question="Does life have meaning?",
                panelists_file=str(self.panelists_file),
                profile="strict",  # no evidence_envelope -> config error, never degrade
                concurrency=10,
                timeout_seconds=30,
                retries=0,
            )

    def test_profile_strict_conflicts_with_explicit_false(self):
        with self.assertRaises(ControllerError):
            self.controller.start(
                question="Does life have meaning?",
                panelists_file=str(self.panelists_file),
                evidence_envelope=evidence_envelope(),
                profile="strict",
                fail_closed=False,  # explicit contradiction -> fail fast
                concurrency=10,
                timeout_seconds=30,
                retries=0,
            )

    def test_finalize_builds_authority_surface_from_admitted_claims(self):
        opening = self.controller.start(
            question="Does life have meaning?",
            panelists_file=str(self.panelists_file),
            evidence_envelope=evidence_envelope(),  # snapshot text == fake's quote
            profile="strict",
            concurrency=10,
            timeout_seconds=30,
            retries=0,
        )
        final = self.controller.finalize(opening["run_id"])
        entry = next(r for r in final["results"] if r["panelist_id"] == "panelist_01")
        units = entry["finalized"]["answer"]["authority_units"]
        self.assertEqual(units[0]["text"], "克己復禮為仁")  # sourced from the snapshot span
        self.assertEqual(units[0]["render_as"], "quotation")
        self.assertIn("克己復禮為仁", entry["finalized"]["surface_a"])
        self.assertIsNone(entry.get("finalization_error"))
        # S4: the deterministic assurance footer is exposed and reflects the one rendered unit.
        self.assertIn("Authority assurance", entry["assurance_footer"])
        self.assertIn("Textual claims rendered: 1", entry["assurance_footer"])
        self.assertIn("Curated snapshot-span verified: 1", entry["assurance_footer"])

    def test_strict_is_not_finalized_until_debate_finalize(self):
        # Workflow invariant: a strict run carries finalization_required and is NOT finalized
        # after collect; only a successful debate_finalize marks it finalized. collect never
        # yields a machine-enforced authority surface (no surface_a / finalized response).
        opening = self.controller.start(
            question="Does life have meaning?",
            panelists_file=str(self.panelists_file),
            evidence_envelope=evidence_envelope(),
            profile="strict",
            concurrency=10,
            timeout_seconds=30,
            retries=0,
        )
        self.assertTrue(opening["finalization_required"])
        self.assertFalse(opening["finalized"])
        collected = self.controller.collect(opening["run_id"], limit=50)
        self.assertTrue(collected["finalization_required"])
        self.assertFalse(collected["finalized"])
        for result in collected["results"]:
            self.assertNotIn("surface_a", result)  # collect is not the finalized answer
        final = self.controller.finalize(opening["run_id"])
        self.assertTrue(final["finalized"])
        recollected = self.controller.collect(opening["run_id"], limit=50)
        self.assertTrue(recollected["finalized"])  # only debate_finalize sets this

    def test_finalization_error_does_not_mark_round_finalized(self):
        opening = self.controller.start(
            question="Does life have meaning?",
            panelists_file=str(self.panelists_file),
            evidence_envelope=evidence_envelope(),
            profile="strict",
            concurrency=10,
            timeout_seconds=30,
            retries=0,
        )
        original = render_finalizer.finalize

        def boom(*args, **kwargs):
            raise render_finalizer.FinalizationError("trace-text-not-canonical", "forced")

        render_finalizer.finalize = boom
        try:
            final = self.controller.finalize(opening["run_id"])
        finally:
            render_finalizer.finalize = original
        self.assertFalse(final["finalized"])
        self.assertTrue(any("finalization_error" in entry for entry in final["results"]))
        recollected = self.controller.collect(opening["run_id"], limit=50)
        self.assertFalse(recollected["finalized"])

    def test_non_strict_run_does_not_require_finalization(self):
        opening = self.controller.start(
            question="Does life have meaning?",
            panelists_file=str(self.panelists_file),
            concurrency=10,
            timeout_seconds=30,
            retries=0,
        )
        self.assertFalse(opening["finalization_required"])

    def test_finalize_requires_fail_closed_run(self):
        opening = self.controller.start(
            question="Does life have meaning?",
            panelists_file=str(self.panelists_file),
            evidence_envelope=evidence_envelope(),
            structured_claims=True,
            verify_claims=True,  # B2 only, no fail_closed
            concurrency=10,
            timeout_seconds=30,
            retries=0,
        )
        with self.assertRaises(ControllerError):
            self.controller.finalize(opening["run_id"])

    def test_verification_error_degrades_gracefully(self):
        # An unexpected verifier crash must record a flag and let the round/barrier complete.
        original = claim_verification.verify_bound_claims

        def boom(*args, **kwargs):
            raise RuntimeError("verifier exploded")

        claim_verification.verify_bound_claims = boom
        try:
            opening = self.controller.start(
                question="Does life have meaning?",
                panelists_file=str(self.panelists_file),
                evidence_envelope=evidence_envelope(),
                structured_claims=True,
                verify_claims=True,
                concurrency=10,
                timeout_seconds=30,
                retries=0,
            )
        finally:
            claim_verification.verify_bound_claims = original
        self.assertEqual(opening["status"], "complete")  # barrier intact despite the crash
        result, _ = self._structured_result(opening["run_id"])
        self.assertIn("verification_error", result)
        self.assertIn("verifier exploded", result["verification_error"])
        self.assertNotIn("error", result)  # not a transport failure; the round still completes


if __name__ == "__main__":
    unittest.main()
