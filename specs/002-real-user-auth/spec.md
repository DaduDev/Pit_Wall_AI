# Feature Specification: Real User Authentication

**Feature Branch**: `002-real-user-auth`  
**Created**: 2026-11-28  
**Status**: Draft  
**Input**: User description: "Replace the placeholder \"demo racing engineer\" login in PitWall AI with real user authentication. Users must be able to register with email and password, see clear feedback when email confirmation is required, sign in, stay signed in across page reloads, and sign out. Remove all hardcoded demo credentials, pre-filled demo login buttons, and unauthenticated bypasses. Every chat, telemetry, and historical query request must require a valid authenticated session and cleanly reject missing, invalid, or expired sessions, while public health and service status endpoints remain accessible without authentication. The sign-in and sign-up UI must match PitWall AI's existing design and clearly surface authentication or validation errors."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Account Registration & Email Confirmation Feedback (Priority: P1)

A new user opens PitWall AI, switches to the account creation view, and registers with an email address and password. If immediate sign-in is enabled, the user enters the authenticated application; if email confirmation is required before activation, the user receives a clear, unambiguous notice explaining that they must confirm their email before signing in.

**Why this priority**: Real user onboarding is impossible without self-service registration and clear email-confirmation feedback. Replacing placeholder credentials requires real accounts created by users themselves.

**Independent Test**: Can be fully tested by registering a brand-new user with valid credentials, attempting duplicate or invalid registrations, and verifying both immediate activation and email-confirmation-required feedback flows.

**Acceptance Scenarios**:

1. **Given** an unauthenticated visitor on the authentication screen, **When** they choose Create Account and submit a valid email address and compliant password, **Then** their account is created and either an authenticated session starts immediately or a clear confirmation-pending message instructs them to check their email before signing in.
2. **Given** a visitor registering with an invalid email format, blank required field, or non-compliant password, **When** they submit the sign-up form, **Then** registration is prevented and a specific, readable validation error is shown in the UI.
3. **Given** an unauthenticated user whose account requires email confirmation before first sign-in, **When** they attempt to sign in prior to confirming their email, **Then** access is denied with a clear message explaining that email confirmation is pending.

---

### User Story 2 - Sign In, Persistent Sessions & Sign Out (Priority: P1)

A registered user signs in with their email and password, uses PitWall AI, reloads the browser page, and remains signed in seamlessly. When finished, they click Sign Out, immediately ending their local session and returning to the sign-in screen.

**Why this priority**: Core daily usability and security depend on reliable sign-in, reload persistence without re-entering credentials, and clean session termination on sign-out.

**Independent Test**: Can be tested by signing in with an existing account, reloading the application window to confirm the authenticated state and user identity remain intact, and clicking Sign Out to verify return to the login gate and inability to submit queries afterward.

**Acceptance Scenarios**:

1. **Given** a registered and confirmed user on the sign-in screen, **When** they submit their valid email and password, **Then** they are authenticated, granted access to PitWall AI, and see their signed-in identity in the header.
2. **Given** a signed-in user actively using PitWall AI, **When** they reload or reopen the application tab within the active session lifetime, **Then** they remain signed in without being prompted for credentials again.
3. **Given** a signed-in user, **When** they click Sign Out, **Then** their stored session is cleared immediately and the application returns to the sign-in view.
4. **Given** a user entering an incorrect email or password on sign-in, **When** they submit the form, **Then** authentication fails cleanly and displays a clear error message without granting access.

---

### User Story 3 - Protected Query Access & Removal of Demo Bypasses (Priority: P1)

Every conversational chat, telemetry, strategy, historical race query, and research operation verifies that the caller holds a valid authenticated session and rejects missing, malformed, or expired credentials. All hardcoded demo accounts, pre-filled login forms, one-click demo buttons, and unauthenticated bypass paths are permanently removed, while public health and service status checks remain accessible without authentication.

**Why this priority**: Without server-side enforcement across every query capability and removal of hardcoded credentials, authentication is only cosmetic and leaves the application open to unauthorized usage.

**Independent Test**: Can be tested by invoking chat, telemetry, historical, and research operations with no credentials, forged credentials, and expired credentials (expecting rejection), while invoking public health and status endpoints without credentials (expecting normal readiness output).

**Acceptance Scenarios**:

1. **Given** an unauthenticated visitor or external caller without a valid session, **When** they attempt any chat, telemetry, historical query, or research operation, **Then** the system rejects the request with an explicit authentication-required error and performs no query execution.
2. **Given** a caller presenting an invalid, tampered, or expired session credential, **When** they submit any protected request, **Then** the request is rejected cleanly and, in the interactive application, the user is returned to the sign-in screen with a clear session-expired notice.
3. **Given** the login screen rendered for a fresh visitor, **When** the page loads, **Then** the email and password inputs are empty, no hardcoded demo credentials or pre-filled demo sign-in buttons exist anywhere in the interface or default credential store, and no unauthenticated bypass option is offered.
4. **Given** an automated health probe or monitoring check with no authentication credentials, **When** it queries the public health or service status endpoints, **Then** it succeeds normally without requiring sign-in.

---

### User Story 4 - Unified PitWall AI Sign-In & Sign-Up Experience (Priority: P2)

Visitors interact with a cohesive Sign In / Sign Up screen matching PitWall AI's existing dark telemetry cockpit visual aesthetic, offering crisp mode switching, clear loading indicators while requests are in flight, and high-contrast validation and authentication feedback.

**Why this priority**: A unified visual design and clear error feedback maintain product trust and prevent user confusion between sign-in, sign-up, and confirmation states.

**Independent Test**: Can be tested visually and interactively by toggling between Sign In and Create Account, triggering validation errors and server authentication errors, and verifying consistent styling and high-contrast readable feedback.

**Acceptance Scenarios**:

1. **Given** a visitor on the authentication screen, **When** they toggle between Sign In and Create Account modes, **Then** stale errors from the previous mode are cleared and the form fields and primary action update cleanly within PitWall AI's existing dark HUD styling.
2. **Given** an active authentication request in progress, **When** the form is awaiting a response, **Then** duplicate submissions are prevented and a loading state is visibly communicated until the request completes.

---

### Edge Cases

- What happens when a user's session expires mid-conversation while they try to send a follow-up question? The protected request is rejected, their expired local session is cleared, and they are returned cleanly to the sign-in screen with a clear message to sign in again.
- How does the system behave when email confirmation is enabled on the authentication service versus disabled? When confirmation is pending, sign-up communicates the confirmation requirement instead of silently failing or falsely logging the user in; when confirmation is not required, sign-up immediately establishes a valid session.
- What happens when a user registers with an email address that already exists? The system surfaces a clear, non-ambiguous account-exists or verification guidance message without crashing or revealing sensitive internals.
- What happens if stored session state in the browser becomes corrupted or lacks a valid credential? The application discards the corrupted local state on startup and displays the clean sign-in screen.
- What happens if a caller accesses public health or root status endpoints during deployment readiness checks without credentials? Public health and service status endpoints respond normally without requiring authentication.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST provide self-service account registration accepting an email address and password (with optional display name), enforcing valid email format syntax and a minimum password length of 6 characters with inline validation feedback before and during account creation.
- **FR-002**: System MUST inspect registration results and display clear, explicit user feedback whenever email confirmation is required before signing in, rather than attempting to enter the workspace without an active session.
- **FR-003**: System MUST provide email-and-password sign-in that authenticates against real user accounts and establishes a verifiable authenticated session upon success.
- **FR-004**: System MUST persist the user's authenticated session across browser page reloads and restore their signed-in identity automatically while the session remains valid.
- **FR-005**: System MUST provide an explicit Sign Out action that terminates the current session cleanly, removes stored local session credentials, resets active conversation state, and returns the user to the sign-in screen.
- **FR-006**: System MUST completely remove all hardcoded demo accounts, default demo passwords, pre-filled login inputs, one-click demo login buttons, and unauthenticated bypass flags or modes.
- **FR-007**: System MUST require a valid authenticated session on every chat stream, telemetry comparison, strategy analysis, historical race query, and research query capability, cleanly rejecting requests with missing, invalid, or expired sessions.
- **FR-008**: System MUST keep public service health and readiness status endpoints as well as read-only service capability descriptors (containing no user or analytical query data) accessible without authentication so monitoring probes and service discovery operate uninterrupted.
- **FR-009**: When an active user's session expires or becomes invalid during application usage, the client interface MUST clear invalid local credentials and active workspace conversation state, transition cleanly back to the sign-in screen, and explain why re-authentication is required.
- **FR-010**: The sign-in and sign-up interface MUST preserve PitWall AI's existing dark pit-wall cockpit design language (dark `#0B0F17` canvas, accent styling, and readable contrast) and clearly display field-level or authentication errors and loading states.

### Key Entities *(include if feature involves data)*

- **User Account**: A real registered identity uniquely associated with an email address, verification/confirmation status, optional display profile, and password-based credentials. No seeded placeholder demo user exists.
- **Authenticated Session**: A verifiable, time-bounded credential issued upon successful authentication or immediate sign-up confirmation, linking protected analytical requests to a real User Account and persisting across page reloads until expiration or sign-out.
- **Public Service Status Resource**: Read-only health and readiness information exposed without authentication to support infrastructure monitoring and deployment verification.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: 100% of protected chat, telemetry, historical, and research requests issued without a valid session or with an invalid/expired session are rejected without executing underlying queries or returning analytical data.
- **SC-002**: 100% of public health and readiness status requests succeed without authentication credentials.
- **SC-003**: Zero hardcoded demo credentials, pre-filled demo inputs, or demo auto-login bypasses remain anywhere in the user interface or default runtime configuration.
- **SC-004**: New users can complete registration (receiving immediate entry or clear email-confirmation instructions) in under 30 seconds, and returning confirmed users can sign in cleanly.
- **SC-005**: Signed-in users retain their authenticated session across browser page reloads 100% of the time within the valid session window, and sign-out returns them to the login gate within 1 second while revoking subsequent local access.
- **SC-006**: All authentication failures (invalid credentials, duplicate email, weak password, unconfirmed email, expired session) surface human-readable error feedback matching PitWall AI's dark HUD styling with zero raw internal tracebacks exposed.

## Assumptions

- Users supply a real email address and password meeting standard minimum complexity requirements (minimum password length and valid email syntax).
- Email delivery and verification link handling for email confirmation (when enabled in the chosen identity configuration) are performed by the configured authentication service; PitWall AI's responsibility is registering the user, detecting the confirmation-pending state, and giving clear user feedback.
- Existing authenticated analytical features (historical analytics, car telemetry comparison, tyre strategy analysis, research intelligence, and visualization rendering) remain functionally unchanged once a valid authenticated session is present.
- Public health/readiness endpoints expose only non-sensitive service availability metadata and require no authentication.
