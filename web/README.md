# ShortList Dashboard (React)

Recruiter-facing dashboard for AI-powered CV shortlisting.

## Setup

```bash
cd web
npm install
cp .env.example .env
# Edit .env with your Supabase credentials
npm run dev
```

Opens at `http://localhost:3000`.

## Features (P4)

- **Login**: Supabase Auth
- **Jobs page**: create job, copy apply link, start search
- **Shortlist view**: ranked candidates, per-criterion scores, evidence quotes, flags
- **Clearly labelled**: "Decision support — human makes final call"

## TODO (future phases)

- Hook up to live API endpoints
- View full CV from shortlist card
- Edit search + re-run
- Bulk export shortlist
- Recruiter dashboard analytics
