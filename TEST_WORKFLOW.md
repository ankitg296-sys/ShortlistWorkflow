# ShortList Workflow Test Guide

> Validate the full pipeline: CV upload → parsing → scoring → ranking → shortlist

---

## Quick Start

### 1. Get Your API Key
- Go to https://console.anthropic.com
- Create an API key (or use existing)
- Copy it (format: `sk-ant-...`)

### 2. Start Both Services

**Terminal 1 (Intake Service):**
```bash
cd C:\Users\Ankit\Desktop\Shortlist-new\ShortlistWorkflow
python -m uvicorn intake_service.main:app --reload --port 8001
```

**Terminal 2 (Processing Service):**
```bash
cd C:\Users\Ankit\Desktop\Shortlist-new\ShortlistWorkflow
python -m uvicorn processing_service.main:app --reload --port 8002
```

### 3. Run the Test Script

```bash
python test_single_cv.py --api-key sk-ant-YOUR-KEY-HERE
```

Or interactive (will prompt for key):
```bash
python test_single_cv.py
```

---

## What the Test Does

The script runs the **complete ShortList workflow** in 10 steps:

| Step | Action | Validates |
|------|--------|-----------|
| 1 | Sign up org + recruiter | Auth + multi-tenant org isolation |
| 2 | Add API key | Key storage (encrypted, no plaintext) |
| 3 | Test API key | Key validation + Anthropic connectivity |
| 4 | Create job | Job creation + apply link generation |
| 5 | Submit CV | Intake service + file upload + routing |
| 6 | Wait for parsing | Async parsing: PDF/DOCX → clean text |
| 7 | Create search | Rubric builder: prompt + JD → criteria |
| 8 | Run search | Trigger scoring pipeline |
| 9 | Poll results | Wait for async scoring to complete |
| 10 | Display shortlist | Score + evidence + rank |

---

## Example Output

```
======================================================================
  ShortList End-to-End Workflow Test
======================================================================
Testing: Sign up → Parse CV → Score → Rank → Shortlist

→ Step 1: Create org and recruiter account
✅ Signed up:
   Org ID: org-abc123
   User ID: user-xyz789
   Email: tester+1717584290@shortlist.test

→ Step 2: Add customer's Anthropic API key
✅ API key added:
   Key ID: key-q1w2e3r4
   Hint: t-4x (last 4 chars)

→ Step 3: Test API key validity
✅ API key validated successfully

→ Step 4: Create a job posting
✅ Job created:
   Job ID: job-5d6e7f8g
   Title: Senior Python Engineer
   Apply link token: abc123def456

→ Step 5: Candidate submits CV
✅ CV submitted:
   Application ID: app-h9i0j1k2
   Name: John Doe
   Email: john.doe@example.com

→ Step 6: Wait for CV parsing to complete
   (Parsing runs asynchronously; polling every 2 seconds...)
   Polling... (0s elapsed)
✅ CV parsed and candidate ready

→ Step 7: Create search with rubric
✅ Search created with rubric:
   Search ID: search-l3m4n5o6
   Status: pending
   Criteria (3):
     - production_ml_shipping (weight 0.40): Shipped ML systems to production
     - team_leadership (weight 0.35): Led and mentored engineering teams
     - python_depth (weight 0.25): Deep Python expertise and best practices

→ Step 8: Trigger scoring pipeline
✅ Scoring pipeline started
   Waiting for results (typically 30s-2min for 1 CV)...

→ Step 9: Poll for scoring results
   Status: running (0s elapsed, 0 scores)
   Status: running (10s elapsed, 0 scores)
   Status: complete (45s elapsed, 1 scores)
✅ Scoring complete!

→ Step 10: Retrieve and display shortlist

✅ SHORTLIST RESULTS (1 candidate(s)):
======================================================================

#1 Candidate app-h9i0j1k2...
    Overall Score: 0.87 / 1.0 (87%)
    Summary: Strong ML engineer with proven production shipping experience, solid leadership, and deep Python expertise. Would be a great fit for this role.
    Criteria Breakdown:
      • production_ml_shipping: 0.95
        Evidence: "Shipped fraud detection ML system to production, reducing false positives by 40%"
      • team_leadership: 0.75
        Evidence: "Led team of 4 engineers on ML infrastructure and data pipeline projects"
      • python_depth: 0.90
        Evidence: "7 years of Python programming, TensorFlow, PyTorch, Scikit-learn expertise"
    Flags: none

======================================================================
✅ TEST COMPLETE - Full pipeline validated!
======================================================================

Summary:
  Org: Test Shortlist Org
  Job: Senior Python Engineer
  Candidates scored: 1
  Top score: 0.87
  Search ID: search-l3m4n5o6
```

---

## Troubleshooting

### "Services not running"
**Fix:** Make sure both services started successfully (check for errors in terminals)

### "API key validation failed"
**Cause:** Invalid Anthropic API key
**Fix:** Get a valid key from https://console.anthropic.com

### "Search did not complete within 4 minutes"
**Cause:** Scoring is taking too long (rare)
**Fix:** Check processing-service logs for errors, or try again

### "Parsing status still shows pending"
**Cause:** Async parsing still in progress (normal)
**Fix:** Script continues anyway; parsing happens in background

---

## Testing Different CVs

### Use Your Own CV
```bash
python test_single_cv.py --api-key sk-ant-YOUR-KEY --cv /path/to/your/cv.pdf
```

### Test Multiple CVs (Sequential)
```bash
for cv in cv1.pdf cv2.pdf cv3.pdf; do
  python test_single_cv.py --api-key sk-ant-YOUR-KEY --cv $cv
done
```

---

## What's Being Tested

✅ **Intake Service:**
- Public apply link
- CV file upload (PDF/DOCX)
- Fire-and-forget routing to processing

✅ **Processing Service:**
- Auth (org signup, JWT)
- Key management (encrypt, store, validate)
- Rubric builder (prompt → criteria)
- Scoring pipeline (one CV per call, isolated)
- Evidence validation (quotes from CV)
- Ranking (deterministic sort)
- Shortlist API (top-N results)

✅ **Multi-tenant Isolation:**
- Each org's data is separate
- Keys encrypted per org
- Audit log captures events

✅ **Model Integration:**
- Uses **your** Anthropic API key (BYOK model)
- Prompt caching (JD cached across calls)
- Cache-friendly (ephemeral cache control)

---

## Next Steps

Once the test passes:

1. **Try with 10 CVs:** Upload 10 different CVs and run one search
2. **Modify the prompt:** Change `TEST_PROMPT` to test different evaluation criteria
3. **Check audit log:** `GET /compliance/audit-log` to see all events logged
4. **Test the React dashboard:** Connect the UI to the API endpoints
5. **Golden test gate:** Run 300 CVs with expert top-10 answer key (tests P4 gate)

---

## Architecture

```
Candidate uploads CV via apply link
         ↓
    [Intake Service]
         ↓
  File stored in Supabase Storage
  Application row created
         ↓
  Event: application.received
         ↓
    [Processing Service - Async]
         ↓
  1. Parse CV → clean text (PDF/DOCX + OCR)
  2. Store parsed_text on candidate row
         ↓
  Recruiter creates search (rubric)
         ↓
  Recruiter triggers search.run
         ↓
  1. Decrypt org's API key
  2. Score each candidate (one model call per CV)
  3. Prompt-cache shared JD/rubric
  4. Validate evidence quotes
  5. Deterministic ranking
  6. Optional: refine top-15
         ↓
  Shortlist returned (top-N, ranked, with evidence)
```

---

## Environment Variables

The test uses these from `.env`:
- `SUPABASE_URL` - Supabase project URL
- `SUPABASE_SERVICE_ROLE_KEY` - For processing service
- `SUPABASE_JWT_SECRET` - For token validation
- `INTERNAL_AUTH_TOKEN` - Shared between services
- `ENCRYPTION_MASTER_KEY` - For key vault
- `DEFAULT_MODEL` - (optional) Default Claude model

All required; fill in `.env` before running.

---

## Questions?

Check the logs:
```
[Intake Service Log] http://localhost:8001/health
[Processing Service Log] http://localhost:8002/health
[API Docs] http://localhost:8002/docs
[Audit Log] GET /compliance/audit-log (requires JWT)
```
