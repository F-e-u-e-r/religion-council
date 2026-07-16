#!/usr/bin/env python3
"""Project retriever entry point (ADR 0006 §1 — migration phase 3).

The project-side retriever the orchestrated council uses. It emits the **same**
``religion-council/retrieval/v1`` envelope, the same record fields, and the same stable-identity
inputs as the portable retriever, so the B-axis (B1 adapter, B2 verifier, B3 boundary, P1
finalizer) consumes it without any backend-specific branch (ADR 0006 §4.5).

Today it is a thin, file-based wrapper over the portable retriever. Later it MAY grow a local
index / chunk store / RAG client — changing only its internals and its ``retriever_kind``, never
the contract or the downstream guarantees. Unlike the portable retriever, this module MAY import
project code: it is **not** bound by the stdlib-only rule (ADR 0006 §4.4). It IS bound by the
shared conformance suite (``tests/retrieval_contract/test_contract_project.py``).

No index, RAG, or network backend is selected here; that is gated on a later benchmark ADR
(ADR 0006 §6).
"""
import argparse
import importlib.util
import json
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
_PORTABLE_RETRIEVER = _ROOT / "skills" / "religion-council" / "scripts" / "retrieve.py"

RETRIEVER_KIND = "project-file"


def _load_portable():
    """Load the portable retriever by path (it is not an installed module)."""
    spec = importlib.util.spec_from_file_location(
        "religion_portable_retrieve", _PORTABLE_RETRIEVER
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


_portable = _load_portable()

# Re-export the portable backend's contract surface so a caller can treat this module as the
# retriever directly (TRADITIONS, the contract version, and the three retrieval entry points).
RETRIEVAL_CONTRACT_VERSION = _portable.RETRIEVAL_CONTRACT_VERSION
TRADITIONS = _portable.TRADITIONS


def parse_reference(tradition):
    return _portable.parse_reference(tradition)


def retrieve(tradition, query, k=5):
    return _portable.retrieve(tradition, query, k)


def retrieve_envelope(tradition, query, k=5):
    return _portable.retrieve_envelope(tradition, query, k)


# --- No-answer gate (ADR 0007 §1, §8.2 — the threshold half, adopted as an explicit project API) ---
#
# When the lexical confidence (the top record's lexical score) for a (tradition, query) is below the
# threshold, the gated retrieval returns "no support" (an empty result), so an off-corpus query does
# not surface a noise-floor match as if it were evidence. The cutoff is applied to the LEXICAL score
# (the calibrated integer signal the t2/t3 thresholds were tuned against in v0.12.3), never to a
# re-ranking float scale.
#
# This is deliberately ADDITIVE: ``retrieve()`` / ``retrieve_envelope()`` are unchanged, so the
# retrieval-v1 lexical baseline and the ADR 0006 conformance suite keep measuring the raw signal and
# the committed benchmark reports stay byte-identical. ``retrieve_gated`` / ``retrieve_envelope_gated``
# are the project retriever's no-answer POLICY, validated by the committed
# ``retrieval-v1-lexical-threshold-t3`` report. Flipping a default and re-pointing the baseline to the
# portable retriever are deferred to the BM25 adoption after the independent-judge / κ gate
# (ADR 0007 §8.4, §9); this module does not change default behavior or select any backend.
NO_ANSWER_THRESHOLD = 3  # t3: ADR 0007 — t2/t3 are equivalent on retrieval-v1; t3 is more conservative.


def retrieve_gated(tradition, query, k=5, threshold=NO_ANSWER_THRESHOLD):
    """Lexical retrieval with the ADR 0007 no-answer gate.

    Returns the raw lexical-ranked top-``k`` **unchanged** when the top lexical score meets
    ``threshold``; returns an empty list (no support) when it is below ``threshold``. The gate only
    decides whether the whole result set is admitted — it never re-orders or mutates records, so the
    identity and ordering of any returned record are exactly what :func:`retrieve` returns.
    """
    ranked = _portable.retrieve(tradition, query, k)
    if not ranked or _portable.score(query, ranked[0]) < threshold:
        return []
    return ranked


def retrieve_envelope_gated(tradition, query, k=5, threshold=NO_ANSWER_THRESHOLD):
    """Versioned envelope around :func:`retrieve_gated`.

    Same ``contract_version`` as :func:`retrieve_envelope`; an empty ``records`` list is the
    no-support signal. The envelope shape is unchanged, so the B1 adapter and downstream consumers
    treat a gated no-answer as "zero records", not as a contract error.
    """
    return {
        "contract_version": RETRIEVAL_CONTRACT_VERSION,
        "records": retrieve_gated(tradition, query, k, threshold),
    }


def score(query, record):
    """Lexical relevance score for one record (re-exported from the wrapped backend).

    This is the *lexical* scoring of today's file-based backend, not part of the retrieval
    envelope contract (ADR 0006 §2) — a future index/dense backend would replace it. The
    retrieval-v1 benchmark uses it to rank the whole corpus for a query; that benchmark is
    explicitly the lexical-baseline measurement (docs/benchmarks/retrieval-v1.md).
    """
    return _portable.score(query, record)


def capabilities():
    """Project retriever capability metadata (ADR 0006 §3).

    Inherits the wrapped backend's capabilities (so ``contract_version`` and the stable-identity /
    network flags cannot drift from what actually retrieves) and overrides only ``retriever_kind``.
    A future index/service backend would report ``project-index`` / ``project-service`` and MAY set
    ``supports_network_acquisition`` — at which point it MUST also guarantee
    ``supports_stable_occurrence_identity`` (the ADR 0006 §3 invariant), or fail closed in the
    adapter (ADR 0005).
    """
    caps = dict(_portable.capabilities())
    caps["retriever_kind"] = RETRIEVER_KIND
    return caps


def main():
    parser = argparse.ArgumentParser(description="Worldview Council project retriever")
    parser.add_argument("--tradition", choices=sorted(TRADITIONS))
    parser.add_argument("--query")
    parser.add_argument("--k", type=int, default=5)
    parser.add_argument(
        "--capabilities",
        action="store_true",
        help="Print this retriever's capability metadata (ADR 0006) and exit.",
    )
    args = parser.parse_args()
    if args.capabilities:
        json.dump(capabilities(), sys.stdout, ensure_ascii=False, indent=2)
        sys.stdout.write("\n")
        return
    if not args.tradition or args.query is None:
        parser.error("--tradition and --query are required (or pass --capabilities)")
    try:
        result = retrieve(args.tradition, args.query, args.k)
    except ValueError as exc:
        parser.error(str(exc))
    json.dump(result, sys.stdout, ensure_ascii=False, indent=2)
    sys.stdout.write("\n")


if __name__ == "__main__":
    main()
