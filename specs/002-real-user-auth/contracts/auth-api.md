# API & Auth Contracts: Real User Authentication

**Feature**: `002-real-user-auth` | **Date**: 2026-11-28

## Authorization Model

All protected FastAPI endpoints require:
```http
Authorization: Bearer <supabase_access_token>
```

Token validation enforces:
1. Valid signature verified via cached `PyJWKClient` against `{SUPABASE_URL}/auth/v1/.well-known/jwks.json` (or `SUPABASE_JWT_SECRET` HS256 fallback for legacy HS256 tokens).
2. Unexpired `exp` claim (`ExpiredSignatureError` → `401`).
3. Required `sub` claim and `aud == "authenticated"`.
4. Valid `iss == "{SUPABASE_URL}/auth/v1"` when verifying JWKS tokens via `SUPABASE_URL`.

---

## Route Access Matrix

### Public Endpoints (No Authentication Required)
| Method & Path | Purpose | Unauthenticated Response |
|---|---|---|
| `GET` / `HEAD /` | Root service descriptor | `200 OK` |
| `GET /health` | Container health & readiness probe | `200 OK` (`status`, `env`, `duckdb_ready`, `fastf1_cache_dir`, `active_providers`) |
| `GET /api/health` | API health alias | `200 OK` |
| `GET /a2a/*/.well-known/agent-card.json` | Static A2A capability descriptors (no user/query data) | `200 OK` |

### Protected Endpoints (`Authorization: Bearer <token>` Required)
Missing, malformed, invalid-signature, wrong-audience, or expired tokens return **`401 Unauthorized`**:
```json
{
  "detail": "Authentication credentials missing." // or "Token has expired. Please sign in again." / "Invalid authentication token."
}
```
Response headers include `WWW-Authenticate: Bearer`.

| Method & Path | Purpose | Auth Enforcement |
|---|---|---|
| `GET /api/auth/me` | Return authenticated user claims (`id`, `email`, `display_name`) | `Depends(get_current_user)` |
| `POST /api/chat/stream` | Primary conversational SSE endpoint (forwards caller token to internal A2A hops) | `Depends(get_current_user)` |
| `POST /a2a/historical` & `/a2a/historical/query` | DuckDB SQL query execution | `Depends(get_current_user)` |
| `POST /a2a/telemetry` & `/a2a/telemetry/*` | Corner comparison, full-lap overlay, tyre stint analytics | `Depends(get_current_user)` |
| `POST /a2a/research` & `/a2a/research/*` | Grounded web search & corner alias learning | `Depends(get_current_user)` |
| `POST /a2a/viz` & `/a2a/viz/render` | Dark HUD Plotly/card rendering | `Depends(get_current_user)` |

*(Legacy mock endpoints `POST /api/auth/login` and `POST /api/auth/register` backed by hardcoded `USERS_DB` are removed; sign-up and sign-in are executed directly against Supabase Auth from `@supabase/supabase-js`.)*

---

## Frontend Auth Flows (`@supabase/supabase-js`)

### Sign Up
- Calls `supabase.auth.signUp({ email, password, options: displayName ? { data: { display_name: displayName } } : undefined })`.
- **Immediate session (`data.session !== null`)**: Enters authenticated HUD immediately.
- **Email confirmation required (`data.user !== null && data.session === null`)**: Remains on auth screen and renders a clear HUD confirmation banner instructing the user to check their email and confirm before signing in.

### Sign In & Reload Persistence
- Calls `supabase.auth.signInWithPassword({ email, password })`.
- On startup / page reload, `supabase.auth.getSession()` restores the active session automatically and `onAuthStateChange` tracks refreshes or sign-outs across events.

### Per-Request Token Attachment & Expiry Handling
- Before `POST /api/chat/stream` or `GET /api/auth/me`, client awaits `supabase.auth.getSession()` to attach the active `session.access_token`.
- If the backend responds with `401 Unauthorized`, the client signs out (`supabase.auth.signOut()`), clears chat history, and displays `"Your session has expired or is invalid. Please sign in again."` on `LoginPage`.
