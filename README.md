# ShortList

A bring-your-own-key (BYOK) AI shortlisting engine. Candidates apply with a CV; recruiters get a ranked, evidence-cited shortlist in minutes — on their own API key.

## Architecture

Two services in one repo:

- **intake-service** (`intake_service/`) — public, candidate-facing. CV upload and application intake. Holds no API keys and does no AI work.
- **processing-service** (`processing_service/`) — private. AI engine, recruiter dashboard, encrypted key vault.

See `SPEC.md` for the product spec and `BUILD_PLAN.md` for the phased roadmap.

## Prerequisites

- Python 3.11+
- [Supabase CLI](https://supabase.com/docs/guides/cli) (for migrations)
- A [Supabase project](https://supabase.com) (free tier works for local dev)

## 1. Clone and install

```bash
git clone https://github.com/ankitg296-sys/ShortlistWorkflow.git
cd ShortlistWorkflow
pip install -r requirements.txt
```

## 2. Set up environment variables

```bash
cp .env.example .env
```

Open `.env` and fill in:

| Variable | Where to find it |
|---|---|
| `SUPABASE_URL` | Supabase project → Settings → API |
| `SUPABASE_ANON_KEY` | Same page |
| `SUPABASE_SERVICE_ROLE_KEY` | Same page (keep secret) |
| `ENCRYPTION_MASTER_KEY` | Generate: `python -c "import os, base64; print(base64.b64encode(os.urandom(32)).decode())"` |

## 3. Run the database migration

**Option A — Supabase CLI:**

```bash
supabase login
supabase link --project-ref <your-project-ref>
supabase db push
```

**Option B — SQL editor:**

Paste the contents of `supabase/migrations/20260604000000_initial_schema.sql` into your Supabase project's SQL editor and run it.

## 4. Run both services

Open two terminals from the repo root:

```bash
# Terminal 1 — intake service (port 8001)
uvicorn intake_service.main:app --reload --port 8001

# Terminal 2 — processing service (port 8002)
uvicorn processing_service.main:app --reload --port 8002
```

## 5. Verify

```bash
curl http://localhost:8001/health
# → {"status":"ok","service":"intake"}

curl http://localhost:8002/health
# → {"status":"ok","service":"processing"}
```

## Commands reference

| Action | Command |
|---|---|
| Run intake service | `uvicorn intake_service.main:app --reload --port 8001` |
| Run processing service | `uvicorn processing_service.main:app --reload --port 8002` |
| Run tests | `pytest` |
| Lint | `ruff check .` |
| Format | `ruff format .` |
| Golden gate test | `python -m tests.golden_run` |

## Project layout

```
intake_service/                  # FastAPI — public, no keys, no AI
processing_service/              # FastAPI — private engine + key vault
  vault/                         # Envelope encryption for org API keys (P0)
shared/                          # Pydantic schemas shared across services
  schemas.py                     # CandidateScore — the scoring output contract
web/                             # React frontend (Phase 1+)
tests/                           # pytest suite
supabase/
  migrations/                    # SQL migrations (run in order)
SPEC.md                          # Product spec
BUILD_PLAN.md                    # Phased roadmap
PROGRESS.md                      # Running build log
```
