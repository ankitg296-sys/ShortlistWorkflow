# ShortList Customer Onboarding Guide

> For pilot partners and early customers. Covers setup, API key management, and best practices.

---

## Quick Start (5 minutes)

### 1. Sign Up
- Visit `https://shortlist.your-domain.com` (or your instance)
- Create account with email
- Verify email link

### 2. Add Your API Key
- Bring your **Anthropic API key** (get one at console.anthropic.com)
- In the ShortList dashboard: **Settings → API Keys → Add Key**
- Paste your key → Click **Test Key** (validates it works)
- Copy the key hint for your records

### 3. Create a Job
- **Jobs → New Job**
- Title: e.g., "Senior Python Engineer, SF"
- Job description (paste the full JD)
- Click **Create**
- Copy the apply link

### 4. Share the Apply Link with Candidates
- Send the link to your applicant pool (email, careers page, LinkedIn, etc.)
- Candidates click → upload CV (PDF or DOCX) → submit
- CVs arrive securely in ShortList

### 5. Run Your First Search
- **Searches → New Search**
- Select the job
- Paste your **evaluation prompt** (e.g., "Find candidates who have shipped ML systems in production")
- Review the criteria generated (edit if needed)
- Click **Run Search**
- Wait 2–5 min (depending on candidate count)

### 6. Review the Shortlist
- Once complete, click **View Shortlist**
- Ranked candidates with scores, criteria breakdown, evidence quotes
- **Download** to CSV or forward to your team

---

## API Key Safety

### Keep Your Key Secure
- **Never** share your API key in Slack, email, or version control
- **Never** paste it in logs or error reports
- Use a password manager or env var to store it locally
- Rotate your key every 90 days

### Test Your Key
- **Settings → API Keys → Test** to verify it still works
- If a key fails, delete it and add a new one

### What We Never Do
- We never log your plaintext API key
- We never return your key in API responses
- Your key is encrypted at rest in our database
- Only your org can decrypt and use your key

---

## Best Practices

### 1. Start Narrow
- Test with a small role (e.g., 20 candidates) first
- Tweak your prompt and criteria based on results
- Then scale to 100+ candidates

### 2. Evidence Quotes
- Every shortlisted candidate has a real quote from their CV
- If a candidate has no evidence, they're marked "insufficient evidence"
- Review these carefully—they're your audit trail

### 3. Decision Support, Not Auto-Reject
- ShortList is a **decision support tool**
- You (the recruiter) always make the final call
- We surface the top 10 of 300—but you may find value outside the top 10

### 4. Give Feedback
- After each search: **Feedback → Rate the Results**
- Help us improve our scoring for your industry/role

### 5. Data Privacy
- All candidate CVs are encrypted
- You can delete all org data anytime: **Settings → Data → Delete**
- We comply with DPDP / GDPR retention windows

---

## Troubleshooting

### "No Active API Key"
**Fix:** Add a key via Settings → API Keys

### "Search Failed to Complete"
**Check:**
- Is your API key still valid? Test it via Settings
- Do you have candidates with parsed CVs? (Check Applications)
- Do you have available quota? (Check Settings → Quotas)

### "Parse Quality: Low Confidence"
**Cause:** The CV was scanned (image-only) and OCR fallback was used
**Fix:** Ask candidate to resubmit as a text PDF or Word doc

### "Search Quota Exceeded"
**Limit:** 100 searches/month, 10 concurrent, 50k candidates/month
**Fix:** Contact support to increase limits, or wait for quota reset

---

## Support & Feedback

- **Issues:** support@shortlist.io
- **Feature requests:** feedback@shortlist.io
- **Documentation:** https://docs.shortlist.io
- **Status page:** https://status.shortlist.io

---

## Terms of Service

By using ShortList:
- You own all CVs and search results
- We do not use your data to train models
- Your API key is your responsibility—rotate if compromised
- We comply with DPDP / GDPR / CCPA data protection laws
- Full terms: https://shortlist.io/terms

---

## What's Next?

- **Invite your team:** Settings → Team → Add Members
- **Schedule a demo:** sales@shortlist.io
- **Join the pilot program:** We offer 3–6 months free for select partners

Welcome to ShortList! 🚀
