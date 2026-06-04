# SPEC.md — ShortList (Product Specification)

> The *what*. Stable reference for the product, data model, and the scoring contract.
> Operating rules and current phase: **CLAUDE.md**. Phased roadmap: **BUILD_PLAN.md**. Diagram: **shortlist_workflow.mermaid**.

---

## 1. One-line definition

A **bring-your-own-key (BYOK) AI shortlisting engine** for recruiters: candidates apply with just a CV, and recruiters get a ranked, evidence-cited shortlist in minutes — with every token of inference paid by the customer's own API key. This is **decision support**, not autonomous hiring. A human always makes the final call.

## 2. Core requirement & acceptance criteria

> **Reliably surface the top 10 candidates out of 300 CVs for a given job — and scale beyond without degrading.**

How: each CV is scored **on its own** (like grading 300 exam papers one at a time), so the AI never confuses one candidate with another and there is no practical ceiling on pool size. Ordering is a plain numeric sort (no AI). The AI only takes a careful second look at the top handful.

Acceptance criteria:
- 300 CVs → correct, stable top-10 shortlist (≥8/10 overlap with an expert answer key, agreed up front).
- No cross-candidate contamination (no experience attributed to the wrong person).
- Every score backed by a cited quote from that candidate's CV.
- Scales to 1,000+ CVs (bounded by cost/time, not accuracy).

## 3. What we are NOT building (v1)

- **Not** a public **discovery** job board (candidates browsing all roles like a marketplace). *Deferred.*
  - **In scope:** candidate **application screens** (apply to a specific job via a shared link).
- **Not** an autonomous AI recruiter that contacts or rejects candidates.
- **Not** native multi-provider integration up front. Claude direct via a provider layer; others later.
- **Not** the MCQ weight-elicitation system. *(v2 differentiation play.)*

## 4. System architecture: two services

**4.1 Intake service (candidate-facing).** Hosts the application input screens. Candidate opens a job link, completes minimal fields, submits a CV. Groups submissions under the Job. Exposed to the internet, so it **holds no API keys and does no AI work**.

**4.2 Routing layer.** New applications are routed (queue/webhook) to the processing service. Decoupled so neither side slows the other.

**4.3 Processing & ranking service (private).** Where the entire AI action happens: parsing, scoring, ranking, refinement, recruiter dashboard. Holds the **encrypted BYOK key vault**. Not exposed to candidates.

## 5. Core value proposition

1. Works day one on data the customer already has — no marketplace cold-start.
2. Pennies per search, on the customer's key — removes the cost and data-residency objections at once.
3. One-line ROI: replaces a recruiter manually skimming 300 CVs per role.
4. Audit-ready by design: every score carries cited evidence, logged.

## 6. Primary user flows

**6.1 Candidate (intake):** open per-job apply link → minimal fields + CV upload → stored & grouped → routed to processing. (Alt: recruiter bulk-uploads a folder.)

**6.2 Recruiter (processing):** log in → open Job → enter prompt and/or attach JD → optional criterion weights → run score→rank→refine → view ranked shortlist with per-criterion scores, evidence quotes, and flags.

**6.3 BYOK key management:** org adds provider key → envelope-encrypted, never logged/displayed → org selects a model (or accepts the tiered default).

## 7. The ranking engine (the moat)

**7.1 Why not single-prompt ranking.** All CVs in one prompt causes attribution bleed, lost-in-the-middle, and ranking decay. Reliable single-shot ranking caps at ~10–15 CVs. We do not do this.

**7.2 Score → Rank → Refine.**
- **Score (map):** judge each CV independently — one CV per call. Isolation removes contamination. Parallel + batch-friendly. Effectively unlimited pool size.
- **Rank (reduce):** sort numeric scores in deterministic code. Zero hallucination in ordering.
- **Refine:** one comparative pass over the top ~15 full CVs for exact order.
- **Optional prefilter:** embeddings or a cheap model call to drop obvious non-matches first.

**7.3 Hallucination controls (also the compliance story):** isolation per candidate; forced evidence quote; explicit `insufficient_evidence` escape hatch; structured JSON output against a fixed rubric.

**7.4 Scoring output schema (per candidate):**
```json
{
  "candidate_id": "uuid",
  "overall_score": 0.0,
  "criteria": [
    {
      "name": "Python proficiency",
      "weight": 0.4,
      "score": 0.0,
      "evidence_quote": "verbatim snippet from the CV",
      "insufficient_evidence": false
    }
  ],
  "summary": "2-3 sentence, evidence-grounded rationale",
  "flags": ["e.g. employment_gap", "no_evidence_for_X"]
}
```

## 8. Model strategy

- **Provider layer:** all model calls go through one swap-able abstraction.
- **MVP default:** **Claude API direct** (Anthropic SDK) — simpler, no third-party dependency or fee, native **prompt caching** and **batch API**.
- **OpenRouter:** optional, add **only when a customer needs a non-Claude key**. It is a convenience router, not a requirement.
- **Model IDs live in config, never in code** (models churn fast).
- **Cost levers:** prompt-cache the shared JD/rubric (up to 90% off cached input); run scoring in parallel; batch API for non-realtime (50% off); tiered routing (cheap/embeddings prefilter → stronger model on the shortlist).

## 9. Cost model

| Item | Who pays | Magnitude |
|---|---|---|
| Inference per search | **Customer's key (BYOK)** | ~$1–5 for a 300-CV search → top 10, by model tier |
| Our marginal cost per search | Us | fraction of a cent (infra only) |
| Build (solo, Claude Code) | Us | ~8–12 build-weeks to pilot |
| Infra (early) | Us | ~$50–150/mo, scales with usage |
| Maintenance | Us | ~20–40% of build effort ongoing |

## 10. Security & compliance (from day one)

- **Key vault:** envelope encryption (KMS-backed), never logged, never returned in plaintext. "We never see your key" is part of the pitch.
- **Service separation:** public intake holds no keys; only private processing does.
- **Multi-tenant isolation:** row-level separation between orgs.
- **Posture:** decision-support + human-in-the-loop; cited evidence + immutable audit log per search.
- **Aware of:** India DPDP Act (candidate data — primary near-term), NYC Local Law 144 (bias audits), EU AI Act (hiring = high-risk).

## 11. Tech stack

Python + FastAPI (both services) · routing via queue/webhook · Supabase (Postgres + pgvector + auth + storage) · provider layer over the Anthropic SDK · React (separate candidate-apply UI + recruiter dashboard) · Render/Railway/Fly · robust PDF/DOCX parser with OCR fallback.

## 12. Data model

- `orgs` — tenant root
- `users` — recruiters, belong to an org
- `api_keys` — encrypted, per org, with selected model config
- `jobs` — a role/opening (the "Application name")
- `applications` — a candidate CV submission, grouped under a job
- `candidates` — parsed CV data + link to source file
- `searches` — one ranking run (prompt + JD + weights + model used)
- `scores` — per candidate per search (schema in 7.4)
- `audit_log` — immutable record of every search (inputs, model, outputs)

## 13. Go-to-market

First ICP: independent recruiters + small staffing agencies → then SMB in-house TA → enterprise later (SSO, SOC 2 — defer). Pitch: *"Candidates apply with a CV; you get a ranked, evidence-cited shortlist in two minutes, on your own API key, for a few cents."*

## 14. Build roadmap

See **BUILD_PLAN.md** for the full phased plan and gates. (Not duplicated here.)

## 15. Open decision

**Tenant model: agencies (multi-client) vs in-house (single org).** Default: **org-as-tenant**, built so an agency client-layer can be added later. Confirm before the P0 schema is finalised.
