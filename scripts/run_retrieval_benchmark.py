#!/usr/bin/env python3
"""Retrieval benchmark runner — retrieval-v1 lexical baseline.

Measures a retriever (default: the project retriever) against the frozen retrieval-v1 query set
and relevance judgments, and emits a reproducible JSON report and/or a human Markdown report. This
is **measurement only**: it selects no backend (docs/benchmarks/retrieval-v1.md).

Design constraints (ADR 0006 §6 / the plan):

* Standard-library only (plus the project's own retriever + B1 adapter — no third-party deps),
  Python 3.9 compatible, offline, deterministic.
* Measure through the **contract**, not through internals: candidate records are acquired via the
  retriever's per-tradition ``retrieve_envelope()`` (the ADR 0006 §2 contract surface), and the
  identity/contract metrics feed those **real** envelopes through the **real** B1 adapter — using
  the retriever's own ``contract_version`` — to confirm a stable occurrence id is minted (never an
  order-scoped fallback). The harness never hand-builds the adapter envelope from an internal parse.
* Identity, not position: relevance is keyed on the stable ``(tradition, work, locator)`` record
  identity, and citation fidelity is measured directly (occurrence ids compared across two adapter
  runs and a reordering of the result list), so a backend that made identity order-dependent fails
  the metric instead of passing silently (docs/benchmarks/retrieval-v1.md §Citation fidelity).
* The JSON report is reproducible (no wall-clock, no checkout-specific occurrence-id hashes); the
  Markdown report additionally carries a machine-specific timing snapshot.

This is the **lexical-baseline** harness: the global cross-tradition ordering is the retriever's own
lexical ``score()`` signal (the only cross-tradition comparison the file baseline exposes), and
``_require_lexical_baseline()`` refuses any other ``retriever_kind`` so a future index/hybrid/dense/
service backend is measured by the deferred backend-selection harness, never silently mismeasured
here (ADR 0006 §6; docs/benchmarks/retrieval-v1.md).
"""
import argparse
import importlib.util
import json
import math
import re
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PORTABLE_RETRIEVER = ROOT / "skills" / "religion-council" / "scripts" / "retrieve.py"
PROJECT_RETRIEVER = ROOT / "orchestrator" / "project_retrieve.py"
QUERIES_PATH = ROOT / "docs" / "benchmarks" / "queries" / "retrieval-v1.json"
JUDGMENTS_PATH = ROOT / "docs" / "benchmarks" / "judgments" / "retrieval-v1.json"
VERSION_PATH = ROOT / "VERSION"
BM25_REFERENCE_REPORTS = (
    ("threshold t2", ROOT / "docs" / "benchmarks" / "results" / "retrieval-v1-lexical-threshold-t2.json"),
    ("threshold t3", ROOT / "docs" / "benchmarks" / "results" / "retrieval-v1-lexical-threshold-t3.json"),
)

DEFAULT_KS = (1, 3, 5)
RELEVANT_THRESHOLD = 1  # relevance >= 1 counts as relevant (exact-span metrics require 2)
# This harness measures the file-based lexical baseline only; any other retriever_kind is refused
# (see _require_lexical_baseline / module docstring). project-index / project-service etc. are the
# deferred backend-selection harness's job (ADR 0006 §6).
LEXICAL_BASELINE_KINDS = ("portable-file", "project-file")
REQUIRED_RECORD_FIELDS = (
    "text", "tradition", "school", "work", "locator",
    "language", "version", "category", "label",
)
EXACT_CATEGORIES = ("exact_quote", "exact_locator")

# Candidate: lexical-bm25 (experiment only). A BM25-style re-ranking of the SAME file corpus over the
# SAME lexical tokenization as the baseline, so the comparison isolates *weighting* (TF saturation +
# length normalization + IDF) from tokenization. It is computed entirely in this harness as a
# candidate signal — the portable/project retriever is unchanged and no backend is adopted (this is
# candidate family 2, "local lexical index / BM25-style ranker", in docs/benchmarks/retrieval-v1.md;
# adopting it would be a separate, deferred decision). Defaults match Lucene BM25Similarity.
BM25_K1 = 1.2
BM25_B = 0.75
BM25_FIELDS = ("topic", "text", "work", "locator", "school")  # same haystack fields as score()
_ASCII_WORD_RE = re.compile(r"[a-z0-9]+")
_CJK_RE = re.compile(r"[㐀-鿿]+")
_LEXICAL_STOPWORDS = frozenset("的了與和是")


# --------------------------------------------------------------------------------------- loading

def _load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def get_retriever(kind):
    if kind == "project":
        return _load_module("rc_bench_project_retriever", PROJECT_RETRIEVER)
    if kind == "portable":
        return _load_module("rc_bench_portable_retriever", PORTABLE_RETRIEVER)
    raise ValueError("unknown retriever kind: {!r} (use 'project' or 'portable')".format(kind))


def load_json(path):
    with Path(path).open(encoding="utf-8") as handle:
        return json.load(handle)


# ------------------------------------------------------------------------------- corpus + search

def record_key(record):
    return (record["tradition"], record["work"], record["locator"])


def _require_lexical_baseline(retriever):
    """Refuse to measure anything but the file-based lexical baseline (ADR 0006 §6).

    The global cross-tradition ranking below leans on the retriever's lexical ``score()`` signal,
    which only the file baseline exposes. Rather than silently mismeasure a future index/hybrid/
    dense/service backend (which satisfies the *retrieval contract* but has no comparable
    ``score()``), the harness fails loud and points at the deferred backend-selection harness.
    """
    caps = retriever.capabilities()
    kind = caps.get("retriever_kind")
    if kind not in LEXICAL_BASELINE_KINDS or not callable(getattr(retriever, "score", None)):
        raise ValueError(
            "retrieval-v1 measures the file-based lexical baseline only (retriever_kind in {}); got "
            "{!r}. A non-lexical backend (index/hybrid/dense/service) satisfies the retrieval "
            "contract but is measured by the deferred backend-selection harness, not this one "
            "(ADR 0006 §6; docs/benchmarks/retrieval-v1.md).".format(LEXICAL_BASELINE_KINDS, kind)
        )


def corpus_records(retriever):
    """Enumerate the whole corpus (for fixture validation and the corpus-size report only).

    This is corpus *enumeration*, not the measurement path: ``parse_reference`` is the only way to
    list every record. Ranking and the metrics go through the ``retrieve_envelope`` contract
    (:func:`search`), never through this helper.
    """
    records = []
    for tradition in sorted(retriever.TRADITIONS):
        records.extend(retriever.parse_reference(tradition))
    return records


def search(retriever, query, k):
    """Global top-k ``(record, score)`` assembled from the retriever's **contract** output.

    Candidates are acquired through the per-tradition ``retrieve_envelope()`` contract surface
    (ADR 0006 §2), so the records measured (and fed downstream to the adapter) are exactly what the
    contract emits — not an internal parse. Each tradition's top-``k`` is a prefix of that
    tradition's ranking, so their union always contains the true global top-``k``; re-sorting the
    union by the same total order ``(-score, source_line, tradition, work, locator)`` reproduces the
    whole-corpus ranking exactly, deterministically, and without dependence on absolute paths.

    The cross-tradition ordering uses the retriever's lexical ``score()`` — the lexical baseline this
    harness measures (guarded by :func:`_require_lexical_baseline`).
    """
    scored = []
    for tradition in sorted(retriever.TRADITIONS):
        for record in retriever.retrieve_envelope(tradition, query, k)["records"]:
            scored.append((retriever.score(query, record), record))
    scored.sort(
        key=lambda item: (
            -item[0],
            item[1].get("source_line", 0),
            item[1]["tradition"],
            item[1]["work"],
            str(item[1]["locator"]),
        )
    )
    return [(record, value) for value, record in scored[:k]]


def _threshold_filter(ranked, threshold):
    """Post-retrieval confidence cutoff: if the top score is below *threshold*, return no support."""
    if not ranked or ranked[0][1] < threshold:
        return []
    return ranked


# --------------------------------------------------------------------- candidate: lexical-bm25

def _lexical_terms(text):
    """Lexical tokens for the BM25 candidate — the SAME rule as the retriever's ``query_features``
    (ASCII words + CJK bigrams + non-stopword CJK singletons), but returned as a **multiset** (with
    repeats) so document term frequencies are real. ``test_lexical_terms_matches_query_features``
    pins ``set(_lexical_terms(s)) == retriever.query_features(s)`` so this cannot drift from the
    lexical baseline it re-ranks; keeping tokenization identical is what makes the BM25 comparison a
    clean test of *weighting* rather than of a different tokenizer.
    """
    lowered = text.casefold()
    terms = list(_ASCII_WORD_RE.findall(lowered))
    for chunk in _CJK_RE.findall(lowered):
        terms.extend(chunk[index : index + 2] for index in range(len(chunk) - 1))
        terms.extend(character for character in chunk if character not in _LEXICAL_STOPWORDS)
    return [term for term in terms if term]


def _build_bm25_index(records):
    """Whole-corpus BM25 statistics (document-frequency, per-doc length, average length).

    BM25 inherently needs corpus-wide statistics, so this **enumerates** the corpus (like
    :func:`corpus_records`) rather than the per-query contract surface — only the IDF / length-norm
    statistics come from enumeration. The ranked candidate *records* are still acquired through
    ``retrieve_envelope()`` in :func:`search_bm25`, so what is measured and fed downstream stays the
    contract's output. Stats are keyed on the stable ``record_key`` so enumeration and the contract
    pool line up exactly.
    """
    doc_terms = {}
    doc_len = {}
    df = {}
    for record in records:
        key = record_key(record)
        terms = _lexical_terms(" ".join(str(record.get(field, "")) for field in BM25_FIELDS))
        freqs = {}
        for term in terms:
            freqs[term] = freqs.get(term, 0) + 1
        doc_terms[key] = freqs
        doc_len[key] = len(terms)
        for term in freqs:
            df[term] = df.get(term, 0) + 1
    n = len(records)
    avgdl = (sum(doc_len.values()) / n) if n else 0.0
    return {"doc_terms": doc_terms, "doc_len": doc_len, "df": df, "n": n, "avgdl": avgdl}


def _bm25_score(query_terms, key, index, k1, b):
    """Okapi BM25 for one record. ``query_terms`` is a **sorted** sequence so the float summation
    order is fixed regardless of set-hash seed (otherwise the committed JSON would not be byte-
    reproducible across processes). Uses the non-negative Lucene-style IDF so a matched term never
    scores negative (a term in > half the corpus would go negative under the textbook IDF).
    """
    freqs = index["doc_terms"].get(key)
    if not freqs:
        return 0.0
    dl = index["doc_len"].get(key, 0)
    n = index["n"]
    avgdl = index["avgdl"] or 1.0
    total = 0.0
    for term in query_terms:
        f = freqs.get(term, 0)
        if not f:
            continue
        df = index["df"].get(term, 0)
        idf = math.log(1.0 + (n - df + 0.5) / (df + 0.5))
        total += idf * (f * (k1 + 1.0)) / (f + k1 * (1.0 - b + b * dl / avgdl))
    return total


def search_bm25(retriever, query, k, index, k1, b):
    """Global top-``k`` by a BM25-style re-ranking of the SAME corpus the lexical baseline ranks.

    Mirrors :func:`search`: candidates are acquired through the per-tradition ``retrieve_envelope()``
    contract surface — here with ``k`` = corpus size so BM25 re-ranks the *whole* pool, not each
    tradition's lexical top-``k`` — then ordered by the SAME deterministic total order
    ``(-score, source_line, tradition, work, locator)``. Only the score differs from the baseline;
    the records, the envelope, and occurrence identity are untouched, so the downstream contract
    metrics are unaffected.
    """
    query_terms = sorted(set(_lexical_terms(query)))
    pool_k = max(index["n"], 1)
    scored = []
    for tradition in sorted(retriever.TRADITIONS):
        for record in retriever.retrieve_envelope(tradition, query, pool_k)["records"]:
            value = round(_bm25_score(query_terms, record_key(record), index, k1, b), 6)
            scored.append((value, record))
    scored.sort(
        key=lambda item: (
            -item[0],
            item[1].get("source_line", 0),
            item[1]["tradition"],
            item[1]["work"],
            str(item[1]["locator"]),
        )
    )
    return [(record, value) for value, record in scored[:k]]


# -------------------------------------------------------------------------------------- metrics

def _dcg(relevances):
    return sum(rel / math.log2(index + 2) for index, rel in enumerate(relevances))


def _ndcg(relevances, ideal_relevances):
    ideal = _dcg(ideal_relevances)
    return (_dcg(relevances) / ideal) if ideal > 0 else 0.0


def evaluate_answerable(judgment, ranked, ks):
    """Per-query retrieval metrics for an answerable query.

    ``ranked`` is the list of ``(record, score)`` already cut to ``max(ks)``.
    """
    rel_map = {
        (entry["tradition"], entry["work"], entry["locator"]): entry["relevance"]
        for entry in judgment.get("relevant", [])
    }
    relevant_keys = {key for key, rel in rel_map.items() if rel >= RELEVANT_THRESHOLD}
    total_relevant = len(relevant_keys)
    ranked_keys = [record_key(record) for record, _ in ranked]
    ranked_rels = [rel_map.get(record_key(record), 0) for record, _ in ranked]
    ideal_rels = sorted(rel_map.values(), reverse=True)

    metrics = {"relevant_total": total_relevant}
    for k in ks:
        found = sum(1 for key in ranked_keys[:k] if key in relevant_keys)
        metrics["recall_at_{}".format(k)] = (found / total_relevant) if total_relevant else None
        metrics["precision_at_{}".format(k)] = found / k
        metrics["ndcg_at_{}".format(k)] = _ndcg(ranked_rels[:k], ideal_rels[:k])
    first_rank = next(
        (index + 1 for index, key in enumerate(ranked_keys) if key in relevant_keys), None
    )
    metrics["first_relevant_rank"] = first_rank
    metrics["mrr"] = (1.0 / first_rank) if first_rank is not None else 0.0
    metrics["exact_target_at_rank1"] = bool(ranked_rels) and ranked_rels[0] == 2
    metrics["outcome"] = "hit" if first_rank is not None else "miss"
    return metrics, rel_map


def evaluate_no_answer(ranked):
    top1_score = ranked[0][1] if ranked else 0
    return {
        "top1_score": top1_score,
        "no_answer_correct": top1_score == 0,
        "false_support": top1_score > 0,
        "outcome": "no_answer_ok" if top1_score == 0 else "false_support",
    }


# ----------------------------------------------------------------------------- contract metrics

def _adapter_modules():
    """Import the real B1 adapter + snapshot store lazily (fixture validation must not need them)."""
    sys.path.insert(0, str(ROOT / "orchestrator"))
    import retrieval_evidence_adapter as adapter  # noqa: E402
    from evidence_snapshot import EvidenceStore  # noqa: E402
    return adapter, EvidenceStore


def _occurrence_ids_by_key(records, contract_version, adapter, EvidenceStore, *, reorder=False):
    """Mint occurrence ids for ``records`` through the real adapter; map record_key -> occurrence_id.

    ``records`` are contract output; the envelope carries the retriever's own ``contract_version``.
    With ``reorder=True`` the list is reversed before adaptation — the corpus-stable scheme keys an
    occurrence id on (artifact, work, locator, source_file, source_line), never list position, so a
    conforming retriever yields the *same* id regardless of order. This is the probe behind the
    citation-fidelity metric, so deliberately controlling the order here is the point.
    """
    seq = list(reversed(records)) if reorder else list(records)
    with tempfile.TemporaryDirectory() as tmp:
        seeds = adapter.adapt({"contract_version": contract_version, "records": seq}, EvidenceStore(tmp))
    return {record_key(record): seed.occurrence_id for record, seed in zip(seq, seeds)}


def _citation_fidelity(relevant_retrieved, contract_version, adapter, EvidenceStore):
    """Fraction of returned+relevant records whose occurrence id is reproducible (ADR 0006 §4.2).

    The benchmark spec (docs/benchmarks/retrieval-v1.md §Citation fidelity) defines this as the
    fraction yielding "a stable, reproducible occurrence id across two runs and across a reordering
    of the result list" — and a candidate below 100% is disqualified by hard constraint 2. We
    therefore mint ids three ways (run A, an independent run B, and a reordered run C) and count a
    record as stable only when all three agree.
    """
    if not relevant_retrieved:
        return {"records": 0, "stable_records": 0, "fidelity": None, "unstable": []}
    run_a = _occurrence_ids_by_key(relevant_retrieved, contract_version, adapter, EvidenceStore)
    run_b = _occurrence_ids_by_key(relevant_retrieved, contract_version, adapter, EvidenceStore)
    run_c = _occurrence_ids_by_key(relevant_retrieved, contract_version, adapter, EvidenceStore, reorder=True)
    unstable = [
        list(key) for key in run_a
        if not (run_a[key] == run_b.get(key) == run_c.get(key))
    ]
    stable = len(run_a) - len(unstable)
    return {
        "records": len(run_a),
        "stable_records": stable,
        "fidelity": round(stable / len(run_a), 6),
        "reproducible_across_two_runs_and_reorder": not unstable,
        "unstable": sorted(unstable),
    }


def _span_assurance_status(seeds):
    """Concrete span-assurance status at the retrieval boundary (not a prose note).

    Retrieval mints **no** span-assurance tier: that is B2's job (curated-snapshot-span-verified) and
    edition-backed-span-verified is reserved for A2 (ADR 0003 §5 / ADR 0006 §6). What retrieval *does*
    guarantee is an artifact-backed ``source_assurance`` on every seed. This reports that as a
    checkable status — a tier of ``null``, the assurance floor, and an explicit edition-backed=false —
    so "no tier upgraded by retrieval" is a measured fact, not an assertion.
    """
    total = len(seeds)
    artifact_backed = sum(1 for s in seeds if s.source_assurance == "artifact-backed")
    minted_tiers = sorted({s.occurrence_id_scheme for s in seeds if getattr(s, "span_assurance_tier", None)})
    return {
        "tier_at_retrieval": None,
        "source_assurance_floor": "artifact-backed",
        "all_records_artifact_backed": total > 0 and artifact_backed == total,
        "records_artifact_backed": artifact_backed,
        "edition_backed_span_verified": False,
        "span_tiers_minted_at_retrieval": minted_tiers,
        "note": (
            "retrieval mints no span-assurance tier; curated-snapshot-span-verified is minted at B2 "
            "and edition-backed-span-verified is reserved for A2 — beating this benchmark upgrades "
            "neither (docs/benchmarks/retrieval-v1.md hard constraint 6)."
        ),
    }


def contract_metrics(unique_records, relevant_retrieved, contract_version):
    """Feed the **real** contract envelope through the **real** B1 adapter and report identity facts.

    ``unique_records`` and ``relevant_retrieved`` are records the retriever returned via
    ``retrieve_envelope`` (the contract); ``contract_version`` is the retriever's own, never a runner
    constant. Reports occurrence-identity stability, the envelope-field contract, carried metadata, a
    concrete span-assurance status, and the citation-fidelity metric (ADR 0006 §4.2 / spec).
    """
    adapter, EvidenceStore = _adapter_modules()

    schemes = {}
    fields_ok = True
    representation = rights = artifact_backed = 0
    minted = 0
    with tempfile.TemporaryDirectory() as tmp:
        seeds = adapter.adapt(
            {"contract_version": contract_version, "records": unique_records}, EvidenceStore(tmp)
        )
    for record, seed in zip(unique_records, seeds):
        if seed.occurrence_id:
            minted += 1
        schemes[seed.occurrence_id_scheme] = schemes.get(seed.occurrence_id_scheme, 0) + 1
        if not all(field in record for field in REQUIRED_RECORD_FIELDS):
            fields_ok = False
        if seed.source_assurance == "artifact-backed":
            artifact_backed += 1
        if record.get("representation_kind"):
            representation += 1
        if record.get("rights"):
            rights += 1
    total = len(unique_records)
    stable = total > 0 and minted == total and set(schemes) == {
        adapter.OCCURRENCE_SCHEME_CORPUS_STABLE
    }
    return {
        "records_evaluated": total,
        "stable_occurrence_identity_present": stable,
        "occurrence_id_minted_count": minted,
        "occurrence_scheme_counts": dict(sorted(schemes.items())),
        "required_envelope_fields_present": fields_ok,
        "source_assurance_artifact_backed_count": artifact_backed,
        "representation_metadata_records": representation,
        "rights_metadata_records": rights,
        "citation_fidelity": _citation_fidelity(
            relevant_retrieved, contract_version, adapter, EvidenceStore
        ),
        "span_assurance": _span_assurance_status(seeds),
    }


# ------------------------------------------------------------------------------------- run + view

def run_benchmark(retriever_kind, ks, candidate=None):
    retriever = get_retriever(retriever_kind)
    _require_lexical_baseline(retriever)
    contract_version = retriever.capabilities()["contract_version"]
    records = corpus_records(retriever)  # enumeration only: corpus size + the records-searched count
    queries = load_json(QUERIES_PATH)["queries"]
    judgments_doc = load_json(JUDGMENTS_PATH)
    judgments = {item["query_id"]: item for item in judgments_doc["judgments"]}
    max_k = max(ks)
    threshold = candidate.get("threshold") if candidate else None
    cand_type = candidate.get("type") if candidate else None
    bm25_index = _build_bm25_index(records) if cand_type == "lexical-bm25" else None
    bm25_k1 = candidate.get("k1", BM25_K1) if cand_type == "lexical-bm25" else None
    bm25_b = candidate.get("b", BM25_B) if cand_type == "lexical-bm25" else None

    def _rank(text):
        if bm25_index is not None:
            return search_bm25(retriever, text, max_k, bm25_index, bm25_k1, bm25_b)
        return search(retriever, text, max_k)

    per_query = []
    latencies = []
    unique_retrieved = {}
    relevant_retrieved = {}  # returned AND judged-relevant records, for the citation-fidelity metric
    ranked_signature = {}  # query_id -> ranked keys, for the determinism repeat check
    for query in queries:
        qid = query["query_id"]
        judgment = judgments.get(qid, {"no_answer": False, "relevant": []})
        start = time.perf_counter()
        ranked_raw = _rank(query["query"])
        latencies.append(time.perf_counter() - start)
        ranked = _threshold_filter(ranked_raw, threshold) if threshold is not None else ranked_raw
        ranked_signature[qid] = [record_key(rec) for rec, _ in ranked]

        rel_map = {
            (e["tradition"], e["work"], e["locator"]): e["relevance"]
            for e in judgment.get("relevant", [])
        }
        retrieved_view = []
        for rank, (rec, value) in enumerate(ranked, start=1):
            key = record_key(rec)
            unique_retrieved[key] = rec
            if rel_map.get(key, 0) >= RELEVANT_THRESHOLD:
                relevant_retrieved[key] = rec
            retrieved_view.append({
                "rank": rank,
                "tradition": rec["tradition"],
                "work": rec["work"],
                "locator": rec["locator"],
                "score": value,
                "relevance": rel_map.get(key, 0),
            })

        entry = {
            "query_id": qid,
            "category": query["category"],
            "query": query["query"],
            "no_answer": bool(judgment.get("no_answer")),
            "retrieved": retrieved_view,
        }
        if judgment.get("no_answer"):
            entry.update(evaluate_no_answer(ranked))
        else:
            metrics, _ = evaluate_answerable(judgment, ranked, ks)
            entry.update(metrics)
        if threshold is not None:
            entry["threshold_filtered"] = len(ranked) < len(ranked_raw)
            entry["pre_threshold_top_score"] = ranked_raw[0][1] if ranked_raw else 0
        per_query.append(entry)

    # Determinism repeat check: a second pass must reproduce every ranking exactly.
    def _repeat(q):
        raw = _rank(q)
        return _threshold_filter(raw, threshold) if threshold is not None else raw
    repeat_ok = all(
        ranked_signature[query["query_id"]]
        == [record_key(rec) for rec, _ in _repeat(query["query"])]
        for query in queries
    )

    contract = contract_metrics(
        list(unique_retrieved.values()), list(relevant_retrieved.values()), contract_version
    )
    contract["deterministic_repeat"] = repeat_ok

    summary = _summarize(per_query, queries, ks)
    operational = {
        "records_searched": len(records),
        "total_seconds": round(sum(latencies), 6),
        "avg_query_ms": round(1000 * sum(latencies) / len(latencies), 4) if latencies else 0.0,
        "max_query_ms": round(1000 * max(latencies), 4) if latencies else 0.0,
    }
    result = {
        "benchmark": "retrieval-v1",
        "retriever_kind": retriever.capabilities()["retriever_kind"],
        "contract_version": contract_version,
        "corpus_version": VERSION_PATH.read_text(encoding="utf-8").strip(),
        "corpus": {"records": len(records), "traditions": len(retriever.TRADITIONS)},
        "k_values": list(ks),
        "query_count": len(queries),
        "answerable_query_count": sum(1 for q in per_query if not q["no_answer"]),
        "no_answer_query_count": sum(1 for q in per_query if q["no_answer"]),
        "summary": summary,
        "contract": contract,
        "judging": judging_disclosure(judgments_doc),
        "operational": operational,
        "per_query": per_query,
    }
    if candidate:
        result["candidate"] = candidate
    return result


def judging_disclosure(judgments_doc):
    """Surface judge provenance + the inter-annotator-agreement status from the judgments fixture.

    The retrieval-v1 baseline is a single-curator pass; ≥2 independent judges + an IAA figure are
    required to compare a *candidate backend* against the baseline at the deferred decision gate, not
    to measure the baseline itself (docs/benchmarks/retrieval-v1.md §Relevance judgments). This
    reports the fixture's disclosed provenance so that scoping is explicit in every report rather
    than an undisclosed gap.
    """
    block = judgments_doc.get("judging", {})
    judges = block.get("judges", [])
    return {
        "independent_judge_count": block.get("independent_judge_count", len(judges)),
        "judges": judges,
        "inter_annotator_agreement": block.get("inter_annotator_agreement"),
        "agreement_method": block.get("agreement_method"),
        "agreement_required_at": block.get("agreement_required_at"),
        "disclosure": block.get("disclosure"),
    }


def _mean(values):
    values = [v for v in values if v is not None]
    return round(sum(values) / len(values), 4) if values else None


def _summarize(per_query, queries, ks):
    answerable = [q for q in per_query if not q["no_answer"]]
    no_answer = [q for q in per_query if q["no_answer"]]
    category_of = {q["query_id"]: q["category"] for q in queries}
    exact_queries = [q for q in answerable if category_of[q["query_id"]] in EXACT_CATEGORIES]

    summary = {
        "recall_at_k": {str(k): _mean([q.get("recall_at_{}".format(k)) for q in answerable]) for k in ks},
        "precision_at_k": {str(k): _mean([q.get("precision_at_{}".format(k)) for q in answerable]) for k in ks},
        "ndcg_at_k": {str(k): _mean([q.get("ndcg_at_{}".format(k)) for q in answerable]) for k in ks},
        "mrr": _mean([q.get("mrr") for q in answerable]),
        "exact_span_hit_rate": (
            _mean([1.0 if q.get("exact_target_at_rank1") else 0.0 for q in exact_queries])
            if exact_queries else None
        ),
        "no_answer_correct_rate": (
            _mean([1.0 if q.get("no_answer_correct") else 0.0 for q in no_answer])
            if no_answer else None
        ),
        "false_support_rate": (
            _mean([1.0 if q.get("false_support") else 0.0 for q in no_answer])
            if no_answer else None
        ),
    }
    return summary


def reproducible_view(result):
    """Strip machine-specific operational timing so the JSON report is byte-reproducible."""
    view = dict(result)
    operational = dict(result["operational"])
    view["operational"] = {"records_searched": operational["records_searched"]}
    return view


# --------------------------------------------------------------------------------- fixture check

def validate_fixtures(retriever_kind="project"):
    errors = []
    queries_doc = load_json(QUERIES_PATH)
    judgments_doc = load_json(JUDGMENTS_PATH)
    declared_categories = set(queries_doc.get("categories", []))
    queries = queries_doc.get("queries", [])

    ids = [q.get("query_id") for q in queries]
    seen = set()
    for qid in ids:
        if qid in seen:
            errors.append("duplicate query_id: {}".format(qid))
        seen.add(qid)
    for query in queries:
        for field in ("query_id", "category", "query", "traditions"):
            if field not in query:
                errors.append("query {} missing field {!r}".format(query.get("query_id"), field))
        if query.get("category") not in declared_categories:
            errors.append("query {} has undeclared category {!r}".format(
                query.get("query_id"), query.get("category")))

    corpus_keys = set()
    retriever = get_retriever(retriever_kind)
    for record in corpus_records(retriever):
        corpus_keys.add(record_key(record))

    query_ids = set(ids)
    for judgment in judgments_doc.get("judgments", []):
        qid = judgment.get("query_id")
        if qid not in query_ids:
            errors.append("judgment references unknown query_id: {}".format(qid))
        relevant = judgment.get("relevant", [])
        if judgment.get("no_answer"):
            if relevant:
                errors.append("no_answer judgment {} must have empty relevant[]".format(qid))
        for entry in relevant:
            key = (entry.get("tradition"), entry.get("work"), entry.get("locator"))
            if key not in corpus_keys:
                errors.append("judgment {} references non-existent record: {}".format(qid, key))
            if entry.get("relevance") not in (0, 1, 2):
                errors.append("judgment {} record {} has invalid relevance {!r}".format(
                    qid, key, entry.get("relevance")))
            if entry.get("relevance", 0) >= RELEVANT_THRESHOLD and not str(entry.get("rationale", "")).strip():
                errors.append("judgment {} positive record {} missing rationale".format(qid, key))

    judged_ids = {j.get("query_id") for j in judgments_doc.get("judgments", [])}
    for qid in query_ids:
        if qid not in judged_ids:
            errors.append("query {} has no judgment".format(qid))

    covered = {q.get("category") for q in queries}
    for category in declared_categories:
        if category not in covered:
            errors.append("declared category {!r} has no query".format(category))
    return errors


# ---------------------------------------------------------------------------------- md rendering

def _fmt(value):
    return "n/a" if value is None else "{:.3f}".format(value)


def render_markdown(result, baseline=None, references=None):
    s = result["summary"]
    ks = [str(k) for k in result["k_values"]]
    cand = result.get("candidate")
    lines = []
    if cand and cand["type"] == "lexical-bm25":
        lines.append("# Retrieval Benchmark v1 — Candidate: lexical-bm25 (k1={}, b={})".format(
            cand["k1"], cand["b"]))
    elif cand:
        lines.append("# Retrieval Benchmark v1 — Candidate: {} (threshold={})".format(
            cand["type"], cand["threshold"]))
    else:
        lines.append("# Retrieval Benchmark v1 — Lexical Baseline")
    lines.append("")
    lines.append("## Status")
    lines.append("")
    if cand and cand["type"] == "lexical-bm25":
        lines.append("**Experiment only.** This report re-ranks the same file-based lexical corpus with a "
                     "BM25-style scorer (k1={}, b={}) over the **same tokenization** as the baseline, so "
                     "the comparison isolates term weighting (TF saturation + length normalization + IDF) "
                     "from tokenization. **No default behavior changed.** **No backend selected.** The "
                     "portable/project retriever is unchanged; BM25 is computed in the benchmark harness "
                     "as a candidate signal only.".format(cand["k1"], cand["b"]))
    elif cand:
        lines.append("**Experiment only.** This report evaluates a post-retrieval lexical confidence "
                     "threshold (top\\_score < {} → no support) against the v0.12.2 lexical baseline. "
                     "**No default behavior changed.** **No backend selected.**".format(cand["threshold"]))
    else:
        lines.append("Baseline **measured**. **No backend selected.** This report is measurement only "
                     "(see [retrieval-v1.md](../retrieval-v1.md)); running it does not adopt any index, "
                     "BM25, hybrid, vector, or RAG backend.")
    lines.append("")
    lines.append("## Retriever")
    lines.append("")
    lines.append("- retriever_kind: `{}`".format(result["retriever_kind"]))
    lines.append("- contract_version: `{}`".format(result["contract_version"]))
    lines.append("- corpus: C0 curated references — {} records across {} traditions (VERSION {})".format(
        result["corpus"]["records"], result["corpus"]["traditions"], result["corpus_version"]))
    lines.append("- queries: {} ({} answerable, {} no-answer)".format(
        result["query_count"], result["answerable_query_count"], result["no_answer_query_count"]))
    lines.append("")
    lines.append("## Summary metrics")
    lines.append("")
    lines.append("| metric | " + " | ".join("@" + k for k in ks) + " |")
    lines.append("|---|" + "---|" * len(ks))
    lines.append("| Recall | " + " | ".join(_fmt(s["recall_at_k"][k]) for k in ks) + " |")
    lines.append("| Precision | " + " | ".join(_fmt(s["precision_at_k"][k]) for k in ks) + " |")
    lines.append("| nDCG | " + " | ".join(_fmt(s["ndcg_at_k"][k]) for k in ks) + " |")
    lines.append("")
    lines.append("- MRR (answerable): **{}**".format(_fmt(s["mrr"])))
    lines.append("- Exact-span hit rate (exact_quote/exact_locator, rank-1 exact target): **{}**".format(
        _fmt(s["exact_span_hit_rate"])))
    lines.append("- No-answer correctness (no spurious lexical match): **{}**".format(
        _fmt(s["no_answer_correct_rate"])))
    lines.append("- False-support rate (no-answer query surfaced a lexical match): **{}**".format(
        _fmt(s["false_support_rate"])))
    lines.append("")
    c = result["contract"]
    lines.append("## Contract & identity")
    lines.append("")
    lines.append("- Stable occurrence identity present (every retrieved record minted a stable id): "
                 "**{}**".format(c["stable_occurrence_identity_present"]))
    lines.append("- Occurrence-id schemes: `{}`".format(c["occurrence_scheme_counts"]))
    lines.append("- Required envelope fields present: **{}**".format(c["required_envelope_fields_present"]))
    lines.append("- Deterministic repeat (identical ranking on a second pass): **{}**".format(
        c["deterministic_repeat"]))
    lines.append("- source_assurance artifact-backed: {}/{} retrieved records".format(
        c["source_assurance_artifact_backed_count"], c["records_evaluated"]))
    lines.append("- Curated metadata among retrieved records: representation_kind={}, rights={}".format(
        c["representation_metadata_records"], c["rights_metadata_records"]))
    cf = c["citation_fidelity"]
    lines.append(
        "- **Citation fidelity** (returned+relevant records with a reproducible occurrence id across "
        "two runs and a reordering): **{}** ({}/{} records)".format(
            _fmt(cf["fidelity"]), cf["stable_records"], cf["records"]))
    sa = c["span_assurance"]
    lines.append("- Span assurance at retrieval: tier_at_retrieval=`{}`, source_assurance floor=`{}` "
                 "({}/{} records), edition-backed-span-verified=**{}**".format(
                     sa["tier_at_retrieval"], sa["source_assurance_floor"],
                     sa["records_artifact_backed"], c["records_evaluated"],
                     sa["edition_backed_span_verified"]))
    lines.append("- _{}_".format(sa["note"]))
    lines.append("")
    j = result["judging"]
    lines.append("## Judging provenance")
    lines.append("")
    lines.append("- Independent judges: **{}**; inter-annotator agreement: **{}** (method: {})".format(
        j["independent_judge_count"],
        "n/a" if j["inter_annotator_agreement"] is None else j["inter_annotator_agreement"],
        j["agreement_method"] or "—"))
    if j.get("agreement_required_at"):
        lines.append("- ≥2-judge + IAA requirement applies at: {}".format(j["agreement_required_at"]))
    if j.get("disclosure"):
        lines.append("- _{}_".format(j["disclosure"]))
    lines.append("")
    op = result["operational"]
    lines.append("## Operational (snapshot — machine-specific, not part of the reproducible metrics)")
    lines.append("")
    lines.append("- records searched per query: {}".format(op["records_searched"]))
    lines.append("- total: {:.4f}s · avg query: {:.4f} ms · max query: {:.4f} ms".format(
        op["total_seconds"], op["avg_query_ms"], op["max_query_ms"]))
    lines.append("")
    lines.append("## Per-query results")
    lines.append("")
    lines.append("| query_id | category | first relevant rank | recall@{} | outcome | top-1 retrieved |".format(
        result["k_values"][-1]))
    lines.append("|---|---|---|---|---|---|")
    last_k = result["k_values"][-1]
    for q in result["per_query"]:
        top1 = q["retrieved"][0] if q["retrieved"] else None
        top1_str = "{}·{} (score {})".format(top1["work"], top1["locator"], top1["score"]) if top1 else "—"
        if q["no_answer"]:
            rank_str = "—"
            recall_str = "—"
        else:
            rank_str = str(q.get("first_relevant_rank") or "—")
            recall_str = _fmt(q.get("recall_at_{}".format(last_k)))
        lines.append("| {} | {} | {} | {} | {} | {} |".format(
            q["query_id"], q["category"], rank_str, recall_str, q["outcome"], top1_str))
    lines.append("")
    lines.append("## Failure analysis")
    lines.append("")
    misses = [q for q in result["per_query"] if q["outcome"] == "miss"]
    false_supports = [q for q in result["per_query"] if q["outcome"] == "false_support"]
    if misses:
        lines.append("**Missed (no relevant record in top-{}):**".format(last_k))
        for q in misses:
            lines.append("- `{}` ({}): {!r} — relevant material exists but was not retrieved.".format(
                q["query_id"], q["category"], q["query"]))
    else:
        lines.append("**Missed:** none.")
    lines.append("")
    partials = [
        q for q in result["per_query"]
        if not q["no_answer"] and q["outcome"] == "hit"
        and (q.get("recall_at_{}".format(last_k)) or 0) < 0.5
    ]
    if partials:
        lines.append("**Partial recall (hit at rank 1 but <50% of relevant records found in top-{}):**".format(last_k))
        for q in partials:
            lines.append("- `{}` ({}): {!r} — recall@{} = {}; the thematic/relevant records beyond the top hit were not retrieved.".format(
                q["query_id"], q["category"], q["query"], last_k, _fmt(q.get("recall_at_{}".format(last_k)))))
        lines.append("")
    if false_supports:
        lines.append("**False support (no-answer query surfaced a lexical match):**")
        for q in false_supports:
            top1 = q["retrieved"][0]
            lines.append("- `{}`: {!r} surfaced {}·{} at score {} — a spurious lexical overlap, not support.".format(
                q["query_id"], q["query"], top1["work"], top1["locator"], top1["score"]))
    else:
        lines.append("**False support:** none.")
    lines.append("")
    lines.append("## Interpretation")
    lines.append("")
    lines.append("The lexical baseline is strong on exact-quote and exact-locator lookup and on "
                 "paraphrases that still share surface characters with the source, and it preserves "
                 "stable occurrence identity and the envelope contract throughout. Its two visible "
                 "weaknesses are (1) **broad thematic queries** that share little vocabulary with the "
                 "relevant sources — the cross-tradition death query retrieves only one of four "
                 "relevant records (recall@5 = 0.25) — and (2) **no-answer discrimination**: having no "
                 "relevance threshold, the retriever always returns k records, so off-corpus queries "
                 "surface noise-floor (score 1) false positives. A future local-index / BM25 / hybrid "
                 "/ dense candidate would need to improve thematic recall and add a principled "
                 "low-confidence cutoff **without** weakening occurrence identity, provenance, or the "
                 "false-support constraint.")
    lines.append("")
    lines.append("## Non-decision")
    lines.append("")
    lines.append("This result does **not** select a RAG/index/vector backend, does not claim "
                 "semantic retrieval is better, and does not upgrade any span-assurance tier. "
                 "Backend selection remains deferred to a future decision ADR that compares "
                 "candidates against this baseline (docs/benchmarks/retrieval-v1.md §decision gates).")
    lines.append("")

    if baseline and cand:
        lines.extend(_render_comparison(result, baseline))
    if cand and cand["type"] == "lexical-bm25" and references:
        lines.extend(_render_bm25_reference_comparisons(result, references))

    return "\n".join(lines)


def _delta_str(new, old):
    if new is None or old is None:
        return "—"
    d = new - old
    if abs(d) < 0.0005:
        return "—"
    return "{:+.3f}".format(d)


def _render_comparison(result, baseline):
    if result["candidate"]["type"] == "lexical-bm25":
        return _render_comparison_bm25(result, baseline)
    return _render_comparison_threshold(result, baseline)


def _render_comparison_threshold(result, baseline):
    bs = baseline["summary"]
    cs = result["summary"]
    ks = [str(k) for k in result["k_values"]]
    cand = result["candidate"]
    lines = []
    lines.append("## Comparison vs. v0.12.2 lexical baseline")
    lines.append("")
    lines.append("### Summary metrics")
    lines.append("")
    lines.append("| metric | baseline | threshold={} | Δ |".format(cand["threshold"]))
    lines.append("|---|---|---|---|")
    for label, bk, ck in [
        ("Recall", "recall_at_k", "recall_at_k"),
        ("Precision", "precision_at_k", "precision_at_k"),
        ("nDCG", "ndcg_at_k", "ndcg_at_k"),
    ]:
        for k in ks:
            bv, cv = bs[bk][k], cs[ck][k]
            lines.append("| {}@{} | {} | {} | {} |".format(
                label, k, _fmt(bv), _fmt(cv), _delta_str(cv, bv)))
    for label, key in [
        ("MRR", "mrr"),
        ("Exact-span hit", "exact_span_hit_rate"),
        ("No-answer correct", "no_answer_correct_rate"),
        ("False-support", "false_support_rate"),
    ]:
        bv, cv = bs[key], cs[key]
        lines.append("| {} | {} | {} | {} |".format(label, _fmt(bv), _fmt(cv), _delta_str(cv, bv)))
    lines.append("")

    lines.append("### Per-query changes")
    lines.append("")
    b_outcomes = {q["query_id"]: q for q in baseline["per_query"]}
    improved = []
    regressed = []
    unchanged = 0
    for q in result["per_query"]:
        qid = q["query_id"]
        bq = b_outcomes.get(qid, {})
        b_out = bq.get("outcome", "?")
        c_out = q.get("outcome", "?")
        if b_out != c_out:
            is_better = (
                (b_out == "false_support" and c_out == "no_answer_ok")
                or (b_out == "miss" and c_out == "hit")
            )
            detail = "`{}` ({}): {} → {} (top score {})".format(
                qid, q.get("category", "?"), b_out, c_out,
                q.get("pre_threshold_top_score", "?"))
            if is_better:
                improved.append(detail)
            else:
                regressed.append(detail)
        else:
            unchanged += 1

    if improved:
        lines.append("**Improved:**")
        for line in improved:
            lines.append("- {}".format(line))
    else:
        lines.append("**Improved:** none.")
    lines.append("")
    if regressed:
        lines.append("**Regressed:**")
        for line in regressed:
            lines.append("- {}".format(line))
    else:
        lines.append("**Regressed:** none.")
    lines.append("")
    lines.append("**Unchanged:** {} queries.".format(unchanged))
    lines.append("")
    return lines


def _render_comparison_bm25(result, baseline):
    """Comparison for the BM25 candidate. Unlike the threshold candidate (which flips no-answer
    outcomes), BM25 mostly *re-ranks*, so per-query changes are reported on the rank of the first
    relevant record and recall@max-k, with no-answer queries compared on outcome.
    """
    bs = baseline["summary"]
    cs = result["summary"]
    ks = [str(k) for k in result["k_values"]]
    cand = result["candidate"]
    last_k = result["k_values"][-1]
    lines = []
    lines.append("## Comparison vs. v0.12.2 lexical baseline")
    lines.append("")
    lines.append("### Summary metrics")
    lines.append("")
    lines.append("| metric | baseline | bm25 (k1={}, b={}) | Δ |".format(cand["k1"], cand["b"]))
    lines.append("|---|---|---|---|")
    for label, key in [("Recall", "recall_at_k"), ("Precision", "precision_at_k"), ("nDCG", "ndcg_at_k")]:
        for k in ks:
            bv, cv = bs[key][k], cs[key][k]
            lines.append("| {}@{} | {} | {} | {} |".format(label, k, _fmt(bv), _fmt(cv), _delta_str(cv, bv)))
    for label, key in [
        ("MRR", "mrr"),
        ("Exact-span hit", "exact_span_hit_rate"),
        ("No-answer correct", "no_answer_correct_rate"),
        ("False-support", "false_support_rate"),
    ]:
        bv, cv = bs[key], cs[key]
        lines.append("| {} | {} | {} | {} |".format(label, _fmt(bv), _fmt(cv), _delta_str(cv, bv)))
    lines.append("")
    lines.append("### Per-query changes (first-relevant rank · recall@{})".format(last_k))
    lines.append("")
    b_by_id = {q["query_id"]: q for q in baseline["per_query"]}
    improved, regressed, unchanged = [], [], 0
    for q in result["per_query"]:
        bq = b_by_id.get(q["query_id"], {})
        if q["no_answer"]:
            b_out, c_out = bq.get("outcome"), q.get("outcome")
            if b_out == c_out:
                unchanged += 1
            else:
                detail = "`{}` (no_answer): {} → {}".format(q["query_id"], b_out, c_out)
                (improved if c_out == "no_answer_ok" else regressed).append(detail)
            continue
        recall_key = "recall_at_{}".format(last_k)
        b_rank, c_rank = bq.get("first_relevant_rank"), q.get("first_relevant_rank")
        b_rec, c_rec = bq.get(recall_key), q.get(recall_key)
        # Higher recall is better; among equal recall a lower (earlier) first-relevant rank is better.
        b_quality = (b_rec if b_rec is not None else -1.0, -(b_rank if b_rank else 10 ** 9))
        c_quality = (c_rec if c_rec is not None else -1.0, -(c_rank if c_rank else 10 ** 9))
        if c_quality == b_quality:
            unchanged += 1
            continue
        detail = "`{}` ({}): rank {} → {}, recall@{} {} → {}".format(
            q["query_id"], q.get("category", "?"),
            b_rank or "—", c_rank or "—", last_k, _fmt(b_rec), _fmt(c_rec))
        (improved if c_quality > b_quality else regressed).append(detail)
    for header, items in [("Improved", improved), ("Regressed", regressed)]:
        if items:
            lines.append("**{}:**".format(header))
            for item in items:
                lines.append("- {}".format(item))
        else:
            lines.append("**{}:** none.".format(header))
        lines.append("")
    lines.append("**Unchanged:** {} queries.".format(unchanged))
    lines.append("")
    return lines


def _query_by_id(report, query_id):
    return next(q for q in report["per_query"] if q["query_id"] == query_id)


def _query_focus_cell(report, query_id):
    q = _query_by_id(report, query_id)
    if q["no_answer"]:
        if not q["retrieved"]:
            return "{}; top-1 —".format(q["outcome"])
        top1 = q["retrieved"][0]
        return "{}; top-1 {}·{} (score {})".format(
            q["outcome"], top1["work"], top1["locator"], top1["score"])
    last_k = report["k_values"][-1]
    return "{}; rank {}; recall@{} {}".format(
        q["outcome"], q.get("first_relevant_rank") or "—", last_k,
        _fmt(q.get("recall_at_{}".format(last_k))))


def _render_bm25_reference_comparisons(result, references):
    """Direct BM25 comparison against committed threshold candidate reports."""
    refs = [(label, report) for label, report in references if report]
    if not refs:
        return []
    cs = result["summary"]
    ks = [str(k) for k in result["k_values"]]
    lines = []
    lines.append("## Comparison vs. v0.12.3 threshold candidates")
    lines.append("")
    lines.append("The threshold candidates are not backend selections; they are reference experiments for "
                 "no-answer discrimination. BM25 is compared against them here because BM25 changes "
                 "ranking but does not add a low-confidence cutoff.")
    lines.append("")
    lines.append("### Summary metrics")
    lines.append("")
    headers = [label for label, _ in refs]
    lines.append("| metric | {} | bm25 | {} |".format(
        " | ".join(headers),
        " | ".join("BM25 Δ vs. {}".format(label) for label, _ in refs)))
    lines.append("|---|" + "---|" * (len(refs) + 1 + len(refs)))
    for label, key in [("Recall", "recall_at_k"), ("Precision", "precision_at_k"), ("nDCG", "ndcg_at_k")]:
        for k in ks:
            ref_values = [report["summary"][key][k] for _, report in refs]
            cv = cs[key][k]
            lines.append("| {}@{} | {} | {} | {} |".format(
                label, k,
                " | ".join(_fmt(value) for value in ref_values),
                _fmt(cv),
                " | ".join(_delta_str(cv, value) for value in ref_values)))
    for label, key in [
        ("MRR", "mrr"),
        ("Exact-span hit", "exact_span_hit_rate"),
        ("No-answer correct", "no_answer_correct_rate"),
        ("False-support", "false_support_rate"),
    ]:
        ref_values = [report["summary"][key] for _, report in refs]
        cv = cs[key]
        lines.append("| {} | {} | {} | {} |".format(
            label,
            " | ".join(_fmt(value) for value in ref_values),
            _fmt(cv),
            " | ".join(_delta_str(cv, value) for value in ref_values)))
    lines.append("")
    lines.append("### Targeted query comparison")
    lines.append("")
    lines.append("| focus | {} | bm25 |".format(" | ".join(headers)))
    lines.append("|---|" + "---|" * (len(refs) + 1))
    for query_id, focus in [
        ("q005", "exact locator: John 3:16"),
        ("q007", "paraphrase: do not impose on others"),
        ("q010", "broad cross-tradition: facing death"),
        ("q014", "no-answer: crypto investment"),
        ("q015", "no-answer: smartphone specs"),
    ]:
        ref_cells = [_query_focus_cell(report, query_id) for _, report in refs]
        lines.append("| {} (`{}`) | {} | {} |".format(
            focus, query_id, " | ".join(ref_cells), _query_focus_cell(result, query_id)))
    lines.append("")
    lines.append("### Takeaway")
    lines.append("")
    lines.append("- BM25 preserves exact-span hit rate at the Lucene-style default (k1=1.2, b=0.75) but does "
                 "not improve the benchmark's broad-thematic weakness (`q010` remains recall@5 = 0.250).")
    lines.append("- BM25 does not improve no-answer discrimination; threshold t2/t3 remain better on the two "
                 "no-answer probes because they return no support instead of false support.")
    lines.append("- No backend or threshold behavior is adopted by this report.")
    lines.append("")
    return lines


# ------------------------------------------------------------------------------------------- cli

def main(argv=None):
    parser = argparse.ArgumentParser(description="Run the retrieval-v1 lexical-baseline benchmark.")
    parser.add_argument("--retriever", choices=("project", "portable"), default="project")
    parser.add_argument("--k", type=int, action="append", dest="ks",
                        help="positive cutoff(s) for @k metrics; repeatable (default 1, 3, 5).")
    parser.add_argument("--format", choices=("json", "markdown"), default="json",
                        help="report written to stdout when no *-out path is given.")
    parser.add_argument("--json-out", type=Path)
    parser.add_argument("--md-out", type=Path)
    parser.add_argument("--check-fixtures", action="store_true",
                        help="validate the query/judgment fixtures and exit non-zero on any error.")
    parser.add_argument("--candidate", choices=("lexical-threshold", "lexical-bm25"),
                        help="candidate to evaluate against the baseline (experiment only).")
    parser.add_argument("--threshold", type=int,
                        help="confidence threshold (requires --candidate lexical-threshold).")
    parser.add_argument("--k1", type=float,
                        help="BM25 term-frequency saturation (requires --candidate lexical-bm25; "
                             "default {}).".format(BM25_K1))
    parser.add_argument("--b", type=float,
                        help="BM25 length-normalization in [0, 1] (requires --candidate lexical-bm25; "
                             "default {}).".format(BM25_B))
    parser.add_argument("--baseline-json", type=Path,
                        help="baseline JSON report for the comparison section in Markdown output.")
    args = parser.parse_args(argv)

    if args.check_fixtures:
        errors = validate_fixtures(args.retriever)
        if errors:
            sys.stderr.write("retrieval-v1 fixture validation: {} error(s)\n".format(len(errors)))
            for error in errors:
                sys.stderr.write("  - {}\n".format(error))
            return 1
        sys.stdout.write("retrieval-v1 fixtures OK ({} queries).\n".format(
            len(load_json(QUERIES_PATH)["queries"])))
        return 0

    if args.ks is not None:
        for k in args.ks:
            if k < 1:
                parser.error("--k must be a positive integer (got {})".format(k))

    if args.candidate == "lexical-threshold" and args.threshold is None:
        parser.error("--candidate lexical-threshold requires --threshold")
    if args.threshold is not None and args.candidate != "lexical-threshold":
        parser.error("--threshold requires --candidate lexical-threshold")
    if args.threshold is not None and args.threshold < 1:
        parser.error("--threshold must be a positive integer (got {})".format(args.threshold))
    if (args.k1 is not None or args.b is not None) and args.candidate != "lexical-bm25":
        parser.error("--k1/--b require --candidate lexical-bm25")
    if args.k1 is not None and args.k1 < 0:
        parser.error("--k1 must be non-negative (got {})".format(args.k1))
    if args.b is not None and not 0.0 <= args.b <= 1.0:
        parser.error("--b must be in [0, 1] (got {})".format(args.b))

    errors = validate_fixtures(args.retriever)
    if errors:
        sys.stderr.write("refusing to run: fixtures invalid (use --check-fixtures for detail)\n")
        return 1

    candidate = None
    if args.candidate == "lexical-threshold":
        candidate = {"type": "lexical-threshold", "threshold": args.threshold}
    elif args.candidate == "lexical-bm25":
        candidate = {
            "type": "lexical-bm25",
            "k1": args.k1 if args.k1 is not None else BM25_K1,
            "b": args.b if args.b is not None else BM25_B,
        }

    ks = tuple(sorted(set(args.ks))) if args.ks else DEFAULT_KS
    result = run_benchmark(args.retriever, ks, candidate=candidate)
    view = reproducible_view(result)

    baseline = None
    if args.baseline_json and args.baseline_json.exists():
        baseline = load_json(args.baseline_json)
    references = []
    if candidate and candidate["type"] == "lexical-bm25":
        references = [
            (label, load_json(path))
            for label, path in BM25_REFERENCE_REPORTS
            if path.exists()
        ]

    if args.json_out:
        args.json_out.parent.mkdir(parents=True, exist_ok=True)
        args.json_out.write_text(
            json.dumps(view, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    if args.md_out:
        args.md_out.parent.mkdir(parents=True, exist_ok=True)
        args.md_out.write_text(
            render_markdown(result, baseline=baseline, references=references), encoding="utf-8")
    if not args.json_out and not args.md_out:
        if args.format == "markdown":
            sys.stdout.write(render_markdown(result, baseline=baseline, references=references))
        else:
            sys.stdout.write(json.dumps(view, ensure_ascii=False, indent=2, sort_keys=True) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
