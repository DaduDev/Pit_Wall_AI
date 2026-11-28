# Data Model: Real User Authentication

**Feature**: `002-real-user-auth` | **Date**: 2026-11-28

## Stateless Domain Entities

### 1. AuthenticatedUser (Backend Request Principal)
Derived deterministically on every protected request from verified Supabase JWT claims—zero local `USERS_DB` or persistent user file on the backend.

| Field | Source Claim | Required | Validation / Notes |
|---|---|---|---|
| `id` | `payload["sub"]` | Yes | Supabase user UUID string; rejected with 401 if empty/missing |
| `email` | `payload.get("email")` | No | Lowercase email string from JWT claims (empty string fallback if omitted) |
| `display_name` | `user_metadata.display_name` / `user_metadata.full_name` / `email` prefix | No | Human-readable pit-wall label shown in header |
| `role` | `payload.get("role")` | No | Defaults to `"authenticated"` |

### 2. SupabaseJWTVerificationConfig (Backend Settings)
| Setting | Env Variable | Default | Notes |
|---|---|---|---|
| `SUPABASE_URL` | `SUPABASE_URL` | `""` | Base Supabase project URL; derives JWKS endpoint `{SUPABASE_URL}/auth/v1/.well-known/jwks.json` and issuer `{SUPABASE_URL}/auth/v1` |
| `SUPABASE_JWT_SECRET` | `SUPABASE_JWT_SECRET` | `""` | Optional HS256 fallback secret for legacy HS256 Supabase tokens |
| `SUPABASE_JWT_AUDIENCE` | `SUPABASE_JWT_AUDIENCE` | `"authenticated"` | Expected `aud` claim validated on every token |

### 3. ClientAuthState (Frontend Session State)
Managed via `@supabase/supabase-js` (`getSession` + `onAuthStateChange`).

| Field | Type | Description |
|---|---|---|
| `user` | `{ id: string; email: string; display_name: string } \| null` | Mapped from Supabase `Session.user` |
| `token` | `string \| null` | Current `Session.access_token` (refreshed via `getSession()` before API calls) |
| `isAuthenticated` | `boolean` | `true` only when a live Supabase session exists |
| `isInitializing` | `boolean` | Prevents login screen flash while initial `getSession()` resolves on page reload |
| `confirmationMessage` | `string \| null` | Non-error prompt shown when `signUp()` returns `user` with `session: null` |
| `error` | `string \| null` | Inline validation, credential, confirmation, or 401 session-expired message |

## State Transitions

```text
Unauthenticated ──[signUp -> session != null]──────────────▶ Authenticated
Unauthenticated ──[signUp -> user != null, session == null]▶ ConfirmationPending (stay on Auth UI w/ notice)
Unauthenticated ──[signInWithPassword success]─────────────▶ Authenticated
Authenticated   ──[page reload + getSession() valid]───────▶ Authenticated
Authenticated   ──[signOut() OR HTTP 401 session expired]──▶ Unauthenticated (local session cleared)
```
