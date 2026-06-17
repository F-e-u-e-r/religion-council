"""Canonical enum sets, loaded from the quote-admissibility policy manifest.

Single source of truth so the B1 evidence/claim layer never hardcodes — and never
drifts from — the enums in ``policies/quote-admissibility.v2.json``. The manifest is
the authority (ADR 0001 / ADR 0002); these frozensets are derived from it at import.
"""
import json
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
POLICY_PATH = _ROOT / "policies" / "quote-admissibility.v2.json"


def load_manifest():
    with open(POLICY_PATH, encoding="utf-8") as handle:
        return json.load(handle)


_MANIFEST = load_manifest()


def _ids(key):
    items = _MANIFEST.get(key)
    if not isinstance(items, list):
        raise ValueError(
            "policy manifest key missing or not a list: {!r} in {}".format(key, POLICY_PATH.name)
        )
    return frozenset(item["id"] for item in items)


CLAIM_TYPES = _ids("claim_types")
EVIDENCE_TYPES = _ids("evidence_types")
REPRESENTATION_KINDS = _ids("representation_kinds")
RENDERING_MODES = _ids("rendering_modes")
EVIDENTIARY_ROLES = _ids("evidentiary_roles")
ARTIFACT_KINDS = _ids("artifact_kinds")
ACQUISITION_ORIGINS = _ids("acquisition_origins")
RETRIEVAL_PATHS = _ids("retrieval_paths")
SOURCE_ASSURANCES = _ids("source_assurances")
SPAN_ASSURANCE_TIERS = _ids("span_assurance_tiers")
VERIFICATION_STATES = _ids("verification_states")
RESPONSE_ENFORCEMENT_MODES = _ids("response_enforcement_modes")
BOUNDARY_DENIAL_REASONS = _ids("boundary_denial_reasons")
