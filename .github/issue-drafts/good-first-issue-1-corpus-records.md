---
title: "Add corpus records for an underrepresented teaching"
labels: ["good first issue", "corpus"]
---

## Context

Each tradition currently has exactly 7 curated records. The retrieval benchmark (v0.12.2) showed that **broad thematic queries** — like "how should one face death" — retrieve only 1 of 4 relevant records at recall@5, partly because the corpus is small.

Adding a well-sourced record to a tradition directly improves benchmark coverage.

## What to do

1. Pick a tradition and a teaching that is **missing** from its `references/<tradition>.md`.
2. Find a **public-domain** source text (original language preferred; mark translations as renderings).
3. Add the record to **both** `skills/religion-council/references/<tradition>.md` and `.claude/skills/religion-council/references/<tradition>.md` (they must stay byte-identical except for the two documented differences — see [CONTRIBUTING.md](../../CONTRIBUTING.md)).
4. Add a `presentation.json` entry with `provenance` and `rights` fields.
5. Run `python3 scripts/corpus_inventory.py --check` and `python3 -m unittest discover -s tests -v` to verify.

## Suggestions (pick one or propose your own)

- **Buddhism:** a Zen/Chan koan or a Theravāda sutta on mindfulness
- **Christianity:** a Psalms excerpt on suffering or praise
- **Islam:** a Qur'an verse on justice (e.g. 4:135) — mark the Chinese as a meaning-rendering
- **Confucianism:** a 大學 or 中庸 excerpt
- **Hinduism:** a Bhagavad Gita verse on dharma beyond the existing karma-yoga cluster
- **Taoism:** a Zhuangzi passage (莊子) — currently all records are from 道德經

## Rights requirement

Every new record must have a per-snippet `rights` note in `presentation.json`. The project asserts public-domain basis by age/edition but does **not** independently audit it — that defers to the A2 redistribution review. See [CORPUS.md](../../docs/CORPUS.md).
