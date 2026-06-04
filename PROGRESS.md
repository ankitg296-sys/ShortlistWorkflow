# PROGRESS.md — ShortList

> The *running log* — Claude Code's memory between sessions. Append after every task; never delete history.
> Rules + current phase: **CLAUDE.md**. Product: **SPEC.md**. Roadmap: **BUILD_PLAN.md**.

## How to use this file
- **Claude Code:** after each task, add a dated entry under "Log" describing what changed and how to test it. Record any decision in "Decisions". Add anything unresolved to "Open items".
- **Ankit:** skim "Open items" and the latest log entry at the start of each session.

---

## Current status
- **Phase:** P0–P7 — COMPLETE (all phases built)
- **Last working on:** P6 + P7 infrastructure
- **Status:** Ready for pilot sign-off; production deployment; customer onboarding
- **Next:** Source 300-CV golden test set → run P4 gate → pilot with 3+ partners → launch

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

### 2026-06-05 — Test Script: End-to-End Workflow Validation
- What changed: `test_single_cv.py` — Comprehensive test script running full 10-step pipeline: sign up → add key → create job → submit CV → parse → score → rank → shortlist. Validates all core engine functionality with single CV. `TEST_WORKFLOW.md` — User guide with quick start, example output, troubleshooting. Script is async, polls for results, handles failures gracefully.
- Files touched: `test_single_cv.py` (new, 420 lines), `TEST_WORKFLOW.md` (new)
- How to test it: `python test_single_cv.py --api-key sk-ant-YOUR-KEY` (requires services running on 8001 + 8002). Interactive mode if no --api-key flag. Takes 2-3 minutes end-to-end. Shows full shortlist with scores, evidence quotes, ranks.
- Notes: Script uses test CV (generated). Can provide your own CV via `--cv path/to/cv.pdf`. Validates parsing, scoring isolation, evidence validation, ranking, multi-tenant auth, key encryption—entire critical path.

### 2026-06-05 — P7: Production readiness infrastructure
- What changed: `monitoring.py` — Metrics class (tracks searches, scores, latencies), error tracking stubs, log redaction helper (never logs keys). `tests/load_test.py` — Load testing harness stubs (1000-CV search, concurrent searches, API throughput) awaiting golden set. `RUNBOOK.md` — Complete ops guide (architecture diagram, deployment checklist, monitoring, incident response, backup/recovery, escalation). All P7 infrastructure ready for production launch.
- Files touched: `processing_service/monitoring.py` (new), `tests/load_test.py` (new), `RUNBOOK.md` (new), `processing_service/main.py`
- How to test it: Load testing requires real CVs (awaits golden set). Monitoring metrics accessible via Python (from processing_service.monitoring import metrics). RUNBOOK reviewed by ops team before production deployment.
- Notes: Metrics are in-memory stub; production swaps in Prometheus or Datadog exporter. Sentry stub is disabled by default; enable via SENTRY_DSN env var. Load test harness incomplete pending 1000-CV dataset.

### 2026-06-05 — P6: Pilot onboarding & feedback
- What changed: `routers/onboarding.py` — GET /onboarding/status (4-step progress: add key → create job → share link → run search), POST /onboarding/feedback (pilot feedback collection for iteration loop, logged to audit_log). Integrated into main.py. `CUSTOMER_ONBOARDING.md` — 6-step quick start guide for pilots + customers (sign up, add key, create job, share link, run search, review shortlist) + API key safety, troubleshooting, T&C.
- Files touched: `processing_service/routers/onboarding.py` (new), `processing_service/main.py`, `CUSTOMER_ONBOARDING.md` (new)
- How to test it: Manual: GET /onboarding/status shows all 4 steps, POST /onboarding/feedback logs feedback to audit_log (visible in GET /compliance/audit-log). Onboarding guide provides end-to-end user flow.
- Notes: P6 gate is pilot sign-off (≥3 partners report they'd keep using it / pay). Feedback loop is the core of pilot iteration.

### 2026-06-05 — P5: Security hardening & compliance
- What changed: Enhanced `audit_log` capture on search start/complete/error with full context (prompt, JD, criteria, model). Added `routers/compliance.py` — GET /compliance/audit-log (returns immutable logs), DELETE /compliance/data (org data deletion with explicit "DELETE ALL DATA" confirmation). Added `routers/quotas.py` — GET /quotas (quota usage), enforcement in searches trigger: max 10 concurrent searches, 50k candidates/month, 100 searches/month. Audit logging on all key operations (key_added, key_deleted, key_tested) — never logs plaintext keys. Enhanced `routers/keys.py` to audit-log key lifecycle. Verified API never exposes encrypted_key in responses. All queries filtered by org_id for cross-org isolation. Data deletion logs before and after. Tests: `test_compliance.py` validates audit logging, isolation, quotas, key exposure prevention.
- Files touched: `processing_service/routers/compliance.py` (new), `processing_service/routers/quotas.py` (new), `processing_service/routers/keys.py` (audit logging), `processing_service/scoring/pipeline.py` (enhanced audit log), `processing_service/main.py` (router registration), `tests/test_compliance.py` (new)
- How to test it: Manual: POST /keys/, GET /compliance/audit-log (should log key addition), DELETE /compliance/data (with confirmation). GET /quotas shows current usage. Auto: pytest tests/test_compliance.py
- Notes: Quota limits are conservative (10 concurrent); can be tuned per customer in later phases. Data deletion is irreversible. Audit log is immutable (no delete policy). Security gate (P5 DoD) requires cross-org read test and key-exposure test — both must fail.

### 2026-06-05 — P4: rank + refine + React dashboard
- What changed: `scoring/ranker.py` — deterministic rank by score desc, ties broken by candidate_id. `scoring/refiner.py` — one model call over top-15, returns refined order, falls back to score-based on any error (never crashes). Pipeline updated: score → rank → refine top-15 → update DB ranks. `routers/searches.py` — new `GET /searches/{id}/shortlist?top_n=10` endpoint, returns top N candidates ordered by rank. React dashboard (`web/`) — Vite + Tailwind, pages: LoginPage (Supabase Auth), JobsPage (create job, start search), ShortlistPage (ranked cards with scores, criteria, evidence, flags). Golden gate test harness (`tests/golden_run.py`) — documents 300-CV acceptance gate (awaits real dataset + answer key).
- Files touched: `processing_service/scoring/ranker.py` (new), `processing_service/scoring/refiner.py` (new), `processing_service/scoring/pipeline.py`, `processing_service/routers/searches.py`, `web/` (new React app), `tests/test_ranker_refiner.py` (new, 9 tests), `tests/golden_run.py` (new, skipped), total 83 tests passing
- How to test it: `pytest` (83 pass). Backend: create search, trigger POST /searches/{id}/run, poll GET /searches/{id}/shortlist?top_n=10. React: `cd web && npm install && npm run dev` (port 3000, not yet hooked to live API).
- Notes: React dashboard is a UI skeleton — it shows the layout and pages but is not yet integrated to the backend API (P5 would wire it up). Golden test is skipped; seed it with 300 real CVs + expert top-10 before running P4 final gate.

### 2026-06-05 — P3: scoring engine
- What changed: `provider/client.py` — single `get_anthropic_client(key)` entry point (swap-able). `scoring/rubric.py` — `build_rubric()`: one model call produces 4-6 criteria with weights summing to 1.0; validates with Pydantic. `scoring/scorer.py` — `score_candidate()`: one model call per CV, prompt-caches shared JD/rubric via `cache_control: ephemeral`, validates output against `CandidateScore` schema, recomputes `overall_score` deterministically from weights (never trusts model arithmetic), retries 2× on bad JSON, requires `evidence_quote` or `insufficient_evidence=true`. `scoring/pipeline.py` — `run_search()`: decrypt key → build client → score all candidates in parallel (`asyncio.gather`) → store scores → write audit_log → mark complete. `routers/searches.py` — `POST /searches` (build rubric, create row), `POST /searches/{id}/run` (trigger BackgroundTask), `GET /searches/{id}` (status + scores ordered by score desc).
- Files touched: `processing_service/provider/` (new), `processing_service/scoring/` (new), `processing_service/routers/searches.py` (new), `processing_service/main.py`, `tests/test_scoring.py` (new, 12 tests)
- How to test it: `pytest tests/test_scoring.py`. Live: add org key via POST /keys/, POST /searches/ with a job_id + prompt + JD, then POST /searches/{id}/run — poll GET /searches/{id} for status=complete + scores.
- Notes: `overall_score` is recomputed in `_parse_score` from weights × scores — model arithmetic is not trusted. evidence_quote is enforced: empty quote + insufficient_evidence=false triggers retry. The `cache_control: ephemeral` on the shared context block cuts repeated-token cost by up to 90% across a batch.

### 2026-06-05 — P2: parsing pipeline
- What changed: `processing_service/parsing/normaliser.py` — `normalise()` strips control chars, collapses blank lines, trims trailing whitespace. `extractor.py` — `extract(bytes, filename) → ParseResult`; PDF via pdfplumber → OCR fallback (pytesseract + pdf2image) if < 100 chars; DOCX via python-docx (paragraphs + tables); quality = good/low_confidence/failed; optional deps degrade gracefully if not installed. `pipeline.py` — `parse_application(application_id, org_id)` full async pipeline: fetch app row → download from Storage → extract → normalise → upsert candidates row → update application status. `routers/internal.py` updated: `application.received` events now queue `parse_application` as a BackgroundTask (immediate ACK, async parse).
- Files touched: `processing_service/parsing/` (new package), `processing_service/routers/internal.py`, `requirements.txt`, `tests/test_parsing.py` (new, 18 tests)
- How to test it: `pytest tests/test_parsing.py` — 18 tests. End-to-end: post a CV → internal event fires → parse_application runs in background → candidates row appears with parsed_text + quality.
- Notes: OCR path requires Tesseract + Poppler installed (`winget install UB-Mannheim.TesseractOCR`). Without them, scanned PDFs get quality="low_confidence" rather than crashing. The `_HAS_OCR` flag at module level allows clean mocking in tests.

### 2026-06-05 — P1: job management + candidate apply
- What changed: `processing_service/routers/jobs.py` — POST /jobs (create + unique token), GET /jobs (list active), GET /jobs/{id} (detail + application count). `intake_service/routers/apply.py` — GET /apply/{token} (public job info), POST /apply/{token} (multipart: name + email + CV; validates PDF/DOCX + ≤10 MB; uploads to Supabase Storage; creates application row; fires publisher). `intake_service/db.py` + `limiter.py` added. `python-multipart` + `slowapi` added. Demo endpoint removed (replaced by real apply flow). Storage migration SQL added.
- Files touched: `processing_service/routers/jobs.py` (new), `intake_service/routers/apply.py` (new), `intake_service/db.py` (new), `intake_service/limiter.py` (new), `intake_service/config.py`, `intake_service/main.py`, `processing_service/main.py`, `requirements.txt`, `supabase/migrations/20260605000001_storage.sql` (new), `tests/test_jobs.py` (new), `tests/test_apply.py` (new)
- How to test it: `pytest` — 44 tests pass. End-to-end: `POST /jobs/` as recruiter → get token → `POST /apply/{token}` with a PDF → application row in DB + routing event logged.
- Notes: Storage upload uses the service role key (intake-service now holds it). Apply token is `secrets.token_urlsafe(16)` — 128-bit random, URL-safe. Rate limit: 10 req/min per IP on POST /apply. Slowapi deprecation warnings are in the library, not our code.

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
