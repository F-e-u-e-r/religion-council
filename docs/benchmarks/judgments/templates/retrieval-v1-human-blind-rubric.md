# retrieval-v1 — human blind judge rubric & instructions

This package lets a **human** judge add an independent, **blind** relevance pass for the retrieval-v1
BM25 default-ranking gate (ADR 0007 §9). It exists so the gate can rest on a human inter-annotator
agreement (κ), not only the disclosed *provisional model-judge* κ already recorded (see
[`docs/benchmarks/retrieval-v1.md`](../../retrieval-v1.md) and the
[BM25 gate decision issue](https://github.com/F-e-u-e-r/religion-council/issues/42)).

The companion file is `retrieval-v1-human-blind-template.json` — the frozen 110-item pool with empty
`label` slots.

## Blind protocol (read first)

Judge **only** from each item's `query` plus the record's own `topic` / `text`. Do **not** look at:

- curator-1's labels or the model judge's labels (they are deliberately **not** in this template);
- the committed benchmark reports or `judging.iaa` in the fixture;
- the candidates' retrieval scores or rankings.

This blindness is what makes the agreement figure meaningful. The labels you have not seen are what κ
measures.

## Rubric (graded relevance, same scale as curator-1)

| label | meaning |
|------:|---------|
| **2** | Direct / canonical source for the query's intent — the exact quote, the exact locator, or the definitive text that answers it. |
| **1** | Partial or cross-tradition thematic support — related to the query's theme but not the central/best source. |
| **0** | Not relevant to the query. |

Judge **relevance to the query**, not the passage's importance in general. For a locator/work-specific
query (e.g. `約翰福音 3:16`, `法句經`), an item from the *same work* but a different verse is usually
**1**; a different work is usually **0**.

## How to fill it

1. Copy `retrieval-v1-human-blind-template.json` (keep the pool order).
2. Set each item's `label` to `0`, `1`, or `2`.
3. Fill `judge.id` (e.g. `human-judge-1`). Leave `judge.judge_type: "human"` and the `blind_to` list.
4. Validate:
   ```bash
   python3 scripts/validate_human_judge_template.py path/to/your-filled-template.json --filled
   ```
   (Validate the blank template — schema + blindness + pool parity — with `--blank`.)

## Schema

```json
{
  "template": "retrieval-v1-human-blind",
  "judge": { "id": "human-judge-1", "judge_type": "human",
             "blind_to": ["curator-1 labels", "model-judge labels", "candidate retrieval scores"] },
  "label_set": [0, 1, 2],
  "pool": [
    {"query_id": "q001", "query": "…", "tradition": "…", "work": "…", "locator": "…",
     "topic": "…", "text": "…", "label": 2}
  ]
}
```

## What happens next (not your step)

A maintainer merges the filled labels into the fixture's `judging.iaa.pool` as a new judge
(`judge_type: human`, `blind_to: …`) in a **separate PR**, then `scripts/compute_iaa.py` recomputes
Cohen's κ (human vs curator-1, and optionally human vs the model judge) and the benchmark reports
re-surface it. Curator-1's authoritative scoring set (`judgments[].relevant[]`) is **not** changed by
this; the pool affects κ only. Only after a human κ exists (or the owner explicitly accepts the
model-judge κ) does the BM25 default-flip decision proceed — never in the same PR as the labels.
