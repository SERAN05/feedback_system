# Deploy This Repo on Railway

This project is now configured for Railway deployment.

## Added for Railway

- `requirements.txt` at repo root (points to `main/requirements.txt`)
- `Procfile` with Gunicorn start command
- `railway.json` with explicit start command and healthcheck

## One-time steps

1. Push your latest commit to GitHub.
2. Go to Railway dashboard and click **New Project**.
3. Choose **Deploy from GitHub repo**.
4. Select this repository and branch.
5. Railway will build and deploy automatically.

## Add database

1. In Railway project, click **New** -> **Database** -> **PostgreSQL**.
2. Open your service -> **Variables**.
3. Add `DATABASE_URL` and set it to the Postgres connection URL from Railway.
4. Add `SECRET_KEY` with a strong random value.

## Run migrations (important)

After the first deploy, run this command in Railway service shell:

```bash
cd main
flask --app app:create_app db upgrade --directory admin/migrations
```

## Redeploy

1. Trigger a redeploy from Railway dashboard after migration.
2. Open service URL and test login/dashboard.

## Notes

- Free/trial limits may pause services when idle, depending on Railway plan.
- If app fails to boot, check logs for missing env vars (`DATABASE_URL`, `SECRET_KEY`).
