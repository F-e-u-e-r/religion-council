"""B1b claim binding — bind a validated ``claim/v1`` payload to B1a EvidenceSeeds.

This is where ``Claim`` / ``ClaimEvidenceEdge`` / initial ``VerificationResult`` are
finally created: the B1a *seed* side (occurrence-level evidence identity, minted by
:mod:`retrieval_evidence_adapter`) meets the B1b *claim* side (a panelist's structured
payload, validated by :func:`claim_protocol.validate_claim_payload`).

Scope (ADR 0002 B1 / ADR 0003): schema-level only.

* It resolves each edge's ``evidence_seed_id`` against the per-run evidence catalog and
  rejects an unknown id as a dangling reference (schema-level), mirroring the adapter's
  unknown-artifact rejection.
* ``evidentiary_role`` is claim-relative — taken from the edge's own declaration, never
  inferred from the resolved seed (ADR 0003 §6).
* ``source_assurance`` is stamped from the resolved seed (the seed knows whether real
  artifact bytes back it); ``verification_state`` is forced to ``"unverified"`` (ADR 0003
  §3). It does NOT verify evidence, validate spans, or remove a failed support edge — those
  are B2.

The catalog and the bound claims are plain-JSON serializable so the controller can persist
them additively in ``state.json`` and rebuild them on a later round / retry.
"""
from dataclasses import asdict, dataclass, field
from typing import List, Optional

from claim_protocol import SchemaRejection, validate_claim_payload


def _snippet(text, limit=160):
    collapsed = " ".join(text.split())
    return collapsed if len(collapsed) <= limit else collapsed[: limit - 1] + "…"


@dataclass
class CatalogSeed:
    """One prompt-facing evidence seed: a compact id over an occurrence-level identity."""

    seed_id: str  # compact, prompt-facing (e.g. "S1"); stable within one run's catalog
    occurrence_id: str  # the real binding key (per-occurrence; not bytes-deduped)
    artifact_id: str
    source_assurance: str
    artifact_kind: str
    # Carried metadata, for prompt rendering only — never identity:
    work: Optional[str] = None
    locator: Optional[str] = None
    tradition: Optional[str] = None
    snippet: Optional[str] = None
    # A1 curated presentation/provenance (carried-not-trusted): present only when the curation
    # sidecar marked the source record, so a renderer can present a rendering correctly.
    representation_kind: Optional[str] = None
    rendering_mode: Optional[str] = None
    provenance: Optional[dict] = None
    rights: Optional[str] = None
    # ADR 0004: interpretation-only classification (a cross-locus thematic cue / paraphrase, not a
    # source-bound quotation). The finalizer refuses to mint Surface-A authority from such a seed.
    interpretation_only: Optional[bool] = None


class EvidenceCatalog:
    """Per-run catalog mapping compact ``S#`` ids to occurrence-level evidence seeds."""

    def __init__(self, seeds):
        self.seeds = list(seeds)
        self._by_id = {seed.seed_id: seed for seed in self.seeds}

    def get(self, seed_id):
        return self._by_id.get(seed_id)

    def __len__(self):
        return len(self.seeds)

    @classmethod
    def from_seeds_and_records(cls, evidence_seeds, records, snippet_chars=160):
        """Build a catalog from adapter seeds aligned 1:1 with their envelope records.

        ``adapt()`` emits exactly one seed per record in order, so the two align by
        position; the record supplies the human-readable snippet the seed does not carry.
        """
        if len(evidence_seeds) != len(records):
            raise ValueError(
                "seeds/records length mismatch: {} vs {}".format(
                    len(evidence_seeds), len(records)
                )
            )
        catalog = []
        for index, (seed, record) in enumerate(zip(evidence_seeds, records), start=1):
            text = record.get("text") if isinstance(record, dict) else None
            catalog.append(
                CatalogSeed(
                    seed_id="S{}".format(index),
                    occurrence_id=seed.occurrence_id,
                    artifact_id=seed.artifact_id,
                    source_assurance=seed.source_assurance,
                    artifact_kind=seed.artifact_kind,
                    work=seed.work,
                    locator=seed.locator,
                    tradition=seed.tradition,
                    snippet=_snippet(text, snippet_chars) if isinstance(text, str) else None,
                    representation_kind=getattr(seed, "declared_representation_kind", None),
                    rendering_mode=getattr(seed, "declared_rendering_mode", None),
                    provenance=getattr(seed, "provenance", None),
                    rights=getattr(seed, "rights", None),
                    interpretation_only=getattr(seed, "interpretation_only", None),
                )
            )
        return cls(catalog)

    def to_state(self):
        return [asdict(seed) for seed in self.seeds]

    @classmethod
    def from_state(cls, entries):
        fields = CatalogSeed.__dataclass_fields__
        seeds = [
            CatalogSeed(**{key: value for key, value in entry.items() if key in fields})
            for entry in (entries or [])
        ]
        return cls(seeds)

    def render_for_prompt(self):
        """Compact, prompt-facing listing. Returns the empty-state note when no seeds."""
        if not self.seeds:
            return "(No structured evidence seeds were supplied for this run.)"
        lines = []
        for seed in self.seeds:
            where = " ".join(part for part in (seed.work, seed.locator) if part)
            head = "{}: {}".format(seed.seed_id, where) if where else seed.seed_id
            if seed.snippet:
                head += " — “{}”".format(seed.snippet)
            # A1: flag a curated rendering so a panelist treats it as a rendering, not the
            # original wording (e.g. a Chinese Qur'an rendering).
            if seed.rendering_mode:
                marker = seed.representation_kind or "rendering"
                head += " [{}: {}]".format(marker, seed.rendering_mode)
            lines.append(head)
        return "\n".join(lines)


@dataclass
class ClaimEvidenceEdge:
    claim_id: str
    evidence_seed_id: str
    occurrence_id: str
    artifact_id: str
    evidentiary_role: str  # claim-relative; from the producer's declaration (ADR 0003 §6)
    evidence_type: str
    source_assurance: str  # stamped from the resolved seed
    verification_state: str = "unverified"  # system-set; only B2 may change it


@dataclass
class ClaimRecord:
    claim_id: str
    claim_type: str
    text: str
    representation_kind: Optional[str] = None
    rendering_mode: Optional[str] = None
    verification_state: str = "unverified"  # initial VerificationResult (ADR 0003 §3)
    edges: List[ClaimEvidenceEdge] = field(default_factory=list)


@dataclass
class BoundClaims:
    protocol_version: str
    claims: List[ClaimRecord]

    def to_state(self):
        return {
            "protocol_version": self.protocol_version,
            "claims": [asdict(claim) for claim in self.claims],
        }


def bind_payload(payload, catalog):
    """Bind a validated ``claim/v1`` payload to ``catalog`` seeds; return :class:`BoundClaims`.

    Re-runs :func:`validate_claim_payload` defensively (raises :class:`SchemaRejection`),
    then resolves each ``edge.evidence_seed_id`` to a catalog seed. An unknown id is a
    schema-level dangling reference and is rejected. ``evidentiary_role`` comes from the
    edge's own declaration; ``verification_state`` is forced to ``"unverified"``.
    """
    validate_claim_payload(payload)
    records = []
    by_id = {}
    for claim in payload["claims"]:
        record = ClaimRecord(
            claim_id=claim["claim_id"],
            claim_type=claim["claim_type"],
            text=claim["text"],
            representation_kind=claim.get("representation_kind"),
            rendering_mode=claim.get("rendering_mode"),
        )
        records.append(record)
        by_id[record.claim_id] = record

    for edge in payload.get("edges", []):
        seed = catalog.get(edge["evidence_seed_id"])
        if seed is None:
            raise SchemaRejection(
                "edge references unknown evidence_seed_id: {!r}".format(
                    edge["evidence_seed_id"]
                )
            )
        by_id[edge["claim_id"]].edges.append(
            ClaimEvidenceEdge(
                claim_id=edge["claim_id"],
                evidence_seed_id=seed.seed_id,
                occurrence_id=seed.occurrence_id,
                artifact_id=seed.artifact_id,
                evidentiary_role=edge["evidentiary_role"],
                evidence_type=edge["evidence_type"],
                source_assurance=seed.source_assurance,
                verification_state="unverified",
            )
        )

    return BoundClaims(protocol_version=payload["protocol_version"], claims=records)
