# PROGRESS.md — ShortList

> The *running log* — Claude Code's memory between sessions. Append after every task; never delete history.
> Rules + current phase: **CLAUDE.md**. Product: **SPEC.md**. Roadmap: **BUILD_PLAN.md**.

## How to use this file
- **Claude Code:** after each task, add a dated entry under "Log" describing what changed and how to test it. Record any decision in "Decisions". Add anything unresolved to "Open items".
- **Ankit:** skim "Open items" and the latest log entry at the start of each session.

---

## Current status
- **Phase:** P0 — Foundations (in progress)
- **Last working on:** Recruiter auth
- **Next up:** Encrypted key vault (add org API key → envelope-encrypt → store; "test key" button)

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

### 2026-06-04 — P0: recruiter auth
- What changed: `processing_service/db.py` (Supabase client singleton). `processing_service/dependencies.py` — two deps: `get_token_claims` (JWT-only, no DB) and `get_current_user` (JWT + profile lookup); returns typed dataclasses. `processing_service/routers/auth.py` — `POST /auth/signup` (create org + user row, idempotent) and `GET /auth/me` (return profile + org). Router wired into `main.py`. `PyJWT` added to requirements. `SUPABASE_JWT_SECRET` added to config and `.env.example`. 7 tests in `tests/test_auth.py`: error paths (no token, bad token) + happy paths with MagicMock Supabase client.
- Files touched: `processing_service/config.py`, `processing_service/db.py` (new), `processing_service/dependencies.py` (new), `processing_service/routers/` (new), `processing_service/main.py`, `requirements.txt`, `.env.example`, `tests/conftest.py`, `tests/test_auth.py` (new)
- How to test it: `pytest tests/test_auth.py` (7 tests). For manual end-to-end: fill `.env` with real Supabase creds + JWT secret, run processing-service, call Supabase Auth `signUp()` from a client to get a JWT, then `POST /auth/signup` with `{"org_name": "My Org"}` and `Authorization: Bearer <token>`.
- Notes: sign-in is handled by the Supabase client SDK on the frontend — no `/auth/signin` endpoint needed. `SUPABASE_JWT_SECRET` is in Supabase → Settings → API → JWT Settings.

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
