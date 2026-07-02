"""Corpus-metadata enum sets (ADR 0008), loaded from ``policies/corpus-metadata.v1.json``.

Textual-witness / canon / recension classification carried per-record via the A1 ``presentation.json``
sidecar. Kept **separate** from ``policy_enums`` (the frozen quote-admissibility policy) — a different
concern (ADR 0008 §Decision 1). Enum membership is enforced in ``tests/test_corpus_curation.py``; the
portable retriever only type-checks these fields (carried-not-trusted), never enum-checks them.
"""
import json
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
POLICY_PATH = _ROOT / "policies" / "corpus-metadata.v1.json"


def load_manifest():
    with open(POLICY_PATH, encoding="utf-8") as handle:
        return json.load(handle)


_MANIFEST = load_manifest()


def _ids(key):
    items = _MANIFEST.get(key)
    if not isinstance(items, list):
        raise ValueError(
            "corpus-metadata manifest key missing or not a list: {!r} in {}".format(
                key, POLICY_PATH.name
            )
        )
    return frozenset(item["id"] for item in items)


WITNESS_KINDS = _ids("witness_kinds")
CANON_SCOPES = _ids("canon_scopes")
TEXTUAL_WITNESSES = _ids("textual_witnesses")
COMMENTARIAL_LINEAGES = _ids("commentarial_lineages")
CORPUS_FAMILIES = _ids("corpus_families")

# Sidecar field -> the enum its value must belong to (checked in the curation test suite). `version`
# is a free-form source-edition string (e.g. 通行本), not enum-controlled.
SIDECAR_ENUM_FIELDS = {
    "witness_kind": WITNESS_KINDS,
    "canon_scope": CANON_SCOPES,
    "textual_witness": TEXTUAL_WITNESSES,
    "commentarial_lineage": COMMENTARIAL_LINEAGES,
    "corpus_family": CORPUS_FAMILIES,
}
