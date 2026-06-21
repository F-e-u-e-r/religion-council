#!/usr/bin/env python3
"""Run the v0.9.0 strict-finalization path with an offline deterministic transport fixture."""

import json
import sys
import tempfile
from copy import deepcopy
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
EXAMPLE_DIR = Path(__file__).resolve().parent
CLAIM_BLOCK = """\
Fixture panelist prose; only the structured payload below can enter Surface A.
<<<CLAIM_PROTOCOL_V1>>>
{"protocol_version":"religion-council/claim/v1","claims":[{"claim_id":"claim-text-1","claim_type":"text","text":"克己復禮為仁"},{"claim_id":"claim-interpretation-1","claim_type":"interpretation","text":"仁 is interpreted here as a disciplined return to ritual propriety."}],"edges":[{"claim_id":"claim-text-1","evidence_seed_id":"S1","evidentiary_role":"primary-source","evidence_type":"quotation"}]}
<<<END_CLAIM_PROTOCOL_V1>>>
"""


class OfflineCodexFixture:
    """Minimal deterministic Codex-MCP substitute; the controller pipeline remains real."""

    def call_tool(self, name, arguments, timeout):
        del timeout
        if name == "codex":
            panelist_id = arguments["prompt"].split("Panelist ID: ", 1)[1].splitlines()[0]
            if panelist_id == "admitted":
                return {"thread_id": "fixture-admitted", "content": CLAIM_BLOCK}
            if panelist_id == "denied":
                return {
                    "thread_id": "fixture-denied",
                    "content": "This fixture deliberately supplies no structured payload.",
                }
        if name == "codex-reply":
            return {
                "thread_id": arguments["threadId"],
                "content": "This fixture deliberately supplies no structured payload.",
            }
        raise AssertionError("unexpected MCP tool: {}".format(name))

    def close(self):
        pass


def load_json(path):
    with path.open(encoding="utf-8") as handle:
        return json.load(handle)


def panelist_entry(entries, panelist_id):
    return next(entry for entry in entries if entry["panelist_id"] == panelist_id)


def main():
    sys.path.insert(0, str(ROOT / "orchestrator"))
    import claim_binding  # noqa: PLC0415
    from debate_controller import DebateController  # noqa: PLC0415
    from evidence_snapshot import EvidenceStore  # noqa: PLC0415
    from render_finalizer import FinalizationError, finalize  # noqa: PLC0415

    evidence_envelope = load_json(EXAMPLE_DIR / "evidence-envelope.json")
    expected = load_json(EXAMPLE_DIR / "expected-authority-surface.json")
    panelists = {
        "panelists": [
            {"id": "admitted", "role": "fixture source reader", "priorities": []},
            {"id": "denied", "role": "fixture rejected payload", "priorities": []},
        ]
    }

    with tempfile.TemporaryDirectory() as temporary:
        temporary_path = Path(temporary)
        panelists_file = temporary_path / "panelists.json"
        panelists_file.write_text(json.dumps(panelists), encoding="utf-8")
        controller = DebateController(project_root=ROOT, state_dir=temporary_path / "runs")
        controller._client = OfflineCodexFixture()
        try:
            # Public MCP API: debate_start(profile="strict", evidence_envelope=...).
            started = controller.start(
                question="What does Confucius mean by ren?",
                panelists_file=str(panelists_file),
                evidence_envelope=evidence_envelope,
                profile="strict",
                concurrency=2,
                timeout_seconds=30,
                retries=0,
            )
            assert started["finalization_required"] is True
            assert started["finalized"] is False

            # Public MCP API: debate_collect. It is not a finalized answer render.
            collected = controller.collect(started["run_id"], limit=50)
            assert collected["finalization_required"] is True
            assert collected["finalized"] is False
            assert all("surface_a" not in result for result in collected["results"])

            # The B3 gate denied the no-payload response. Supply the empty verified artifact a
            # persisted B3 denial carries so the finalizer can demonstrate that valid empty path.
            state_path = temporary_path / "runs" / started["run_id"] / "state.json"
            state = load_json(state_path)
            state["rounds"]["1"]["results"]["denied"]["claim_verification"] = {
                "protocol_version": "religion-council/claim/v1",
                "claims": [],
            }
            state_path.write_text(json.dumps(state, ensure_ascii=False), encoding="utf-8")

            # Public MCP API: debate_finalize.
            finalized = controller.finalize(started["run_id"])
            assert finalized["finalization_required"] is True
            assert finalized["finalized"] is True

            admitted = panelist_entry(finalized["results"], "admitted")["finalized"]
            denied = panelist_entry(finalized["results"], "denied")["finalized"]
            authority = admitted["answer"]["authority_units"]
            assert authority[0]["text"] == evidence_envelope["records"][0]["text"]
            assert authority[0]["claim_id"] == "claim-text-1"
            # The producer declared no representation metadata; finalization derives it from S1.
            assert authority[0]["representation_kind"] == "published-translation"
            assert authority[0]["rendering_marker"] == "meaning-rendering"
            assert not denied["answer"]["authority_units"]
            assert not denied["answer"]["interpretation_units"]
            assert denied["surface_b_frame"]

            # A hostile extra admitted text claim cannot serialize the valid first authority unit.
            state = load_json(state_path)
            bad_result = deepcopy(state["rounds"]["1"]["results"]["admitted"])
            bad_result["claim_verification"]["claims"].append(
                {
                    "claim_id": "claim-bad-1",
                    "claim_type": "text",
                    "text": "not backed by an evidence edge",
                    "verification_state": "runtime-validated",
                    "edges": [],
                }
            )
            bad_result["boundary_decision"]["claims"].append(
                {"claim_id": "claim-bad-1", "decision": "admit", "render_as": "text"}
            )
            catalog = claim_binding.EvidenceCatalog.from_state(state["evidence_catalog"])
            store = EvidenceStore(temporary_path / "runs" / started["run_id"] / "evidence")
            partial_surface_a = None
            try:
                partial_surface_a = finalize(bad_result, catalog, store.read_snapshot).surface_a
            except FinalizationError as exc:
                atomic_reason = exc.reason
            else:
                raise AssertionError("hostile claim unexpectedly finalized")
            assert partial_surface_a is None

            output = {
                "accepted": {
                    "authority_claim_ids": [unit["claim_id"] for unit in authority],
                    "interpretation_count": len(admitted["answer"]["interpretation_units"]),
                    "representation_kind": authority[0]["representation_kind"],
                    "rendering_marker": authority[0]["rendering_marker"],
                    "surface_a": admitted["surface_a"],
                    "surface_b_frame": admitted["surface_b_frame"],
                },
                "atomic_failure": atomic_reason,
                "denied": {
                    "audit_reason_codes": denied["audit"]["reason_codes"],
                    "authority_unit_count": len(denied["answer"]["authority_units"]),
                    "interpretation_unit_count": len(denied["answer"]["interpretation_units"]),
                    "surface_a": denied["surface_a"],
                    "surface_b_frame": denied["surface_b_frame"],
                },
            }
            assert output == expected["output"]
            print(json.dumps(output, ensure_ascii=False, indent=2, sort_keys=True))
        finally:
            controller.close()


if __name__ == "__main__":
    main()
