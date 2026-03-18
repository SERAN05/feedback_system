# Deploy This Project on Render (Free Tier)

This repository is now configured for Render Blueprint deploy.

## What was prepared

- Added `render.yaml` at repo root.
- Added `main/requirements.txt` for installation from the app root.
- Updated `main/admin/requirements.txt` with production essentials (`gunicorn`, `psycopg2-binary`).
- Made sentiment analysis resilient if `transformers` is unavailable.

## Deploy steps

1. Push your latest commit to GitHub.
2. Open Render dashboard -> New -> Blueprint.
3. Connect this repository and select the branch.
4. Render will detect `render.yaml` and create:
   - Web service: `feedback-app`
   - Postgres database: `feedback-db`
5. Click **Apply**.
6. Wait for build and first deploy to finish.

## Runtime behavior

- Render runs from `main/` (`rootDir: main`).
- App command:
  - `gunicorn app:app --bind 0.0.0.0:$PORT --workers 1 --threads 4 --timeout 120`
- Post-deploy migration command:
  - `flask --app app:create_app db upgrade --directory admin/migrations`

## Required environment variables

Configured automatically by `render.yaml`:

- `DATABASE_URL` (from `feedback-db` connection string)
- `SECRET_KEY` (auto-generated)
- `PYTHON_VERSION=3.11.10`

## Notes

- Free web services may sleep when idle.
- First cold start may be slower.
- If you want SQLite-only local runs, current fallback remains unchanged in app config.
