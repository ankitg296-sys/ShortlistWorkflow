# ShortList Operations Runbook

> Internal guide for ops, support, and incident response.

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────┐
│ Intake Service (Public, port 8001)                          │
│ - Candidate apply screens & CV upload                       │
│ - NO API keys stored here                                   │
└──────────────────────┬──────────────────────────────────────┘
                       │ Fire-and-forget event
                       ▼
┌─────────────────────────────────────────────────────────────┐
│ Processing Service (Private, port 8002)                     │
│ - Encrypted key vault                                       │
│ - Scoring engine (Anthropic SDK)                            │
│ - Recruiter dashboard API                                   │
│ - Audit log                                                 │
└─────────────────────────────────────────────────────────────┘
                       │
                       ▼
          ┌────────────────────────┐
          │  Supabase (Database)   │
          │  - Multi-tenant (org)  │
          │  - RLS policies        │
          │  - Audit log           │
          │  - CV storage (S3)     │
          └────────────────────────┘
```

---

## Deployment Checklist

- [ ] Services deployed to staging
- [ ] Supabase migrations applied
- [ ] CORS origins configured for your domain
- [ ] INTERNAL_AUTH_TOKEN set (intake ↔ processing secret)
- [ ] ENCRYPTION_MASTER_KEY set (org key vault)
- [ ] Supabase JWT_SECRET set
- [ ] Anthropic API key added (customer BYOK, not stored here)
- [ ] Error tracking (Sentry) initialized
- [ ] DB backups enabled (daily snapshots)
- [ ] Monitoring/alerting configured

---

## Operational Tasks

### Adding a Customer
1. Create org via POST /auth/signup
2. Confirm they have an Anthropic API key (console.anthropic.com)
3. Send onboarding guide (CUSTOMER_ONBOARDING.md)
4. Monitor first 3 searches for errors

### Key Rotation (Customer)
1. Customer adds new key via Settings → API Keys
2. Customer tests new key (POST /keys/{id}/test)
3. Customer deletes old key
4. Check audit_log for key lifecycle

### Emergency: Suspect Key Compromise
1. Customer deletes the compromised key immediately (DELETE /keys/{id})
2. Check audit_log for unauthorized usage
3. If accessed: rotate ENCRYPTION_MASTER_KEY immediately
4. All keys re-encrypted under new master key

### Data Subject Access Request (DPDP/GDPR)
1. Customer requests their data: support@shortlist.io
2. Fetch all CVs, searches, scores for that org
3. Export as CSV/JSON from audit_log
4. Deliver within 30 days

### Data Deletion (Customer Request)
1. Customer calls DELETE /compliance/data with confirmation
2. Audit_log records deletion before/after
3. Verify via GET /compliance/audit-log (last 90 days)

### Quota Increase Request
1. Customer hits 100 searches/month limit
2. Edit quotas.py::check_quotas_before_search or add per-org config
3. Redeploy
4. Notify customer

---

## Monitoring & Alerts

### Key Metrics (check daily)
- Search completion rate (% completed vs. failed)
- Average scoring latency (should be < 5 min for 100 CVs)
- API error rate (target: < 1%)
- Org count, search count (growth)

### Alert on:
- API 500 errors (processing-service logs)
- Scoring failures (> 5% of scores failed)
- DB connection pool exhaustion
- Key decryption failures (possible corruption)

### Log Sources
- **intake-service.log:** candidate submissions, apply link access
- **processing-service.log:** searches, scoring, API calls (keys REDACTED)
- **Supabase audit_log table:** immutable activity log (never deleted)

---

## Troubleshooting

### Search Hangs (Status: "running" for > 30 min)
1. Check processing-service logs for scoring task
2. Check Anthropic API status (status.anthropic.com)
3. If stuck: manually update search status to "error" in DB
4. Ask customer to retry with fewer candidates

### "Cannot Decrypt Key"
1. Check ENCRYPTION_MASTER_KEY environment variable matches DB setup
2. If master key was rotated: run key re-encryption migration
3. If no recovery possible: ask customer to add new key

### API Rate Limit (429 Too Many Requests)
1. Check GET /quotas for org usage
2. If under limit but 429: check global API rate limiting (slowapi)
3. Increase intake-service rate limit (limiter.py)

### Candidate CV Parse Fails
1. Check parsing/extractor.py for errors
2. Tesseract/OCR dependency missing? Check pytesseract install
3. If parsing consistently fails: contact Anthropic (PDF format issue)

---

## Backup & Recovery

### Daily Backups
- Supabase auto-snapshots (via managed hosting)
- Encrypted keys backed up (never in plaintext)
- Audit log backed up (immutable)

### Recovery
1. If DB corrupted: restore from last snapshot
2. If encryption master key lost: **UNRECOVERABLE** (all keys encrypted under it)
   - Mitigation: customer adds new keys
3. If audit_log corrupted: restore from snapshot (read-only)

---

## Security Incidents

### Suspected Key Exposure in Logs
1. Check all log sources (intake, processing, DB)
2. If key in plaintext: rotate ENCRYPTION_MASTER_KEY immediately
3. Force all customers to re-add keys
4. File incident report

### Unauthorized Cross-Org Access
1. Check audit_log for suspicious queries
2. Review RLS policies (supabase/migrations/)
3. Check org_id filters in all routers/queries
4. File security incident

---

## Performance Tuning

### Slow Scoring (> 10 min for 100 CVs)
1. Check Anthropic API latency (API status)
2. Check prompt_cache hit rate (should be 90%+)
3. Consider cheaper model for large batches (via model_config)
4. Run scoring in more parallel workers

### High API Error Rate
1. Check API error logs for pattern (e.g., "invalid prompt")
2. Update prompt/rubric builder
3. Increase retry count in scorer.py

---

## Release Checklist

Before shipping a new version:
- [ ] All tests pass (pytest tests/)
- [ ] Golden test passes (tests/golden_run.py)
- [ ] Security review (no key exposure, cross-org isolation works)
- [ ] Load test passes (tests/load_test.py)
- [ ] Docs updated (CUSTOMER_ONBOARDING.md, RUNBOOK.md)
- [ ] Changelog updated
- [ ] Staging deployed and tested with real org
- [ ] Production deployed (blue-green if possible)

---

## Escalation Contacts

- **Anthropic API Issues:** api-support@anthropic.com
- **Supabase Database Issues:** support@supabase.io
- **Security Issues:** security@shortlist.io
- **Customer Support:** support@shortlist.io
