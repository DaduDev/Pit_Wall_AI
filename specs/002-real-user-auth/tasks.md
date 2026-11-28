---

description: "Task list for 002-real-user-auth (Stateless Supabase Auth & Frontend Session Management)"
---

# Tasks: Real User Authentication (Supabase Auth)

**Input**: Design documents from `/specs/002-real-user-auth/`  
**Prerequisites**: [plan.md](file:///D:/Learning/F1_Tracker/f1-race-engineer/specs/002-real-user-auth/plan.md) (required), [spec.md](file:///D:/Learning/F1_Tracker/f1-race-engineer/specs/002-real-user-auth/spec.md) (required), [research.md](file:///D:/Learning/F1_Tracker/f1-race-engineer/specs/002-real-user-auth/research.md), [data-model.md](file:///D:/Learning/F1_Tracker/f1-race-engineer/specs/002-real-user-auth/data-model.md), [auth-api.md](file:///D:/Learning/F1_Tracker/f1-race-engineer/specs/002-real-user-auth/contracts/auth-api.md), [quickstart.md](file:///D:/Learning/F1_Tracker/f1-race-engineer/specs/002-real-user-auth/quickstart.md)

**Tests**: Backend authentication, token validation (valid, expired, invalid, missing), and protected route tests are included per implementation plan & `quickstart.md`.

**Organization**: Tasks are grouped by user story (`US1`–`US4`) in priority order so each slice can be implemented and validated cleanly.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies on incomplete tasks)
- **[Story]**: User story label (`[US1]`, `[US2]`, `[US3]`, `[US4]`) — omitted in Setup, Foundational, and Polish phases
- Every task includes exact workspace file path(s)

---

## Phase 1: Setup (Shared Dependencies & Environment Contracts)

**Purpose**: Declare cryptographic JWT dependencies, frontend Supabase client package, and environment configuration without installing the heavy full Supabase Python SDK or storing local users.

- [X] T001 Explicitly add `cryptography>=42.0.0` alongside `pyjwt>=2.9.0` (and omit full `supabase` Python SDK / remove unused `passlib` local auth dependency) in `backend/requirements.txt` and `backend/pyproject.toml`
- [X] T002 [P] Add `@supabase/supabase-js` dependency and lockfile update in `frontend/package.json`
- [X] T003 [P] Declare `VITE_API_URL`, `VITE_SUPABASE_URL`, and `VITE_SUPABASE_ANON_KEY` in `frontend/src/vite-env.d.ts` for strict TypeScript compilation and document them in `frontend/.env.example`
- [X] T004 [P] Add `SUPABASE_URL`, optional `SUPABASE_JWT_SECRET`, and `SUPABASE_JWT_AUDIENCE` settings (citing `data-model.md`: `SupabaseJWTVerificationConfig.SUPABASE_URL`, `SupabaseJWTVerificationConfig.SUPABASE_JWT_SECRET`, `SupabaseJWTVerificationConfig.SUPABASE_JWT_AUDIENCE`) in `backend/app/config.py`

---

## Phase 2: Foundational (Blocking Auth Core Prerequisites)

**Purpose**: Establish stateless backend Supabase JWT verification, internal A2A header forwarding, and singleton browser Supabase client before user story UI/endpoint wiring.

**⚠️ CRITICAL**: No user story work should run until Phase 2 is complete.

- [X] T005 [P] Create singleton `@supabase/supabase-js` client (`persistSession: true`, `autoRefreshToken: true`, explicit missing-env guard) in `frontend/src/lib/supabase.ts`
- [X] T006 Implement 100% stateless Supabase Bearer JWT verification in `backend/app/auth/dependencies.py`: remove `USERS_DB`, `DEMO_PASSWORD`, `DEMO_SALT`, `DEMO_HASH`, and `bcrypt` password helpers; verify asymmetric tokens against `{SUPABASE_URL}/auth/v1/.well-known/jwks.json` using cached `PyJWKClient` executed off the async event loop via `asyncio.to_thread`; support optional `SUPABASE_JWT_SECRET` HS256 fallback; validate `audience="authenticated"` and extract user claims (citing `data-model.md`: `AuthenticatedUser.id`, `AuthenticatedUser.email`, `AuthenticatedUser.display_name`, `AuthenticatedUser.role`, `SupabaseJWTVerificationConfig.SUPABASE_URL`, `SupabaseJWTVerificationConfig.SUPABASE_JWT_SECRET`, `SupabaseJWTVerificationConfig.SUPABASE_JWT_AUDIENCE`)
- [X] T007 Remove legacy local `USERS_DB` `/api/auth/login` and `/api/auth/register` routes and protect `GET /api/auth/me` with `Depends(get_current_user)` in `backend/app/auth/router.py`
- [X] T008 [P] Add `contextvars.ContextVar` Bearer authorization header propagation in `backend/app/a2a/client.py` so internal orchestrator A2A hops forward the authenticated caller token cleanly
- [X] T009 Update shared `auth_header` pytest fixture in `backend/tests/conftest.py` to mint stateless test JWTs (with offline test JWKS / `SUPABASE_JWT_SECRET` setup) instead of relying on `USERS_DB`

**Checkpoint**: Stateless backend token verification and browser Supabase client ready — user stories can now proceed.

---

## Phase 3: User Story 1 - Account Registration & Email Confirmation Feedback (Priority: P1) 🎯 MVP

**Goal**: Enable real self-service email/password registration via Supabase Auth with immediate clear UI feedback whenever email confirmation is pending before sign-in.

**Independent Test**: Submit a new registration in Create Account mode with email confirmation enabled (verify confirmation-pending banner & no false workspace entry) and disabled (verify immediate entry), plus validation errors on malformed email/weak password.

### Implementation for User Story 1

- [X] T010 [P] [US1] Update `User` and `AuthState` TypeScript interfaces in `frontend/src/types/index.ts` (citing `data-model.md`: `ClientAuthState.user`, `ClientAuthState.token`, `ClientAuthState.isAuthenticated`, `ClientAuthState.isInitializing`, `ClientAuthState.confirmationMessage`, `ClientAuthState.error`)
- [X] T011 [US1] Implement `signUp(email, password, displayName?)` using `supabase.auth.signUp()` with explicit `confirmation_required` vs `signed_in` detection (`data.user && !data.session`) and clean user-facing validation error mapping (citing `data-model.md`: `ClientAuthState.confirmationMessage`, `ClientAuthState.error`) in `frontend/src/hooks/useAuth.ts`
- [X] T012 [US1] Build Create Account registration mode with empty inputs, optional display name, password validation (>= 6 characters), and confirmation-required HUD notice banner (and zero hardcoded demo inputs) in `frontend/src/components/Auth/LoginPage.tsx`

**Checkpoint**: User Story 1 functional — new users can register and receive clear confirmation-pending feedback or immediate entry.

---

## Phase 4: User Story 2 - Sign In, Persistent Sessions & Sign Out (Priority: P1)

**Goal**: Allow confirmed users to sign in with email and password, stay signed in across browser page reloads, attach fresh access tokens per request, and sign out cleanly.

**Independent Test**: Sign in via `LoginPage`, reload the browser page confirming session & identity persist without re-login, send a query verifying current token attachment, and click Sign Out to clear local session and return to login.

### Implementation for User Story 2

- [X] T013 [US2] Implement `signIn(email, password)` (`signInWithPassword`), reload persistence (`getSession()` + `onAuthStateChange` with `isInitializing` guard), `signOut()`, and `handleUnauthorized()` session-expiry handler (citing `data-model.md`: `ClientAuthState.user`, `ClientAuthState.token`, `ClientAuthState.isAuthenticated`, `ClientAuthState.isInitializing`) in `frontend/src/hooks/useAuth.ts`
- [X] T014 [US2] Update `frontend/src/services/api.ts` with `getAccessToken()` and `authHeaders()` reading `supabase.auth.getSession()` dynamically before every backend request
- [X] T015 [US2] Update `frontend/src/hooks/useSSEStream.ts` to read the latest Supabase session `access_token` right before `POST /api/chat/stream` and invoke `onUnauthorized()` cleanly if the backend rejects with HTTP 401
- [X] T016 [US2] Wire `isInitializing` splash guard, authenticated header user display, `signOut` + `resetChat` cleanup, and `onUnauthorized` callback in `frontend/src/App.tsx`

**Checkpoint**: User Stories 1 & 2 complete — full registration, login, reload persistence, fresh per-request token usage, and sign-out work end-to-end.

---

## Phase 5: User Story 3 - Protected Query Access & Removal of Demo Bypasses (Priority: P1)

**Goal**: Enforce valid Bearer authentication on every chat, telemetry, historical, and research query route while keeping public health/status probes open, eliminating all hardcoded demo credentials and unauthenticated bypasses.

**Independent Test**: Run `pytest` verifying 401 responses on missing, expired, malformed, and wrong-audience tokens across `/api/chat/stream`, `/a2a/*`, and `/api/auth/me`, 200 OK on `/`, `/health`, `/api/health`, and zero occurrences of `demo@pitwall.ai` / `Pitwall2024!`.

### Tests for User Story 3

- [X] T017 [P] [US3] Rewrite `backend/tests/test_auth_and_session.py` to test stateless `PyJWT` + `PyJWKClient` (mocked JWKS ES256/RS256 keys, cache reuse, `asyncio.to_thread` execution), optional `SUPABASE_JWT_SECRET` HS256 fallback, valid tokens, expired tokens, wrong `audience`, invalid signatures, and missing Bearer headers (removing legacy `USERS_DB` / `demo@pitwall.ai` tests)
- [X] T018 [P] [US3] Add unauthenticated, invalid-token, expired-token (`401`), valid-token (`200`), and public health (`/`, `/health`, `/api/health`) enforcement tests in `backend/tests/test_deployment_hardening.py`

### Implementation for User Story 3

- [X] T019 [US3] Protect `POST /api/chat/stream` with `Depends(get_current_user)` and bind/reset the incoming `Authorization` header inside the A2A `ContextVar` around stream execution in `backend/app/chat/router.py`
- [X] T020 [US3] Enforce `Depends(get_current_user)` across all `/a2a/*` execution endpoints (`/a2a/historical*`, `/a2a/telemetry*`, `/a2a/research*`, `/a2a/viz*`) while keeping `/.well-known/agent-card.json` discovery cards and `/`, `/health`, `/api/health` public in `backend/app/a2a/registry.py` and `backend/app/main.py`
- [X] T021 [US3] Update existing authenticated test calls in `backend/tests/test_a2a_specialists.py`, `backend/tests/test_chat_stream.py`, `backend/tests/test_a2a_orchestrator_e2e.py`, `backend/tests/test_strategy.py`, and rate-limit tests in `backend/tests/test_deployment_hardening.py` to supply `auth_header`

**Checkpoint**: User Story 3 verified — zero demo credentials/bypasses remain and all analytical routes reject missing/invalid/expired JWTs.

---

## Phase 6: User Story 4 - Unified PitWall AI Sign-In & Sign-Up Experience (Priority: P2)

**Goal**: Polish PitWall AI's dark HUD Sign In / Create Account interface (`#0B0F17`) with clean tab switching, inline error/confirmation alert states, and loading UX.

**Independent Test**: Toggle between Sign In and Create Account, trigger validation/auth errors and expired-session notices, and verify clean reset and WCAG AA dark HUD readability.

### Implementation for User Story 4

- [X] T022 [US4] Refine dark HUD `#0B0F17` / `#121824` / `#E10600` Sign In & Create Account tab switcher, automatic error/confirmation banner reset on mode change, disabled loading states, and clear 401 session-expired banner in `frontend/src/components/Auth/LoginPage.tsx` and `frontend/src/App.tsx`

**Checkpoint**: All 4 user stories independently verified with cohesive PitWall AI HUD UX.

---

## Phase 7: Polish & Cross-Cutting Concerns

**Purpose**: Final security audit, strict TypeScript build verification, and end-to-end test validation.

- [X] T023 [P] Audit repository to confirm zero hardcoded demo credentials (`demo@pitwall.ai`, `Pitwall2024!`), zero `supabase` Python SDK imports, and zero local `USERS_DB` files remain in `backend/` and `frontend/`
- [X] T024 Run full backend suite (`python -m pytest backend/tests/ -v`) and frontend strict TypeScript + Vite production build (`npm run build` in `frontend/`)
- [X] T025 Validate deployment quickstart scenarios and document auth env vars cleanly in `specs/002-real-user-auth/quickstart.md`

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: Starts immediately; `T002`, `T003`, `T004` run in parallel with `T001`.
- **Foundational (Phase 2)**: Depends on Setup (`T001`, `T003`, `T004`). `T005` & `T008` run in parallel; `T006` blocks `T007` and `T009`.
- **User Story 1 (Phase 3 - P1 MVP)**: Depends on Phase 2 (`T005`).
- **User Story 2 (Phase 4 - P1)**: Depends on Phase 2 (`T005`) and builds cleanly atop `useAuth.ts` / `LoginPage.tsx` from US1.
- **User Story 3 (Phase 5 - P1)**: Depends on Phase 2 (`T006`, `T008`, `T009`). Can execute in parallel with frontend US1/US2 work (`backend/` vs `frontend/`).
- **User Story 4 (Phase 6 - P2)**: Depends on US1 & US2 (`LoginPage.tsx`, `App.tsx`).
- **Polish (Phase 7)**: Runs after US1–US4 completion.

### Parallel Opportunities

```text
# Parallel Backend Setup + Frontend Setup:
T001 (backend/requirements.txt) || T002 (frontend/package.json) || T003 (vite-env.d.ts) || T004 (backend/app/config.py)

# Parallel Backend Auth Enforcement vs Frontend Supabase Auth (post-Phase 2):
Backend track: T017 -> T019 -> T020 -> T018 -> T021
Frontend track: T010 -> T011 -> T012 -> T013 -> T014 -> T015 -> T016 -> T022
```

---

## Implementation Strategy

### MVP First (User Story 1 + Phase 2 Core)
1. Complete Phase 1 Setup (`T001`–`T004`) and Phase 2 Foundational (`T005`–`T009`).
2. Complete Phase 3 User Story 1 (`T010`–`T012`) to prove real user sign-up + confirmation-pending UX.
3. Layer Phase 4 (persistent session + per-request Bearer injection) and Phase 5 (full backend route protection & test matrix) sequentially.
4. Polish HUD UX (Phase 6) and execute full verification suite (Phase 7).
