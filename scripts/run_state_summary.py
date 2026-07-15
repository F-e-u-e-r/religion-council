#!/usr/bin/env python3
"""Read-only cross-run observability summary over ``.religion-council/runs/*/state.json``.

Aggregates operational rates the per-run state already records — enforcement-mode
distribution, round outcomes, schema / boundary / finalization results, denial reason
codes, and B2 downgrade counts — so an operator can judge whether the gates are too
loose or too tight and where the runs are failing.

It is strictly diagnostic: it NEVER mutates a run, asserts no assurance, and computes no
new verdict. It only counts what finalization / the response boundary already decided,
tolerating partial or older state files (an unreadable one is counted, not fatal).
"""
import argparse
import json
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "orchestrator"))

# Reuse the canonical enforcement-mode ladder (ADR 0002 §6) so this report can never drift
# from what the controller itself reports; it is a pure function over a state dict.
from debate_controller import DebateController  # noqa: E402

DEFAULT_RUNS_DIR = ROOT / ".religion-council" / "runs"


def _new_summary(runs_dir):
    return {
        "runs_dir": str(runs_dir),
        "runs": {
            "total": 0,
            "unreadable": 0,
            "by_profile": Counter(),
            "modes": Counter(),
            "enforcement_mode": Counter(),
            "finalization_required": 0,
            "finalized_rounds": 0,
        },
        "rounds": {"total": 0, "by_status": Counter()},
        "results": {
            "total": 0,
            "schema_status": Counter(),
            "errored": 0,
            "stage_errors": {"verification_error": 0, "boundary_error": 0},
            "verification": Counter(),
            "boundary": {
                "with_decision": 0,
                "admitted": 0,
                "denied": 0,
                "response_denial_reasons": Counter(),
                "claims_admitted": 0,
                "claims_denied": 0,
                "claim_denial_reasons": Counter(),
            },
        },
    }


def _accumulate_result(summary, result):
    res = summary["results"]
    res["total"] += 1
    res["schema_status"][result.get("schema_status") or "none"] += 1
    if "error" in result:
        res["errored"] += 1
    # B2/B3 degrade gracefully: a crash persists verification_error / boundary_error (a string) and
    # NO verification_summary / boundary_decision, so a crashed gate would otherwise read as zero
    # activity. Count the crashes so an operator sees the gate actually failed.
    if "verification_error" in result:
        res["stage_errors"]["verification_error"] += 1
    if "boundary_error" in result:
        res["stage_errors"]["boundary_error"] += 1
    vs = result.get("verification_summary")
    if isinstance(vs, dict):
        for key in ("claims", "runtime_validated", "failed", "downgraded"):
            value = vs.get(key)
            if isinstance(value, int):
                res["verification"][key] += value
    boundary = result.get("boundary_decision")
    if isinstance(boundary, dict):
        res["boundary"]["with_decision"] += 1
        if boundary.get("admitted"):
            res["boundary"]["admitted"] += 1
        else:
            res["boundary"]["denied"] += 1
            reason = boundary.get("response_denial")
            if reason:
                res["boundary"]["response_denial_reasons"][reason] += 1
        # Claim-level decisions: a response can be admitted at the RESPONSE level while individual
        # claims are still denied (denied_count > 0) — its own gate-tightness signal the response
        # flag alone would hide.
        claims = boundary.get("claims")
        if isinstance(claims, list):
            for claim in claims:
                if not isinstance(claim, dict):
                    continue
                decision = claim.get("decision")
                if decision == "admit":
                    res["boundary"]["claims_admitted"] += 1
                elif decision == "deny":
                    res["boundary"]["claims_denied"] += 1
                    claim_reason = claim.get("reason")
                    if claim_reason:
                        res["boundary"]["claim_denial_reasons"][claim_reason] += 1
    # Per-result finalization outcome (the atomic bypass reason) is NOT persisted into state.json —
    # debate_finalize returns it but only writes the round-level ``finalized`` flag (counted as
    # runs.finalized_rounds). The persisted finalization-relevant signal is the B3 boundary above.


def _accumulate_run(summary, state):
    runs = summary["runs"]
    runs["total"] += 1
    runs["by_profile"][state.get("profile") or "none"] += 1
    for flag in ("structured_claims", "verify_claims", "fail_closed"):
        if state.get(flag):
            runs["modes"][flag] += 1
    if state.get("finalization_required"):
        runs["finalization_required"] += 1
    rounds = state.get("rounds")
    if not isinstance(rounds, dict):
        return
    for round_key, round_state in rounds.items():
        if not isinstance(round_state, dict):
            continue
        summary["rounds"]["total"] += 1
        summary["rounds"]["by_status"][round_state.get("status") or "unknown"] += 1
        if round_state.get("finalized"):
            runs["finalized_rounds"] += 1
        # _enforcement_mode reads this round's results; a malformed (non-dict) results in an older
        # or partial state would raise AttributeError there, so keep the report tolerant.
        try:
            mode = DebateController._enforcement_mode(state, int(round_key))
        except (ValueError, TypeError, KeyError, AttributeError):
            mode = "unknown"
        runs["enforcement_mode"][mode] += 1
        results = round_state.get("results")
        if isinstance(results, dict):
            for result in results.values():
                if isinstance(result, dict):
                    _accumulate_result(summary, result)


def _to_plain(obj):
    if isinstance(obj, Counter):
        return dict(obj)
    if isinstance(obj, dict):
        return {key: _to_plain(value) for key, value in obj.items()}
    return obj


def summarize(runs_dir):
    """Aggregate every ``<runs_dir>/*/state.json`` into a plain, JSON-serializable summary."""
    runs_dir = Path(runs_dir)
    summary = _new_summary(runs_dir)
    if runs_dir.is_dir():
        for state_path in sorted(runs_dir.glob("*/state.json")):
            try:
                state = json.loads(state_path.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                summary["runs"]["unreadable"] += 1
                continue
            if not isinstance(state, dict):
                summary["runs"]["unreadable"] += 1
                continue
            _accumulate_run(summary, state)
    return _to_plain(summary)


def _pct(part, whole):
    return "{:.0%}".format(part / whole) if whole else "-"


def _fmt_counter(counter):
    if not counter:
        return "(none)"
    return ", ".join("{}={}".format(key, counter[key]) for key in sorted(counter))


def render_text(summary):
    runs = summary["runs"]
    rounds = summary["rounds"]
    res = summary["results"]
    total_runs = runs["total"]
    lines = [
        "Run-state summary — {}".format(summary["runs_dir"]),
        "=" * 64,
        "Runs: {} readable ({} unreadable)".format(total_runs, runs["unreadable"]),
        "  profile:          {}".format(_fmt_counter(runs["by_profile"])),
        "  opt-in modes:     {}".format(_fmt_counter(runs["modes"])),
        "  enforcement mode: {}".format(_fmt_counter(runs["enforcement_mode"])),
        "  finalization:     required={}, finalized rounds={}".format(
            runs["finalization_required"], runs["finalized_rounds"]
        ),
        "Rounds: {} — {}".format(rounds["total"], _fmt_counter(rounds["by_status"])),
        "Panelist results: {}".format(res["total"]),
        "  schema_status:    {}".format(_fmt_counter(res["schema_status"])),
        "  errored:          {} ({})".format(res["errored"], _pct(res["errored"], res["total"])),
        "  stage crashes:    verification_error={}, boundary_error={}".format(
            res["stage_errors"]["verification_error"], res["stage_errors"]["boundary_error"]
        ),
    ]
    verification = res["verification"]
    claims = verification.get("claims", 0)
    lines.append(
        "  B2 verification:  claims={}, runtime_validated={}, failed={}, downgraded={} ({})".format(
            claims,
            verification.get("runtime_validated", 0),
            verification.get("failed", 0),
            verification.get("downgraded", 0),
            _pct(verification.get("downgraded", 0), claims),
        )
    )
    boundary = res["boundary"]
    lines.append(
        "  B3 boundary:      responses decided={}, admitted={}, denied={} ({})".format(
            boundary["with_decision"],
            boundary["admitted"],
            boundary["denied"],
            _pct(boundary["denied"], boundary["with_decision"]),
        )
    )
    lines.append(
        "    response denial reasons: {}".format(_fmt_counter(boundary["response_denial_reasons"]))
    )
    claims_total = boundary["claims_admitted"] + boundary["claims_denied"]
    lines.append(
        "    claims:         admitted={}, denied={} ({})".format(
            boundary["claims_admitted"],
            boundary["claims_denied"],
            _pct(boundary["claims_denied"], claims_total),
        )
    )
    lines.append("    claim denial reasons: {}".format(_fmt_counter(boundary["claim_denial_reasons"])))
    return "\n".join(lines)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--runs-dir",
        default=str(DEFAULT_RUNS_DIR),
        help="Directory holding <run_id>/state.json (default: .religion-council/runs)",
    )
    parser.add_argument("--json", action="store_true", help="Emit machine-readable JSON")
    args = parser.parse_args(argv)
    summary = summarize(args.runs_dir)
    if args.json:
        print(json.dumps(summary, ensure_ascii=False, indent=2))
    else:
        print(render_text(summary))
    return 0


if __name__ == "__main__":
    sys.exit(main())
