# ADR 0010 — Weaponization-first safety routing (a second routing axis)

- Status: **Proposed** (accepted on merge). This ADR decides a **second, distinct safety-routing
  axis + its policy + tool-surface wiring** — it does **not** add any content *detection*,
  classifier, or automatic routing.
- Scope: give the council a machine backstop for a discipline it already espouses — *attack
  propositions, never people or communities* — so a request whose evident purpose is to **use the
  council to produce targeted attack, dehumanization, harassment, or incitement material** against a
  religious/belief group or individual cannot be run as a council debate. A routing decision, **not**
  a new detection capability and **not** a claim to detect every weaponization attempt.
- Owner stage: safety hardening (arena-ization). The **second axis** alongside crisis-first
  ([ADR 0009](0009-expose-crisis-classification-on-tool-surface.md)).
- Relationship: **reuses the ADR 0009 mechanism** (caller-supplied classification → optional
  single-value enum on `debate_start` → tool-boundary enforcement → `start()` guard → surface
  obligations → MCP-path tests) but keeps the axes **distinct**: a separate `weaponization_classification`
  input, a separate `guard_weaponization_routing` / `WeaponizationRoutingError`, and a separate,
  sibling policy `policies/weaponization-routing.v1.json`. It does **not** overload `crisis_classification`,
  and it does **not** reuse crisis emergency-help wording (the two harms are different).

## Context

- The project already forbids weaponizing the debate against people: `skills/religion-council/SKILL.md`
  and the moderator instructions say *"Attack propositions, premises, and consequences directly; never
  attack a participant, believer, or community."* But that discipline was **prose-only** — there was no
  machine routing boundary that a weaponization-labelled request could not bypass. Beyond crisis-first
  and citation-admissibility, nothing stopped the council being pointed at producing targeted hate /
  harassment / incitement material.
- The crisis-first axis (ADR 0009) established a clean, honest pattern for exactly this shape of
  problem: a fallible caller-supplied classification, wired as an optional single-value enum on the
  public tool surface, enforced at the `ControllerMcpServer._dispatch_tool` boundary and in `start()`,
  with the machine guaranteeing only *routing given a classification*, never detection. The same
  pattern applies to weaponization with a different narrow definition and a different refusal contract.
- The hard part is **not** the mechanism (it is a mirror of ADR 0009) but the **definition**: what the
  arena refuses is a values decision for the owner. This ADR fixes it **narrowly** so ordinary use is
  never blocked (see Decision §4).

## Decision

1. **Add a distinct classification + guard.** `WEAPONIZATION_FIRST_CLASSIFICATION = "weaponization-first"`,
   `guard_weaponization_routing(classification)` raising `WeaponizationRoutingError(ControllerError)`
   iff the classification equals the enum member. `start()` gains an optional `weaponization_classification`
   argument and calls the guard first, alongside the crisis guard, before any run dir / snapshot / panelist work.
2. **Declare + enforce the enum on the tool surface,** exactly as ADR 0009: an optional
   `weaponization_classification` property (`{"type":"string","enum":["weaponization-first"]}`,
   single-sourced to the constant, `additionalProperties` stays false), enforced at
   `_dispatch_tool` keyed on presence (an explicit null, a typo, or a non-string is rejected — no
   fail-open), with `start()` rejecting non-`None` non-enum values as defense in depth.
3. **Sibling policy + surface obligations.** `policies/weaponization-routing.v1.json` single-sources the
   contract, the canonical rule, the routing-only guarantee boundary, and the required operational
   surfaces; the moderator and both `SKILL.md` surfaces gain the obligation to classify per policy and,
   when weaponization-first, decline to run the council (offer proposition-level examination instead).
   A conformance test mirrors the crisis `SurfaceConformanceTest`.
4. **Narrow definition (the values call), routing-only.** *Weaponization-first* is **only** a request
   whose evident purpose is to produce **targeting** material — attack, dehumanization, harassment, or
   incitement of hatred/violence against a religious/belief group or individual. It is **not** critical,
   academic, historical, or comparative discussion of religions and their doctrines, and it is **not**
   attacking a *claim or doctrine* (which the council exists to do). `machine_guarantees` / `not_claimed`
   keep the honest boundary: the system guarantees routing given a classification and never claims to
   detect weaponization.

## Consequences

- **Positive:** a second, independent safety guarantee closes a real arena-abuse path (producing
  targeted hate/harassment material) with the same enforced-on-the-tool-surface rigor as crisis-first,
  and gives the existing "attack ideas, not people" discipline a machine backstop.
- **Residual risk — fallible classification:** false negatives (a weaponization request never labelled,
  so the council runs) and false positives (legitimate critical/academic discussion mis-labelled and
  refused) both remain possible. The narrow definition and the routing-only wording exist to keep false
  positives from chilling ordinary use; the wording must never be upgraded to imply detection.
- **Two axes, one mechanism:** the enum-enforcement helper is shared, but the classifications, guards,
  errors, contracts, and policies are distinct, so neither axis's semantics leak into the other.

## Open questions (owner decision)

- **Definition scope:** is the narrow "targeting-material-production" definition the intended line, or
  should it also cover adjacent cases (e.g. requests to draft one-sided polemic that stops short of
  targeting a group)? Kept narrow here on purpose; widening is an owner call.
- **Refusal UX:** on refusal the guard surfaces `WeaponizationRoutingError` as an `isError` text. Should
  the weaponization-first path instead return a structured response offering the proposition-level
  reframe to the end user?
- **User-facing surfaces:** this ADR wires the *operational* surfaces (moderator + SKILLs). Should
  `README.md` / `DISCLAIMER.md` also carry the weaponization boundary, as they do for crisis-first?
