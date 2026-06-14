# Religion Council · 多傳統哲學議會

> A source-grounded, moderated roundtable across the world's major religious and
> philosophical traditions — as a drop-in skill for AI coding agents.
>
> 以原典為據、由中立主持人調度的「跨傳統哲學議會」——可直接掛載到 AI coding agent 的 skill。

![code: MIT](https://img.shields.io/badge/code-MIT-blue.svg)
![content: CC BY 4.0](https://img.shields.io/badge/content-CC%20BY%204.0-lightgrey.svg)
![runs on: Codex · Claude Code · any agent](https://img.shields.io/badge/runs%20on-Codex%20·%20Claude%20Code%20·%20any%20agent-green.svg)
![version: v0.2.0](https://img.shields.io/badge/version-v0.2.0-orange.svg)

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

Version **v0.2.0** supports three execution modes:

1. **Claude Code only** — 35 specialized Claude agents (1 moderator + 34 voices).
2. **Codex only** — a portable Codex skill, with native Codex subagents when requested.
3. **Claude moderator + Codex panelists** — a deterministic Python MCP controller manages
   persistent Codex threads, barriers, retries, and audit records.

All three modes share one quote-admissibility policy (`quote-admissibility/v1`), but the
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
├── VERSION                       # current release: v0.2.0
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

The whole plan pivots on **one seam — `retrieve.py`'s output contract.** Keep that fixed and
the personas never need to change.

| Phase | What | Retrieval |
|---|---|---|
| **0 — Curated council** *(today)* | Voices quote hand-picked snippets in `references/`. Works fully offline, in any agent. | `retrieve.py` parses and lexically ranks cited reference entries. |
| **0.5 — Deterministic hybrid panel** *(v0.1)* | Claude moderates persistent Codex MCP panelists through a local controller with barriers, retries, and JSON records. | Still file-based; no embeddings required. |
| **1 — Deeper corpus** | Expand `references/` and fill out `01–08/典籍清單.md` + `思想概要.md` with more curated, public-domain / openly-licensed excerpts + metadata. | Still file-based. |
| **2 — Full 典籍 + local index** | Store complete public-domain / open scriptures in-repo, chunked by book/chapter/verse; build an embedding index; rewrite `retrieve.retrieve()` as real similarity search. | Local vector search — **same output contract**, so `SKILL.md` and all 34 voices are untouched. |
| **3 — RAG server** | Move the index behind a retrieval service (vector DB + embeddings); `retrieve.py` becomes a thin client. Optionally expose the council itself as an API/app. | Networked retrieval — still the same contract. |

**Suggested split for the roadmap:** keep the **portable `skills/` distribution snippet-based
and dependency-free** (it's the demo anyone can run anywhere), and grow the
**`.claude/` project side into the full RAG system**. They share `references/` today and
diverge in purpose as the corpus scales.

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

目前 **v0.2.0** 支援三種執行方式:

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

整套計畫的樞紐只有一個:**`retrieve.py` 的輸出契約**。守住它,persona 就永遠不必改。

| 階段 | 內容 | 檢索 |
|---|---|---|
| **0 — 精選議會**(現在) | 各成員引用 `references/` 中手選片段,離線、任何 agent 皆可跑。 | `retrieve.py` 解析並以詞彙比對排序附出處片段。 |
| **0.5 — 可重現混合 panel**(v0.1) | Claude 主持持久 Codex MCP 議員;controller 管理 barrier、retry 與 JSON 紀錄。 | 仍為檔案式,不需要 embedding。 |
| **1 — 加厚語料** | 擴充 `references/`,把 `01–08/典籍清單.md`、`思想概要.md` 補上更多公有領域/開放授權的精選片段與 metadata。 | 仍為檔案式。 |
| **2 — 完整典籍 + 本地索引** | 把公有領域/開放典籍全文入庫(按書/章/節切分),建嵌入索引,改寫 `retrieve.retrieve()` 為真正相似度檢索。 | 本地向量檢索——**契約不變**,故 `SKILL.md` 與 34 個聲音原封不動。 |
| **3 — RAG server** | 把索引移到檢索服務(向量庫+嵌入),`retrieve.py` 變薄客戶端;亦可把議會本身做成 API/應用。 | 網路檢索——仍是同一契約。 |

**藍圖建議:** 讓可攜的 `skills/` 發行版**維持片段式、零依賴**(它是人人皆可跑的 demo),
把 **`.claude/` 專案端養成完整 RAG 系統**。兩者今日共用 `references/`,隨語料規模擴大而分工。

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
