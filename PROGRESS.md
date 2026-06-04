# PROGRESS.md — ShortList

> The *running log* — Claude Code's memory between sessions. Append after every task; never delete history.
> Rules + current phase: **CLAUDE.md**. Product: **SPEC.md**. Roadmap: **BUILD_PLAN.md**.

## How to use this file
- **Claude Code:** after each task, add a dated entry under "Log" describing what changed and how to test it. Record any decision in "Decisions". Add anything unresolved to "Open items".
- **Ankit:** skim "Open items" and the latest log entry at the start of each session.

---

## Current status
- **Phase:** P0 — Foundations (in progress)
- **Last working on:** Service scaffold + Supabase schema
- **Next up:** Recruiter auth (Supabase) + encrypted key vault

## Decisions (append-only)
- 2026-06-04 — Product is a B2B BYOK shortlisting **engine**, not a public job board. Candidate apply screens are in v1; public discovery board deferred.
- 2026-06-04 — Two services: public **intake** (no keys) + private **processing** (engine + key vault).
- 2026-06-04 — Scoring is **one CV per model call** (isolation) with cited evidence + `insufficient_evidence`; ranking order is deterministic code.
- 2026-06-04 — Model access via a **provider layer**; MVP on **Claude direct** (Anthropic SDK); OpenRouter only when a non-Claude customer needs it.
- 2026-06-04 — Tenant model default: **org-as-tenant** (extendable to an agency client-layer). *To confirm.*

## Open items / questions
- [x] Confirm tenant model: **org-as-tenant** confirmed. Schema built to allow agency client-layer extension later.
- [ ] Choose hosting (Render vs Railway vs Fly).
- [ ] Begin sourcing the 300-CV golden test set (needed by Phase 4 — start early).

---

## Log (newest at top)

### 2026-06-04 — P0: service scaffold + schema
- What changed: full repo structure created. Two FastAPI services (`intake_service/`, `processing_service/`) each with a `/health` endpoint and pydantic-settings config. `shared/schemas.py` defines the `CandidateScore` contract from SPEC §7.4. Supabase SQL migration with all 9 tables from SPEC §12, `updated_at` triggers, and per-table RLS policies using a `current_org_id()` helper (SECURITY DEFINER to avoid recursive lookup on `users`). `audit_log` is insert+select only — no UPDATE/DELETE policy. `.gitignore`, `.env.example`, `requirements.txt`, `pyproject.toml`, `README.md` added.
- Files touched: `intake_service/`, `processing_service/`, `shared/`, `tests/`, `supabase/migrations/`, `requirements.txt`, `pyproject.toml`, `.gitignore`, `.env.example`, `README.md`
- How to test it: `pip install -r requirements.txt` → `pytest` (both health checks pass). Run `uvicorn intake_service.main:app --reload --port 8001` and `curl http://localhost:8001/health` → `{"status":"ok","service":"intake"}`. Same for port 8002 / "processing". Apply migration via Supabase CLI or SQL editor.
- Notes: `intake_service` imports no vault or key logic — that boundary is enforced structurally. `processing_service/vault/` is a stub placeholder for the next P0 task.

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
