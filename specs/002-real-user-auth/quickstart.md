# Quickstart Validation Guide: Real User Authentication

**Feature**: `002-real-user-auth` | **Date**: 2026-11-28

## Prerequisites

- Backend environment variables:
  - `SUPABASE_URL=https://<your-project>.supabase.co`
  - Optional: `SUPABASE_JWT_SECRET=<legacy-hs256-secret>`
  - `CORS_ORIGINS=https://pit-wall-ai.onrender.com` (production) or `http://localhost:5173,http://127.0.0.1:5173` (local)
- Frontend environment variables (shared root `.env` via `vite.config.mjs` `envDir`):
  - `VITE_SUPABASE_URL=https://<your-project>.supabase.co`
  - `VITE_SUPABASE_ANON_KEY=<supabase-anon-key>`
  - `VITE_API_URL=http://localhost:8000` (or Vercel backend URL in production)

## Validation Scenarios

### V1: Public Health Without Auth vs Protected Chat Rejection
```bash
# Public health stays accessible (HTTP 200)
curl -i http://localhost:8000/health

# Missing token on chat stream fails cleanly (HTTP 401)
curl -i -X POST http://localhost:8000/api/chat/stream \
  -H "Content-Type: application/json" \
  -d '{"message": "Who won the 2023 Bahrain GP?"}'

# Missing token on specialist execution fails cleanly (HTTP 401)
curl -i -X POST http://localhost:8000/a2a/historical/query \
  -H "Content-Type: application/json" \
  -d '{"question": "Who won the 2023 Bahrain GP?"}'
```

### V2: Automated Backend Pytest Verification
Runs stateless JWKS (RS256/ES256 mocked keys), optional HS256 `SUPABASE_JWT_SECRET` fallback, valid/expired/invalid/missing token checks, and full deployment hardening regression suite:
```bash
python -m pytest backend/tests/test_auth_and_session.py backend/tests/test_deployment_hardening.py -v
python -m pytest backend/tests/ -v
```

### V3: Frontend Strict TypeScript Build & Browser Auth Flow
```bash
cd frontend
npm install
npm run build
```
Manual browser check (`npm run dev`):
1. Open `/`: Verify inputs are empty with zero hardcoded demo credentials or Quick Sign In buttons.
2. Switch to **Create Account**: Register a new email & password; confirm either immediate entry (when email confirmation is off) or explicit check-your-email confirmation notice (when email confirmation is on).
3. Sign in with confirmed email & password, reload page, verify user remains signed in, send a query, then click **Sign Out** and verify return to Sign In.
