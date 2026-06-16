"""RetrievalEvidenceAdapterV1 (B1a) — retrieval envelope -> evidence seeds.

Consumes the versioned retrieval envelope (``religion-council/retrieval/v1``),
ingests each record's ``text`` as an immutable, content-addressed Artifact, and
emits one :class:`EvidenceSeed` per *occurrence*. Artifacts dedupe by bytes; seeds
never do (each carries its own ``occurrence_id``).

Scope (ADR 0002 B1 / ADR 0003): schema-level rejection only; ``verification_state``
is always ``"unverified"``. The adapter does NOT decide admissibility and does NOT
create Claims, ClaimEvidenceEdges, or VerificationResults — those are B1b (and
``evidentiary_role`` is claim-relative, so it cannot exist without a claim).
"""
import hashlib
from dataclasses import dataclass
from typing import Optional

import policy_enums
from claim_protocol import SchemaRejection

ACCEPTED_CONTRACT_VERSION = "religion-council/retrieval/v1"
_UNIT_SEP = "\x1f"


@dataclass
class EvidenceSeed:
    occurrence_id: str
    artifact_id: str
    byte_offset: int
    byte_length: int
    artifact_kind: str
    acquisition_origin: str
    retrieval_path: str
    source_assurance: str
    verification_state: str
    # Producer-declared metadata: carried, never trusted (ADR 0003 §2).
    declared_label: Optional[str]
    declared_evidence_type: Optional[str]
    declared_verbatim: Optional[bool]
    # Carried context (not identity):
    tradition: Optional[str] = None
    work: Optional[str] = None
    locator: Optional[str] = None
    topic: Optional[str] = None
    language: Optional[str] = None
    retrieval_rank: Optional[int] = None
    source_file: Optional[str] = None
    source_line: Optional[int] = None
    # representation_kind / rendering_mode are intentionally omitted at B1a:
    # representation_kinds has no "unknown" member, and neither is inferable from a
    # retrieval record (e.g. a Chinese Qur'an snippet is a meaning-rendering, but
    # language=zh-Hant alone cannot say so). They are set at B1b / during curation.


def artifact_kind_of(record):
    """Derive artifact_kind from evidence_type/verbatim — never from category."""
    evidence_type = record.get("evidence_type")
    verbatim = record.get("verbatim")
    if evidence_type == "quotation" and verbatim is True:
        return "source-text"
    if evidence_type == "source-bound-summary" and verbatim is False:
        return "reference-summary"
    return "unknown"


def occurrence_id(record, artifact_id, record_index):
    """Per-occurrence id; never the artifact_id alone.

    The same bytes can appear at different work/locator/source lines, so identity
    must not collapse to ``artifact_id``. Two regimes:

    * **With origin hints** (``source_file`` + ``source_line``, i.e. A0/A1): the id is
      **corpus-stable** and excludes retrieval rank, so it is stable across queries.
    * **Without origin hints** (e.g. an A3 network backend): the id falls back to the
      envelope ``record_index`` and is therefore **retrieval-order scoped** — a
      different ordering yields a different id. This is a deliberate stop-gap: when
      A2/A3 records carry ``artifact_ref`` + ``span`` those should become the stable
      occurrence key. Do not treat the fallback id as corpus-stable.
    """
    source_file = record.get("source_file")
    source_line = record.get("source_line")
    work = str(record.get("work", ""))
    locator = str(record.get("locator", ""))
    if source_file is not None and source_line is not None:
        parts = [artifact_id, work, locator, str(source_file), str(source_line)]
    else:
        parts = [
            artifact_id,
            "idx:{}".format(record_index),
            work,
            locator,
            str(record.get("topic", "")),
            str(record.get("tradition", "")),
        ]
    return hashlib.sha256(_UNIT_SEP.join(parts).encode("utf-8")).hexdigest()


def _require_text(record, index):
    text = record.get("text")
    if not isinstance(text, str):
        raise SchemaRejection(
            "record[{}].text must be a string, got {}".format(index, type(text).__name__)
        )
    # Reject the exact empty string only; whitespace-only text is canonicalized
    # (not trimmed), so it is a legitimate artifact.
    if text == "":
        raise SchemaRejection("record[{}].text must not be the empty string".format(index))
    return text


def adapt(envelope, store, *, acquisition_origin="bundled", retrieval_path="retrieved-via-seam"):
    """Adapt a retrieval envelope into EvidenceSeeds, persisting immutable snapshots.

    Schema-level rejection only. ``verification_state`` is always ``"unverified"``.
    """
    if not isinstance(envelope, dict):
        raise SchemaRejection("envelope must be an object")
    version = envelope.get("contract_version")
    if version != ACCEPTED_CONTRACT_VERSION:
        raise SchemaRejection("unsupported contract_version: {!r}".format(version))
    records = envelope.get("records")
    if not isinstance(records, list):
        raise SchemaRejection("envelope.records must be a list")
    if acquisition_origin not in policy_enums.ACQUISITION_ORIGINS:
        raise ValueError("invalid acquisition_origin: {!r}".format(acquisition_origin))
    if retrieval_path not in policy_enums.RETRIEVAL_PATHS:
        raise ValueError("invalid retrieval_path: {!r}".format(retrieval_path))

    # Preflight every record before any persistence side effect, so a schema-invalid
    # envelope leaves the store untouched (no partial snapshots / origins).
    for index, record in enumerate(records):
        if not isinstance(record, dict):
            raise SchemaRejection("record[{}] must be an object".format(index))
        _require_text(record, index)

    seeds = []
    for index, record in enumerate(records):
        text = _require_text(record, index)
        aid, byte_length = store.put_snapshot(text)
        occ = occurrence_id(record, aid, index)
        seeds.append(
            EvidenceSeed(
                occurrence_id=occ,
                artifact_id=aid,
                byte_offset=0,
                byte_length=byte_length,
                artifact_kind=artifact_kind_of(record),
                acquisition_origin=acquisition_origin,
                retrieval_path=retrieval_path,
                source_assurance="artifact-backed",
                verification_state="unverified",
                declared_label=record.get("label"),
                declared_evidence_type=record.get("evidence_type"),
                declared_verbatim=record.get("verbatim"),
                tradition=record.get("tradition"),
                work=record.get("work"),
                locator=record.get("locator"),
                topic=record.get("topic"),
                language=record.get("language"),
                retrieval_rank=index,
                source_file=record.get("source_file"),
                source_line=record.get("source_line"),
            )
        )
        store.append_origin(
            {
                "artifact_id": aid,
                "occurrence_id": occ,
                "tradition": record.get("tradition"),
                "work": record.get("work"),
                "locator": record.get("locator"),
                "topic": record.get("topic"),
                "source_file": record.get("source_file"),
                "source_line": record.get("source_line"),
                "retrieval_rank": index,
            }
        )
    return seeds
