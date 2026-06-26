# Religion Council · 多傳統哲學議會

> A source-grounded, moderated roundtable across the world's major religious and
> philosophical traditions — as a drop-in skill for AI coding agents.
>
> 以原典為據、由中立主持人調度的「跨傳統哲學議會」——可直接掛載到 AI coding agent 的 skill。

![code: MIT](https://img.shields.io/badge/code-MIT-blue.svg)
![content: CC BY 4.0](https://img.shields.io/badge/content-CC%20BY%204.0-lightgrey.svg)
![runs on: Codex · Claude Code · any agent](https://img.shields.io/badge/runs%20on-Codex%20·%20Claude%20Code%20·%20any%20agent-green.svg)
![version: v0.12.5](https://img.shields.io/badge/version-v0.12.5-orange.svg)

**English** · [繁體中文](#繁體中文)

---

## What is this?

**Religion Council** turns your AI agent into a neutral **moderator** that convenes a
fair, **source-grounded** dialogue among religious and philosophical traditions —
without flattening them into one mushy consensus.

Ask *"does life have meaning?"* and you hear Buddhism, Taoism, and Confucianism each
argue from **its own texts**. Every claim is tagged as either a **[Text]** quotation
(with a real locator) or an **[Interpretation]**, and the moderator surfaces the
genuine tensions instead of forcing agreement.

Version **v0.12.5** supports three execution modes:

1. **Claude Code only** — 37 specialized Claude agents (1 moderator + 36 voices).
2. **Codex only** — a portable Codex skill, with native Codex subagents when requested.
3. **Claude moderator + Codex panelists** — a deterministic Python MCP controller manages
   persistent Codex threads, barriers, retries, and audit records.

All three modes share one quote-admissibility policy (`quote-admissibility/v2`). In the
hybrid controller, v0.5.0 added opt-in B1b structured claims: `debate_start` can accept a
retrieval `evidence_envelope`, ask panelists for a `religion-council/claim/v1` payload,
schema-check it, repair or drop malformed payloads, and bind valid claims to B1a evidence
seeds. Version v0.6.0 adds opt-in B2 validation for that same structured path: with
`verify_claims=true`, quotation claims are checked against curated evidence snapshots and
stored with per-claim `runtime-validated` or `failed` outcomes. Version v0.7.0 adds opt-in
B3 fail-closed boundary enforcement with `fail_closed=true`: only affirmatively admitted
claims may pass the response boundary, while unknown claim types, unverified `[Text]`,
renderer bypasses, and unsupported protocols are default-denied. Claude-only and portable
modes stay instruction-enforced. See the
[assurance matrix](docs/ORCHESTRATION.md#quote-admissibility-assurance) and
[ADR 0002](docs/adr/0002-roadmap-stage-nomenclature.md).

Version v0.8.0 added the A1 corpus-enrichment metadata foundation: `retrieve.py` can merge
curated `representation_kind`, `rendering_mode`, `provenance`, and `rights` from a portable
`presentation.json` sidecar, with seed curation for the existing Chinese Qur'an
meaning-renderings. Bulk public-domain excerpt expansion remains source- and rights-reviewed
content work.

v0.9.0 adds the strict-finalization capstone for the hybrid controller. `profile="strict"`
requires the structured → verify → fail-closed graph and an evidence envelope, then makes
finalization a separate, explicit step. See [ADR 0004](docs/adr/0004-renderer-trust-boundary.md)
and the [v0.9.0 changelog](CHANGELOG.md#v090--2026-06-21--strict-finalization--traceable-authority).

v0.11.0 adds stable occurrence identity and a rights-scoped corpus baseline as **A2/A3
readiness only**. It does not add an index, vector store, or RAG backend; that work remains gated
on the retriever-fork contract and benchmark decisions.

v0.12.0 establishes the retriever fork for that next stage: the portable retriever remains
stdlib-only and file-based, while the project retriever has the same versioned retrieval envelope
and shared conformance suite. It does not select an index, vector store, RAG backend, or
edition-backed assurance; those remain gated on benchmark evidence. See
[ADR 0006](docs/adr/0006-retriever-fork-contract.md).

v0.12.1 defines that benchmark and its adoption gates: a candidate must both beat the lexical
baseline and preserve stable occurrence identity, the retrieval contract, artifact lifecycle,
rights boundaries, and assurance honesty. See
[Retrieval Benchmark v1](docs/benchmarks/retrieval-v1.md).

v0.12.2 runs the first retrieval-v1 lexical baseline. The benchmark now has a frozen 18-query
fixture set, graded relevance judgments, a deterministic offline runner, and committed
JSON/Markdown baseline reports. The baseline identifies two main weaknesses of the current lexical
retriever: broad thematic recall and no-answer discrimination. No backend is selected.

v0.12.3 evaluates an experiment-only lexical confidence threshold and adds GitHub issue templates
for public feedback intake. Thresholds 2 and 3 eliminate the benchmark's no-answer false-support
cases without answerable-query regression, while threshold 5 regresses q007 and q010. No threshold
or backend is adopted yet.

v0.12.4 evaluates an experiment-only BM25-style lexical ranking candidate. BM25 improves some
ranking metrics, including MRR and nDCG@5, while preserving exact-span hit rate, but it does not
improve no-answer discrimination or broad thematic recall. No backend is selected and default
retrieval remains unchanged.

v0.12.5 evaluates an experiment-only BM25 + lexical confidence threshold candidate. BM25 supplies
ranking gains while the threshold supplies no-answer discrimination: MRR improves from 0.938 to
0.969, nDCG@5 from 0.902 to 0.919, exact-span hit remains 1.000, no-answer correctness reaches
1.000, and false-support falls to 0.000. Broad thematic recall remains weak on q010, so no backend
is selected and default retrieval remains unchanged.

### Strict finalization: the guarantee boundary

For a strict run, the lifecycle is:

```text
debate_start(profile="strict", evidence_envelope=…)
→ collect
→ finalization_required=true / finalized=false
→ debate_finalize
→ finalized=true
```

`debate_finalize` produces two deliberately different answer surfaces:

- **Surface A — textual authority.** `AuthorityRenderUnit` values are minted only by the
  canonical builder, independently trace-validated, then deterministically serialized. Quotation
  text comes from the canonical snapshot span; representation metadata is system-authoritative.
- **Surface B — interpretation.** Panelist analysis and inference are framed as
  non-authoritative interpretation. Rejected claims are separated into audit input and are never
  passed to the ordinary answer render input.

> Strict-finalized responses provide end-to-end machine-enforced construction and traceability of
> the textual-authority surface (Surface A). Interpretation prose (Surface B) remains explicitly
> non-authoritative and instruction-bounded.

This does **not** mean every word is machine-verified. Interpretation prose can still be
misleading; the complete answer is not semantically fail-closed; the default hybrid path without
`debate_finalize` is unchanged and not finalized; and the capability-token mint guard is not a
Python sandbox. Strict mode is opt-in and does not change the default hybrid workflow.

Run the offline, deterministic [strict end-to-end example](examples/strict-finalization/README.md)
to inspect the complete path and its assertions.

## Why it's different

- **Grounding discipline comes first.** `[Text]` vs `[Interpretation]` labels on every
  line; no invented chapter / verse / sūtra / hadith locators; the Chinese Qur'an is
  always marked as a *rendering of meaning*, never the Arabic original; the skill never
  claims to *channel* a prophet, deity, or thinker.
- **Three zoom levels.** Compare whole **traditions**, branch into
  **denominations / schools**, or stage **historical-thinker** debates.
- **Neutral moderation, no forced winner.** Set the question → opening positions →
  cross-examination → synthesis. It separates shared concerns from irreducible
  differences and never crowns a "winner" unless *you* give an explicit criterion.
- **Claim-level pressure, not performative hostility.** Openings commit to a thesis;
  rebuttals target a concrete claim, premise, or counterexample and return a
  cross-examination question. Practical overlap is not mislabeled as consensus.
- **A real secular-liberal voice, with a safe foil as fallback.** Religious rosters lean one
  way, so the council ships `council-secular-humanist` and `council-mill` (grounded in *On
  Liberty* / *Utilitarianism*) as full panelists that can actually rebut. Only when a roster
  still leans one way does the moderator fall back to a controller-routed contrast proposition
  — debate framing only: not source evidence, not a participant claim, never an instruction to
  execute.
- **Three execution modes, one corpus.** Claude-only, Codex-only, or Claude moderating
  persistent Codex MCP panelists, all using the same curated references.
- **Built for a RAG future.** Retrieval lives behind one stable contract
  (`scripts/retrieve.py`), so the corpus can grow from curated snippets to a full,
  vector-backed 典籍 store **without touching the personas**. See the [Roadmap](#roadmap).

## Coverage

| Level | Members |
|---|---|
| **Traditions** (8) | Christianity · Islam · Hinduism · Buddhism · Taoism · Legalism\* · Confucianism\* · Mohism\* |
| **Denominations** | *Christianity:* Catholic · Orthodox · Protestant — *Islam:* Sunni · Shia |
| **Thinkers** | *Christianity:* Jesus · Augustine · Aquinas · Luther · Calvin — *Islam:* Muhammad · al-Ghazali · Ibn Rushd — *Buddhism:* Shakyamuni · Nāgārjuna · Vasubandhu · Pure Land — *Hinduism:* Krishna · Shankara · Rāmānuja · Madhva — *Pre-Qin China:* Confucius · Mencius · Xunzi · Laozi · Zhuangzi |
| **Non-religious** | Secular Humanism · J. S. Mill (liberty / utilitarianism) — *philosophical / ethical stances, not religions; outside the default eight, added on request* |

\* Legalism, Confucianism, and Mohism are **philosophical / intellectual traditions**, not
religions, and the skill labels them as such (and distinguishes philosophical from
religious Taoism where it matters).

## Quick start

**1. Claude Code only** (uses the 37 custom agents):

```bash
git clone https://github.com/F-e-u-e-r/religion-council.git
cd religion-council
claude            # open Claude Code in the repo root
```
Then, in the conversation:
> 用議會討論:人生有沒有意義?請佛教、道教、儒家三家先各自陳述,再交叉辯論。

The main agent hands off to **`council-moderator`**, which frames the question, dispatches
each `council-*` voice, relays their arguments to one another, and synthesizes.

**2. Codex only** (portable, self-contained):

Ask Codex to install `skills/religion-council/` from this repository, restart Codex, then invoke:
> Use $religion-council to convene a sourced roundtable on whether life has meaning.

`skills/religion-council/SKILL.md` is fully self-contained and degrades gracefully to a
single-context dialogue when sub-agents aren't available.

**3. Claude moderator + Codex panelists**:

Authenticate Codex, start Claude Code at the repo root, approve the project MCP server in
`/mcp`, then ask Claude to use `religion-council-controller` with
`orchestrator/panelists/religion-8.json`. The controller preserves each Codex `threadId`
across rounds and refuses to advance before the current round reaches its barrier.

→ Full per-platform setup: **[INSTALL.md](INSTALL.md)**

## Example prompts

```text
# Cross-tradition
Convene a council: where does meaning come from? Buddhism, Taoism, and Confucianism,
opening statements then cross-examination.

# Denomination debate (Level 1)
How do Catholic, Orthodox, and Protestant views on salvation differ?
遜尼與什葉對「先知之後誰該領導」的分歧是什麼?

# Thinker debate (Level 2)
儒家內部對人性的看法一致嗎?請孔子、孟子、荀子各自說明,再交叉辯論。
Nāgārjuna vs Vasubandhu on emptiness vs consciousness.
Self-power or other-power for liberation? Pure Land vs Zen / Theravāda.
al-Ghazali vs Ibn Rushd on faith and reason.

# Secular vs religious (non-religious tier)
Must life's meaning come from religion or an afterlife? Secular humanism vs Christianity and Buddhism.
在不傷害他人、不違法並承擔後果下,個人是否仍有義務按宗教或傳統美德生活?請彌爾與儒家、天主教辯論。
```

## How it works

```
┌──────────────────────────────────────────────────────────────┐
│  SKILL.md  — the operating manual                              │
│  question layers · grounding rules · anti-quote-mining ·       │
│  roundtable flow (set → open → cross-examine → synthesize)     │
└──────────────────────────────────────────────────────────────┘
        │ every voice reads it before speaking
        ▼
┌──────────────────────────────────────────────────────────────┐
│  references/<tradition>.md  — the personas                     │
│  voice & tone · core concepts · quotable snippets WITH         │
│  citations · cross-tradition tension points                    │
└──────────────────────────────────────────────────────────────┘
        │ Claude Code only
        ▼
┌──────────────────────────────────────────────────────────────┐
│  council-moderator  ──dispatches──▶  council-* sub-agents      │
│  (sub-agents can't talk directly, so the moderator relays)     │
└──────────────────────────────────────────────────────────────┘
        │ optional hybrid mode
        ▼
┌──────────────────────────────────────────────────────────────┐
│  debate_controller.py  ──MCP──▶  codex mcp-server             │
│  persistent thread IDs · barriers · retries · audit records   │
└──────────────────────────────────────────────────────────────┘
        │ retrieval seam (stable contract)
        ▼
┌──────────────────────────────────────────────────────────────┐
│  scripts/retrieve.py   →   { text, tradition, school, work,    │
│  v0.1: lexical references    locator, language, version,       │
│  later: vector search        category }                        │
└──────────────────────────────────────────────────────────────┘
```

The **personas, moderation, and citation rules sit above the retrieval seam and are
already stable.** Everything below it — curated snippets today, a vector store tomorrow —
can evolve without rewriting a single voice.

## Repository layout

```
religion/
├── README.md                     # you are here
├── INSTALL.md                    # per-platform setup (Codex / Claude Code / other)
├── CONTRIBUTING.md               # add a tradition / denomination / thinker
├── DISCLAIMER.md                 # sourcing rules + religious-sensitivity statement
├── LICENSE                       # MIT — skill logic, agents, scripts, config
├── LICENSE-CONTENT               # CC BY 4.0 — references & corpus
├── VERSION                       # current release: v0.12.5
├── .mcp.json                     # Claude → deterministic Codex controller
│
├── skills/religion-council/      # ▸ PORTABLE skill (Codex & any agent)
│   ├── SKILL.md                  #   English operating manual (self-contained)
│   ├── references/               #   16 persona files (snippets + citations)
│   ├── scripts/retrieve.py       #   dependency-free lexical retrieval
│   └── agents/openai.yaml        #   Codex interface metadata
│
├── .claude/                      # ▸ CLAUDE CODE distribution
│   ├── agents/council-*.md       #   37 sub-agents (1 moderator + 36 voices)
│   └── skills/religion-council/
│       ├── SKILL.md              #   繁中 operating manual
│       ├── USAGE.md              #   how to convene a council
│       ├── references/           #   16 persona files (+ 延伸語料 corpus pointers)
│       └── scripts/retrieve.py   #   lexical retrieval (stable {text+metadata} contract)
│
├── orchestrator/                 # ▸ CLAUDE MODERATOR + CODEX PANELISTS
│   ├── debate_controller.py      #   MCP server, barriers, retries, persistence
│   ├── render_types.py           #   Surface A/B/audit render types and mint guard
│   ├── render_finalizer.py       #   strict finalizer + trace validator + serializer
│   └── panelists/                #   8-member and 30-member example rosters
├── examples/strict-finalization/ # offline strict workflow fixture and runnable example
├── scripts/smoke_codex_mcp.py    # opt-in authenticated create/reply MCP check
├── tests/                        # controller persistence and pagination tests
├── docs/CORPUS.md                # corpus & RAG-roadmap notes
├── docs/ORCHESTRATION.md         # controller architecture and limitations
└── 01-基督宗教/ … 08-墨家/       # 典籍清單.md + 思想概要.md (corpus seed)
```

> The two distributions are intentionally different: `skills/` is **dependency-free and
> portable**, while `.claude/` is **project-integrated** (its references point back into the
> `01–08` corpus folders and it orchestrates real sub-agents).

## Roadmap

The project develops along **two low-coupling axes** that meet at one versioned seam.
Architecture stages are **A0–A3** (corpus & retrieval) and **B0–B3** (citation
admissibility & enforcement). PR numbers are delivery history, not stage names. Normative
detail: **[ADR 0002](docs/adr/0002-roadmap-stage-nomenclature.md)** (nomenclature +
enforcement ladder) and **[ADR 0003](docs/adr/0003-retrieval-evidence-adapter.md)**
(the retrieval→evidence adapter).

**Axis A — corpus & retrieval.** Pivots on one seam: the retrieval envelope contract.
Keep it stable and the 36 personas never change as the backend grows from files to a
vector service.

| Stage | What | Retrieval |
|---|---|---|
| **A0 — Curated council** | Voices quote hand-picked, cited snippets in `references/`. Offline, any agent. | File parse + lexical ranking. |
| **A1 — Deeper corpus** *(metadata foundation, v0.8.0)* | Adds the `presentation.json` provenance/rights sidecar and seeds existing Qur'an meaning-renderings; broader public-domain excerpt expansion remains rights-reviewed curation work. | Still file-based. |
| **A2 — Full 典籍 + local index** | Store complete open scriptures in-repo, chunked; benchmark lexical / cross-lingual / dense / hybrid; build the chosen index. | Local index — same envelope contract. |
| **A3 — RAG server** | Index behind a retrieval service; `retrieve.py` becomes a thin client. Optionally expose the council as an API/app. | Networked — same contract. |

*(The v0.1 deterministic hybrid panel — Claude moderating persistent Codex panelists — is
delivery history, not an Axis-A stage: it did not change retrieval.)*

**Axis B — citation admissibility & enforcement.** Pivots on the structured claim /
quote-admissibility policy, escalating from prompt-only to a fail-closed boundary.

| Stage | What | Enforcement |
|---|---|---|
| **B0 — Unified policy** *(done, v0.2.0)* | One policy source → four surfaces; memory alone never supports `[Text]`; packets are untrusted data. | Instruction-enforced; **not** fail-closed. |
| **B1 — Structured claims + evidence seam** *(done, v0.5.0)* | Hybrid opt-in mode parses `religion-council/claim/v1`, rejects malformed payloads (retry → repair → drop), and binds valid claims to `RetrievalEvidenceAdapterV1` evidence seeds. Initial verification is always `unverified`. | Schema rejection only; not B2 validation or B3 fail-closed. |
| **B2 — Claim-level validation** *(done, v0.6.0)* | Hybrid opt-in `verify_claims=true` validates bound `[Text]` quotation edges against curated snapshots, validates source-bound summaries by evidence edge, removes failed support edges, and downgrades all-failed `[Text]` claims to `[Unverified citation]`; the council still completes. | Claim-level runtime validation; not B3 fail-closed. |
| **B3 — Fail-closed boundary** *(done, v0.7.0)* | Hybrid opt-in `fail_closed=true` runs a response-boundary gate after B2: unknown claim types, unvalidated `[Text]`, renderer bypasses, and unsupported protocols are default-denied before rendering. | Hybrid runtime-enforced / fail-closed. |
| **ADR 0004 capstone — strict finalization** *(done, v0.9.0)* | `profile="strict"` requires the complete graph and `debate_finalize` builds a deterministic, trace-validated Surface A from admitted claims only, with a non-removable Surface B frame and separate audit input. | End-to-end machine-enforced construction and traceability of Surface A for strict-finalized responses only. |

The **enforcement ladder** keeps three rejections distinct: **B1** rejects malformed
structure (retry/repair/drop) · **B2** removes a failed `[Text]` support edge (may keep a
non-supporting `[Unverified citation]`) and continues · **B3** default-denies at the
response boundary. Claude-only and portable modes stay instruction-enforced. From v0.7.0,
hybrid structured runs surface a response-level enforcement mode:
`structured-schema-enforced` when payloads bind successfully, or
`structured-claim-validated` when `verify_claims=true` and B2 validation ran, or
`structured-fail-closed` when `fail_closed=true` and the B3 boundary gate ran. Per-claim
runtime assurance and renderability remain in the claim verification and boundary decision
records.

**Where the axes meet.** Axis A's retrieval envelope is converted by the B1 adapter into
immutable, content-addressed Artifact/Span identity — so A can swap retrieval backends
without rewriting personas, and B can raise enforcement without first building a vector DB:

```text
retrieve_envelope() → RetrievalEvidenceAdapterV1 → Artifact + Span → ClaimEvidenceEdge → validator → renderer
```

**Distribution split.** The portable **`skills/`** stays snippet-based, file-based,
instruction-enforced — the demo anyone can clone and run. The project-integrated
**`.claude/` + `orchestrator/` + retrieval service** grows the full corpus, structured
protocol, validator, and hybrid fail-closed enforcement. Both share the core policy, not
dependencies or enforcement guarantees. The portable and project retrievers are now intentionally
forked ([ADR 0006](docs/adr/0006-retriever-fork-contract.md)): they share one **retrieval-envelope
contract**, proven by a conformance suite (`tests/retrieval_contract/`) rather than by byte-parity.
Byte-parity is kept only as a narrow same-artifact check between the two portable `retrieve.py` copies.

**Rights gate (tiered).** A1 requires excerpt-level provenance + a rights note per snippet;
A2 requires full operational redistribution clearance (`redistributable = true`,
jurisdiction notes, review record) before any full text enters the distributable corpus.

## Sourcing, ethics & limits

This project takes source integrity seriously: no fabricated locators, no presenting a
generated translation as a published quotation, the Qur'an in Chinese always marked as a
rendering, and the strongest honest version of each position before any critique. For
personal crises (self-harm, abuse, medical/legal/financial), it points to professional help
first and treats the council as supplementary reflection only.

→ Read the full policy: **[DISCLAIMER.md](DISCLAIMER.md)**

## Contributing

Want to add a tradition, denomination, or thinker — or grow the corpus? The citation rules
are the heart of the project, so please read the guide first.

→ **[CONTRIBUTING.md](CONTRIBUTING.md)**

## License

Dual-licensed, by purpose:

| Part | License | Covers |
|---|---|---|
| **Skill logic** | [MIT](LICENSE) | `SKILL.md`, `USAGE.md`, `.claude/agents/*.md`, `orchestrator/`, `scripts/*.py`, `.mcp.json`, `agents/openai.yaml` |
| **Written content** | [CC BY 4.0](LICENSE-CONTENT) | `references/`, the `01–08` corpus, `docs/CORPUS.md` |

Quoted primary scriptures are public-domain source texts in their original languages; CC BY
4.0 covers this project's curation, summaries, and renderings. Attribute to
"Religion Council contributors."

---
---

# 繁體中文

[English](#religion-council--多傳統哲學議會) · **繁體中文**

> 以原典為據、由中立主持人調度的「跨傳統哲學議會」——可直接掛載到 AI coding agent 的 skill。

## 這是什麼?

**多傳統哲學議會(Religion Council)** 讓你的 AI agent 化身為中立的**主持人**,召集一場
**以原典為據**、公平的跨傳統對話——而不是把各家硬揉成一團含糊的共識。

問一句「人生有沒有意義?」,你會聽到佛教、道教、儒家**各自從自己的經典**立論。每一句發言都
標注為**〔據典〕**(引文+真實出處)或**〔詮釋〕**;主持人負責把真正的張力點攤開,而非強行
調和。

目前 **v0.12.5** 支援三種執行方式:

1. **純 Claude Code**——附 37 個專屬 agent(1 位主持人 + 36 個聲音)。
2. **純 Codex**——可攜 Codex skill;明確要求時可用 Codex 原生 subagent。
3. **Claude 主持 + Codex 議員**——Python MCP controller 保存 Codex threadId、執行
   barrier、重試及紀錄。

三種模式共用同一份引用可採性政策(`quote-admissibility/v2`)。混合 controller 在 v0.5.0
加入 opt-in B1b 結構化 claim;v0.6.0 進一步加入 opt-in B2 `verify_claims=true`,可把 quotation
claim 對 curated evidence snapshot 做執行期驗證,並以每個 claim 的 `runtime-validated` 或
`failed` 結果寫入 state。v0.7.0 加入 opt-in B3 `fail_closed=true`:只有明確 admit 的 claim 可通過
response boundary;unknown claim type、未 runtime-validated 的〔據典〕、renderer bypass 與不支援
protocol 會預設拒絕。純 Claude 與可攜模式仍維持 instruction-enforced。

v0.8.0 已新增 A1 語料加厚的 metadata 基礎建設:`retrieve.py` 可從可攜的
`presentation.json` sidecar 合併 curated `representation_kind`、`rendering_mode`、
`provenance` 與 `rights`,並為既有古蘭經中文釋義片段建立種子標註。大量新增公有領域摘錄仍屬
需來源與 rights review 的人工 curation 工作。

v0.9.0 加入混合 controller 的 strict-finalization capstone。`profile="strict"` 要求完整的
structured → verify → fail-closed 圖與 evidence envelope，並把 finalization 設成獨立、明確的
步驟。詳見 [ADR 0004](docs/adr/0004-renderer-trust-boundary.md) 與
[v0.9.0 變更紀錄](CHANGELOG.md#v090--2026-06-21--strict-finalization--traceable-authority)。

v0.11.0 新增 stable occurrence identity 與附權利範圍說明的語料基線,僅為 **A2/A3 readiness**;並未
加入 index、vector store 或 RAG backend。後續工作仍受 retriever-fork contract 與 benchmark 決策把關。

v0.12.0 建立下一階段所需的 retriever fork：portable retriever 仍是 stdlib-only、file-based；
project retriever 則以同一份 versioned retrieval envelope 與 shared conformance suite 為約束。這並未
選定 index、vector store、RAG backend 或 edition-backed assurance；它們仍須先有 benchmark evidence。
詳見 [ADR 0006](docs/adr/0006-retriever-fork-contract.md)。

v0.12.1 定義該 benchmark 與採用門檻：候選後端必須同時勝過 lexical baseline，並保住 stable
occurrence identity、retrieval contract、artifact lifecycle、rights 邊界與 assurance honesty。詳見
[Retrieval Benchmark v1](docs/benchmarks/retrieval-v1.md)。

v0.12.2 執行第一次 retrieval-v1 lexical baseline。benchmark 現有凍結 18-query fixture set、graded
relevance judgments、deterministic offline runner，以及已 commit 的 JSON/Markdown baseline reports。
baseline 識別出 lexical retriever 的兩大弱點：broad thematic recall 與 no-answer discrimination。
未選定任何後端。

v0.12.3 評估 experiment-only lexical confidence threshold，並加入 GitHub issue templates 以承接公開
feedback。threshold 2 與 3 消除了 benchmark 的 no-answer false-support cases，且未造成 answerable-query
regression；threshold 5 則使 q007 與 q010 regression。目前仍未採用 threshold 或任何 backend。

v0.12.4 評估 experiment-only BM25-style lexical ranking candidate。BM25 改善部分 ranking metrics，
包含 MRR 與 nDCG@5，並保住 exact-span hit rate；但它沒有改善 no-answer discrimination 或 broad
thematic recall。未選定任何 backend，default retrieval 也維持不變。

v0.12.5 評估 experiment-only BM25 + lexical confidence threshold candidate。BM25 提供 ranking
改善，threshold 提供 no-answer discrimination：MRR 從 0.938 提升到 0.969，nDCG@5 從 0.902
提升到 0.919，exact-span hit 維持 1.000，no-answer correctness 達到 1.000，false-support
降到 0.000。q010 的 broad thematic recall 仍然偏弱，因此未選定任何 backend，default retrieval
也維持不變。

### Strict finalization：保證邊界

strict run 的生命週期如下：

```text
debate_start(profile="strict", evidence_envelope=…)
→ collect
→ finalization_required=true / finalized=false
→ debate_finalize
→ finalized=true
```

`debate_finalize` 產生兩個刻意分離的 answer surface：

- **Surface A — textual authority。** `AuthorityRenderUnit` 只能由 canonical builder mint，
  經獨立 trace validation 後才 deterministic serialization。quotation 文字取自 canonical snapshot
  span；representation metadata 以系統資料為準。
- **Surface B — interpretation。** 議員的分析與推論會被框定為 non-authoritative interpretation。
  被拒絕的 claim 留在 audit input，絕不傳入一般 answer render input。

> Strict-finalized responses provide end-to-end machine-enforced construction and traceability of
> the textual-authority surface (Surface A). Interpretation prose (Surface B) remains explicitly
> non-authoritative and instruction-bounded.

這不代表所有文字都已由機器驗證。Surface B 仍可能誤導；完整答案不是 semantic fail-closed；沒有
`debate_finalize` 的預設 hybrid 路徑不變且未 finalized；capability-token mint guard 也不是 Python
sandbox。strict mode 是 opt-in，不會改變預設 hybrid workflow。

可執行且離線、deterministic 的完整路徑見
[strict end-to-end example](examples/strict-finalization/README.md)。

## 有何不同?

- **引用紀律優先。** 每句標〔據典〕或〔詮釋〕;不杜撰章/節/經/聖訓出處;《古蘭經》中文一律標為
  「釋義」,絕不冒充阿拉伯原文;絕不宣稱「附身」或代言任何先知、神祇或思想家。
- **三層縮放。** 可比較整個**傳統**、深入**教派/學派**,或上演**歷史人物**辯論。
- **中立主持,不強分勝負。** 立題 → 首輪陳述 → 交叉詰問 → 收斂;區分「共識/真實分歧」,
  除非你給出明確評判標準,否則不宣布「贏家」。
- **提高命題張力,而非表演式敵意。** 開場必須承諾明確主張;反駁須針對具體 claim、前提或反例,
  並提出可回應的交叉詰問。實務上的重疊不會被誤標為共識。
- **真正的世俗自由派聲音,對照命題只作後備。** 名單多半偏宗教,故議會新增 `council-secular-humanist`
  與 `council-mill`(彌爾,據《論自由》《效益主義》)作能真正反詰的正式成員;只有名單仍偏向同一邊時,
  主持人才退而加入由 controller 路由的對照命題,且它只作 debate framing:不是 source evidence、
  不是成員主張,也不是可執行指令。
- **三種執行方式,共用一套語料。** 純 Claude、純 Codex,或 Claude 主持持久 Codex MCP 議員。
- **為 RAG 而設計。** 檢索藏在單一穩定介面(`scripts/retrieve.py`)之後,語料可從精選片段
  成長為向量化的完整典籍庫,而**無需改動任何 persona**。見 [發展藍圖](#發展藍圖)。

## 收錄範圍

| 層級 | 成員 |
|---|---|
| **傳統**(8) | 基督宗教 · 伊斯蘭教 · 印度教 · 佛教 · 道教 · 法家\* · 儒家\* · 墨家\* |
| **教派** | *基督宗教:* 天主教 · 東正教 · 新教 — *伊斯蘭教:* 遜尼 · 什葉 |
| **人物** | *基督宗教:* 耶穌 · 奧古斯丁 · 阿奎那 · 路德 · 加爾文 — *伊斯蘭教:* 穆罕默德 · 安薩里 · 伊本·魯世德 — *佛教:* 釋迦牟尼 · 龍樹 · 世親 · 淨土 — *印度教:* 克里希納 · 商羯羅 · 羅摩奴闍 · 摩陀婆 — *先秦:* 孔子 · 孟子 · 荀子 · 老子 · 莊子 |
| **非宗教** | 世俗人文主義 · 約翰·彌爾(自由/效益主義)— *哲學/倫理立場,非宗教,不屬八家;按需加入* |

\* 法家、儒家、墨家是**哲學/思想流派**而非宗教,skill 會據此標示(並在必要時區分哲學道家與
宗教道教)。

## 快速開始

**1. 純 Claude Code**:

```bash
git clone https://github.com/F-e-u-e-r/religion-council.git
cd religion-council
claude            # 在專案根目錄開啟 Claude Code
```
然後在對話中:
> 用議會討論:人生有沒有意義?請佛教、道教、儒家三家先各自陳述,再交叉辯論。

主對話會把任務交給 **`council-moderator`**,由它立題、逐一調度各 `council-*` 成員、轉述彼此
論點並收斂分歧。

**2. 純 Codex**(可攜、自足):

把 agent 的 skill 載入路徑指向 `skills/religion-council/`,然後呼叫:
> Use $religion-council to convene a sourced roundtable on whether life has meaning.

`skills/religion-council/SKILL.md` 完全自足;沒有 sub-agent 時會自動降級為單一脈絡內的對話。

**3. Claude 主持 + Codex 議員**:

先登入 Codex,在 repo 根目錄啟動 Claude Code,並於 `/mcp` 批准專案 MCP server;再請 Claude
使用 `religion-council-controller` 與 `orchestrator/panelists/religion-8.json`。Controller
會跨輪保存同一批 Codex `threadId`,並在全員完成前阻止進入下一輪。

→ 各平台完整設定:**[INSTALL.md](INSTALL.md)**

## 運作原理

發言前,每個聲音都先讀 `SKILL.md`(提問層次、引用紀律、防斷章取義、圓桌流程);各傳統的立場與
可引用片段放在 `references/<傳統>.md`。在 Claude Code 中,`council-moderator` 透過 Agent
工具調度各 `council-*` 成員(sub-agent 之間不能直接對話,故由主持人轉述)。檢索則統一走
`scripts/retrieve.py` 的穩定介面(輸出 `text` + `tradition/school/work/locator/language/
version/category` metadata):**v0.1** 解析並以詞彙比對排序 references 片段,**未來**換成向量檢索,而上層的
persona 與引用紀律不必更動。

## 發展藍圖

整個專案沿**兩條低耦合的軸線**發展,並在一個版本化的接縫處交會。架構階段只用
**A0–A3**(語料與檢索)與 **B0–B3**(引用可採性與強制力);PR 編號只是交付歷史,不是階段名稱。
規範細節見 **[ADR 0002](docs/adr/0002-roadmap-stage-nomenclature.md)**(階段命名 + 強制力梯度)
與 **[ADR 0003](docs/adr/0003-retrieval-evidence-adapter.md)**(檢索→證據 adapter)。

**軸線 A — 語料與檢索。** 樞紐是一條接縫:檢索 envelope 契約。守住它,後端由檔案逐步升級為
向量服務時,36 個 persona 都不必改。

| 階段 | 內容 | 檢索 |
|---|---|---|
| **A0 — 精選議會** | 各成員引用 `references/` 中手選、附出處片段,離線、任何 agent 皆可跑。 | 檔案解析 + 詞彙排序。 |
| **A1 — 加厚語料**(metadata 基礎,v0.8.0) | 新增 `presentation.json` provenance/rights sidecar,並為既有古蘭經中文釋義建立種子標註;更大規模的公有領域摘錄擴充仍須逐筆來源與 rights review。 | 仍為檔案式。 |
| **A2 — 完整典籍 + 本地索引** | 把開放典籍全文入庫並切分;benchmark lexical / cross-lingual / dense / hybrid;再建所選索引。 | 本地索引——envelope 契約不變。 |
| **A3 — RAG server** | 索引移到檢索服務,`retrieve.py` 變薄客戶端;亦可把議會做成 API/應用。 | 網路檢索——仍是同一契約。 |

*(v0.1 的可重現混合 panel——Claude 主持持久 Codex 議員——是交付歷史,不是 Axis-A 階段:它沒有改動檢索。)*

**軸線 B — 引用可採性與強制力。** 樞紐是結構化 claim / quote-admissibility 政策,由純 prompt
指示逐步升級為 fail-closed 邊界。

| 階段 | 內容 | 強制力 |
|---|---|---|
| **B0 — 統一政策**(已完成,v0.2.0) | 同一政策來源 → 四個 surface;僅憑記憶永不支持〔據典〕;packet 視為不可信資料。 | instruction-enforced;**尚未** fail-closed。 |
| **B1 — 結構化 claim + 證據接縫**(已完成,v0.5.0) | 混合模式可 opt-in 解析 `religion-council/claim/v1`,對格式錯誤 payload 執行 retry → repair → drop,並把有效 claim 綁定至 `RetrievalEvidenceAdapterV1` evidence seeds。initial verification 恆為 `unverified`。 | 僅 schema 拒絕;不是 B2 驗證,也不是 B3 fail-closed。 |
| **B2 — claim 層驗證**(已完成,v0.6.0) | 混合模式可 opt-in `verify_claims=true`,對已綁定〔據典〕quotation edge 做 curated snapshot 驗證,source-bound summary 以 evidence edge 驗證;失敗 support edge 會移除,全失敗〔據典〕降為〔未驗證引用〕,議會仍可完成。 | claim 層執行期驗證;不是 B3 fail-closed。 |
| **B3 — fail-closed 邊界**(已完成,v0.7.0) | 混合模式可 opt-in `fail_closed=true`,在 B2 之後執行 response-boundary gate:未知 claim type、未驗證〔據典〕、renderer bypass 與 unsupported protocol 會在 render 前預設拒絕。 | 混合模式 runtime-enforced / fail-closed。 |
| **ADR 0004 capstone — strict finalization**(已完成,v0.9.0) | `profile="strict"` 要求完整圖；`debate_finalize` 只從 admitted claim 建立 deterministic、trace-validated 的 Surface A，附有不可移除的 Surface B frame 與分離 audit input。 | 僅 strict-finalized responses 的 Surface A 具有端到端 machine-enforced construction 與 traceability。 |

**強制力梯度**把三種「拒絕」分清楚:**B1** 拒絕格式不良的結構(retry/repair/drop)·**B2** 移除失敗
〔據典〕的 support edge(可保留 non-supporting〔未驗證引用〕)後續行·**B3** 在 response 邊界預設拒絕。
純 Claude 與可攜模式維持 instruction-enforced。v0.7.0 起,混合模式的結構化回合會顯示
response-level enforcement mode:成功綁定時為 `structured-schema-enforced`;若同時
`verify_claims=true` 且 B2 驗證已執行,則為 `structured-claim-validated`;若再加
`fail_closed=true` 且 B3 邊界已執行,則為 `structured-fail-closed`。每個 claim 的真實 runtime
assurance 與可否 render 仍以 claim verification 與 boundary decision records 為準。

**兩軸交會處。** 軸線 A 的檢索 envelope 由 B1 adapter 轉換為不可變、content-addressed 的
Artifact/Span identity——因此 A 可更換檢索後端而不重寫 persona,B 可提升強制力而不必先建向量庫:

```text
retrieve_envelope() → RetrievalEvidenceAdapterV1 → Artifact + Span → ClaimEvidenceEdge → validator → renderer
```

**發行分工。** 可攜的 **`skills/`** 維持片段式、檔案式、instruction-enforced——人人 clone 後即可跑
的 demo。專案整合版 **`.claude/` + `orchestrator/` + 檢索服務**則養成完整語料、結構化 protocol、
validator 與混合 fail-closed 強制力。兩者共用核心政策,但不共用依賴或強制力保證。可攜版與專案版檢索器
現已依 [ADR 0006](docs/adr/0006-retriever-fork-contract.md) 正式分叉:兩者共用同一份**檢索 envelope 契約**
(由 `tests/retrieval_contract/` 的 conformance suite 保證),而非位元組 parity;位元組 parity 僅保留為
兩份可攜 `retrieve.py` 副本之間的窄同源檢查。

**Rights gate(分層)。** A1 要求每個片段具 excerpt 層 provenance + rights note;A2 要求完整的
operational redistribution clearance(`redistributable = true`、jurisdiction notes、review record),
全文方可進入可分發 corpus。

## 來源、倫理與限度

本專案重視來源誠信:不杜撰出處、不把自動生成的翻譯當成已出版引文、《古蘭經》中文一律標「釋義」、
批評任何立場前先呈現其最強且誠實的版本。遇到個人危機(自傷、受虐、醫療/法律/財務)時,優先指向
專業協助,議會僅作輔助性反思。

→ 完整守則:**[DISCLAIMER.md](DISCLAIMER.md)**

## 參與貢獻

想新增傳統、教派或人物,或擴充語料?引用紀律是本專案的核心價值,動手前請先讀指南。

→ **[CONTRIBUTING.md](CONTRIBUTING.md)**

## 授權

依用途雙重授權:

| 部分 | 授權 | 範圍 |
|---|---|---|
| **Skill 邏輯** | [MIT](LICENSE) | `SKILL.md`、`USAGE.md`、`.claude/agents/*.md`、`orchestrator/`、`scripts/*.py`、`.mcp.json`、`agents/openai.yaml` |
| **書面內容** | [CC BY 4.0](LICENSE-CONTENT) | `references/`、`01–08` 語料、`docs/CORPUS.md` |

所引原典在其原文中多屬公有領域;CC BY 4.0 涵蓋的是本專案的選編、摘要與釋義。請標註出處
「Religion Council contributors」。
