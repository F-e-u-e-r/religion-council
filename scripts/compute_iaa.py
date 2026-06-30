#!/usr/bin/env python3
"""Inter-annotator agreement (Cohen's κ) for the retrieval-v1 relevance judgments.

Standard-library only, offline, deterministic. Computes Cohen's κ between independent judges from the
judgments fixture's optional ``judging.iaa`` pool — the shared set of ``(query, record)`` items that
two or more judges each labeled with a relevance grade.

Why a separate *pool*: ``judgments[].relevant[]`` is curator-1's authoritative scoring set (it feeds
nDCG/MRR and lists only the records deemed relevant). κ instead needs a fixed item universe that every
judge labels — including the records a judge calls *not* relevant — so disagreement is actually
observable. That universe lives under ``judging.iaa.pool`` and never disturbs the scoring labels.

With fewer than two judges in the pool there is no agreement to measure, so κ is reported as ``n/a``
— never fabricated (docs/benchmarks/retrieval-v1.md §Relevance judgments; ADR 0007 §9,
"Outstanding gate item before the default ranking flips"). The κ figure gates the BM25
*default-ranking* flip only; the no-answer gate shipped in v0.13.0 does not depend on it.

Fixture schema (additive, optional)::

    "judging": {
      ...,
      "iaa": {
        "label_set": [0, 1, 2],
        "pool": [
          {"query_id": "q001", "tradition": "...", "work": "...", "locator": "...",
           "labels": {"curator-1": 2, "judge-2": 1}}
        ]
      }
    }

Usage::

    python3 scripts/compute_iaa.py            # human summary against the committed fixture
    python3 scripts/compute_iaa.py --json     # machine-readable report
"""
import argparse
import json
from itertools import combinations
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
JUDGMENTS_PATH = ROOT / "docs" / "benchmarks" / "judgments" / "retrieval-v1.json"
KAPPA_PRECISION = 4


def cohen_kappa(labels_a, labels_b):
    """Cohen's κ for two aligned sequences of categorical labels.

    Returns a float in ``[-1.0, 1.0]``, or ``None`` when κ is undefined: no items, or expected
    agreement ``pe == 1`` (both raters used a single identical category throughout, so observed
    agreement carries no information). Deterministic — depends only on the inputs.
    """
    if len(labels_a) != len(labels_b):
        raise ValueError("label sequences must be aligned (equal length)")
    n = len(labels_a)
    if n == 0:
        return None
    categories = sorted(set(labels_a) | set(labels_b))
    agree = sum(1 for a, b in zip(labels_a, labels_b) if a == b)
    p_observed = agree / n
    count_a = {c: 0 for c in categories}
    count_b = {c: 0 for c in categories}
    for a, b in zip(labels_a, labels_b):
        count_a[a] += 1
        count_b[b] += 1
    p_expected = sum((count_a[c] / n) * (count_b[c] / n) for c in categories)
    if p_expected == 1:
        return None
    return (p_observed - p_expected) / (1 - p_expected)


def _pool(judging):
    return ((judging or {}).get("iaa") or {}).get("pool") or []


def judges_in_pool(pool):
    """Judge ids that appear in the pool, in first-seen order (deterministic)."""
    seen = []
    for item in pool:
        for judge in item.get("labels", {}):
            if judge not in seen:
                seen.append(judge)
    return seen


def aligned_labels(pool, judge_a, judge_b):
    """The two judges' labels over exactly the pool items both of them labeled."""
    labels_a, labels_b = [], []
    for item in pool:
        labels = item.get("labels", {})
        if judge_a in labels and judge_b in labels:
            labels_a.append(labels[judge_a])
            labels_b.append(labels[judge_b])
    return labels_a, labels_b


def pairwise_kappa(judging):
    """Pairwise κ for every judge pair sharing pool items, or ``None`` when < 2 judges exist.

    Shape: ``{"judges": [...], "pool_size": N, "pairs": [{"judges": [a, b], "n": k,
    "kappa": float|None}, ...]}``.
    """
    pool = _pool(judging)
    judges = judges_in_pool(pool)
    if len(judges) < 2:
        return None
    pairs = []
    for judge_a, judge_b in combinations(judges, 2):
        labels_a, labels_b = aligned_labels(pool, judge_a, judge_b)
        kappa = cohen_kappa(labels_a, labels_b)
        pairs.append({
            "judges": [judge_a, judge_b],
            "n": len(labels_a),
            "kappa": None if kappa is None else round(kappa, KAPPA_PRECISION),
        })
    return {"judges": judges, "pool_size": len(pool), "pairs": pairs}


def overall_kappa(judging):
    """A single representative κ (the lone pair for two judges, else the mean of pairwise κ).

    Returns ``None`` when no ≥2-judge pool exists — the honest single-curator state.
    """
    summary = pairwise_kappa(judging)
    if not summary:
        return None
    values = [pair["kappa"] for pair in summary["pairs"] if pair["kappa"] is not None]
    if not values:
        return None
    return round(sum(values) / len(values), KAPPA_PRECISION)


def load_judging(path=JUDGMENTS_PATH):
    return json.loads(Path(path).read_text(encoding="utf-8")).get("judging", {})


def report(judging):
    """Build the deterministic IAA report dict for a fixture's ``judging`` block."""
    summary = pairwise_kappa(judging)
    if not summary:
        declared = judging.get("independent_judge_count", len(judging.get("judges", [])))
        return {
            "independent_judge_count": declared,
            "inter_annotator_agreement": None,
            "method": judging.get("agreement_method"),
            "status": ("n/a — fewer than two judges have labeled a shared IAA pool "
                       "(single-curator baseline; not fabricated)"),
        }
    return {
        "independent_judge_count": len(summary["judges"]),
        "judges": summary["judges"],
        "pool_size": summary["pool_size"],
        "method": "cohen_kappa",
        "inter_annotator_agreement": overall_kappa(judging),
        "pairwise": summary["pairs"],
        "status": "computed",
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--judgments", default=str(JUDGMENTS_PATH),
                        help="path to the judgments fixture (default: retrieval-v1)")
    parser.add_argument("--json", action="store_true", help="emit the machine-readable report")
    args = parser.parse_args(argv)

    data = report(load_judging(args.judgments))
    if args.json:
        print(json.dumps(data, ensure_ascii=False, indent=2))
        return 0

    print("Inter-annotator agreement — Cohen's κ")
    print("  independent judges: {}".format(data["independent_judge_count"]))
    print("  method: {}".format(data.get("method")))
    if data.get("status") != "computed":
        print("  κ: n/a")
        print("  {}".format(data["status"]))
        return 0
    print("  pool size: {}".format(data["pool_size"]))
    print("  overall κ: {}".format(data["inter_annotator_agreement"]))
    for pair in data["pairwise"]:
        print("    {} vs {}: κ={} (n={})".format(
            pair["judges"][0], pair["judges"][1], pair["kappa"], pair["n"]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
