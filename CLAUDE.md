# CLAUDE.md — ShortList

> Root operating file for Claude Code. Read this fully at the start of every session.
> Deeper detail lives in **SPEC.md** (product spec) and **BUILD_PLAN.md** (phased roadmap).
> Architecture diagram: **shortlist_workflow.mermaid**.

---

## What we're building

A **bring-your-own-key (BYOK) AI shortlisting engine** for recruiters. Candidates apply with just a CV; recruiters paste a prompt + JD and get a **ranked, evidence-cited shortlist**. Inference runs on the **customer's own API key**.

It is **decision support** — a human always makes the final hiring call. It never auto-rejects anyone.

**Core acceptance target:** reliably surface the **top 10 of 300 CVs**, scaling to 1,000+, with zero cross-candidate contamination.

---

## Architecture (two services + an engine)

1. **intake-service** — public-facing. Candidate apply screens, CV upload, group by job, route the application onward. **Holds NO API keys. Does NO AI work.**
2. **processing-service** — private. The engine + recruiter dashboard. Holds the encrypted key vault and makes all model calls.

**The engine (inside processing-service):**
`Parse CV → Score each CV ALONE → Rank by score (plain code) → Refine top ~15 → Shortlist`

Model calls go through **one swap-able provider layer**. Default provider = **Claude API direct** (use the Anthropic SDK; native prompt caching + batch). OpenRouter is an **optional later** addition for non-Claude customer keys — do not add it until a real customer needs it.

---

## Repo layout

```
/intake-service        # FastAPI, public
/processing-service    # FastAPI, private (engine + dashboard API)
/web                   # React: candidate apply UI + recruiter dashboard
/shared                # provider layer, schemas, db models
/tests                 # incl. golden 300-CV test set
SPEC.md  BUILD_PLAN.md  PROGRESS.md  CLAUDE.md
```

## Tech stack

Python + FastAPI · Supabase (Postgres + RLS + auth + storage + pgvector) · React · Anthropic SDK (via provider layer) · Render/Railway hosting. Secrets and model IDs live in env/config only.

## Commands (fill in / keep current as we build)

- Run intake: `uvicorn intake_service.main:app --reload --port 8001`
- Run processing: `uvicorn processing_service.main:app --reload --port 8002`
- Tests: `pytest`
- **Golden gate test:** `python -m tests.golden_run`  → must pass before Phase 4 is "done"
- Lint/format: `ruff check . && ruff format .`

---

## Golden rules

### NEVER
- **Never** hard-code API keys or model names. Read them from env/config.
- **Never** log, print, or return a customer's API key — redact in all logs and error messages.
- **Never** let the intake-service touch or store provider keys.
- **Never** put more than one candidate's CV in a single scoring model call. Each CV is scored in isolation — this is what prevents hallucination and attribution bleed.
- **Never** do the ranking order via the model. Ordering is deterministic code over numeric scores.
- **Never** write logic that auto-rejects or auto-contacts candidates. Output is a shortlist for a human.
- **Never** invent qualifications — if a CV lacks evidence for a criterion, set `insufficient_evidence: true`.

### ALWAYS
- **Always** route every model call through the single provider abstraction layer.
- **Always** validate model output against the scoring JSON schema (see SPEC §7.4). Retry on invalid JSON; never let one bad CV fail the whole run.
- **Always** require an `evidence_quote` that appears verbatim in that candidate's CV.
- **Always** enforce org-level row isolation (Supabase RLS). An org sees only its own data.
- **Always** prompt-cache the shared JD/rubric across a search; run scoring calls in parallel; support a batch mode.
- **Always** keep the golden test set green — re-run it after any change to parsing, the rubric, or model config.
- **Always** write an immutable `audit_log` row for every search (prompt, JD, weights, model, results).

---

## Build order & current status

Phases (detail in BUILD_PLAN.md). Critical path: **scoring (P3) + rank/refine (P4)** are where the product lives or dies.

- [ ] **P0** Foundations: two services, schema + RLS, recruiter auth, encrypted key vault, routing, CI/deploy
- [ ] **P1** Intake: job + apply-link, candidate screens, CV upload, route to processing
- [ ] **P2** Parsing: PDF/DOCX → clean text, OCR fallback, flag bad parses
- [ ] **P3** Scoring engine: rubric builder, isolated per-CV scoring + evidence, provider layer, caching/parallel/batch
- [ ] **P4** Rank + refine + recruiter dashboard ·  ⛔ GATE: 300 → top 10, stable over 3 runs
- [ ] **P5** Compliance & security hardening ·  ⛔ GATE: security review (no key/data leaks)
- [ ] **P6** Pilot with 3–5 design partners ·  ⛔ GATE: partners would keep using / pay
- [ ] **P7** Production launch & scale-readiness

> **CURRENT PHASE: P0.** Start with auth + multi-tenant orgs + the encrypted key vault.

---

## How to work with me

1. **Plan first.** Before writing code for a task, give a 3–5 step plan in plain English and wait for my OK.
2. **Thin slice first.** Build the simplest end-to-end path (one job, one CV, one score) before adding breadth.
3. **Commit + log.** After each task: commit with a clear message and append to PROGRESS.md (what changed + how I test it).
4. **Explain simply.** When I ask, explain what you built in plain terms and exactly how I verify it myself.
5. **Stay in config.** Keys and model IDs in env/config, never in code.

---

## Open decision (confirm before P0 schema is final)

**Tenant model: agencies (multi-client) vs in-house (single org).**
Default until I say otherwise: **org-as-tenant** (one org = one customer; recruiters belong to an org; jobs belong to an org). This works for in-house now and can extend to a client layer for agencies later — build it so that extension is possible.
