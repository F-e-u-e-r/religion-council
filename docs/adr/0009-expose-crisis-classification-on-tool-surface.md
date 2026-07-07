# ADR 0009 — Expose `crisis_classification` on the public tool surface (routing-only)

- Status: **Proposed** (accepted on merge). This ADR decides an **approval + a schema/wiring
  boundary** — it does **not** add any crisis *detection*, classifier, or automatic routing.
- Scope: make the ONE machine guarantee of the safety-routing policy — *a request classified
  crisis-first cannot enter the council pipeline* — actually reachable on the real MCP tool path,
  by declaring the already-supported `crisis_classification` input on `debate_start`. A
  routing/approval decision, **not** a new safety mechanism and **not** a detection claim.
- Owner stage: safety hardening (arena-ization pre-req). Complements [ADR 0004](0004-renderer-trust-boundary.md)'s
  trust boundary on the *output* side with a routing boundary on the *input* side.
- Relationship: converts the deferral recorded in `policies/safety-routing.v1.json`
  (`deferrals[]`, "Wiring the `crisis_classification` input through the MCP `debate_start` schema
  … kept out of the public tool surface until routing is approved"). **This ADR is that
  approval.** It leaves the *other* deferral — semantic / keyword crisis **detection** and any
  automatic runtime routing — untouched and still deferred to a future ADR.

## Context

- The guard already exists and is correct. `guard_crisis_routing(classification)`
  (`orchestrator/debate_controller.py`) raises `CrisisRoutingError` iff
  `classification == CRISIS_FIRST_CLASSIFICATION` (`"crisis-first"`), and `DebateController.start()`
  calls it **first**, before question validation or any run-dir / snapshot / panelist work.
  `CrisisRoutingError` subclasses `ControllerError`, so every `except ControllerError` handler
  still fails closed.
- **But the guard is dead on the real MCP path.** `debate_start`'s `inputSchema` has
  `additionalProperties: false` and does **not** declare `crisis_classification`, so a
  schema-conformant MCP host/client cannot send it. Every real `debate_start` therefore arrives
  with `crisis_classification = None`, the guard passes, and the council runs. Today live crisis
  handling rests **entirely on the moderator agent's prose self-discipline**
  (`.claude/agents/council-moderator.md`), with no machine value ever reaching the guard.
- The gap was intentional and recorded: `policies/safety-routing.v1.json`
  `guarantee_boundary.machine_guarantees` claims routing only; `not_claimed` explicitly disclaims
  detection; and `deferrals[]` kept the schema wiring off the public surface "until routing is
  approved". This ADR supplies that approval so the guarantee stops being a documentation promise
  and becomes machine-enforced on the tool path.
- Existing coverage proves the guard but not the surface: `tests/test_safety_routing.py`
  refuses a crisis-first `start()` **via a direct Python call**, never through
  `ControllerMcpServer` — so nothing exercised the path a real caller uses.

## Decision

1. **Declare `crisis_classification` on `debate_start`'s `inputSchema`** as
   `{"type": "string", "enum": ["crisis-first"]}`, **optional** (not in `required`), with
   `additionalProperties` staying `false`. The `enum` is deliberate: it rejects typos /
   unknown labels rather than letting an unrecognized value silently fail open.
2. **Enforce the enum at the tool boundary, not only in the advisory schema.** `ControllerMcpServer._dispatch_tool`
   splats arguments straight into `start()` with no schema validation, so a non-validating MCP host/client
   could send a malformed safety label — a typo (`"crisis_first"`) or an explicit `null` — that would
   otherwise be treated as non-crisis and **fail open** (start a run). Two layers close this:
   - `_dispatch_tool` enforces the enum **keyed on presence**: a truly omitted field is the non-crisis
     default, but if `crisis_classification` is supplied at all, its value must be exactly the enum member —
     an explicit `null`, a typo, or a non-string is rejected. (Key presence is only visible at this boundary;
     `start()` cannot distinguish an omitted arg from an explicit `null`, as both arrive as `None`.)
   - `start()` additionally rejects any non-`None`, non-enum value as defense in depth for direct Python callers.

   The schema `enum` is single-sourced to `CRISIS_FIRST_CLASSIFICATION` so the surface and the guard cannot drift.
3. **Honest boundary is unchanged.** `machine_guarantees` / `not_claimed` in the policy stay
   exactly as written (routing only; no detection claim). The tool description states
   `crisis_classification` is a *caller-supplied routing label, not detection*. We do **not**
   claim the system detects crises.
4. **The classification remains the moderator's fallible in-band judgment.** Wiring the input does
   not add a classifier. The moderator must classify each request per
   `policies/safety-routing.v1.json` and, when crisis-first, respond with the `crisis_first_contract`
   (immediate-safety guidance) and **not** route the request into a debate (equivalently: pass
   `crisis_classification="crisis-first"` to trip the guard). Automatic/semantic detection stays
   deferred.

## On acceptance (follow-on work, tracked as one focused unit)

- `policies/safety-routing.v1.json`: remove the *schema-wiring* deferral (now satisfied); **keep**
  the *detection* deferral; leave `machine_guarantees` / `not_claimed` unchanged. Reference this
  ADR from `enforced_by` / status.
- `.claude/agents/council-moderator.md` **and** both `SKILL.md` surfaces
  (`skills/religion-council/SKILL.md`, `.claude/skills/religion-council/SKILL.md`): add the explicit
  obligation to classify per policy and set `crisis_classification` / refuse to start. The existing
  `SurfaceConformanceTest` `must_contain` markers must stay green.
- Land as its own PR (never folded into unrelated corpus work), per the focused-PR discipline.

## Consequences

- **Positive:** the policy's single machine guarantee becomes real on the surface a caller actually
  uses; a crisis-first `debate_start` is refused before any run work. Covered by new MCP-path tests
  (`tests/test_safety_routing.py::McpSurfaceCrisisRoutingTest`).
- **Residual risk — fallible classification:** false negatives (a real crisis never gets classified,
  so the council still runs) and false positives (ordinary academic self-harm/religion discussion
  mis-flagged and refused) both remain possible. The guarantee covers *routing given a
  classification*, never detection — the wording must never be upgraded to imply otherwise.
- **Enforced, not merely advisory:** `start()` rejects any non-enum `crisis_classification`, so the
  routing guarantee holds even against a non-validating MCP host — a typo cannot fail open. The
  remaining schema surface (`additionalProperties:false` and the *other* fields) is still honored by
  the host, not the server; generic whole-argument validation is out of scope here.

## Open questions (owner decision)

- **Schema strictness:** ~~enum vs free string~~ — **resolved**: a single-value `enum`, enforced in
  `start()` (a typo'd label is rejected, not silently run). Kept here for the record.
- **Crisis UX:** on refusal the guard surfaces `CrisisRoutingError` as an `isError` text to the
  moderator. Should the crisis-first path instead return a *structured* safety response carrying the
  `crisis_first_contract` bullets / local-help guidance for the end user?
- **Is a moderator-supplied value a sufficient "live gate",** or is the eventual intent a separate
  pre-classifier (which would need its own ADR under the still-standing detection deferral)?
