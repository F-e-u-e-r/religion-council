---
title: "Review and improve safety-routing wording"
labels: ["good first issue", "docs"]
---

## Context

The project routes crisis-first topics (self-harm, abuse, medical/legal/financial emergencies) to professional resources before entering the council pipeline. The wording lives in:

- `policies/safety-routing.v1.json` — the canonical single source
- `DISCLAIMER.md` — the user-facing policy (EN + ZH)
- `README.md` — the brief mention (EN + ZH)
- Both `SKILL.md` files — the operating manuals

A conformance test (`tests/test_safety_routing.py`) verifies that every surface carries the rule.

## What to do

- Read the current wording in all four locations.
- Suggest clearer, more compassionate phrasing — especially for someone in distress who may encounter the council accidentally.
- Ensure the wording is culturally appropriate for a multi-tradition, multilingual audience.
- The **rule** (crisis-first routing) is non-negotiable; the **wording** is improvable.

## Acceptance

- `tests/test_safety_routing.py` still passes
- Wording change appears in all required surfaces
- No new crisis categories added without discussion (that changes the contract)
