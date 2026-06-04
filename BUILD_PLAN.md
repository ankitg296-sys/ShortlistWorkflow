# BUILD_PLAN.md — ShortList

> The *how and when*. The phased roadmap and gates. From empty repo → deployed product with pilot customers.
> Product detail: **SPEC.md**. Operating rules + current phase: **CLAUDE.md**. Running log: **PROGRESS.md**.

**Build model:** solo, with Claude Code as the primary builder.

---

## How to read this plan

- Durations are **focused build-weeks (full-time equivalent)**. Part-time → multiply calendar time ~2–3×.
- **Total to pilot: ~8–12 build-weeks.** MVP engine (Phases 0–4) is ~6–8; hardening + pilot is the rest.
- Each phase ends with a **Definition of Done (DoD)**. Don't start the next until it's met.
- **Validation gates (⛔)** are hard stops. The big one is the 300 → top 10 test in Phase 4.

### Working with Claude Code
1. Each session: have it read CLAUDE.md, then PROGRESS.md and the relevant BUILD_PLAN phase.
2. Give it **one step at a time**. Build **vertical slices** (one job, one CV, end-to-end) before breadth.
3. Commit per task; keep keys and model IDs in env/config.
4. Run each phase's DoD checks yourself before moving on.

---

## Phase at a glance

| Phase | Name | FTE weeks | Hard gate |
|---|---|---|---|
| 0 | Foundations & two-service skeleton | 1 | — |
| 1 | Intake service (candidate apply) | 1 | — |
| 2 | Parsing pipeline (CV → clean data) | 1 | — |
| 3 | Scoring engine (the core AI) | 1.5–2 | — |
| 4 | Rank, refine & recruiter dashboard | 1.5 | ⛔ 300 → top 10 |
| 5 | Compliance & security hardening | 1 | ⛔ security review |
| 6 | Pilot with design partners | 2–4 (light build) | ⛔ pilot sign-off |
| 7 | Production launch & scale-readiness | 1 + ongoing | — |

---

## Pre-flight (once, before Phase 0)

Accounts/tools: GitHub · Supabase project · Render/Railway/Fly · Anthropic API key (your dev key) · Claude Max for Claude Code · a KMS/secrets store for the key vault.

**Decision that gates the schema:** agencies vs in-house (SPEC §15). Default org-as-tenant; build so an agency client-layer can be added later.

---

## Phase 0 — Foundations & two-service skeleton  ·  ~1 week
**Goal (plain):** stand up the two empty services, log in, store an encrypted key — no AI yet.

Tasks:
- Scaffold `intake-service` and `processing-service` (FastAPI).
- Supabase schema from **SPEC §12** with row-level security (an org reads only its own rows).
- Recruiter auth (Supabase). A user belongs to one org.
- **Key vault:** add org API key → envelope-encrypt → store; never log/return plaintext; "test key" button makes one OpenRouter/Anthropic call and shows only success/failure.
- Routing transport between services (queue/webhook) — pass one dummy message end-to-end.
- CI + auto-deploy to staging on push.

**DoD:** both services on staging; recruiter signs up, adds a key (stored encrypted + validated live); a message routes intake → processing.

## Phase 1 — Intake service (candidate apply)  ·  ~1 week
**Goal (plain):** a candidate opens a link, drops a CV, it lands grouped by job.

Tasks:
- Recruiter creates a **Job** + gets a shareable apply-link; list its applications.
- Candidate **application screens** (React): minimal fields + CV upload (PDF/DOCX).
- On submit: store file in Supabase storage, create `applications` row grouped under the job, route to processing.
- Guardrails: file-type/size limits, rate limiting, **no API keys on this service**.

**DoD:** 20 test applications via the link land correctly grouped under one job and arrive at processing.

## Phase 2 — Parsing pipeline (CV → clean data)  ·  ~1 week
**Goal (plain):** turn messy CV files into clean, reliable text — including ugly multi-column and scanned ones.

Tasks:
- Robust PDF + DOCX extraction; handle multi-column + tables; OCR fallback for scanned PDFs.
- Normalise to clean text + light structure; store on the `candidates` row.
- Flag low-confidence parses as "needs review" rather than passing empty text forward.

**DoD:** 95%+ of a varied 20-CV test batch parse to usable text; bad parses are flagged, not hidden.

## Phase 3 — Scoring engine (the core AI)  ·  ~1.5–2 weeks
**Goal (plain):** score each CV on its own, with cited evidence and an "I can't tell from this CV" option. *Don't rush this.*

Tasks:
- **Rubric builder:** prompt + JD (+ optional weights) → fixed scoring criteria; show recruiter to tweak.
- **Independent per-CV scoring:** one CV per model call (via the provider layer; model from org config). Output exactly the **SPEC §7.4** JSON: per-criterion score, real `evidence_quote`, `insufficient_evidence`, summary, flags. Validate JSON every time; retry on bad output. Never two candidates in one call.
- **Cost optimisation:** prompt-cache the shared JD/rubric; run scoring in parallel; config switch for cheap-model/embeddings prefilter → stronger model. Model names in config.

**DoD:** 50 CVs score end-to-end; every score has a real cited quote; no candidate's evidence bleeds from another's CV.

## Phase 4 — Rank, refine & recruiter dashboard  ·  ~1.5 weeks
**Goal (plain):** turn scores into a ranked shortlist and prove it nails the top 10 of 300.

Tasks:
- **Deterministic rank:** sort by weighted score in plain code.
- **Refine pass:** one comparative call over the top ~15 full CVs.
- **Recruiter dashboard (React):** ranked shortlist; per candidate → overall score, per-criterion breakdown, evidence quotes, flags, link to source CV. Clearly labelled decision-support.
- **Golden test set (start early in the phase):** 300 CVs for one realistic role with an expert top-10 answer key.

**⛔ GATE — the 300 → top 10 test:** run the full pipeline on the golden set. Pass = engine top-10 matches the answer key at the agreed threshold (e.g. ≥8/10), **zero cross-candidate contamination**, every shortlisted score evidence-backed. Re-run 3× to confirm stability. If it fails: tune the rubric/scoring prompt, **not** the architecture; re-test.

**DoD:** gate passes, stably; a recruiter can run a real search and read the shortlist.

## Phase 5 — Compliance & security hardening  ·  ~1 week
Tasks: immutable **audit log** of every search; key-vault hardening (encryption, scoping, rotation; keys never in logs/errors); human-in-the-loop UI labelling; DPDP-aligned data retention/deletion + export; rate limits + per-org quotas; option to mask name/contact before scoring.

**⛔ GATE — security review:** attempt a cross-org data read and attempt to surface a stored key in logs/errors — both must fail to leak.

**DoD:** audit log captures a full search; security review passes; data deletion works.

## Phase 6 — Pilot with design partners  ·  ~2–4 weeks (light build)
Tasks: onboard 3–5 design partners (start with independent recruiters/small agencies); onboarding flow (add key → create job → share link/bulk-upload → run search); tight weekly feedback loop; iterate the rubric against real roles; track "did it save time and did they trust it?"

**⛔ GATE — pilot sign-off:** ≥3 partners run real searches and say they'd keep using it / pay.

**DoD:** documented feedback, fixes shipped, ≥3 partners validating value.

## Phase 7 — Production launch & scale-readiness  ·  ~1 week + ongoing
Tasks: error tracking + uptime/latency monitoring (keys redacted); DB backups + queue retry/dead-letter; intake and processing scale independently; load-test a 1,000-CV search; documented config-only model swap process; customer onboarding guide + internal runbook; pricing + landing page + first-cohort outreach.

**DoD:** monitored, backed-up, documented; a 1,000-CV search completes reliably; first non-pilot customers onboarding.

---

## Cross-cutting: testing strategy
- **Golden set is sacred:** version-control the 300-CV/top-10 set; re-run after any change to parsing, rubric, or model config.
- **Output validation everywhere:** every model response JSON-validated; malformed → retry, never corrupt a run.
- **Evidence audits:** spot-check that each `evidence_quote` exists in the source CV — your best hallucination detector.

## Critical-path summary
Foundations → Intake → Parsing → **Scoring → Rank/Refine (300→10 gate)** → Hardening → Pilot → Launch.
The scoring + ranking pair (Phases 3–4) is where the product lives or dies.
