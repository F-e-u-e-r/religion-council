# Install & Use · 安裝與使用

[English](#english) · [繁體中文](#繁體中文)

---

## English

Religion Council supports three execution modes:

| Mode | Moderator | Panelists | Best for |
|---|---|---|---|
| **1. Claude Code** | Claude | Claude custom subagents | Native Claude workflow with the bundled 37-agent roster. |
| **2. Codex** | Codex | Native Codex subagents when explicitly requested | Portable Codex skill and direct Codex use. |
| **3. Claude + Codex** | Claude | Persistent Codex MCP threads | Deterministic fan-out, round barriers, retries, and persisted audit records. |

A0 and the controller require no third-party Python packages. Mode 3 uses the currently
experimental `codex mcp-server` surface, so production use should retain timeout, retry, and
failure handling.

## Prerequisites

- Git
- Python 3.9 or newer for file-based retrieval and the Mode 3 controller
- Claude Code for Modes 1 and 3
- Codex CLI, authenticated with `codex login`, for Modes 2 and 3

Clone the repository:

```bash
git clone https://github.com/F-e-u-e-r/religion-council.git
cd religion-council
```

## Mode 1 — Claude Code

Start Claude Code at the repository root:

```bash
claude
```

Claude Code loads `.claude/agents/` and `.claude/skills/religion-council/`. Ask:

> 用議會討論:人生有沒有意義?請佛教、道教、儒家三家先各自陳述,再交叉辯論。

The `council-moderator` dispatches the selected `council-*` custom subagents and synthesizes
their responses. Custom subagents are loaded at session start; restart Claude Code after adding
or changing an agent definition.

## Mode 2 — Codex

Install the portable skill from GitHub:

```text
Use $skill-installer to install the skill from
https://github.com/F-e-u-e-r/religion-council/tree/main/skills/religion-council
```

Restart Codex, then invoke:

> Use $religion-council to convene a sourced roundtable on whether life has meaning.

To request native parallel panelists explicitly:

> Use $religion-council. Spawn one independent Codex agent for each of the eight traditions,
> keep Round 1 independent, then conduct one rebuttal round.

### Configure native Codex agent capacity

Codex reads personal defaults from `~/.codex/config.toml`. A trusted repository can also use
`.codex/config.toml` for project-scoped settings. Add:

```toml
[agents]
max_threads = 36
max_depth = 1
job_max_runtime_seconds = 1800
```

- `max_threads` caps simultaneously open native Codex agent threads. The documented default is
  6, so a full eight-member native council needs at least 8.
- `max_depth = 1` allows the moderator to create panelists but prevents panelists from recursively
  creating more agents.
- `job_max_runtime_seconds` controls CSV fan-out workers; it does not set the lifetime of ordinary
  persistent `spawn_agent` threads.

Preserve the rest of an existing TOML file. Validate it with:

```bash
codex doctor --summary
```

Restart Codex after changing configuration. Do not commit a personal `~/.codex/config.toml`, and
do not copy secrets or machine-specific MCP paths into project configuration.

## Mode 3 — Claude Moderator + Codex Panelists

This repository includes a project-level `.mcp.json` that starts:

```text
Claude moderator
       |
       v
Religion Council controller (Python MCP server)
       |
       v
codex mcp-server
       |
       +-- persistent Codex thread 01
       +-- persistent Codex thread 02
       +-- ...
```

The controller exposes:

- `debate_start`: create one independent Codex thread per panelist and wait at the Round 1 barrier;
- `debate_collect`: read responses in bounded batches;
- `debate_finalize`: construct the strict textual-authority surface after collection;
- `debate_reply`: send an anonymized issue matrix to the same `threadId` values;
- `debate_retry`: retry only failed panelists;
- `debate_status`: inspect barriers and persisted state.

`debate_start` also has an opt-in B1b structured path: pass `structured_claims=true` with an
`evidence_envelope` from `retrieve_envelope(...)`. The controller will render compact evidence
seed IDs into the prompt, parse and schema-check `religion-council/claim/v1`, repair or drop
malformed payloads, and persist bound claims. To enable B2 claim validation, also pass
`verify_claims=true`; quotation edges are checked against curated evidence snapshots,
source-bound summaries validate by evidence edge, and per-claim outcomes are written under
`claim_verification`. B1b bindings remain `verification_state = "unverified"`, and the
controller is still not fail-closed. To enable B3, also pass `fail_closed=true`; the
controller writes a `boundary_decision` that default-denies unknown claim types,
unvalidated `[Text]`, missing verification, and unsupported protocols before rendering.

### Strict finalization (v0.9.0)

Strict mode is an opt-in hybrid-controller workflow. It requires Python 3.9+, an authenticated
Codex CLI (`codex login`), and an approved `religion-council-controller` project MCP server in
Claude Code. It also requires a `religion-council/retrieval/v1` `evidence_envelope`; there is no
degraded strict path without one.

Obtain the envelope from the retrieval seam. It must include `contract_version` and a `records`
array; each record must at least provide `text`, with source metadata such as `work`, `locator`,
`tradition`, `evidence_type`, `verbatim`, `source_file`, and `source_line` when available:

```json
{
  "contract_version": "religion-council/retrieval/v1",
  "records": [
    {
      "text": "克己復禮為仁",
      "tradition": "confucianism",
      "work": "論語",
      "locator": "顏淵",
      "evidence_type": "quotation",
      "verbatim": true,
      "source_file": "references/confucianism.md",
      "source_line": 1
    }
  ]
}
```

In the moderator session, invoke the public MCP tools in this order (replace the roster and
question as needed):

```text
debate_start({
  question: "What does Confucius mean by ren?",
  panelists_file: "orchestrator/panelists/religion-8.json",
  profile: "strict",
  evidence_envelope: <the retrieval envelope above>
})

debate_collect({ run_id: <run_id>, limit: 50 })

debate_finalize({ run_id: <run_id> })
```

Immediately after strict `debate_start` and after `debate_collect`, the state reports
`finalization_required=true` and `finalized=false`; collection has no finalized Surface A. A
successful `debate_finalize` returns deterministic Surface A, a non-removable Surface B frame,
separate audit data, and `finalized=true`. Surface A contains only admitted, verified claims and
uses canonical snapshot text rather than panelist-supplied quotation text.

`profile="strict"` turns on `structured_claims`, `verify_claims`, and `fail_closed`. Omit those
three flags when using strict mode; omitted flags are enabled by the profile. An explicit
`structured_claims=false`, `verify_claims=false`, or `fail_closed=false` is a configuration error.
Supplying strict without an `evidence_envelope` also fails fast. If the profile is not strict,
`debate_finalize` still requires a fail-closed run and the default hybrid path remains unchanged
and unfinalized.

For an offline, deterministic [strict finalization example](examples/strict-finalization/README.md)
that asserts the state transitions, canonical quotation source, representation metadata, Surface B
frame, denied-payload separation, and atomic failure, run:

```bash
python3 examples/strict-finalization/run_example.py
```

Run:

```bash
codex login
claude
```

In Claude Code, open `/mcp` and approve `religion-council-controller` if the project server is
pending. Then ask:

> Act as the moderator. Use the religion-council-controller MCP tools with
> `orchestrator/panelists/religion-8.json`. Start an independent opening round on whether life
> has meaning, collect all results, build an anonymized issue matrix, run one reply round on the
> same Codex threads, and produce the final synthesis.

For a generic 30-member panel, use
`orchestrator/panelists/thirty-member-example.json`. Customize that JSON instead of embedding a
large roster in the moderator prompt.

Run records are written atomically under `.religion-council/runs/<run-id>/state.json` and are
ignored by Git. Each Codex panelist runs read-only with approval policy `never`.

Before relying on Mode 3 after installing or upgrading Codex CLI, run one authenticated live
create/reply check:

```bash
python3 scripts/smoke_codex_mcp.py
```

### Direct Codex MCP, without the controller

Claude Code can also consume the raw Codex server:

```bash
claude mcp add --scope project codex -- codex mcp-server
claude mcp get codex
```

This exposes `codex` and `codex-reply` directly. It is useful for prototypes, but Claude must
then remember all thread IDs and enforce barriers itself. The bundled controller is the
recommended Mode 3 path for fixed panel counts and multiple rounds.

### Important retry limitation

MCP tool calls do not provide an application-level idempotency key. If a request times out after
Codex has already created a thread but before the controller receives its response, a retry may
create an orphan duplicate thread. The controller adds request tokens and persists every received
result, but exact-once execution cannot be guaranteed by the current experimental interface.

## Retrieval Stub

The current dependency-free lexical retrieval can be tested independently:

```bash
python3 skills/religion-council/scripts/retrieve.py \
  --tradition buddhism --query "the meaning of life"
```

Valid codes: `christianity`, `islam`, `hinduism`, `buddhism`, `taoism`, `legalism`,
`confucianism`, and `mohism`.

---

## 繁體中文

Religion Council 支援三種執行方式:

| 模式 | 主持人 | 議員 | 適合 |
|---|---|---|---|
| **1. Claude Code** | Claude | Claude custom subagent | 使用內附 37 個 agent 的 Claude 原生流程。 |
| **2. Codex** | Codex | 明確要求時使用 Codex 原生 subagent | 可攜 Codex skill 與直接使用 Codex。 |
| **3. Claude + Codex** | Claude | 持久化 Codex MCP thread | 固定併發、輪次 barrier、重試與完整紀錄。 |

A0 階段與 controller 都不需要第三方 Python 套件。模式 3 使用目前仍標為 Experimental 的
`codex mcp-server`,正式使用時必須保留 timeout、retry 與失敗處理。

## 前置需求

- Git
- Python 3.9 或以上
- 模式 1、3 需要 Claude Code
- 模式 2、3 需要已透過 `codex login` 登入的 Codex CLI

```bash
git clone https://github.com/F-e-u-e-r/religion-council.git
cd religion-council
```

## 模式 1 — Claude Code

在 repo 根目錄執行:

```bash
claude
```

Claude Code 會載入 `.claude/agents/` 與 `.claude/skills/religion-council/`。例如:

> 用議會討論:人生有沒有意義?請佛教、道教、儒家三家先各自陳述,再交叉辯論。

`council-moderator` 會調度指定的 `council-*` custom subagent。新增或修改 agent 定義後,
需重開 Claude Code session。

## 模式 2 — Codex

請 Codex 從 GitHub 安裝:

```text
Use $skill-installer to install the skill from
https://github.com/F-e-u-e-r/religion-council/tree/main/skills/religion-council
```

重開 Codex 後呼叫:

> Use $religion-council to convene a sourced roundtable on whether life has meaning.

若要使用原生平行 agent,須明確要求:

> Use $religion-council. Spawn one independent Codex agent for each of the eight traditions,
> keep Round 1 independent, then conduct one rebuttal round.

### 設定 Codex 原生 agent 容量

個人設定放在 `~/.codex/config.toml`;受信任的 repo 亦可用 `.codex/config.toml`。加入:

```toml
[agents]
max_threads = 36
max_depth = 1
job_max_runtime_seconds = 1800
```

- `max_threads`:Codex 原生 agent 同時開啟的 thread 上限;官方文件列出的預設值是 6,八人完整
  議會至少需設為 8。
- `max_depth = 1`:主持人可建立議員,但議員不可再遞迴建立 agent。
- `job_max_runtime_seconds`:只控制 CSV fan-out worker,並非普通持久 `spawn_agent` thread 的
  存活時間。

保留 TOML 內其他既有設定,並驗證:

```bash
codex doctor --summary
```

修改後重開 Codex。不要把個人的 `~/.codex/config.toml`、密鑰或機器專用路徑 commit 到 repo。

## 模式 3 — Claude 主持 + Codex 議員

Repo 內的 `.mcp.json` 會啟動 Python controller,再由 controller 管理 `codex mcp-server`:

```text
Claude 主持人
    → Religion Council controller
    → codex mcp-server
    → 多條持久 Codex thread
```

Controller 提供 `debate_start`、`debate_collect`、`debate_finalize`、`debate_reply`、`debate_retry`、
`debate_status` 六個 MCP tools。它會保存 `panelist ID ↔ threadId`、等待全員完成才跨過
round barrier,並把紀錄寫到 `.religion-council/runs/<run-id>/state.json`。

`debate_start` 另有 opt-in B1b 結構化路徑:同時傳入 `structured_claims=true` 與
`retrieve_envelope(...)` 產生的 `evidence_envelope`。Controller 會把 compact evidence seed ID
放進 prompt,解析並 schema-check `religion-council/claim/v1`,對格式錯誤 payload 執行 repair 或
drop,再把有效 claim 綁定至 evidence seeds 並寫入 state。若要啟用 B2 claim 驗證,再傳入
`verify_claims=true`;quotation edge 會對 curated evidence snapshot 驗證,source-bound summary 以
evidence edge 驗證,每個 claim 的結果寫在 `claim_verification`。B1b binding 仍保持
`verification_state = "unverified"`。若要啟用 B3,再傳入 `fail_closed=true`;controller 會寫入
`boundary_decision`,並在 render 前預設拒絕未知 claim type、未驗證〔據典〕、缺驗證與不支援
protocol。

### Strict finalization（v0.9.0）

strict mode 是 opt-in 的 hybrid-controller workflow。它需要 Python 3.9+、已用 `codex login`
登入的 Codex CLI，以及在 Claude Code 中已批准的 `religion-council-controller` project MCP server。
它也必須提供 `religion-council/retrieval/v1` 的 `evidence_envelope`；沒有 evidence envelope 時不會
降級執行 strict。

envelope 由 retrieval seam 取得，必須包含 `contract_version` 與 `records` array；每筆 record 至少要
有 `text`，並應帶 `work`、`locator`、`tradition`、`evidence_type`、`verbatim`、`source_file`、
`source_line` 等來源 metadata：

```json
{
  "contract_version": "religion-council/retrieval/v1",
  "records": [
    {
      "text": "克己復禮為仁",
      "tradition": "confucianism",
      "work": "論語",
      "locator": "顏淵",
      "evidence_type": "quotation",
      "verbatim": true,
      "source_file": "references/confucianism.md",
      "source_line": 1
    }
  ]
}
```

在 moderator session 依序呼叫公開 MCP tools（可按需要更換 roster 與問題）：

```text
debate_start({
  question: "What does Confucius mean by ren?",
  panelists_file: "orchestrator/panelists/religion-8.json",
  profile: "strict",
  evidence_envelope: <上面的 retrieval envelope>
})

debate_collect({ run_id: <run_id>, limit: 50 })

debate_finalize({ run_id: <run_id> })
```

strict `debate_start` 後及 `debate_collect` 後，state 都是 `finalization_required=true`、
`finalized=false`；collect 不會產生 finalized 的 Surface A。`debate_finalize` 成功後回傳
deterministic Surface A、不可移除的 Surface B frame、分離的 audit data，且 `finalized=true`。
Surface A 只含 admitted、verified claim，quotation 文字取自 canonical snapshot，不取 panelist
提供的文字。

`profile="strict"` 會自行開啟 `structured_claims`、`verify_claims`、`fail_closed`。strict mode 時
不要傳這三個 flags；省略時由 profile 啟用。明確傳入 `structured_claims=false`、
`verify_claims=false` 或 `fail_closed=false` 會是 configuration error。strict 缺少
`evidence_envelope` 亦會 fail fast。非 strict run 的 `debate_finalize` 仍要求 fail-closed run，預設
hybrid path 不變且未 finalized。

要離線、deterministic 地檢查 state transitions、canonical quotation source、representation metadata、
Surface B frame、denied payload 分離與 atomic failure，見
[strict finalization example](examples/strict-finalization/README.md)，再執行：

```bash
python3 examples/strict-finalization/run_example.py
```

```bash
codex login
claude
```

在 Claude Code 用 `/mcp` 批准 `religion-council-controller`,然後說:

> 請擔任主持人,使用 religion-council-controller MCP tools 和
> `orchestrator/panelists/religion-8.json`,讓八個 Codex 議員獨立完成首輪;收齊後建立匿名
> issue matrix,再用相同 threadId 跑第二輪,最後綜合。

通用 30 人 panel 可使用 `orchestrator/panelists/thirty-member-example.json`。

安裝或升級 Codex CLI 後,先跑一次已登入的真實 create/reply 測試:

```bash
python3 scripts/smoke_codex_mcp.py
```

也可以直接加入原始 Codex MCP:

```bash
claude mcp add --scope project codex -- codex mcp-server
claude mcp get codex
```

此時 Claude 直接看到 `codex` 與 `codex-reply`,但要自行保存 threadId、執行 barrier 與重試。
需要固定人數及多輪時,建議使用內附 controller。

注意:MCP tool call 目前沒有應用層 idempotency key。若 Codex 已建立 thread、但回應在 timeout
前未送回,重試可能留下孤立的重複 thread。Controller 會加入 request token 並保存已收到的結果,
但現階段 Experimental 介面仍無法保證 exact-once。

## 檢索 Stub

```bash
python3 skills/religion-council/scripts/retrieve.py \
  --tradition buddhism --query "人生的意義"
```

有效代碼:`christianity`、`islam`、`hinduism`、`buddhism`、`taoism`、`legalism`、
`confucianism`、`mohism`。
