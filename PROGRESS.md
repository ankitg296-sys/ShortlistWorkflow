# PROGRESS.md — ShortList

> The *running log* — Claude Code's memory between sessions. Append after every task; never delete history.
> Rules + current phase: **CLAUDE.md**. Product: **SPEC.md**. Roadmap: **BUILD_PLAN.md**.

## How to use this file
- **Claude Code:** after each task, add a dated entry under "Log" describing what changed and how to test it. Record any decision in "Decisions". Add anything unresolved to "Open items".
- **Ankit:** skim "Open items" and the latest log entry at the start of each session.

---

## Current status
- **Phase:** P1 — Intake service (starting)
- **Last working on:** P0 complete
- **Next up:** Job management (processing-service) + candidate apply endpoints (intake-service)

## Decisions (append-only)
- 2026-06-04 — Product is a B2B BYOK shortlisting **engine**, not a public job board. Candidate apply screens are in v1; public discovery board deferred.
- 2026-06-04 — Two services: public **intake** (no keys) + private **processing** (engine + key vault).
- 2026-06-04 — Scoring is **one CV per model call** (isolation) with cited evidence + `insufficient_evidence`; ranking order is deterministic code.
- 2026-06-04 — Model access via a **provider layer**; MVP on **Claude direct** (Anthropic SDK); OpenRouter only when a non-Claude customer needs it.
- 2026-06-04 — Tenant model confirmed: **org-as-tenant**.
- 2026-06-05 — CI/deploy skipped; everything runs locally for now. Will revisit when approaching pilot (P6).

## Open items / questions
- [x] Confirm tenant model: **org-as-tenant** confirmed. Schema built to allow agency client-layer extension later.
- [ ] Choose hosting (Render vs Railway vs Fly).
- [ ] Begin sourcing the 300-CV golden test set (needed by Phase 4 — start early).

---

## Log (newest at top)

### 2026-06-05 — P0: routing transport (intake → processing)
- What changed: `intake_service/publisher.py` — `publish_application_received` posts `{"event":"application.received",...}` to processing-service `/internal/events` via httpx; fire-and-forget (errors logged, never propagated). `processing_service/routers/internal.py` — `POST /internal/events` verifies `INTERNAL_AUTH_TOKEN` with `hmac.compare_digest`, logs the event, returns `{"received":true}`; hidden from public docs (`include_in_schema=False`). `intake_service/main.py` — temporary `POST /demo/submit` endpoint to prove the round-trip. `INTERNAL_AUTH_TOKEN` + `PROCESSING_SERVICE_URL` added to both configs and `.env.example`.
- Files touched: `intake_service/publisher.py` (new), `intake_service/config.py`, `intake_service/main.py`, `processing_service/routers/internal.py` (new), `processing_service/config.py`, `processing_service/main.py`, `tests/conftest.py`, `tests/test_routing.py` (new), `.env.example`
- How to test it: `pytest tests/test_routing.py`. End-to-end with both services running: `curl -X POST "http://localhost:8001/demo/submit"` → watch the processing-service log for `received event=application.received`.
- Notes: publisher is deliberately a thin function — swap the body for a queue publish (Redis, SQS, etc.) without changing any callers. `INTERNAL_AUTH_TOKEN` is **the same value** in both services' `.env`. `/demo/submit` is marked for removal in P1.

### 2026-06-05 — P0: encrypted key vault
- What changed: `vault/crypto.py` — AES-256-GCM encrypt/decrypt (random 12-byte nonce per call; base64(nonce||ct||tag) stored). `vault/provider.py` — `test_api_key` calls Anthropic `messages.count_tokens` (free, validates auth without inference); key never logged, only pass/fail. `routers/keys.py` — POST /keys (encrypt + store, key_hint=last-4), GET /keys (metadata only, encrypted_key excluded from SELECT), DELETE /keys/{id} (explicit org_id filter since service role bypasses RLS), POST /keys/{id}/test (decrypt → live call → update validated_at → return {ok}). `default_model` added to config. `anthropic` and `cryptography` added to requirements.
- Files touched: `processing_service/vault/crypto.py` (new), `processing_service/vault/provider.py` (new), `processing_service/routers/keys.py` (new), `processing_service/config.py`, `processing_service/main.py`, `requirements.txt`, `.env.example`, `tests/test_vault.py` (new), `tests/test_keys.py` (new)
- How to test it: `pytest tests/test_vault.py tests/test_keys.py`. For manual end-to-end: run processing-service with real `.env`, sign in to get a JWT, `POST /keys/ {"provider":"anthropic","api_key":"sk-ant-..."}` → ciphertext stored, hint shown; `POST /keys/{id}/test` → `{"ok":true}`.
- Notes: `encrypted_key` is never in any API response — excluded from the SELECT in list_keys and absent from `KeyOut` model. Org isolation on delete/test is enforced in code (explicit `.eq("org_id", ...)`) not just RLS, because service role key bypasses RLS.

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
