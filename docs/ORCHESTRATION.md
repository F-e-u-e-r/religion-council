# Hybrid Orchestration · Claude 主持與 Codex 議員

[English](#english) · [繁體中文](#繁體中文)

---

## English

Version v0.1 adds a pre-RAG orchestration layer. It solves scheduling and persistence; it does
not change how religious source material is retrieved.

```text
Claude Code moderator
        |
        | project MCP tools
        v
orchestrator/debate_controller.py
        |
        | codex / codex-reply
        v
codex mcp-server
        |
        +-- persistent Codex thread per panelist
```

## Why it exists

Directly asking a moderator model to create and remember 30 tool-backed conversations is useful
for prototypes but does not reliably enforce:

- exactly one opening result per configured panelist;
- a complete-round barrier;
- bounded concurrency and timeout handling;
- reuse of the original `threadId`;
- durable records of position changes.

The controller makes those mechanics deterministic while leaving judgment and synthesis with
Claude.

## MCP tools

| Tool | Responsibility |
|---|---|
| `debate_start` | Load a JSON roster, create independent Codex conversations concurrently, and wait for the Round 1 barrier. |
| `debate_collect` | Return one round in pages of at most 50 results. |
| `debate_reply` | Send an anonymized issue matrix to every original `threadId`; refuses to run unless the previous round is complete. |
| `debate_retry` | Retry only failed panelists while preserving successful results. |
| `debate_status` | Report round state, counts, failures, and the persisted state path. |

The controller keeps one `codex mcp-server` subprocess alive for the Claude MCP session and uses
concurrent JSON-RPC `tools/call` requests. Panelists are instructed not to delegate, run in
read-only sandboxes, and use approval policy `never`.

## Panelist rosters

Rosters use JSON to stay dependency-free:

```json
{
  "panelists": [
    {
      "id": "security",
      "role": "security-first engineer",
      "priorities": ["least privilege", "adversarial abuse"],
      "reference": "optional/path/relative/to/repo.md"
    }
  ]
}
```

Included rosters:

- `orchestrator/panelists/religion-8.json`: the eight broad Religion Council perspectives;
- `orchestrator/panelists/thirty-member-example.json`: a generic 30-member decision panel.

## Persisted state

Each run writes `.religion-council/runs/<run-id>/state.json`. It includes:

- question and evidence packet;
- panelist IDs, roles, and source reference paths;
- every received `thread_id`;
- per-round responses, attempts, request tokens, and timestamps;
- barrier status and failures;
- the issue matrix used for each reply round.

The directory is intentionally ignored by Git because transcripts may contain user-supplied or
sensitive material.

## Failure semantics

- A round is `complete` only when every configured panelist succeeded.
- `debate_reply` refuses to advance from a failed or running round.
- Each individual tool call supports bounded retries with exponential backoff.
- `debate_retry` reruns only failed entries.
- There is no application-level idempotency key in the current Codex MCP tool schema. A timeout
  after server-side thread creation can therefore leave an unrecorded orphan thread. Request
  tokens aid diagnosis, but the interface cannot guarantee exact-once execution.
- `codex mcp-server` is marked Experimental in the current Codex CLI reference. Pin and retest
  Codex versions before production deployment.

## Live MCP validation

The automated suite uses `tests/fake_codex_mcp.py` so CI remains deterministic and does not
consume an authenticated Codex session. Before a release or after upgrading Codex CLI, run one
opt-in live create/reply check:

```bash
python3 scripts/smoke_codex_mcp.py
```

The script starts the configured `codex mcp-server`, creates one read-only conversation, calls
`codex-reply` with the returned `threadId`, and fails unless the same thread is reused. Override
the executable when needed with `CODEX_COMMAND="/path/to/codex mcp-server"`.

## Security boundary

The controller is intentionally local and dependency-free. It does not expose an HTTP listener.
Claude Code launches it through project-scoped stdio MCP configuration. Codex panelists receive
only the shared prompt and their configured reference packet, and they cannot write to the
workspace under the controller's default settings.

## Sources

- OpenAI, [Use Codex with the Agents SDK](https://developers.openai.com/codex/guides/agents-sdk)
- OpenAI, [Codex CLI reference](https://developers.openai.com/codex/cli/reference)
- Anthropic, [Connect Claude Code to tools via MCP](https://code.claude.com/docs/en/mcp)
- Anthropic, [Create custom subagents](https://code.claude.com/docs/en/sub-agents)

---

## 繁體中文

v0.1 新增的是 **RAG 之前**的調度層:它處理併發、threadId、barrier、retry 與紀錄,不改變宗教
語料的檢索方式。

Claude Code 透過專案 `.mcp.json` 呼叫 `debate_controller.py`;controller 再呼叫
`codex mcp-server` 的 `codex` / `codex-reply` tools。每位議員有獨立且持久的 Codex thread,
Claude 只負責主持、匿名 issue matrix 與最終綜合。

核心保證:

- Round 1 未全員完成,不可進 Round 2。
- Round 2 必須使用原本相同的 `threadId`。
- 失敗只重試失敗者,不覆蓋成功結果。
- 結果分頁讀取,避免一次把 30 份 transcript 塞進 Claude context。
- 紀錄原子寫入 `.religion-council/runs/<run-id>/state.json`,且不 commit。

目前 Codex MCP tool schema 沒有應用層 idempotency key;若 server 已建立 thread,但 response 在
timeout 前未回到 controller,重試仍可能留下未登記的孤立 thread。因此現階段不能宣稱
exact-once。`codex mcp-server` 目前亦標為 Experimental,正式部署前應固定版本並重新測試。

自動測試使用 `tests/fake_codex_mcp.py`,避免 CI 依賴登入狀態或消耗 Codex session。發版前或
升級 Codex CLI 後,應另跑一次真實 create/reply smoke test:

```bash
python3 scripts/smoke_codex_mcp.py
```

此腳本會建立一條 read-only Codex conversation,再以回傳的 `threadId` 呼叫 `codex-reply`,
並驗證第二輪仍使用同一 thread。
