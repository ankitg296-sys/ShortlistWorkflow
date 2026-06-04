# ShortList Setup Checklist

> Fill in all credentials, then you're ready to test locally.

---

## Credentials You Need to Gather

### **1. Supabase Project** (Free: supabase.com)

- [ ] Go to https://supabase.com
- [ ] Sign up or log in
- [ ] Create a new project (or use existing)
- [ ] Wait for project to initialize (2-3 min)

**Get your 4 Supabase credentials:**

- [ ] **SUPABASE_URL**
  - Where: Project dashboard → Settings → API
  - Copy: **Project URL** (looks like `https://abc123def456.supabase.co`)
  - Paste in `.env`: `SUPABASE_URL=https://abc123def456.supabase.co`

- [ ] **SUPABASE_ANON_KEY**
  - Where: Project dashboard → Settings → API
  - Under "Project API keys", find **anon/public** key
  - Copy: The long JWT-like string (starts with `eyJh...`)
  - Paste in `.env`: `SUPABASE_ANON_KEY=eyJh...`

- [ ] **SUPABASE_SERVICE_ROLE_KEY** (you already have this)
  - Where: Project dashboard → Settings → API
  - Under "Project API keys", find **service_role/secret** key
  - Should already be in `.env` from earlier
  - Verify it starts with `sb_secret_`

- [ ] **SUPABASE_JWT_SECRET** (you already have this)
  - Where: Project dashboard → Settings → API → JWT Settings
  - Copy: **JWT Secret** (UUID format)
  - Should already be in `.env` from earlier
  - Verify it looks like: `926d9b5d-cdb5-4a50-953d-0d2ba1677ef5`

---

### **2. Anthropic API Key** (for testing the scoring engine)

- [ ] Go to https://console.anthropic.com
- [ ] Sign up or log in
- [ ] Click **API Keys** (left sidebar)
- [ ] Click **Create Key** or copy existing key
- [ ] Copy the key (format: `sk-ant-...`)
- [ ] **DO NOT put this in `.env`** — use it directly in the test command:
  ```bash
  python test_single_cv.py --api-key sk-ant-YOUR-KEY-HERE
  ```

---

## Configuration Checklist

### **Step 1: Update `.env` file**

Open `.C:\Users\Ankit\Desktop\Shortlist-new\ShortlistWorkflow\.env` and fill in:

```bash
# Replace these with your actual Supabase values:
SUPABASE_URL=https://YOUR_PROJECT_REF.supabase.co
SUPABASE_ANON_KEY=eyJh... (paste your anon key)
SUPABASE_SERVICE_ROLE_KEY=sb_secret_... (should already be set)
SUPABASE_JWT_SECRET=... (should already be set)
```

**Verify:**
- [ ] `SUPABASE_URL` looks like `https://abc123def456.supabase.co`
- [ ] `SUPABASE_ANON_KEY` is a long string starting with `eyJh`
- [ ] `SUPABASE_SERVICE_ROLE_KEY` starts with `sb_secret_`
- [ ] `SUPABASE_JWT_SECRET` is a UUID
- [ ] `INTERNAL_AUTH_TOKEN` is present (already generated)
- [ ] `ENCRYPTION_MASTER_KEY` is present (already generated)

---

### **Step 2: Apply Supabase Migrations**

The database schema is defined in `supabase/migrations/`. You need to apply these:

**Option A: Via Supabase CLI (recommended)**
```bash
# Install Supabase CLI
npm install -g @supabase/cli

# Link your project
supabase link --project-ref YOUR_PROJECT_REF

# Apply migrations
supabase db push
```

**Option B: Via Supabase Dashboard**
1. Go to your Supabase project dashboard
2. Click **SQL Editor** (left sidebar)
3. Click **New Query**
4. Copy the SQL from `supabase/migrations/20260604000000_initial_schema.sql`
5. Paste and run
6. Repeat for `20260605000001_storage.sql`

**Verify:**
- [ ] Tables exist: `orgs`, `users`, `api_keys`, `jobs`, `applications`, `candidates`, `searches`, `scores`, `audit_log`
- [ ] Storage bucket exists: `cvs` (for CV uploads)
- [ ] RLS policies are enabled (check each table)

---

### **Step 3: Test the Setup**

```bash
# 1. Start intake-service
python -m uvicorn intake_service.main:app --reload --port 8001

# 2. Start processing-service (in another terminal)
python -m uvicorn processing_service.main:app --reload --port 8002

# 3. Run the test script (in a third terminal)
python test_single_cv.py --api-key sk-ant-YOUR-ANTHROPIC-KEY
```

**Expected output:**
- Both services start without errors
- Test script runs through 10 steps
- Final output shows shortlist with scores and evidence

---

## Troubleshooting

### ❌ "SUPABASE_URL is invalid"
- Check format: should be `https://XXXXX.supabase.co`
- Not `http://` (must be HTTPS)
- Not `localhost`

### ❌ "SUPABASE_ANON_KEY is invalid"
- Should be a JWT-like string (long, starts with `eyJ`)
- Not the service role key
- Should be from "anon/public", not "service_role/secret"

### ❌ "Services won't start"
- Check `.env` is in the right location: `C:\Users\Ankit\Desktop\Shortlist-new\ShortlistWorkflow\.env`
- Check Python is installed (`python --version`)
- Check dependencies: `pip install -r requirements.txt`

### ❌ "Test script fails on 'Sign up'"
- Check processing-service is running on port 8002
- Check SUPABASE_URL is correct
- Check SERVICE_ROLE_KEY is correct

### ❌ "Test script fails on 'Add API key'"
- Check your Anthropic API key format (`sk-ant-...`)
- Key may be invalid or revoked
- Get a fresh one from console.anthropic.com

---

## What Each Variable Does

| Variable | Purpose | Security |
|----------|---------|----------|
| `SUPABASE_URL` | Which Supabase project to use | Public (project ID) |
| `SUPABASE_ANON_KEY` | Anonymous client access | Public (limited scope) |
| `SUPABASE_SERVICE_ROLE_KEY` | Full DB access from services | 🔴 **SECRET** — never expose |
| `SUPABASE_JWT_SECRET` | Token signing/verification | 🔴 **SECRET** — never expose |
| `INTERNAL_AUTH_TOKEN` | Service-to-service auth | 🔴 **SECRET** — shared between services |
| `ENCRYPTION_MASTER_KEY` | Customer key vault encryption | 🔴 **SECRET** — losing this = keys unrecoverable |

---

## Final Checklist Before Testing

- [ ] `.env` file exists at project root
- [ ] `SUPABASE_URL` filled in
- [ ] `SUPABASE_ANON_KEY` filled in
- [ ] `SUPABASE_SERVICE_ROLE_KEY` filled in
- [ ] `SUPABASE_JWT_SECRET` filled in
- [ ] `INTERNAL_AUTH_TOKEN` present
- [ ] `ENCRYPTION_MASTER_KEY` present
- [ ] Supabase migrations applied (tables + storage bucket exist)
- [ ] Anthropic API key ready (from console.anthropic.com)
- [ ] Python installed (`python --version`)
- [ ] Dependencies installed (`pip install -r requirements.txt`)
- [ ] Both services can start without errors
- [ ] Test script ready to run

---

## Next: Run the Test

Once all checked, run:

```bash
python test_single_cv.py --api-key sk-ant-YOUR-KEY
```

This validates the entire pipeline:
- Auth + org creation
- Key encryption
- CV parsing
- Scoring (using your API key)
- Ranking
- Shortlist generation

Expected time: **2-3 minutes** for one CV.

---

## Questions?

- **Supabase help:** https://supabase.com/docs
- **Anthropic API help:** https://docs.anthropic.com
- **ShortList docs:** See `README.md`, `CLAUDE.md`, `SPEC.md`
