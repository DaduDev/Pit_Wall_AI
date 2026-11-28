# Implementation Plan: Real User Authentication (Supabase Auth)

**Branch**: `002-real-user-auth` | **Date**: 2026-11-28 | **Spec**: [spec.md](file:///D:/Learning/F1_Tracker/f1-race-engineer/specs/002-real-user-auth/spec.md)  
**Input**: Feature specification from `/specs/002-real-user-auth/spec.md`

## Summary

Replace PitWall AI's placeholder `demo@pitwall.ai` authentication and in-memory `USERS_DB` store with **100% stateless Supabase Auth** across the split production architecture (FastAPI Docker container on Vercel with `CORS_ORIGINS=https://pit-wall-ai.onrender.com`, React/Vite Static Site on Render). On the backend, remove the local user database and full Supabase Python SDK dependency; verify incoming Supabase Bearer JWTs off the async event loop (`asyncio.to_thread`) via `PyJWT` (`pyjwt`) and a cached `PyJWKClient` against `{SUPABASE_URL}/auth/v1/.well-known/jwks.json` (with `cryptography` listed explicitly and optional `SUPABASE_JWT_SECRET` HS256 fallback), validating `audience="authenticated"`. Enforce authentication across `/api/chat/stream`, `/api/auth/me`, and externally exposed `/a2a/*` analytical endpoints while forwarding caller authorization cleanly on internal orchestrator hops and keeping `/`, `/health`, and `/api/health` public. On the frontend, adopt `@supabase/supabase-js` for email/password sign-up (with clear email-confirmation-required UX), sign-in, reload persistence, and sign-out; read the live session `access_token` prior to each API/SSE request; handle `401` expiry gracefully; declare `VITE_SUPABASE_URL` and `VITE_SUPABASE_ANON_KEY` in strict TypeScript; and delete all hardcoded demo credentials and bypasses.

## Technical Context

**Language/Version**: Python 3.11+ (backend Docker container / 3.12+ local), TypeScript 5.6+ (frontend)  
**Primary Dependencies**:
- Backend: FastAPI, `pyjwt>=2.9.0` (`PyJWKClient`), `cryptography>=42.0.0`, `httpx` *(NO full `supabase` Python SDK, NO local `USERS_DB` / file store)*
- Frontend: React 18+, Vite 5, Tailwind CSS, `@supabase/supabase-js`
**Storage**: Stateless JWT verification on backend (zero local user database files); Supabase client manages browser session persistence (`localStorage` via `@supabase/supabase-js`) across reloads. Existing embedded read-only DuckDB & runtime `CACHE_DIR` caches remain unchanged.  
**Testing**: `pytest` (valid, expired, invalid/tampered, and missing Bearer tokens across `/api/chat/stream`, `/a2a/*`, `/api/auth/me`, plus public `/`, `/health`, `/api/health` + deployment hardening regression tests), `tsc && vite build` on frontend  
**Target Platform**: Split cloud deployment — FastAPI Docker container on Vercel (`SUPABASE_URL`, optional `SUPABASE_JWT_SECRET`, `CORS_ORIGINS=https://pit-wall-ai.onrender.com`) + React/Vite Static Site on Render (`VITE_SUPABASE_URL`, `VITE_SUPABASE_ANON_KEY`, `VITE_API_URL`)  
**Project Type**: Web application (`backend/` FastAPI API + `frontend/` React SPA)  
**Performance Goals**: Cached JWKS key lookups avoid per-request remote round trips; non-blocking `asyncio.to_thread` keeps FastAPI SSE event loop responsive during cold JWKS fetches or key rotation; frontend auth hydration prevents login flicker on reload.  
**Constraints**: Stateless container friendly (no local SQLite/JSON user tables), strict TypeScript (`strict: true`, `noUnusedLocals: true`), zero hardcoded demo credentials or unauthenticated bypasses.  
**Scale/Scope**: Single stateless backend auth verifier supporting arbitrary Supabase-registered users concurrently across Render SPA clients.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| # | Principle | Status | Evidence |
|---|-----------|--------|----------|
| I | Zero-Hallucination Math | ✅ PASS | Auth layer touches identity/access control only; all analytics continue executing via DuckDB SQL and OpenF1/NumPy without alteration. |
| II | Data Domain Separation | ✅ PASS | Historical DuckDB and Telemetry OpenF1/FastF1 pipelines remain isolated behind authenticated routes. |
| III | Telemetry HUD Visual Standards | ✅ PASS | Updated Sign In / Create Account and confirmation banners match `#0B0F17` / `#121824` / `#E10600` HUD palette and WCAG AA contrast. |
| IV | Provenance Transparency | ✅ PASS | Engineering Trace provenance remains intact for all authenticated queries. |
| V | Automated Verification | ✅ PASS | Comprehensive `pytest` coverage planned for valid, expired, invalid, and missing Bearer JWTs alongside existing real-data and deployment suites. |
| VI | Official F1 Team Colors | ✅ PASS | Unchanged; visualizations retain dynamic FastF1 team color resolution. |
| VII | Session & Lap Metadata Fidelity | ✅ PASS | Unchanged; SSE chart/trace contracts remain identical once authenticated. |

**Gate Result**: ✅ ALL PASS (pre-design and post-design).

## Project Structure

### Documentation (this feature)

```text
specs/002-real-user-auth/
├── plan.md                      # This file (/speckit-plan output)
├── research.md                  # Phase 0 architectural & security research decisions
├── data-model.md                # Phase 1 stateless user/session/JWT models
├── quickstart.md                # Phase 1 validation scenarios
└── contracts/
    └── auth-api.md              # Protected vs public routes, Bearer JWT & Supabase Auth contracts
```

### Source Code (repository root)

```text
backend/
├── requirements.txt             # Ensure pyjwt>=2.9.0 and cryptography>=42.0.0 explicitly listed; remove unused local password hashing libs if unneeded
├── app/
│   ├── config.py                # Add SUPABASE_URL, SUPABASE_JWT_SECRET (optional HS256 fallback), SUPABASE_JWT_AUDIENCE="authenticated"
│   ├── main.py                  # Keep /, /health, /api/health public; auth middleware/dependencies protect analytical routes
│   ├── auth/
│   │   ├── dependencies.py      # Stateless JWKS PyJWKClient + optional HS256 verifier via asyncio.to_thread, get_current_user dependency; remove USERS_DB & DEMO_*
│   │   └── router.py            # Keep GET /api/auth/me (Depends(get_current_user)); remove hardcoded local mock login/register stores
│   ├── chat/
│   │   └── router.py            # Protect POST /api/chat/stream with Depends(get_current_user); forward Authorization header into orchestrator/A2A hops
│   └── a2a/
│       ├── client.py            # ContextVar / header forwarding for internal ASGI orchestrator calls to protected /a2a/* routes
│       └── registry.py          # Protect /a2a/* query execution routes with Depends(get_current_user)
└── tests/
    ├── conftest.py              # Update auth_header fixture for stateless test JWT + mock JWKS verifier
    ├── test_auth_and_session.py # Test valid, expired, invalid, missing Bearer tokens, HS256 fallback, & protected endpoints
    ├── test_chat_stream.py      # Pass auth_header on protected POST /api/chat/stream calls
    ├── test_a2a_orchestrator_e2e.py
    ├── test_a2a_specialists.py
    ├── test_strategy.py
    └── test_deployment_hardening.py  # Verify 401 on missing/invalid/expired tokens alongside rate limit & health public access

frontend/
├── package.json                 # Add @supabase/supabase-js dependency
├── .env.example                 # Document VITE_API_URL, VITE_SUPABASE_URL, VITE_SUPABASE_ANON_KEY
└── src/
    ├── vite-env.d.ts            # Declare VITE_SUPABASE_URL and VITE_SUPABASE_ANON_KEY for strict TypeScript builds
    ├── lib/
    │   └── supabase.ts          # Singleton Supabase browser client (persistSession, autoRefreshToken)
    ├── types/
    │   └── index.ts             # Clean User & AuthState types (confirmationPending, sessionExpiredNotice)
    ├── services/
    │   └── api.ts               # Read fresh access_token from supabase.auth.getSession() + authHeaders helper
    ├── hooks/
    │   ├── useAuth.ts           # Supabase signInWithPassword, signUp (with confirmation-required handling), getSession, onAuthStateChange, signOut
    │   └── useSSEStream.ts      # Attach Bearer access_token on every /api/chat/stream request; trigger clean sign-out/redirect on 401
    ├── components/
    │   └── Auth/
    │       └── LoginPage.tsx    # Sign In / Create Account HUD form, empty defaults, confirmation notice, error alerts, zero demo creds/buttons
    └── App.tsx                  # Handle auth hydration loading state & wire 401 session-expiry sign-out cleanly
```

**Structure Decision**: Existing monorepo split (`backend/` + `frontend/`) mapped directly to Vercel containerized FastAPI + Render Static Site. Authentication becomes completely stateless on the backend (JWKS + optional legacy HS256 secret) and delegates account lifecycle/persistence to `@supabase/supabase-js` on the frontend.

## Complexity Tracking

> No constitution violations detected — no complexity justifications needed.
