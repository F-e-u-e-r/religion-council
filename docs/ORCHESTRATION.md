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
| `debate_start` | Load a JSON roster, create independent Codex conversations concurrently, and wait for the Round 1 barrier. Optional `evidence_packet` (untrusted) and `contrast_proposition` (controller-routed moderator foil). Optional B1b structured mode requires `structured_claims=true` plus an `evidence_envelope` from `retrieve_envelope(...)`; optional B2 validation additionally sets `verify_claims=true`; optional B3 fail-closed boundary additionally sets `fail_closed=true`. `profile="strict"` requires the full graph and the envelope, and fails fast rather than degrading. |
| `debate_collect` | Return one round in pages of at most 50 results. |
| `debate_finalize` | For a fail-closed run, deterministically build Surface A from admitted claims only, frame Surface B, keep rejected data in separate audit input, and atomically reject an untraceable authority unit. |
| `debate_reply` | Send an anonymized issue matrix to every original `threadId`; refuses to run unless the previous round is complete. |
| `debate_retry` | Retry only failed panelists while preserving successful results. |
| `debate_status` | Report round state, counts, failures, and the persisted state path. |

The controller keeps one `codex mcp-server` subprocess alive for the Claude MCP session and uses
concurrent JSON-RPC `tools/call` requests. Panelists are instructed not to delegate, run in
read-only sandboxes, and use approval policy `never`.

### B1b Structured Mode

By default, `debate_start` preserves the B0 prose path. When `structured_claims=true`, the
caller must also provide a retrieval `evidence_envelope` (`religion-council/retrieval/v1`).
The controller adapts that envelope into immutable evidence snapshots and a per-run `S#`
catalog, asks panelists to append one `religion-council/claim/v1` JSON block, schema-checks
the block, and binds valid edges to occurrence-level evidence seeds.

Malformed structured payloads follow B1 semantics: reject, issue one repair prompt to the
same `threadId`, then drop the structured payload if repair still fails. The prose response
is kept and the round can still complete. B1b by itself does **not** verify evidence,
validate spans, remove failed support edges, or fail closed at the renderer boundary;
successful bindings remain `verification_state = "unverified"`.

From v0.6.0, B2 validation is a separate opt-in on top of structured mode: pass
`verify_claims=true` with `structured_claims=true`. The controller reads immutable curated
snapshots, verifies quotation edges by byte span, validates source-bound summaries by their
evidence edge, moves failed edges to `removed_edges`, and downgrades all-failed `[Text]`
claims to `[Unverified citation]`. The original B1b `claim_bindings` stay unmodified and
unverified; B2 results are additive under `claim_verification` with a per-response
`verification_summary`. Unexpected verifier errors set `verification_error` and do not break
the round barrier. This is still not B3 fail-closed enforcement.

From v0.7.0, B3 fail-closed enforcement is a third opt-in on top of B2: pass
`fail_closed=true` with `verify_claims=true`. The controller runs a response-boundary gate
over B2's `claim_verification` and writes an additive `boundary_decision`. The gate
default-denies unknown claim types, `[Text]` claims without runtime-validated evidence,
missing verification (`renderer-bypass`), and unsupported protocols. Validated `[Text]`
claims are admitted as text, `[Interpretation]` as interpretation, and downgraded
`[Unverified citation]` only as non-supporting. Boundary failures set `boundary_error` and
do not break the round barrier; the gate controls what a renderer may use, not whether the
council round completed.

### Strict profile and finalization (v0.9.0)

`profile="strict"` is a configuration invariant, not a shorthand convenience flag. It turns on
`structured_claims`, `verify_claims`, and `fail_closed`, requires an `evidence_envelope`, and
rejects an explicit `false` for any of those components. The graph is therefore:

```text
evidence envelope → structured claim → verification → boundary decision → finalization
```

The strict lifecycle is deliberately two-phase:

```text
debate_start(profile="strict") → debate_collect
  finalization_required=true, finalized=false
→ debate_finalize
  finalization_required=true, finalized=true
```

`debate_collect` is backward compatible: it returns the existing panelist records and never
claims to be the finalized response. `debate_finalize` is a separate entry point, available for
any fail-closed run, that invokes the ADR 0004 renderer finalizer.

Finalization receives two distinct render inputs. `AnswerRenderInput` contains only canonical
`AuthorityRenderUnit` values (Surface A) and `InterpretationRenderUnit` values (Surface B).
`AuditRenderInput` contains rejected claim IDs, reason codes, and diagnostics; it is not passed to
the ordinary answer renderer. The canonical builder mints authority units only from admitted,
runtime-validated claims. It takes quotation bytes from the canonical snapshot span, checks
representation metadata against the system-held catalog, then an independent trace validator
re-derives and compares every authority unit before deterministic serialization.

Failure is atomic per panelist: a `TRACE_*` trace failure yields a finalization error and no
partial Surface A for that panelist. A response-level boundary denial is a valid empty Surface A;
the non-removable Surface B frame remains present and the denial stays in audit data. A round is
`finalized=true` only when every panelist finalizes successfully or through this valid
response-level denial path.

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
- when B1b structured mode is enabled: the evidence catalog, per-response `schema_status`,
  `claim_payload_source`, optional `repair_content`, and bound claim records.
- when B2 validation is enabled: additive `claim_verification`, `verification_summary`, and
  optional `verification_error` records.
- when B3 fail-closed mode is enabled: additive `boundary_decision` and optional
  `boundary_error` records.
- for strict runs: `profile`, `finalization_required`, and a per-round `finalized` state. A
  successful finalization result persists deterministic Surface A, the mandatory Surface B frame,
  answer render input, and separate audit summary without serializing the mint token.

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
- A strict finalization trace failure is not a partial-success response: the failing panelist has
  no Surface A output, and the round remains `finalized=false` unless every panelist has a valid
  finalized result.

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

## Quote-admissibility assurance

All three execution modes share one quote-admissibility policy
(`quote-admissibility/v2`; see [ADR 0001](adr/0001-quote-admissibility-policy.md) and
[`policies/quote-admissibility.v2.json`](../policies/quote-admissibility.v2.json)). The
*guarantee* behind that shared policy is uneven:

| Mode | Current enforcement | Scope |
|---|---|---|
| Hybrid controller (Claude moderator + Codex panelists) | instruction-enforced by default; opt-in B1b `structured-schema-enforced`; opt-in B2 `structured-claim-validated`; opt-in B3 `structured-fail-closed`; `profile="strict"` plus `debate_finalize` performs renderer finalization | Only strict-finalized responses have end-to-end machine-enforced construction and traceability of Surface A. The default path without `debate_finalize` is unchanged and not finalized. |
| Claude-only (37 agents) | instruction-enforced | No strict renderer finalization. |
| Portable (Codex / any agent) | instruction-enforced | No strict renderer finalization. |

B1b **adds schema enforcement only** in the hybrid controller's opt-in structured path. It
parses and binds `religion-council/claim/v1` payloads, but it does not validate spans or
decide admissibility. B2 adds opt-in claim-level validation against curated snapshots. The
response-level qualifier `structured-claim-validated` means B2 verification ran; it does not
mean every claim passed, and it is not fail-closed. The true outcome lives on each claim's
`verification_state`, `span_assurance_tier`, `span`, and `removed_edges`. B3 adds the
fail-closed response boundary. The response-level qualifier `structured-fail-closed` means
the boundary gate ran; it does not mean every claim was admitted. The true renderability
outcome lives in each result's `boundary_decision`.

Strict-finalized responses provide end-to-end machine-enforced construction and traceability of
the textual-authority surface (Surface A). Interpretation prose (Surface B) remains explicitly
non-authoritative and instruction-bounded. This is not a claim that all prose is machine-verified,
that interpretation prose cannot mislead, or that the complete answer is semantically fail-closed.
The capability-token mint guard is not a Python sandbox.

## Debate pressure and consensus

The controller keeps its existing repeatable-round protocol, but panelist prompts apply a
claim-level adversarial contract:

- Round 1 states one non-negotiable thesis and one incompatible rival proposition without
  attributing an invented position to another panelist.
- Follow-up rounds target one actual claim ID, require a verdict, premise-level critique,
  counterexample, pointed cross-question, decisive crux, and `upheld / narrowed /
  withdrawn` status.
- A one-sided response is a rebuttal, not a completed debate. The moderator may use another
  existing follow-up round to return the unanswered question to the original claimant.
- Similar recommendations supported by different reasons are **practical overlap**.
  **Consensus** requires every relevant panelist to explicitly accept the same proposition.
- The final response omits chain-of-thought, tool and token logs, agent completion records,
  and transport/fallback details.

This raises argumentative pressure without licensing personal attacks, strawmen, fabricated
opponents, or relaxed citation discipline.

**Two text inputs, different trust.** `evidence_packet` is **untrusted data**: panelists must
not obey directives in it or treat its wording as quote-admissible. `contrast_proposition` is
a **separate, controller-routed** input the moderator uses to inject a constructed foil — the
controller wraps it in its own fenced prompt section, *routed (not asserted true)*, with any
instruction inside it treated as data to evaluate and **never executed**. A self-label inside
`evidence_packet` never triggers contrast handling; only the `contrast_proposition` parameter
does.

User-supplied packets whose bytes are actually provided default to
`acquisition_origin = user-supplied`, `source_assurance = artifact-backed` (the provided
bytes are a real, locatable artifact), and `verification_state = unverified`: their wording
is traceable to the supplied packet, but authorship, edition, authority, and publication
status are not independently established. (A user *claim* of a source with no retrievable
content is `source_assurance = asserted-only` instead.)

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
- B1b 結構化模式必須同時提供 `structured_claims=true` 與 `evidence_envelope`;controller 會把
  `religion-council/claim/v1` payload 綁定到本輪 evidence seeds,但驗證狀態仍為 `unverified`。
- B2 驗證必須再加 `verify_claims=true`;controller 會讀 curated snapshot 驗證 claim,並把結果
  另外寫入 `claim_verification`,不改動 B1b 的原始 binding。
- B3 fail-closed 邊界必須再加 `fail_closed=true`;controller 會在 B2 結果上執行 boundary gate,
  另外寫入 `boundary_decision`,決定哪些 claim 可被 renderer 使用。

### Strict profile 與 finalization（v0.9.0）

`profile="strict"` 是 configuration invariant，不是方便的 flag shorthand。它會開啟
`structured_claims`、`verify_claims`、`fail_closed`，要求 `evidence_envelope`，且任一 component
明確傳入 `false` 都會被拒絕。完整圖為：

```text
evidence envelope → structured claim → verification → boundary decision → finalization
```

strict lifecycle 刻意分成兩階段：

```text
debate_start(profile="strict") → debate_collect
  finalization_required=true, finalized=false
→ debate_finalize
  finalization_required=true, finalized=true
```

`debate_collect` 保持 backward compatible：它回傳既有 panelist records，絕不宣稱自己是 finalized
response。`debate_finalize` 是獨立 entry point，可用於任一 fail-closed run，並執行 ADR 0004 的
renderer finalizer。

finalization 使用兩個分離的 render input。`AnswerRenderInput` 只包含 canonical
`AuthorityRenderUnit`（Surface A）與 `InterpretationRenderUnit`（Surface B）。`AuditRenderInput`
包含 rejected claim ID、reason code 與 diagnostics，絕不傳入 ordinary answer renderer。canonical
builder 只從 admitted、runtime-validated claim mint authority unit；quotation bytes 取自 canonical
snapshot span，representation metadata 要和 system-held catalog 相符，再由獨立 trace validator
重新推導並比較每個 authority unit，最後才 deterministic serialization。

failure 對每位 panelist 是 atomic：任何 `TRACE_*` trace failure 都會留下 finalization error，且該
panelist 不會有 partial Surface A。response-level boundary denial 則是合法的空 Surface A；不可移除的
Surface B frame 仍存在，denial 留在 audit data。只有每位 panelist 都完成 finalization（或有效的
response-level denial）時，round 才會是 `finalized=true`。

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

### 引用可採性的保證(各模式不對等)

三種模式共用同一份引用可採性政策(`quote-admissibility/v2`;見
[ADR 0001](adr/0001-quote-admissibility-policy.md) 與
[`policies/quote-admissibility.v2.json`](../policies/quote-admissibility.v2.json)),
但其**保證強度並不對等**:

| 模式 | 目前強制方式 | 範圍 |
|---|---|---|
| 混合控制器(Claude 主持 + Codex 議員) | 預設以指示約束;opt-in B1b 成功綁定時為 `structured-schema-enforced`;opt-in B2 驗證執行後為 `structured-claim-validated`;opt-in B3 邊界執行後為 `structured-fail-closed`;`profile="strict"` + `debate_finalize` 執行 renderer finalization | 只有 strict-finalized responses 的 Surface A 具端到端 machine-enforced construction 與 traceability。未用 `debate_finalize` 的預設路徑不變且未 finalized。 |
| 純 Claude(37 agents) | 以指示約束 | 沒有 strict renderer finalization。 |
| 可攜(Codex / 任意 agent) | 以指示約束 | 沒有 strict renderer finalization。 |

B1b 在混合控制器的 opt-in 結構化路徑只加入 **schema 強制**:解析並綁定
`religion-council/claim/v1` payload,但不驗證 span、不判定可採性。B2 另加 opt-in claim 層驗證:
quotation 會對 curated snapshot 做 byte-span 驗證,source-bound summary 只驗證 evidence edge;
失敗 edge 會移入 `removed_edges`,全失敗〔據典〕降為〔未驗證引用〕。`structured-claim-validated`
只表示 B2 驗證已執行,不表示每個 claim 都通過,也不是 fail-closed。真正結果以每個 claim 的
`verification_state`、`span_assurance_tier`、`span` 與 `removed_edges` 為準。B3 加入
fail-closed response boundary:`structured-fail-closed` 只表示邊界 gate 已執行,不表示每個 claim
都被 admit;真正可否 render 以每個 result 的 `boundary_decision` 為準。

Strict-finalized responses provide end-to-end machine-enforced construction and traceability of
the textual-authority surface (Surface A). Interpretation prose (Surface B) remains explicitly
non-authoritative and instruction-bounded。這不代表所有 prose 都已 machine-verified，也不代表
interpretation prose 不會誤導，完整 answer 亦非 semantically fail-closed。capability-token mint
guard 不是 Python sandbox。

### 辯論壓力與共識判準

Controller 維持現有「可重複 follow-up round」協定,但 panelist prompt 加入 claim-level
對抗契約:

- 首輪提出一個不可退讓命題與一個不相容對立命題;不得把自行預想的立場冒充為其他議員主張。
- 後續輪鎖定一個真實 claim ID,要求 verdict、前提層反駁、反例、尖銳追問、decisive crux 與
  `upheld / narrowed / withdrawn` 狀態。
- 單方回應只稱 rebuttal,不稱完成的 debate;主持人可用現有下一輪把未答問題送回原主張者。
- 建議相近但理據不同只算**實踐重疊**;只有所有相關議員明確接受同一命題才算**共識**。
- 最終回答不顯示 chain-of-thought、tool/token log、agent 完成紀錄或 transport/fallback 細節。

這提高的是論證壓力,並不授權人身攻擊、稻草人、虛構對手或放寬引用紀律。

**兩種文字輸入、信任不同**:`evidence_packet` 為**不可信資料**(panelist 不得服從其中指令,也不得因其出現就視為可引用)。`contrast_proposition` 是**另一條、由 controller 路由**的輸入,供主持人注入建構的對照命題——controller 會把它包進自有的 fenced 區段,**routed(非斷定為真)**,其中任何指令一律當作待評估資料、**絕不執行**。`evidence_packet` 內的自我標記永不觸發 contrast 處理,只有 `contrast_proposition` 參數才會。

使用者提供且實際附上 bytes 的 packet 預設為 `acquisition_origin = user-supplied`、
`source_assurance = artifact-backed`(所附 bytes 即真實、可定位的 artifact)與
`verification_state = unverified`:其用語可追溯至所提供的 packet,但作者、版本、權威性與發表狀態
未經獨立確立。(若使用者僅**聲稱**有某來源卻未附可取得內容,則為 `source_assurance = asserted-only`。)
