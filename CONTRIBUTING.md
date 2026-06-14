# Contributing · 參與貢獻

[English](#english) · [繁體中文](#繁體中文)

Thank you for helping grow the council. **The citation rules in
[DISCLAIMER.md](DISCLAIMER.md) are non-negotiable** — please read them before adding any
content. Everything below assumes you follow them.

---

## English

### Ways to contribute

- **Fix or sharpen** an existing persona, quotation, or locator.
- **Add a voice** — a tradition, a denomination, or a historical thinker.
- **Grow the corpus** — more curated, public-domain / openly licensed excerpts.
- **Improve the docs** or the retrieval tooling.

### Keep the distributions and hybrid roster in sync

A persona reference file lives in **two places**, and they differ only in two small ways:

| | `skills/religion-council/references/` (portable) | `.claude/skills/religion-council/references/` (Claude) |
|---|---|---|
| SKILL.md cite | by **English section name** ("Ground Every Position", "Maintain Representation Discipline") | by **number** (`SKILL.md 第三、四節`) |
| `延伸語料` block | **omit** (the portable skill is dependency-free) | **include** pointers to `0X-<傳統>/典籍清單.md` + `思想概要.md` (when that corpus folder exists) |

Keep the persona body otherwise identical between the two copies.

### Persona reference file — template

```markdown
# <Tradition> 議會成員 persona

## 立場與語氣
<voice & tone: how this tradition's teacher speaks; note internal schools to flag>

## 核心概念(發言時可援引)
<core concepts / vocabulary>

## 可引用片段(附出處)
- 〔主題〕「……verbatim quotation……」——《Work》locator(school / version)

## 看「人生意義」的切入點
<how this tradition frames meaning / the human predicament>

## 與其他傳統的張力點(辯論用)
- <genuine tension vs other traditions>

## 引用紀律
遵守 SKILL.md 的 Ground Every Position 與 Maintain Representation Discipline。
```
(For the Claude copy, change the last line to `遵守 SKILL.md 第三、四節。` and add a
`## 延伸語料` block if a corpus folder exists.)

### Adding a Claude sub-agent

Create `.claude/agents/council-<slug>.md`:

```markdown
---
name: council-<slug>
description: 議會的<X>成員。當議會討論需要從<X>角度回應人生意義或哲學問題時使用。通常由 council-moderator 調度。
tools: Read, Bash
---

你是多傳統哲學議會中**代表<X>**的成員,以<X>師長的口吻發言:<tone>。

回應前先讀:
1. `.claude/skills/religion-council/SKILL.md`(共用操作手冊)
2. `.claude/skills/religion-council/references/<file>.md`(你的 persona)

發言規則:
- 嚴守 SKILL.md 第三節:〔據典〕附出處;〔詮釋〕標明。
- 守第四節:保留脈絡;承認內部分歧,不以偏概全。
- 先標出自己在哪一層發言。誠懇、不貶他者。
```

### Wiring a new voice in

1. Add the persona file to **both** `references/` folders (see the sync table).
2. Add the `council-<slug>.md` sub-agent.
3. **Register** it in:
   - `.claude/agents/council-moderator.md` — add to the correct level list (tradition / denomination / thinker).
   - `.claude/skills/religion-council/USAGE.md` — add to the roster and an example prompt.
   - **Routing**: `skills/religion-council/SKILL.md` ("Route References") and
     `.claude/skills/religion-council/SKILL.md` (§五) if you added a new reference file.
4. If you added a new top-level **tradition** with a corpus folder, also register its code in
   both retrieval scripts' `TRADITIONS` maps and add it to
   `orchestrator/panelists/religion-8.json` (or rename that roster if the council no longer has
   eight members).

### Changing the hybrid controller

Mode 3 lives in `orchestrator/` and is exposed to Claude Code through `.mcp.json`.

- Keep the controller compatible with Python 3.9 and the standard library.
- Preserve `threadId` reuse across reply rounds.
- Never bypass the complete-round barrier.
- Keep panelist Codex sessions read-only with approval policy `never`.
- Persist run records under `.religion-council/`, which must remain ignored by Git.
- Add or update `unittest` coverage in `tests/`.

Run:

```bash
python3 -m unittest discover -s tests -v
python3 -m py_compile orchestrator/debate_controller.py \
  scripts/smoke_codex_mcp.py \
  skills/religion-council/scripts/retrieve.py \
  .claude/skills/religion-council/scripts/retrieve.py
```

CI uses the bundled fake Codex MCP server. Before a release or after changing Codex CLI versions,
also run the authenticated, opt-in live check:

```bash
python3 scripts/smoke_codex_mcp.py
```

### Corpus & retrieval metadata

When you add corpus material (now in `references/` / `01–08/`, later behind a vector store),
target the **stable `retrieve.py` output contract** so nothing upstream breaks:

```json
{ "text": "…", "tradition": "buddhism", "school": "漢傳", "work": "般若波羅蜜多心經",
  "locator": "全經", "language": "zh-Hant", "version": "通行本", "category": "宗教經典",
  "label": "Text", "evidence_type": "quotation", "verbatim": true }
```
`category` is either `宗教經典` (religious scripture) or `哲學思想著作` (philosophical work).
Use `evidence_type: quotation` only for text enclosed as a direct quotation; use
`source-bound-summary` for a close summary with a real work and locator. Do not infer `school`
from an arbitrary parenthetical note; register an explicit marker in both retriever copies.

### Pull-request checklist

- [ ] Persona added to **both** `references/` folders; the only differences are the SKILL.md cite + `延伸語料` block.
- [ ] Sub-agent file has valid frontmatter (`name`, `description`, `tools: Read, Bash`).
- [ ] Registered in `council-moderator.md`, `USAGE.md`, and SKILL.md routing.
- [ ] Every `[Text]` line has a real work **and** locator; failed source-bound claims are removed or retained only as non-supporting `[Unverified citation]`, never relabelled as `[Interpretation]`.
- [ ] Sources are public-domain or openly licensed; no copyrighted modern translations.
- [ ] Qur'an passages are labeled as renderings (e.g. 馬堅譯), not the Arabic original.
- [ ] Tested in a **fresh** Claude Code session (sub-agents load at session start).
- [ ] Hybrid-controller changes pass the complete test suite and preserve persistent thread IDs.

---

## 繁體中文

### 可以怎麼幫忙

- **修正/打磨**既有 persona、引文或出處。
- **新增聲音**——一個傳統、教派或歷史人物。
- **擴充語料**——更多公有領域/開放授權的精選片段。
- **改善文件**或檢索工具。

### 維持兩個發行版與混合模式名冊同步

每個 persona reference 檔存在**兩處**,兩者只差兩個小地方:

| | `skills/religion-council/references/`(可攜) | `.claude/skills/religion-council/references/`(Claude) |
|---|---|---|
| SKILL.md 引用 | 用**英文章節名**("Ground Every Position"、"Maintain Representation Discipline") | 用**節次**(`SKILL.md 第三、四節`) |
| `延伸語料` 區塊 | **省略**(可攜 skill 零依賴) | **加入**指向 `0X-<傳統>/典籍清單.md`、`思想概要.md` 的指引(該語料夾存在時) |

除此之外,persona 本文兩份應保持一致。

### Persona reference 檔——範本

```markdown
# <傳統> 議會成員 persona

## 立場與語氣
<語氣:該傳統師長如何發言;標出需註明的內部派系>

## 核心概念(發言時可援引)
<核心概念/語彙>

## 可引用片段(附出處)
- 〔主題〕「……原文引用……」——《書名》出處(系統/版本)

## 看「人生意義」的切入點
<該傳統如何框定意義/人的困境>

## 與其他傳統的張力點(辯論用)
- <與其他傳統的真實張力>

## 引用紀律
遵守 SKILL.md 的 Ground Every Position 與 Maintain Representation Discipline。
```
(Claude 版把最後一行改成 `遵守 SKILL.md 第三、四節。`,並在有語料夾時加 `## 延伸語料` 區塊。)

### 新增 Claude sub-agent

建立 `.claude/agents/council-<slug>.md`:

```markdown
---
name: council-<slug>
description: 議會的<X>成員。當議會討論需要從<X>角度回應人生意義或哲學問題時使用。通常由 council-moderator 調度。
tools: Read, Bash
---

你是多傳統哲學議會中**代表<X>**的成員,以<X>師長的口吻發言:<語氣>。

回應前先讀:
1. `.claude/skills/religion-council/SKILL.md`
2. `.claude/skills/religion-council/references/<file>.md`

發言規則:
- 嚴守 SKILL.md 第三節:〔據典〕附出處;〔詮釋〕標明。
- 守第四節:保留脈絡;承認內部分歧。
- 先標出自己在哪一層發言。誠懇、不貶他者。
```

### 把新聲音接上線

1. 把 persona 檔加進**兩個** `references/` 資料夾(見同步表)。
2. 新增 `council-<slug>.md` sub-agent。
3. **登錄**於:
   - `.claude/agents/council-moderator.md`——加到正確層級清單(傳統/教派/人物)。
   - `.claude/skills/religion-council/USAGE.md`——加進名冊與一則範例。
   - **路由**:若新增了 reference 檔,更新 `skills/religion-council/SKILL.md`(Route References)
     與 `.claude/skills/religion-council/SKILL.md`(第五節)。
4. 若新增的是有語料夾的頂層**傳統**,也要把代碼登錄到兩份 `retrieve.py` 的 `TRADITIONS`,
   並更新 `orchestrator/panelists/religion-8.json`(若不再是八家,亦應重新命名名冊)。

### 修改混合模式 controller

模式 3 位於 `orchestrator/`,並透過 `.mcp.json` 提供給 Claude Code。

- 保持 Python 3.9 與純標準庫相容。
- reply round 必須重用原本 `threadId`。
- 不可繞過全員完成 barrier。
- Codex 議員維持 read-only 與 approval policy `never`。
- 紀錄放在已被 Git 忽略的 `.religion-council/`。
- 在 `tests/` 新增或更新 `unittest`。

```bash
python3 -m unittest discover -s tests -v
python3 -m py_compile orchestrator/debate_controller.py \
  scripts/smoke_codex_mcp.py \
  skills/religion-council/scripts/retrieve.py \
  .claude/skills/religion-council/scripts/retrieve.py
```

CI 使用內附的假 Codex MCP server。發版前或更換 Codex CLI 版本後,另跑已登入的真實測試:

```bash
python3 scripts/smoke_codex_mcp.py
```

### 語料與檢索 metadata

新增語料時(現放 `references/`、`01–08/`,未來在向量庫後),請對齊 **`retrieve.py` 穩定輸出
契約**,讓上層不必改動:

```json
{ "text": "…", "tradition": "buddhism", "school": "漢傳", "work": "般若波羅蜜多心經",
  "locator": "全經", "language": "zh-Hant", "version": "通行本", "category": "宗教經典",
  "label": "Text", "evidence_type": "quotation", "verbatim": true }
```
`category` 為 `宗教經典` 或 `哲學思想著作`。
只有逐字引文才使用 `evidence_type: quotation`;附真實書名與出處的緊貼原文摘要使用
`source-bound-summary`。不可把任意括號備註推斷為 `school`;新增教派標記時須同步兩份
retriever。

### Pull-request 檢查清單

- [ ] persona 已加進**兩個** `references/` 資料夾;差異僅限 SKILL.md 引用方式與 `延伸語料` 區塊。
- [ ] sub-agent frontmatter 正確(`name`、`description`、`tools: Read, Bash`)。
- [ ] 已登錄於 `council-moderator.md`、`USAGE.md` 與 SKILL.md 路由。
- [ ] 每條 `〔據典〕` 都有真實書名**與**出處;失敗的附出處主張須移除,或僅以不構成支持的 `〔未驗證引用〕` 保留,不可改標 `〔詮釋〕`。
- [ ] 來源為公有領域或開放授權;不含受版權保護的現代譯本。
- [ ] 《古蘭經》引文標為釋義(如馬堅譯),非阿拉伯原文。
- [ ] 已在**全新** Claude Code session 測試(sub-agent 於啟動時載入)。
- [ ] 混合 controller 修改已通過完整測試,並維持持久 threadId。
