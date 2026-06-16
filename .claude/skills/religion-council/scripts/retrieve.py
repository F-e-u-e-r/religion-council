#!/usr/bin/env python3
"""File-based retrieval for the curated Worldview Council references.

This A0 retriever parses cited bullets from a tradition reference file,
ranks them lexically, and returns the stable metadata records expected by
future local-vector and service-backed implementations.
"""

import argparse
import json
import re
import sys
from pathlib import Path

# Envelope-level contract version for retrieve_envelope(). This is the API/shape
# contract that the B1 evidence adapter negotiates on, distinct from each record's
# "version" field (which is the source edition, e.g. "通行本").
RETRIEVAL_CONTRACT_VERSION = "religion-council/retrieval/v1"

# Backend capability metadata (ADR 0006 §3). This portable retriever is file-based and
# standard-library only: it acquires no bytes over the network and emits stable file-based
# occurrence-identity inputs (source_file + source_line) on every record, so it reports stable
# identity and NO network acquisition. The "project" retriever may later report a richer kind
# (project-index / project-service) without changing RETRIEVAL_CONTRACT_VERSION.
RETRIEVER_KIND = "portable-file"

TRADITIONS = {
    "christianity": {
        "file": "01-基督宗教.md",
        "category": "宗教經典",
        "school": "基督宗教",
    },
    "islam": {
        "file": "02-伊斯蘭教.md",
        "category": "宗教經典",
        "school": "伊斯蘭教",
    },
    "hinduism": {
        "file": "03-印度教.md",
        "category": "宗教經典",
        "school": "印度教",
    },
    "buddhism": {
        "file": "04-佛教.md",
        "category": "宗教經典",
        "school": "佛教",
    },
    "taoism": {
        "file": "05-道教.md",
        "category": "宗教經典",
        "school": "道家/道教",
    },
    "legalism": {
        "file": "06-法家.md",
        "category": "哲學思想著作",
        "school": "法家",
    },
    "confucianism": {
        "file": "07-儒家.md",
        "category": "哲學思想著作",
        "school": "儒家",
    },
    "mohism": {
        "file": "08-墨家.md",
        "category": "哲學思想著作",
        "school": "墨家",
    },
}

SCHOOL_MARKERS = {
    "christianity": ("天主教", "東正教", "新教", "改革宗", "路德宗", "聖公會"),
    "islam": ("遜尼", "什葉", "蘇非"),
    "hinduism": ("不二論", "勝義限定不二論", "二元論"),
    "buddhism": ("南傳", "漢傳", "藏傳", "上座部", "大乘", "中觀", "唯識", "淨土"),
    "taoism": ("道家", "道教", "全真", "正一"),
    "legalism": ("法家",),
    "confucianism": ("儒家",),
    "mohism": ("墨家",),
}

REFERENCES_DIR = Path(__file__).resolve().parent.parent / "references"
ENTRY_RE = re.compile(
    r"^- 〔(?P<topic>[^〕]+)〕(?P<text>.+?)——《(?P<work>[^》]+)》(?P<locator>.*)$"
)
ASCII_WORD_RE = re.compile(r"[a-z0-9]+")
CJK_RE = re.compile(r"[\u3400-\u9fff]+")

# A1: optional curated presentation/provenance sidecar. It merges per-record presentation
# dimensions (representation_kind / rendering_mode), provenance / rights, and the ADR 0008
# corpus-versioning fields (version / witness_kind / canon_scope / textual_witness /
# commentarial_lineage / corpus_family) onto matching records by (tradition, work, locator).
# These are curator-declared, carried-not-trusted
# metadata: nothing is inferred. An absent, unparseable, or structurally-invalid sidecar
# leaves retrieval unchanged, and a field whose value has the wrong type is dropped at merge
# (pure-stdlib type-checking; the policy enum-membership check lives in the test suite, since
# this portable retriever must not import the orchestrator's policy_enums).
PRESENTATION_FILE = REFERENCES_DIR / "presentation.json"
PRESENTATION_FIELD_TYPES = {
    "representation_kind": str,
    "rendering_mode": str,
    "provenance": dict,
    "rights": str,
    # ADR 0008 corpus-versioning: classify the textual witness / canon. Enum-checked in the test
    # suite (never at merge — this portable retriever only type-checks, carried-not-trusted). The
    # source edition is carried by the base `version` field, overridden per-record in the merge below
    # (deliberately NOT listed here, so it stays present on every record, curated or not).
    "witness_kind": str,
    "canon_scope": str,
    "textual_witness": str,
    "commentarial_lineage": str,
    "corpus_family": str,
    # ADR 0004 renderer boundary: an interpretation-only classification flag for a cross-locus
    # thematic cue / paraphrase that is NOT a source-bound quotation (e.g. a《古蘭經》theme cited at
    # 多處/multiple loci). Carried-not-trusted and type-checked only here; the orchestrator honors it
    # so the record can never mint a Surface-A [Text] authority unit (routed to Surface B).
    "interpretation_only": bool,
}
PRESENTATION_FIELDS = tuple(PRESENTATION_FIELD_TYPES)


def _load_presentation():
    try:
        with PRESENTATION_FILE.open(encoding="utf-8") as handle:
            data = json.load(handle)
    except (OSError, ValueError):
        return {}
    index = {}
    if isinstance(data, dict):
        for tradition, entries in data.items():
            if not isinstance(entries, list):
                continue  # skip the "_note" string and any malformed section
            for entry in entries:
                if isinstance(entry, dict):
                    index[(tradition, entry.get("work"), entry.get("locator"))] = entry
    return index


PRESENTATION = _load_presentation()


def normalize(value):
    return re.sub(r"\s+", "", value.casefold())


def query_features(query):
    lowered = query.casefold()
    features = set(ASCII_WORD_RE.findall(lowered))
    for chunk in CJK_RE.findall(query):
        features.update(chunk[index : index + 2] for index in range(len(chunk) - 1))
        features.update(character for character in chunk if character not in "的了與和是")
    return {value for value in features if value}


def score(query, record):
    haystack = normalize(
        " ".join(
            [
                record["topic"],
                record["text"],
                record["work"],
                record["locator"],
                record["school"],
            ]
        )
    )
    normalized_query = normalize(query)
    value = 10 if normalized_query and normalized_query in haystack else 0
    for feature in query_features(query):
        if normalize(feature) in haystack:
            value += 2 if len(feature) > 1 else 1
    return value


def extract_school(tradition, locator, default):
    matches = [
        (locator.find(marker), -len(marker), marker)
        for marker in SCHOOL_MARKERS.get(tradition, ())
        if marker in locator
    ]
    return min(matches)[2] if matches else default


def parse_reference(tradition):
    config = TRADITIONS.get(tradition)
    if config is None:
        raise ValueError(
            "unknown tradition: {}; valid values: {}".format(
                tradition, ", ".join(sorted(TRADITIONS))
            )
        )
    path = REFERENCES_DIR / config["file"]
    records = []
    for line_number, line in enumerate(
        path.read_text(encoding="utf-8").splitlines(), start=1
    ):
        match = ENTRY_RE.match(line.strip())
        if not match:
            continue
        raw_text = match.group("text").strip()
        quoted = raw_text.startswith("「") and raw_text.endswith("」")
        text = raw_text[1:-1] if quoted else raw_text
        locator = match.group("locator").strip()
        school = extract_school(tradition, locator, config["school"])
        work = match.group("work").strip()
        resolved_locator = locator or "reference file entry"
        record = {
            "text": text,
            "tradition": tradition,
            "school": school,
            "work": work,
            "locator": resolved_locator,
            "language": "zh-Hant",
            "version": "curated-reference-v0.1",
            "category": config["category"],
            "label": "Text",
            "evidence_type": "quotation" if quoted else "source-bound-summary",
            "verbatim": quoted,
            "topic": match.group("topic").strip(),
            "source_file": str(path),
            "source_line": line_number,
        }
        # A1: merge curated presentation/provenance for this exact (work, locator), if any.
        # Only carry a field whose value has the expected type; a wrong-typed value is dropped
        # so a malformed sidecar cannot inject garbage into the contract.
        curation = PRESENTATION.get((tradition, work, resolved_locator))
        if curation:
            # `version` is the source edition (ADR 0006/0008): a curated string overrides the
            # placeholder default on this record; the field stays present on every record either way.
            sidecar_version = curation.get("version")
            if isinstance(sidecar_version, str) and sidecar_version:
                record["version"] = sidecar_version
            for field, expected_type in PRESENTATION_FIELD_TYPES.items():
                value = curation.get(field)
                if isinstance(value, expected_type):
                    record[field] = value
        records.append(record)
    return records


def retrieve(tradition, query, k=5):
    if k < 1:
        raise ValueError("k must be at least 1")
    records = parse_reference(tradition)
    ranked = sorted(
        records,
        key=lambda record: (-score(query, record), record["source_line"]),
    )
    return ranked[:k]


def retrieve_envelope(tradition, query, k=5):
    """Versioned envelope around retrieve() for the B1 evidence adapter.

    The retrieval-to-evidence adapter and any future networked retrieval service
    consume this envelope and trust only its contract_version for shape
    negotiation. The bare retrieve() list return is unchanged for legacy callers.

    Each record's "text" is the canonical bytes the adapter content-addresses into
    an immutable snapshot, so artifact identity needs no source_file and survives the
    A3 network backend. The canonical form is sha256(UTF-8(NFC(text))) with newlines
    normalized to LF and spans as byte offsets, so every backend hashes identically
    (see docs/adr/0003-retrieval-evidence-adapter.md).
    """
    return {
        "contract_version": RETRIEVAL_CONTRACT_VERSION,
        "records": retrieve(tradition, query, k),
    }


def capabilities():
    """Declared backend capability metadata (ADR 0006 §3); checkable without retrieving.

    The portable retriever is file-based and stdlib-only, so it supports stable occurrence
    identity (corpus-stable inputs on every record) and does NOT acquire bytes over the network.
    The invariant ``supports_network_acquisition`` implies ``supports_stable_occurrence_identity``
    holds trivially here (False implies anything). ``contract_version`` mirrors the envelope's.
    """
    return {
        "retriever_kind": RETRIEVER_KIND,
        "contract_version": RETRIEVAL_CONTRACT_VERSION,
        "supports_stable_occurrence_identity": True,
        "supports_network_acquisition": False,
    }


def main():
    parser = argparse.ArgumentParser(description="Worldview Council lexical retrieval")
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
