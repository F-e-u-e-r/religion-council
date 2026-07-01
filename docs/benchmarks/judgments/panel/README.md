# retrieval-v1 model-judge panel

Filled **blind** relevance passes for the retrieval-v1 BM25 default-ranking gate (ADR 0007 §9), one
file per judge, all in the shared filled-template schema
(see [`../templates/retrieval-v1-human-blind-rubric.md`](../templates/retrieval-v1-human-blind-rubric.md)).

**Evidence only.** Panel κ does **not** authorize the BM25 default flip;
`judging.gate_evidence.bm25_default_flip_authorized` stays `false` unless the project owner explicitly
accepts model-panel evidence (issue #42).

## Files

- `retrieval-v1-model-judge-claude-opus.json` — Claude / Opus (`claude-opus-4-8`); its labels are the
  committed `model-judge-claude` blind pass (one source of truth — not a divergent re-run).
- `retrieval-v1-model-judge-gpt.json` — GPT / Codex (`gpt-5-codex`); a blind model-judge pass filled
  from the template only, with no curator / other-judge labels or retrieval scores consulted.
- _(add your own: `…-gemini.json`, `…-gpt.json`, `…-human-1.json`, …)_

## Add a judge

1. Copy [`../templates/retrieval-v1-human-blind-template.json`](../templates/retrieval-v1-human-blind-template.json).
2. Fill each `label` (0/1/2) **blind** — judge from the `query` + record `topic`/`text` only; no
   curator / other-judge labels, no benchmark scores. Fill the `judge` metadata (`id`, `judge_type`,
   `provider`, `model`, version/`date`, `prompt`, `generation`, `blind_to`).
3. Validate: `python3 scripts/validate_human_judge_template.py <file> --filled`.
4. Save it here as `retrieval-v1-<judge-id>.json`.

## Compute agreement

```bash
python3 scripts/compute_panel_agreement.py docs/benchmarks/judgments/panel/*.json
```

It reports pairwise Cohen's κ between curator-1 and every judge **and between judges** — each pair is
shown separately **on purpose**: two same-provider judges (e.g. Opus + Sonnet) tend to agree because
they are similar, not because they are right, so a single aggregate would hide that correlation. Treat
panel agreement as a *robustness* layer, not as independence. A multi-rater aggregate (Fleiss' κ /
Krippendorff's α) is a sensible addition once ≥ 3 passes exist.

## Forks

Fork the repo, drop in your own filled passes, and run the two commands above to get your own κ. The
canonical repo stays conservative (guardrail `false`); your fork can set its own evidence threshold and
decide whether model-panel agreement is enough for your needs.
