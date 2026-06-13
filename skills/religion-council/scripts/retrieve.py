#!/usr/bin/env python3
"""File-based retrieval for the curated Religion Council references.

This Phase 0 retriever parses cited bullets from a tradition reference file,
ranks them lexically, and returns the stable metadata records expected by
future local-vector and service-backed implementations.
"""

import argparse
import json
from pathlib import Path
import re
import sys


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
        records.append(
            {
                "text": text,
                "tradition": tradition,
                "school": school,
                "work": match.group("work").strip(),
                "locator": locator or "reference file entry",
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
        )
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


def main():
    parser = argparse.ArgumentParser(description="Religion Council lexical retrieval")
    parser.add_argument("--tradition", required=True, choices=sorted(TRADITIONS))
    parser.add_argument("--query", required=True)
    parser.add_argument("--k", type=int, default=5)
    args = parser.parse_args()
    try:
        result = retrieve(args.tradition, args.query, args.k)
    except ValueError as exc:
        parser.error(str(exc))
    json.dump(result, sys.stdout, ensure_ascii=False, indent=2)
    sys.stdout.write("\n")


if __name__ == "__main__":
    main()
