#!/usr/bin/env python3
"""Reproducible inventory of the curated Religion Council corpus.

Replaces hand-quoted corpus counts with a deterministic report generated from the
same records the portable retriever returns. The script imports the portable
``retrieve.py`` and inventories ``parse_reference(tradition)`` for every tradition,
so the inventory can never drift from what retrieval actually sees (generator /
retriever parity by construction).

Field mapping (plan S2 -> corpus reality). The file-based corpus stores canonical
record ``text`` plus a human ``locator``; it does NOT store byte-offset spans or a
runtime verification tier at rest (those are minted later by the B1a evidence
adapter and B2 verification). Each reported dimension is therefore computed from a
real, present-or-absent record field, and the two runtime-flavored plan fields are
mapped to their honest at-rest analog and labeled as such:

* total                     -> len(records)
* quotation                 -> evidence_type == "quotation" (verbatim)
* source_bound_summary      -> evidence_type == "source-bound-summary"
* with_source_locator       -> locator pins wording to a concrete source ("exact span"
                               analog; a record with the generic fallback locator does not)
* with_provenance           -> A1 provenance sidecar present (non-empty dict)
* with_rights               -> A1 rights note present (non-empty str)
* with_representation_kind  -> A1 representation_kind present
* with_rendering_mode       -> A1 rendering_mode present
* by_representation_kind    -> distribution of representation_kind values
* by_curation_tier          -> at-rest curation tier ("presentation-enriched" if any A1
                               presentation field is present else "reference-baseline");
                               this is the corpus's at-rest "assurance tier" dimension and is
                               NOT the runtime span-assurance tier (curated-snapshot /
                               edition-backed), which only B2 / A2 mint.
* invalid                   -> records failing a structural or policy check (see _validate)

Usage::

    python scripts/corpus_inventory.py                 # text report (default)
    python scripts/corpus_inventory.py --format json   # machine-readable report
    python scripts/corpus_inventory.py --check         # exit non-zero iff invalid records exist

``--check`` fails ONLY on structural / policy violations (invalid records), never merely
because counts changed, so it is safe as a CI gate and a release-doc freshness check.
"""

import argparse
import importlib.util
import json
import statistics
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PORTABLE_RETRIEVER = ROOT / "skills" / "religion-council" / "scripts" / "retrieve.py"
POLICY_MANIFEST = ROOT / "policies" / "quote-admissibility.v2.json"

# Presentation fields whose presence marks a record as curation-enriched (A1 sidecar).
PRESENTATION_FIELDS = ("representation_kind", "rendering_mode", "provenance", "rights")


def load_retriever(path=PORTABLE_RETRIEVER):
    """Import the portable retriever module by path (no package install required)."""
    spec = importlib.util.spec_from_file_location("religion_retrieve_inventory", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def load_policy_enums(path=POLICY_MANIFEST):
    """Read the enum id sets the inventory validates against, straight from the manifest.

    The manifest is the single source of truth (mirrors ``orchestrator/policy_enums.py``);
    a drift test asserts these match the derived frozensets.
    """
    with path.open(encoding="utf-8") as handle:
        manifest = json.load(handle)

    def ids(key):
        return frozenset(item["id"] for item in manifest[key])

    return {
        "representation_kinds": ids("representation_kinds"),
        "rendering_modes": ids("rendering_modes"),
    }


def _has_text(value):
    return isinstance(value, str) and bool(value.strip())


def _has_locator(record):
    """A concrete source locator, not the parser's generic fallback."""
    locator = record.get("locator")
    return _has_text(locator) and locator != "reference file entry"


def _curation_tier(record):
    if any(record.get(field) is not None for field in PRESENTATION_FIELDS):
        return "presentation-enriched"
    return "reference-baseline"


def _validate(record, enums):
    """Return a sorted list of structural / policy reasons this record is invalid.

    Checks mirror the renderer's real admissibility gates (ADR 0004): enum membership,
    the rights gate on curated presentation, and presentation completeness. An empty
    list means the record is structurally and policy-wise sound.
    """
    reasons = []
    for field in ("text", "tradition", "work", "locator"):
        if not _has_text(record.get(field)):
            reasons.append("incomplete-core:{}".format(field))

    representation = record.get("representation_kind")
    if representation is not None and representation not in enums["representation_kinds"]:
        reasons.append("representation-kind-not-in-enum")

    rendering = record.get("rendering_mode")
    if rendering is not None and rendering not in enums["rendering_modes"]:
        reasons.append("rendering-mode-not-in-enum")

    provenance = record.get("provenance")
    if provenance is not None and not (isinstance(provenance, dict) and provenance):
        reasons.append("provenance-malformed")

    # Renderer rights gate: any curated presentation metadata requires a rights note.
    has_presentation = any(
        record.get(field) is not None for field in ("representation_kind", "rendering_mode", "provenance")
    )
    if has_presentation and not _has_text(record.get("rights")):
        reasons.append("curated-presentation-without-rights")

    # A rendering mode is meaningless without the representation it qualifies.
    if rendering is not None and representation is None:
        reasons.append("rendering-mode-without-representation-kind")

    return sorted(reasons)


def _blank_stats():
    return {
        "total": 0,
        "quotation": 0,
        "source_bound_summary": 0,
        "with_source_locator": 0,
        "with_provenance": 0,
        "with_rights": 0,
        "with_representation_kind": 0,
        "with_rendering_mode": 0,
        "by_representation_kind": {},
        "by_curation_tier": {},
        "invalid": 0,
    }


def _accumulate(stats, record, invalid_reasons):
    stats["total"] += 1
    if record.get("evidence_type") == "quotation":
        stats["quotation"] += 1
    elif record.get("evidence_type") == "source-bound-summary":
        stats["source_bound_summary"] += 1
    if _has_locator(record):
        stats["with_source_locator"] += 1
    if isinstance(record.get("provenance"), dict) and record["provenance"]:
        stats["with_provenance"] += 1
    if _has_text(record.get("rights")):
        stats["with_rights"] += 1
    if record.get("representation_kind") is not None:
        stats["with_representation_kind"] += 1
    if record.get("rendering_mode") is not None:
        stats["with_rendering_mode"] += 1
    representation = record.get("representation_kind") or "(none)"
    stats["by_representation_kind"][representation] = (
        stats["by_representation_kind"].get(representation, 0) + 1
    )
    tier = _curation_tier(record)
    stats["by_curation_tier"][tier] = stats["by_curation_tier"].get(tier, 0) + 1
    if invalid_reasons:
        stats["invalid"] += 1


def build_inventory(retriever=None, enums=None):
    """Compute the full deterministic inventory: per-tradition stats, overall, and invalid records."""
    retriever = retriever or load_retriever()
    enums = enums or load_policy_enums()

    per_tradition = {}
    overall = _blank_stats()
    invalid_records = []
    for tradition in sorted(retriever.TRADITIONS):
        stats = _blank_stats()
        for record in retriever.parse_reference(tradition):
            reasons = _validate(record, enums)
            _accumulate(stats, record, reasons)
            _accumulate(overall, record, reasons)
            if reasons:
                invalid_records.append(
                    {
                        "tradition": tradition,
                        "work": record.get("work"),
                        "locator": record.get("locator"),
                        "reasons": reasons,
                    }
                )
        per_tradition[tradition] = stats

    totals = [stats["total"] for stats in per_tradition.values()]
    median_total = statistics.median(totals) if totals else 0
    # Balance signal for S3 enrichment: traditions materially below the project median.
    # Reported, never a --check failure (counts changing must not fail the gate).
    below_median = sorted(
        tradition
        for tradition, stats in per_tradition.items()
        if stats["total"] < median_total
    )
    return {
        "corpus_source": str(PORTABLE_RETRIEVER.relative_to(ROOT)),
        "traditions": per_tradition,
        "overall": overall,
        "balance": {"median_total": median_total, "below_median": below_median},
        "invalid_records": invalid_records,
    }


def _format_stats_line(name, stats):
    return (
        "{name:<14} total={total:<3} quote={quotation:<3} summary={source_bound_summary:<3} "
        "loc={with_source_locator:<3} prov={with_provenance:<3} rights={with_rights:<3} "
        "repr={with_representation_kind:<3} rmode={with_rendering_mode:<3} invalid={invalid}"
    ).format(name=name, **stats)


def format_text(inventory):
    lines = []
    lines.append("Religion Council corpus inventory")
    lines.append("Source: {}".format(inventory["corpus_source"]))
    lines.append("")
    lines.append("Per tradition:")
    for tradition in sorted(inventory["traditions"]):
        lines.append("  " + _format_stats_line(tradition, inventory["traditions"][tradition]))
    lines.append("")
    lines.append(_format_stats_line("OVERALL", inventory["overall"]))
    lines.append("")
    lines.append(
        "Curation tiers (overall): {}".format(
            ", ".join(
                "{}={}".format(tier, count)
                for tier, count in sorted(inventory["overall"]["by_curation_tier"].items())
            )
        )
    )
    balance = inventory["balance"]
    lines.append(
        "Balance: median_total={}; below_median={}".format(
            balance["median_total"],
            ", ".join(balance["below_median"]) or "(none)",
        )
    )
    lines.append("")
    invalid = inventory["invalid_records"]
    if invalid:
        lines.append("INVALID records ({}):".format(len(invalid)))
        for entry in invalid:
            lines.append(
                "  [{}] {} {} -> {}".format(
                    entry["tradition"], entry["work"], entry["locator"], ", ".join(entry["reasons"])
                )
            )
    else:
        lines.append("INVALID records: 0")
    return "\n".join(lines)


def main(argv=None):
    parser = argparse.ArgumentParser(description="Reproducible Religion Council corpus inventory.")
    parser.add_argument("--format", choices=("text", "json"), default="text")
    parser.add_argument(
        "--check",
        action="store_true",
        help="Exit non-zero iff any record fails a structural / policy check.",
    )
    args = parser.parse_args(argv)

    inventory = build_inventory()

    if args.check:
        invalid = inventory["invalid_records"]
        if invalid:
            sys.stderr.write(
                "Corpus inventory: {} invalid record(s).\n".format(len(invalid))
            )
            for entry in invalid:
                sys.stderr.write(
                    "  [{}] {} {} -> {}\n".format(
                        entry["tradition"], entry["work"], entry["locator"], ", ".join(entry["reasons"])
                    )
                )
            return 1
        return 0

    if args.format == "json":
        json.dump(inventory, sys.stdout, ensure_ascii=False, indent=2, sort_keys=True)
        sys.stdout.write("\n")
    else:
        sys.stdout.write(format_text(inventory) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
