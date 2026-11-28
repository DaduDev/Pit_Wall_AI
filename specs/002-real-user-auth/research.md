# Phase 0 Research: Stateless Supabase Auth for PitWall AI

**Feature**: `002-real-user-auth` | **Date**: 2026-11-28

## Research Decisions

### 1. Stateless Backend Verification Without Supabase Python SDK
- **Decision**: Verify Bearer JWTs in `backend/app/auth/dependencies.py` using `PyJWT` (`jwt.decode`) and `jwt.PyJWKClient` pointing to `{SUPABASE_URL}/auth/v1/.well-known/jwks.json`, backed by `cryptography` in `backend/requirements.txt`, without installing the `supabase` Python SDK or maintaining any local `USERS_DB`.
- **Rationale**: The full `supabase` Python SDK pulls heavy HTTP/realtime/storage sub-packages unnecessary for pure token verification in a lightweight Vercel Docker container. Supabase now signs user JWTs asymmetrically (ES256 / RS256 via JWKS) cleanly verifiable via `PyJWKClient` + `cryptography`, while stateless verification eliminates stale in-memory user dictionaries across container cold starts.
- **Alternatives considered**:
  - Calling Supabase `/auth/v1/user` over HTTP on every API request — rejected due to unnecessary external latency (~100–250ms per request) and external availability coupling on every stream turn.
  - Installing full `supabase` Python client — explicitly rejected per container minimalism and architectural requirements.

### 2. Caching & Offloading JWKS Fetches Off the Async Event Loop
- **Decision**: Maintain a thread-safe cached `PyJWKClient` instance (`cache_keys=True`, `lifespan=3600` seconds) per JWKS URL and execute `pyjwk_client.get_signing_key_from_jwt(token)` + `jwt.decode(...)` inside `await asyncio.to_thread(...)`.
- **Rationale**: `PyJWKClient` uses synchronous `urllib.request` internally when fetching or refreshing keys after key rotation. Running it directly inside an `async def` FastAPI dependency would block Uvicorn's event loop during cold starts or key rotation. Offloading to a worker thread preserves non-blocking SSE concurrency while caching avoids redundant network lookups.
- **Alternatives considered**: Custom async `httpx` JWK parser — unnecessary complexity when `PyJWKClient` handles JWK Set parsing, `kid` matching, key caching, and rotation refreshes reliably off-loop.

### 3. Legacy HS256 Token Support via Optional `SUPABASE_JWT_SECRET` Fallback
- **Decision**: Inspect the unverified JWT header (`jwt.get_unverified_header(token)`). If `alg` starts with `"HS"` (e.g., `"HS256"`) and `SUPABASE_JWT_SECRET` is configured (or if asymmetric JWKS verification fails because `SUPABASE_URL` is absent while `SUPABASE_JWT_SECRET` is set), verify cleanly with `SUPABASE_JWT_SECRET` and `algorithms=["HS256"]`, still enforcing `audience="authenticated"` and `exp`/`sub`. Asymmetric tokens (`ES256`, `RS256`, `EdDSA`) always validate against JWKS and enforce `audience="authenticated"` and `issuer="{SUPABASE_URL}/auth/v1"` (when `SUPABASE_URL` is set).
- **Rationale**: Older Supabase projects or local test harnesses frequently issue HS256 tokens signed with the project's JWT secret, whereas modern Supabase projects use asymmetric ES256 JWKS. Supporting both keeps zero-downtime compatibility without weakening algorithm confusion checks (HS256 only runs if `alg == "HS256"` and secret is explicitly configured).
- **Alternatives considered**: Disallowing HS256 altogether or trusting unverified payloads — rejected.

### 4. Protecting Analytical Endpoints & Internal A2A Hops Without Breaking Orchestration
- **Decision**:
  - Public (unauthenticated): `GET /`, `GET /health`, `GET /api/health`, plus `/.well-known/agent-card.json` discovery metadata if needed (while all execution POST routes require auth).
  - Protected (`Depends(get_current_user)`): `POST /api/chat/stream`, `GET /api/auth/me`, and all `/a2a/*` execution endpoints (`/a2a/historical`, `/a2a/historical/query`, `/a2a/telemetry`, `/a2a/telemetry/*`, `/a2a/research`, `/a2a/research/*`, `/a2a/viz`, `/a2a/viz/render`).
  - Internal ASGI delegation (`A2AClient`): Store the validated incoming `Authorization` header (or internal request context token) in a `contextvars.ContextVar` within `/api/chat/stream` so `A2AClient` automatically forwards the caller's verified `Authorization: Bearer ...` header on internal ASGI calls cleanly.
- **Rationale**: Directly prevents external unauthenticated callers from hitting `/a2a/historical/query` or `/a2a/telemetry/compare-corners` around `/api/chat/stream`, while keeping the A2A HTTP/ASGI specialist boundary 100% genuine and authenticated end-to-end without circular deadlocks or secret backdoors.
- **Alternatives considered**: Removing auth checks on `/a2a/*` — leaves telemetry and DuckDB query endpoints publicly exposed on Vercel.

### 5. Frontend Session Lifecycle & Email Confirmation UX (`@supabase/supabase-js`)
- **Decision**: Initialize a single `@supabase/supabase-js` client (`frontend/src/lib/supabase.ts`) using `VITE_SUPABASE_URL` and `VITE_SUPABASE_ANON_KEY`. Use `supabase.auth.getSession()` + `onAuthStateChange` for reload persistence, `signInWithPassword` for login, `signUp` for registration (explicitly surfacing confirmation-pending instructions whenever `data.user` exists and `data.session` is `null`), and read `supabase.auth.getSession()` dynamically before every `fetch` / SSE `/api/chat/stream` call to inject the freshest non-expired `access_token`. On backend `401 Unauthorized`, call `signOut()` and return the user to `LoginPage` with a clear session-expired notice.
- **Rationale**: Supabase automatically handles token refresh before expiry when `getSession()` is queried per request, avoiding failed turns caused by stale cached `localStorage` tokens from an earlier page render, while `data.session === null` cleanly distinguishes email-confirmation-required sign-ups from immediate sign-ins.
- **Alternatives considered**: Storing static access tokens manually in `localStorage.getItem('pitwall_token')` — rejected because `@supabase/supabase-js` manages automatic token refresh and expiration cleanly.
