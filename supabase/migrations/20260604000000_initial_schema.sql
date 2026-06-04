-- ShortList initial schema
-- Org-as-tenant model: every tenant-scoped table carries org_id.
-- RLS locks every row to the org of the authenticated user.

-- ── Extensions ────────────────────────────────────────────────────────────────
CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- ── Helper: resolve the calling user's org ────────────────────────────────────
-- SECURITY DEFINER bypasses RLS on the users table, avoiding a recursive lookup.
CREATE OR REPLACE FUNCTION public.current_org_id()
RETURNS uuid
LANGUAGE sql
STABLE
SECURITY DEFINER
SET search_path = public
AS $$
  SELECT org_id FROM public.users WHERE id = auth.uid()
$$;

-- ── Updated-at trigger ────────────────────────────────────────────────────────
CREATE OR REPLACE FUNCTION public.set_updated_at()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
  NEW.updated_at = now();
  RETURN NEW;
END;
$$;

-- ── orgs ──────────────────────────────────────────────────────────────────────
CREATE TABLE public.orgs (
  id          uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
  name        text        NOT NULL,
  created_at  timestamptz NOT NULL DEFAULT now(),
  updated_at  timestamptz NOT NULL DEFAULT now()
);

CREATE TRIGGER orgs_updated_at
  BEFORE UPDATE ON public.orgs
  FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();

ALTER TABLE public.orgs ENABLE ROW LEVEL SECURITY;
CREATE POLICY "orgs_own" ON public.orgs
  FOR ALL
  USING  (id = public.current_org_id())
  WITH CHECK (id = public.current_org_id());

-- ── users ─────────────────────────────────────────────────────────────────────
-- id mirrors auth.users.id (Supabase Auth UID).
CREATE TABLE public.users (
  id          uuid        PRIMARY KEY,  -- matches auth.uid()
  org_id      uuid        NOT NULL REFERENCES public.orgs(id) ON DELETE CASCADE,
  email       text        NOT NULL,
  full_name   text,
  role        text        NOT NULL DEFAULT 'recruiter',  -- recruiter | admin
  created_at  timestamptz NOT NULL DEFAULT now(),
  updated_at  timestamptz NOT NULL DEFAULT now(),
  UNIQUE (org_id, email)
);

CREATE TRIGGER users_updated_at
  BEFORE UPDATE ON public.users
  FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();

ALTER TABLE public.users ENABLE ROW LEVEL SECURITY;
CREATE POLICY "users_org_isolation" ON public.users
  FOR ALL
  USING  (org_id = public.current_org_id())
  WITH CHECK (org_id = public.current_org_id());

-- ── api_keys ──────────────────────────────────────────────────────────────────
-- Stores envelope-encrypted customer API keys. Plaintext is NEVER stored here.
CREATE TABLE public.api_keys (
  id              uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
  org_id          uuid        NOT NULL REFERENCES public.orgs(id) ON DELETE CASCADE,
  provider        text        NOT NULL,               -- e.g. 'anthropic'
  encrypted_key   text        NOT NULL,               -- envelope-encrypted ciphertext
  key_hint        text,                               -- last 4 chars for display only
  model_config    jsonb       NOT NULL DEFAULT '{}',  -- e.g. {"scoring_model": "..."}
  is_active       boolean     NOT NULL DEFAULT true,
  validated_at    timestamptz,                        -- timestamp of last successful live-test
  created_at      timestamptz NOT NULL DEFAULT now(),
  updated_at      timestamptz NOT NULL DEFAULT now()
);

CREATE TRIGGER api_keys_updated_at
  BEFORE UPDATE ON public.api_keys
  FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();

ALTER TABLE public.api_keys ENABLE ROW LEVEL SECURITY;
CREATE POLICY "api_keys_org_isolation" ON public.api_keys
  FOR ALL
  USING  (org_id = public.current_org_id())
  WITH CHECK (org_id = public.current_org_id());

-- ── jobs ──────────────────────────────────────────────────────────────────────
CREATE TABLE public.jobs (
  id               uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
  org_id           uuid        NOT NULL REFERENCES public.orgs(id) ON DELETE CASCADE,
  created_by       uuid        REFERENCES public.users(id) ON DELETE SET NULL,
  title            text        NOT NULL,
  description      text,                                    -- job description text
  apply_link_token text        UNIQUE,                      -- token embedded in the shareable link
  status           text        NOT NULL DEFAULT 'active',   -- active | closed | archived
  created_at       timestamptz NOT NULL DEFAULT now(),
  updated_at       timestamptz NOT NULL DEFAULT now()
);

CREATE TRIGGER jobs_updated_at
  BEFORE UPDATE ON public.jobs
  FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();

ALTER TABLE public.jobs ENABLE ROW LEVEL SECURITY;
CREATE POLICY "jobs_org_isolation" ON public.jobs
  FOR ALL
  USING  (org_id = public.current_org_id())
  WITH CHECK (org_id = public.current_org_id());

-- ── applications ──────────────────────────────────────────────────────────────
CREATE TABLE public.applications (
  id              uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
  org_id          uuid        NOT NULL REFERENCES public.orgs(id) ON DELETE CASCADE,
  job_id          uuid        NOT NULL REFERENCES public.jobs(id) ON DELETE CASCADE,
  candidate_name  text        NOT NULL,
  candidate_email text        NOT NULL,
  cv_storage_path text        NOT NULL,                    -- Supabase Storage object path
  cv_filename     text        NOT NULL,
  status          text        NOT NULL DEFAULT 'received', -- received | parsing | parsed | scored | error
  submitted_at    timestamptz NOT NULL DEFAULT now(),
  created_at      timestamptz NOT NULL DEFAULT now(),
  updated_at      timestamptz NOT NULL DEFAULT now()
);

CREATE TRIGGER applications_updated_at
  BEFORE UPDATE ON public.applications
  FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();

ALTER TABLE public.applications ENABLE ROW LEVEL SECURITY;
CREATE POLICY "applications_org_isolation" ON public.applications
  FOR ALL
  USING  (org_id = public.current_org_id())
  WITH CHECK (org_id = public.current_org_id());

-- ── candidates ────────────────────────────────────────────────────────────────
CREATE TABLE public.candidates (
  id              uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
  org_id          uuid        NOT NULL REFERENCES public.orgs(id) ON DELETE CASCADE,
  application_id  uuid        NOT NULL UNIQUE REFERENCES public.applications(id) ON DELETE CASCADE,
  parsed_text     text,
  parse_quality   text        NOT NULL DEFAULT 'pending',  -- pending | good | low_confidence | failed
  parse_metadata  jsonb       NOT NULL DEFAULT '{}',
  created_at      timestamptz NOT NULL DEFAULT now(),
  updated_at      timestamptz NOT NULL DEFAULT now()
);

CREATE TRIGGER candidates_updated_at
  BEFORE UPDATE ON public.candidates
  FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();

ALTER TABLE public.candidates ENABLE ROW LEVEL SECURITY;
CREATE POLICY "candidates_org_isolation" ON public.candidates
  FOR ALL
  USING  (org_id = public.current_org_id())
  WITH CHECK (org_id = public.current_org_id());

-- ── searches ──────────────────────────────────────────────────────────────────
CREATE TABLE public.searches (
  id            uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
  org_id        uuid        NOT NULL REFERENCES public.orgs(id) ON DELETE CASCADE,
  job_id        uuid        NOT NULL REFERENCES public.jobs(id) ON DELETE CASCADE,
  created_by    uuid        REFERENCES public.users(id) ON DELETE SET NULL,
  prompt        text        NOT NULL,
  jd_text       text,
  criteria      jsonb       NOT NULL DEFAULT '[]',      -- rubric criteria + weights
  model_used    text        NOT NULL,
  status        text        NOT NULL DEFAULT 'pending', -- pending | running | complete | error
  started_at    timestamptz,
  completed_at  timestamptz,
  created_at    timestamptz NOT NULL DEFAULT now(),
  updated_at    timestamptz NOT NULL DEFAULT now()
);

CREATE TRIGGER searches_updated_at
  BEFORE UPDATE ON public.searches
  FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();

ALTER TABLE public.searches ENABLE ROW LEVEL SECURITY;
CREATE POLICY "searches_org_isolation" ON public.searches
  FOR ALL
  USING  (org_id = public.current_org_id())
  WITH CHECK (org_id = public.current_org_id());

-- ── scores ────────────────────────────────────────────────────────────────────
-- One row per candidate per search. Schema mirrors SPEC §7.4.
CREATE TABLE public.scores (
  id               uuid          PRIMARY KEY DEFAULT gen_random_uuid(),
  org_id           uuid          NOT NULL REFERENCES public.orgs(id) ON DELETE CASCADE,
  search_id        uuid          NOT NULL REFERENCES public.searches(id) ON DELETE CASCADE,
  candidate_id     uuid          NOT NULL REFERENCES public.candidates(id) ON DELETE CASCADE,
  overall_score    numeric(5, 4) NOT NULL CHECK (overall_score >= 0 AND overall_score <= 1),
  criteria_scores  jsonb         NOT NULL DEFAULT '[]', -- array per SPEC §7.4
  summary          text          NOT NULL,
  flags            jsonb         NOT NULL DEFAULT '[]',
  rank             integer,                             -- set after deterministic sort
  created_at       timestamptz   NOT NULL DEFAULT now(),
  UNIQUE (search_id, candidate_id)
);

ALTER TABLE public.scores ENABLE ROW LEVEL SECURITY;
CREATE POLICY "scores_org_isolation" ON public.scores
  FOR ALL
  USING  (org_id = public.current_org_id())
  WITH CHECK (org_id = public.current_org_id());

-- ── audit_log ─────────────────────────────────────────────────────────────────
-- Append-only. No UPDATE or DELETE policy: rows are immutable once written.
CREATE TABLE public.audit_log (
  id          uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
  org_id      uuid        NOT NULL REFERENCES public.orgs(id) ON DELETE CASCADE,
  search_id   uuid        REFERENCES public.searches(id) ON DELETE SET NULL,
  event_type  text        NOT NULL,             -- e.g. 'search_started', 'search_complete'
  payload     jsonb       NOT NULL DEFAULT '{}', -- inputs + model + summary of outputs
  created_at  timestamptz NOT NULL DEFAULT now()
);

ALTER TABLE public.audit_log ENABLE ROW LEVEL SECURITY;
CREATE POLICY "audit_log_select" ON public.audit_log
  FOR SELECT
  USING (org_id = public.current_org_id());
CREATE POLICY "audit_log_insert" ON public.audit_log
  FOR INSERT
  WITH CHECK (org_id = public.current_org_id());
-- Intentionally no UPDATE or DELETE policy: audit records are immutable.

-- ── Indexes ───────────────────────────────────────────────────────────────────
CREATE INDEX idx_users_org_id            ON public.users(org_id);
CREATE INDEX idx_api_keys_org_id         ON public.api_keys(org_id);
CREATE INDEX idx_jobs_org_id             ON public.jobs(org_id);
CREATE INDEX idx_applications_org_id     ON public.applications(org_id);
CREATE INDEX idx_applications_job_id     ON public.applications(job_id);
CREATE INDEX idx_candidates_org_id       ON public.candidates(org_id);
CREATE INDEX idx_searches_org_id         ON public.searches(org_id);
CREATE INDEX idx_searches_job_id         ON public.searches(job_id);
CREATE INDEX idx_scores_org_id           ON public.scores(org_id);
CREATE INDEX idx_scores_search_id        ON public.scores(search_id);
CREATE INDEX idx_audit_log_org_id        ON public.audit_log(org_id);
CREATE INDEX idx_audit_log_search_id     ON public.audit_log(search_id);
