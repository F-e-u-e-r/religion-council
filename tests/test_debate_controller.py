import json
from pathlib import Path
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "orchestrator"))

from debate_controller import ControllerError, DebateController  # noqa: E402


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


if __name__ == "__main__":
    unittest.main()
