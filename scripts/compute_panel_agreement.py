#!/usr/bin/env python3
"""Pairwise Cohen's κ across the retrieval-v1 judge panel (curator-1 + filled model/human passes).

Standard-library only, offline, deterministic. Reads curator-1's labels from the committed fixture and
each filled template passed on the command line (typically ``docs/benchmarks/judgments/panel/*.json``),
aligns every rater pair on the pool items both labeled, and reports Cohen's κ **per pair** — so
same-provider correlation (e.g. two Claude-family judges agreeing because they are similar, not because
they are right) stays visible instead of being hidden inside one aggregate number.

The κ figures are **evidence only**. They do NOT authorize the BM25 default-ranking flip: the gate
guardrail (``judging.gate_evidence.bm25_default_flip_authorized``) stays ``false`` unless the project
owner explicitly accepts model-panel evidence (ADR 0007 §9; issue #42). A multi-rater aggregate
(Fleiss' κ / Krippendorff's α) is the natural addition once ≥ 3 filled passes exist.

Usage::

    python3 scripts/compute_panel_agreement.py docs/benchmarks/judgments/panel/*.json
    python3 scripts/compute_panel_agreement.py --json panel/a.json panel/b.json
"""
import argparse
import importlib.util
import json
from itertools import combinations
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
FIXTURE = ROOT / "docs" / "benchmarks" / "judgments" / "retrieval-v1.json"
IAA_PATH = ROOT / "scripts" / "compute_iaa.py"
KAPPA_PRECISION = 4


def _iaa():
    spec = importlib.util.spec_from_file_location("rc_compute_iaa", IAA_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _key(item):
    return (item.get("query_id"), item.get("tradition"), item.get("work"), item.get("locator"))


def curator_rater(fixture_path=FIXTURE):
    """curator-1's labels from the committed fixture pool: (id, provider, {key: label})."""
    pool = json.loads(Path(fixture_path).read_text(encoding="utf-8"))["judging"]["iaa"]["pool"]
    return "curator-1", "human", {_key(it): it["labels"]["curator-1"] for it in pool}


def panel_rater(path):
    """A filled template's labels: (judge id, provider, {key: label})."""
    doc = json.loads(Path(path).read_text(encoding="utf-8"))
    judge = doc.get("judge", {})
    labels = {_key(it): it["label"] for it in doc["pool"] if it.get("label") is not None}
    return judge.get("id") or Path(path).stem, judge.get("provider", "unknown"), labels


def pairwise(raters):
    """raters: ordered list of (id, provider, {key: label}). Returns a list of pair dicts."""
    iaa = _iaa()
    out = []
    for (id_a, prov_a, la), (id_b, prov_b, lb) in combinations(raters, 2):
        shared = sorted(set(la) & set(lb))
        kappa = iaa.cohen_kappa([la[k] for k in shared], [lb[k] for k in shared])
        out.append({
            "judges": [id_a, id_b],
            "n": len(shared),
            "kappa": None if kappa is None else round(kappa, KAPPA_PRECISION),
            "relation": "same-provider" if prov_a == prov_b else "cross-provider",
        })
    return out


def build_raters(paths, fixture_path=FIXTURE):
    raters = [curator_rater(fixture_path)]
    for path in paths:
        raters.append(panel_rater(path))
    return raters


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("panel", nargs="+", help="filled template JSON file(s)")
    parser.add_argument("--json", action="store_true", help="emit the machine-readable report")
    args = parser.parse_args(argv)

    raters = build_raters(args.panel)
    pairs = pairwise(raters)
    if args.json:
        print(json.dumps({"raters": [r[0] for r in raters], "pairs": pairs},
                         ensure_ascii=False, indent=2))
        return 0

    print("Panel pairwise agreement — Cohen's κ ({} raters)".format(len(raters)))
    for pair in pairs:
        print("  {} vs {}: κ={} (n={}, {})".format(
            pair["judges"][0], pair["judges"][1], pair["kappa"], pair["n"], pair["relation"]))
    print("  note: evidence only — bm25_default_flip_authorized stays false (ADR 0007 §9).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
