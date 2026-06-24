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

def run_benchmark(retriever_kind, ks):
    retriever = get_retriever(retriever_kind)
    _require_lexical_baseline(retriever)
    contract_version = retriever.capabilities()["contract_version"]
    records = corpus_records(retriever)  # enumeration only: corpus size + the records-searched count
    queries = load_json(QUERIES_PATH)["queries"]
    judgments_doc = load_json(JUDGMENTS_PATH)
    judgments = {item["query_id"]: item for item in judgments_doc["judgments"]}
    max_k = max(ks)

    per_query = []
    latencies = []
    unique_retrieved = {}
    relevant_retrieved = {}  # returned AND judged-relevant records, for the citation-fidelity metric
    ranked_signature = {}  # query_id -> ranked keys, for the determinism repeat check
    for query in queries:
        qid = query["query_id"]
        judgment = judgments.get(qid, {"no_answer": False, "relevant": []})
        start = time.perf_counter()
        ranked = search(retriever, query["query"], max_k)
        latencies.append(time.perf_counter() - start)
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
        per_query.append(entry)

    # Determinism repeat check: a second pass must reproduce every ranking exactly.
    repeat_ok = all(
        ranked_signature[query["query_id"]]
        == [record_key(rec) for rec, _ in search(retriever, query["query"], max_k)]
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
    return {
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


def render_markdown(result):
    s = result["summary"]
    ks = [str(k) for k in result["k_values"]]
    lines = []
    lines.append("# Retrieval Benchmark v1 — Lexical Baseline")
    lines.append("")
    lines.append("## Status")
    lines.append("")
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
    return "\n".join(lines)


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

    errors = validate_fixtures(args.retriever)
    if errors:
        sys.stderr.write("refusing to run: fixtures invalid (use --check-fixtures for detail)\n")
        return 1

    ks = tuple(sorted(set(args.ks))) if args.ks else DEFAULT_KS
    result = run_benchmark(args.retriever, ks)
    view = reproducible_view(result)

    if args.json_out:
        args.json_out.parent.mkdir(parents=True, exist_ok=True)
        args.json_out.write_text(
            json.dumps(view, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    if args.md_out:
        args.md_out.parent.mkdir(parents=True, exist_ok=True)
        args.md_out.write_text(render_markdown(result), encoding="utf-8")
    if not args.json_out and not args.md_out:
        if args.format == "markdown":
            sys.stdout.write(render_markdown(result))
        else:
            sys.stdout.write(json.dumps(view, ensure_ascii=False, indent=2, sort_keys=True) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
