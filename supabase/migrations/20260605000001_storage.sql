-- Create the cvs storage bucket for candidate CV uploads.
-- All uploads use the service role key (bypasses storage RLS).
-- Run in Supabase SQL editor or via `supabase db push`.

INSERT INTO storage.buckets (id, name, public)
VALUES ('cvs', 'cvs', false)
ON CONFLICT (id) DO NOTHING;
