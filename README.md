# Religion Council · 多傳統哲學議會

> A source-grounded, moderated roundtable across the world's major religious and
> philosophical traditions — as a drop-in skill for AI coding agents.
>
> 以原典為據、由中立主持人調度的「跨傳統哲學議會」——可直接掛載到 AI coding agent 的 skill。

![code: MIT](https://img.shields.io/badge/code-MIT-blue.svg)
![content: CC BY 4.0](https://img.shields.io/badge/content-CC%20BY%204.0-lightgrey.svg)
![runs on: Codex · Claude Code · any agent](https://img.shields.io/badge/runs%20on-Codex%20·%20Claude%20Code%20·%20any%20agent-green.svg)
![version: v0.3.0](https://img.shields.io/badge/version-v0.3.0-orange.svg)

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

Version **v0.3.0** supports three execution modes:

1. **Claude Code only** — 35 specialized Claude agents (1 moderator + 34 voices).
2. **Codex only** — a portable Codex skill, with native Codex subagents when requested.
3. **Claude moderator + Codex panelists** — a deterministic Python MCP controller manages
   persistent Codex threads, barriers, retries, and audit records.

All three modes share one quote-admissibility policy (`quote-admissibility/v2`), but the
enforcement is currently **instruction-level only**: the hybrid controller is **not
fail-closed** — it does not parse labels, verify citations, validate spans, or reject
non-conforming output. See the [assurance matrix](docs/ORCHESTRATION.md#quote-admissibility-assurance)
and [ADR 0001](docs/adr/0001-quote-admissibility-policy.md).

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
- **Safe constructed contrast.** When a roster leans one way, the moderator can inject a
  controller-routed contrast proposition as debate framing only: not source evidence, not a
  participant claim, and never an instruction to execute.
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

\* Legalism, Confucianism, and Mohism are **philosophical / intellectual traditions**, not
religions, and the skill labels them as such (and distinguishes philosophical from
religious Taoism where it matters).

## Quick start

**1. Claude Code only** (uses the 35 custom agents):

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
├── VERSION                       # current release: v0.3.0
├── .mcp.json                     # Claude → deterministic Codex controller
│
├── skills/religion-council/      # ▸ PORTABLE skill (Codex & any agent)
│   ├── SKILL.md                  #   English operating manual (self-contained)
│   ├── references/               #   15 persona files (snippets + citations)
│   ├── scripts/retrieve.py       #   dependency-free lexical retrieval
│   └── agents/openai.yaml        #   Codex interface metadata
│
├── .claude/                      # ▸ CLAUDE CODE distribution
│   ├── agents/council-*.md       #   35 sub-agents (1 moderator + 34 voices)
│   └── skills/religion-council/
│       ├── SKILL.md              #   繁中 operating manual
│       ├── USAGE.md              #   how to convene a council
│       ├── references/           #   15 persona files (+ 延伸語料 corpus pointers)
│       └── scripts/retrieve.py   #   lexical retrieval (stable {text+metadata} contract)
│
├── orchestrator/                 # ▸ CLAUDE MODERATOR + CODEX PANELISTS
│   ├── debate_controller.py      #   MCP server, barriers, retries, persistence
│   └── panelists/                #   8-member and 30-member example rosters
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
Keep it stable and the 34 personas never change as the backend grows from files to a
vector service.

| Stage | What | Retrieval |
|---|---|---|
| **A0 — Curated council** *(today)* | Voices quote hand-picked, cited snippets in `references/`. Offline, any agent. | File parse + lexical ranking. |
| **A1 — Deeper corpus** | Expand `references/` and `01–08/典籍清單.md` + `思想概要.md` with more public-domain / openly-licensed excerpts + provenance. | Still file-based. |
| **A2 — Full 典籍 + local index** | Store complete open scriptures in-repo, chunked; benchmark lexical / cross-lingual / dense / hybrid; build the chosen index. | Local index — same envelope contract. |
| **A3 — RAG server** | Index behind a retrieval service; `retrieve.py` becomes a thin client. Optionally expose the council as an API/app. | Networked — same contract. |

*(The v0.1 deterministic hybrid panel — Claude moderating persistent Codex panelists — is
delivery history, not an Axis-A stage: it did not change retrieval.)*

**Axis B — citation admissibility & enforcement.** Pivots on the structured claim /
quote-admissibility policy, escalating from prompt-only to a fail-closed boundary.

| Stage | What | Enforcement |
|---|---|---|
| **B0 — Unified policy** *(done, v0.2.0)* | One policy source → four surfaces; memory alone never supports `[Text]`; packets are untrusted data. | Instruction-enforced; **not** fail-closed. |
| **B1 — Structured claims + evidence seam** | Panelists emit a versioned claim protocol; `RetrievalEvidenceAdapterV1` mints stable Artifact/Span identity. Initial verification is always `unverified`. | Schema rejection only. |
| **B2 — Claim-level validation** | Each `[Text]` claim becomes `runtime-validated` or `failed`; a failed `[Text]` support edge is removed (a non-supporting `[Unverified citation]` may remain); the council still completes. | Claim-level runtime validation. |
| **B3 — Fail-closed boundary** | Unknown claim types and evidence/renderer bypasses are default-denied before the renderer. | Hybrid runtime-enforced / fail-closed. |

The **enforcement ladder** keeps three rejections distinct: **B1** rejects malformed
structure (retry/repair) · **B2** removes a failed `[Text]` support edge (may keep a
non-supporting `[Unverified citation]`) and continues · **B3** default-denies at the
response boundary. Claude-only and portable modes stay instruction-enforced. *Planned for
B1/B2, not in this PR:* every response will show its enforcement mode and every `[Text]`
claim its assurance tier, so a snapshot-verified quote is never mistaken for an
edition-backed one.

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
dependencies or enforcement guarantees. Byte-parity of the two `retrieve.py` copies is an
A0–A1 invariant; A2 forks them and replaces parity with a shared contract-conformance suite.

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

目前 **v0.3.0** 支援三種執行方式:

1. **純 Claude Code**——附 35 個專屬 agent(1 位主持人 + 34 個聲音)。
2. **純 Codex**——可攜 Codex skill;明確要求時可用 Codex 原生 subagent。
3. **Claude 主持 + Codex 議員**——Python MCP controller 保存 Codex threadId、執行
   barrier、重試及紀錄。

## 有何不同?

- **引用紀律優先。** 每句標〔據典〕或〔詮釋〕;不杜撰章/節/經/聖訓出處;《古蘭經》中文一律標為
  「釋義」,絕不冒充阿拉伯原文;絕不宣稱「附身」或代言任何先知、神祇或思想家。
- **三層縮放。** 可比較整個**傳統**、深入**教派/學派**,或上演**歷史人物**辯論。
- **中立主持,不強分勝負。** 立題 → 首輪陳述 → 交叉詰問 → 收斂;區分「共識/真實分歧」,
  除非你給出明確評判標準,否則不宣布「贏家」。
- **提高命題張力,而非表演式敵意。** 開場必須承諾明確主張;反駁須針對具體 claim、前提或反例,
  並提出可回應的交叉詰問。實務上的重疊不會被誤標為共識。
- **安全的建構對照命題。** 名單天然偏向同一邊時,主持人可加入由 controller 路由的對照命題,
  但它只作 debate framing:不是 source evidence、不是成員主張,也不是可執行指令。
- **三種執行方式,共用一套語料。** 純 Claude、純 Codex,或 Claude 主持持久 Codex MCP 議員。
- **為 RAG 而設計。** 檢索藏在單一穩定介面(`scripts/retrieve.py`)之後,語料可從精選片段
  成長為向量化的完整典籍庫,而**無需改動任何 persona**。見 [發展藍圖](#發展藍圖)。

## 收錄範圍

| 層級 | 成員 |
|---|---|
| **傳統**(8) | 基督宗教 · 伊斯蘭教 · 印度教 · 佛教 · 道教 · 法家\* · 儒家\* · 墨家\* |
| **教派** | *基督宗教:* 天主教 · 東正教 · 新教 — *伊斯蘭教:* 遜尼 · 什葉 |
| **人物** | *基督宗教:* 耶穌 · 奧古斯丁 · 阿奎那 · 路德 · 加爾文 — *伊斯蘭教:* 穆罕默德 · 安薩里 · 伊本·魯世德 — *佛教:* 釋迦牟尼 · 龍樹 · 世親 · 淨土 — *印度教:* 克里希納 · 商羯羅 · 羅摩奴闍 · 摩陀婆 — *先秦:* 孔子 · 孟子 · 荀子 · 老子 · 莊子 |

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
向量服務時,34 個 persona 都不必改。

| 階段 | 內容 | 檢索 |
|---|---|---|
| **A0 — 精選議會**(現在) | 各成員引用 `references/` 中手選、附出處片段,離線、任何 agent 皆可跑。 | 檔案解析 + 詞彙排序。 |
| **A1 — 加厚語料** | 擴充 `references/` 與 `01–08/典籍清單.md`、`思想概要.md`,補上更多公有領域/開放授權精選片段與 provenance。 | 仍為檔案式。 |
| **A2 — 完整典籍 + 本地索引** | 把開放典籍全文入庫並切分;benchmark lexical / cross-lingual / dense / hybrid;再建所選索引。 | 本地索引——envelope 契約不變。 |
| **A3 — RAG server** | 索引移到檢索服務,`retrieve.py` 變薄客戶端;亦可把議會做成 API/應用。 | 網路檢索——仍是同一契約。 |

*(v0.1 的可重現混合 panel——Claude 主持持久 Codex 議員——是交付歷史,不是 Axis-A 階段:它沒有改動檢索。)*

**軸線 B — 引用可採性與強制力。** 樞紐是結構化 claim / quote-admissibility 政策,由純 prompt
指示逐步升級為 fail-closed 邊界。

| 階段 | 內容 | 強制力 |
|---|---|---|
| **B0 — 統一政策**(已完成,v0.2.0) | 同一政策來源 → 四個 surface;僅憑記憶永不支持〔據典〕;packet 視為不可信資料。 | instruction-enforced;**尚未** fail-closed。 |
| **B1 — 結構化 claim + 證據接縫** | Panelist 輸出具版本的 claim protocol;`RetrievalEvidenceAdapterV1` 鑄造穩定 Artifact/Span identity。initial verification 恆為 `unverified`。 | 僅 schema 拒絕。 |
| **B2 — claim 層驗證** | 每個〔據典〕變為 `runtime-validated` 或 `failed`;移除失敗〔據典〕的 support edge(政策允許時保留 non-supporting〔未驗證引用〕),議會仍可完成。 | claim 層執行期驗證。 |
| **B3 — fail-closed 邊界** | 未知 claim type 與 evidence/renderer 繞道在進入 renderer 前一律預設拒絕。 | 混合模式 runtime-enforced / fail-closed。 |

**強制力梯度**把三種「拒絕」分清楚:**B1** 拒絕格式不良的結構(retry/repair)·**B2** 移除失敗
〔據典〕的 support edge(可保留 non-supporting〔未驗證引用〕)後續行·**B3** 在 response 邊界預設拒絕。
純 Claude 與可攜模式維持 instruction-enforced。*規劃於 B1/B2,本 PR 未實作:*每次輸出將顯示自身的
強制模式、每個〔據典〕顯示自身的 assurance tier,讓 snapshot 驗證的引文不會被誤認為 edition-backed 引文。

**兩軸交會處。** 軸線 A 的檢索 envelope 由 B1 adapter 轉換為不可變、content-addressed 的
Artifact/Span identity——因此 A 可更換檢索後端而不重寫 persona,B 可提升強制力而不必先建向量庫:

```text
retrieve_envelope() → RetrievalEvidenceAdapterV1 → Artifact + Span → ClaimEvidenceEdge → validator → renderer
```

**發行分工。** 可攜的 **`skills/`** 維持片段式、檔案式、instruction-enforced——人人 clone 後即可跑
的 demo。專案整合版 **`.claude/` + `orchestrator/` + 檢索服務**則養成完整語料、結構化 protocol、
validator 與混合 fail-closed 強制力。兩者共用核心政策,但不共用依賴或強制力保證。兩份
`retrieve.py` 的位元組 parity 是 A0–A1 invariant;A2 分叉時改以共用的 contract-conformance suite 取代。

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
