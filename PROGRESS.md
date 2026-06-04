# PROGRESS.md — ShortList

> The *running log* — Claude Code's memory between sessions. Append after every task; never delete history.
> Rules + current phase: **CLAUDE.md**. Product: **SPEC.md**. Roadmap: **BUILD_PLAN.md**.

## How to use this file
- **Claude Code:** after each task, add a dated entry under "Log" describing what changed and how to test it. Record any decision in "Decisions". Add anything unresolved to "Open items".
- **Ankit:** skim "Open items" and the latest log entry at the start of each session.

---

## Current status
- **Phase:** P0 — Foundations (not started)
- **Last working on:** —
- **Next up:** scaffold the two FastAPI services + Supabase schema (SPEC §12) with row-level security.

## Decisions (append-only)
- 2026-06-04 — Product is a B2B BYOK shortlisting **engine**, not a public job board. Candidate apply screens are in v1; public discovery board deferred.
- 2026-06-04 — Two services: public **intake** (no keys) + private **processing** (engine + key vault).
- 2026-06-04 — Scoring is **one CV per model call** (isolation) with cited evidence + `insufficient_evidence`; ranking order is deterministic code.
- 2026-06-04 — Model access via a **provider layer**; MVP on **Claude direct** (Anthropic SDK); OpenRouter only when a non-Claude customer needs it.
- 2026-06-04 — Tenant model default: **org-as-tenant** (extendable to an agency client-layer). *To confirm.*

## Open items / questions
- [ ] Confirm tenant model: agencies (multi-client) vs in-house (single org) before finalising P0 schema.
- [ ] Choose hosting (Render vs Railway vs Fly).
- [ ] Begin sourcing the 300-CV golden test set (needed by Phase 4 — start early).

---

## Log (newest at top)

### 2026-06-04 — Project bootstrapped
- Created the four project docs: CLAUDE.md, SPEC.md, BUILD_PLAN.md, PROGRESS.md, plus the workflow diagram.
- No code yet. Next session: start Phase 0, Step 4 (scaffold services + schema).
- How to verify: n/a (docs only).

<!-- TEMPLATE for new entries — copy below:
### YYYY-MM-DD — <short title>
- What changed:
- Files touched:
- How to test it:
- Notes / gotchas:
-->
