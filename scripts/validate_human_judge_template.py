#!/usr/bin/env python3
"""Validate a retrieval-v1 blind-judge template or filled pass (ADR 0007 §9 gate package).

Standard-library only, offline, deterministic. Checks a template against the committed retrieval-v1
fixture pool so a human or disclosed model judge's independent pass is well-formed and genuinely
**blind** before it is used as panel evidence.

Always checked:
  * the template's pool keys ``(query_id, tradition, work, locator)`` match the fixture's
    ``judging.iaa.pool`` exactly (same set, same count) — no missing, extra, or phantom items;
  * blindness — no item leaks an existing judge's answer: an item carries a single ``label`` field,
    never a ``labels`` map and never a ``curator-1`` / ``model-judge-*`` key;
  * ``judge.judge_type`` is ``"human"`` or ``"model"`` and ``blind_to`` is non-empty.

Mode:
  * ``--blank``  (default): every ``label`` must be ``null`` — the distributable, unfilled template.
  * ``--filled``: every ``label`` must be 0/1/2 and ``judge.id`` must be set — ready to merge.

Usage::

    python3 scripts/validate_human_judge_template.py docs/benchmarks/judgments/templates/retrieval-v1-human-blind-template.json --blank
    python3 scripts/validate_human_judge_template.py path/to/filled.json --filled
"""
import argparse
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
FIXTURE = ROOT / "docs" / "benchmarks" / "judgments" / "retrieval-v1.json"
LABEL_SET = {0, 1, 2}
ALLOWED_JUDGE_TYPES = ("human", "model")  # the human template + model-panel filled passes share this schema
LEAK_KEYS = ("labels", "curator-1", "model-judge-claude")


def _key(item):
    return (item.get("query_id"), item.get("tradition"), item.get("work"), item.get("locator"))


def fixture_pool_keys(fixture_path=FIXTURE):
    pool = json.loads(Path(fixture_path).read_text(encoding="utf-8"))["judging"]["iaa"]["pool"]
    return {_key(item) for item in pool}


def validate(template, fixture_keys, filled=False):
    """Return a list of human-readable error strings ([] == valid)."""
    errors = []
    pool = template.get("pool")
    if not isinstance(pool, list) or not pool:
        return ["template has no pool"]

    judge = template.get("judge", {})
    if judge.get("judge_type") not in ALLOWED_JUDGE_TYPES:
        errors.append("judge.judge_type must be one of {}".format(list(ALLOWED_JUDGE_TYPES)))
    if not judge.get("blind_to"):
        errors.append("judge.blind_to must be a non-empty list")
    if filled and not str(judge.get("id", "")).strip():
        errors.append("judge.id must be set for a filled template")

    keys = set()
    for i, item in enumerate(pool):
        for leak in LEAK_KEYS:
            if leak in item:
                errors.append("item {} leaks a non-blind field: {!r}".format(i, leak))
        keys.add(_key(item))
        label = item.get("label")
        if filled:
            if label not in LABEL_SET:
                errors.append("item {} ({}) label must be 0/1/2, got {!r}".format(
                    i, item.get("query_id"), label))
        else:
            if label is not None:
                errors.append("item {} ({}) label must be null in a blank template, got {!r}".format(
                    i, item.get("query_id"), label))

    if keys != fixture_keys:
        missing = fixture_keys - keys
        extra = keys - fixture_keys
        if missing:
            errors.append("{} pool item(s) missing vs the fixture (e.g. {})".format(
                len(missing), sorted(missing)[0]))
        if extra:
            errors.append("{} pool item(s) not in the fixture (e.g. {})".format(
                len(extra), sorted(extra)[0]))
    return errors


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("template", help="path to the blind-judge template/fill JSON")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--blank", action="store_true", help="require every label to be null (default)")
    mode.add_argument("--filled", action="store_true", help="require every label to be 0/1/2")
    args = parser.parse_args(argv)

    template = json.loads(Path(args.template).read_text(encoding="utf-8"))
    errors = validate(template, fixture_pool_keys(), filled=args.filled)
    if errors:
        print("INVALID ({} error(s)):".format(len(errors)))
        for error in errors:
            print("  - {}".format(error))
        return 1
    print("OK: {} pool items, {} (blind, pool matches retrieval-v1 fixture).".format(
        len(template["pool"]), "filled" if args.filled else "blank"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
