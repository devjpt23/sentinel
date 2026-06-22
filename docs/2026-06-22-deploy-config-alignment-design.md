# Deploy Config Alignment — Frontend to Vercel, VPS to API-only

## Summary

Move the Next.js frontend deployment from VPS to Vercel, clean up stale VPS config, and fix cache accessibility for running services. The VPS becomes API-only (Flask + daemon).

## Changes

### 1. `deploy/sentinel-web.service` — delete

No longer needed. Frontend runs on Vercel.

### 2. `.github/workflows/deploy-frontend.yml` — Vercel deploy

Replace SCP+SSH+VPS-npm workflow with a single `npx vercel deploy --prod` step. Build happens on Vercel's infrastructure. Requires `VERCEL_TOKEN` secret in GitHub.

### 3. `deploy/nginx-sentinel.conf` — strip frontend blocks

Remove the `frontend` upstream block and the `sentinel.app` / `www.sentinel.app` server block. Keep only the `sentinel_api` upstream and `api.sentinel.app` server block.

### 4. `src/api/server.py` — CORS and docstring

- Keep `https://sentinel.app` in CORS origins (user may point domain later)
- Add `https://web-fryhoudgw-devjpt23s-projects.vercel.app` as a default CORS origin
- Update docstring: `0.0.0.0` is intentional, not a docstring bug

### 5. `deploy/sentinel-daemon.service` and `deploy/sentinel-api.service`

Add `/home/sentinel/.cache` to `ReadWritePaths` so the yfinance cache directory is writable at runtime despite `ProtectSystem=strict`.
