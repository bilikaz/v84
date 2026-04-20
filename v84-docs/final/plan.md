
# --- iteration 1 ---
## [v84-1]
Project skeleton — monorepo with backend API, frontend web app, component library with Storybook, Docker infrastructure with reverse proxy and .localhost domains, database, cache/session store, dev email catcher, and a centralized brand system. No features, just the foundation everything else will be built on.

## [v84-1-1]
Monorepo structure and shared tooling — the top-level workspace that ties API, web app, and component library together with shared configs (TypeScript, linting, formatting). Running any one app or the full stack should work from the root.

## [v84-1-2]
Docker development environment — all services defined and orchestrated so `docker compose up` brings up the full stack: API, web app, database, cache/session store, email catcher, and reverse proxy. Each service reachable at its own .localhost domain (e.g. app.localhost, api.localhost, mail.localhost).

### [v84-1-2-1]
Reverse proxy with .localhost domain routing — a proxy that maps clean hostnames to the correct internal service and port. Developers hit browser-friendly URLs, not port numbers.

### [v84-1-2-2]
Database service — a relational database running in Docker, accessible to the API, with a volume for persistence across restarts. Schema management tooling (migrations) wired up but no tables yet.

### [v84-1-2-3]
Cache and session store — an in-memory store running in Docker, accessible to the API, intended for sessions and ephemeral data.

### [v84-1-2-4]
Dev email catcher — a local SMTP service that captures all outgoing email and exposes a web UI to inspect them. Accessible at its own .localhost domain. The API is wired to send through it in development.

## [v84-1-3]
Backend API — a running NestJS application that starts, connects to the database and cache, responds to a health-check endpoint, and is reachable through the reverse proxy at api.localhost. No business logic, just the empty shell with correct project structure.

## [v84-1-4]
Frontend web app — a running Next.js application that starts, renders a placeholder page, and is reachable through the reverse proxy at app.localhost. No pages or features, just the empty shell with correct project structure.

## [v84-1-5]
Component library with Storybook — a package inside the monorepo that exports shared UI components. Storybook runs and is accessible (either at its own .localhost domain or via a port). One placeholder component with a story proves the pipeline works end to end.

## [v84-1-6]
Brand system — a single source of truth where app name, colors, fonts, email subjects, and other brand tokens are defined once. Every other part of the stack (API, web app, component library, email templates) reads from this definition. Changing a value in one place changes it everywhere.

# --- iteration 2 ---
## [v84-2]
User management and token-based authentication system with a secure BFF proxy and admin dashboard.

## [v84-2-1]
Authentication & Session Core — Implementation of the token-based auth mechanism, session tracking, and seed data.

### [v84-2-1-1]
User and Session data models — Database entities for Users (email, username, password, role) and Sessions (track active logins, device info, expiry).

### [v84-2-1-2]
Token-based auth logic — Backend services for generating and validating short-lived access tokens and long-lived refresh tokens.

### [v84-2-1-3]
Dev seed data — Automated seeding of a default admin account (`admin@admin.localhost`) and a regular user for testing.

## [v84-2-2]
Backend Auth API — REST endpoints to handle the authentication lifecycle.

### [v84-2-2-1]
Auth endpoints — API for login, logout, and token refreshing.

### [v84-2-2-2]
Auth guards — Backend decorators and guards to enforce authentication and role-based access (Admin vs User).

## [v84-2-3]
Frontend Auth Bridge (BFF) — Secure proxy layer in Next.js to handle tokens outside the browser's reach.

### [v84-2-3-1]
BFF Auth handlers — Server-side route handlers to manage token exchange, secure cookie storage, and proxying requests to the API.

### [v84-2-3-2]
Frontend Auth state — Auth provider and hooks to manage the user's logged-in state and session persistence.

## [v84-2-4]
User Management Admin Panel — Restricted interface for administrators to manage the user base.

### [v84-2-4-1]
User management API — Admin-only endpoints to list, create, update, and delete users.

### [v84-2-4-2]
User management UI — Admin dashboard page with a user table and forms for creating and editing users.

### [v84-2-4-3]
Admin access guards — Frontend route protection to prevent non-admins from accessing the management panel.

# --- iteration 3 ---
## [v84-3]
Public user registration, email verification, and password recovery — enabling self-service account creation, secure verification via email links, and password reset workflows with brand-compliant email templates.

## [v84-3-1]
User Registration & Email Verification — Account creation, token generation, email delivery, link processing, and dashboard redirection.

### [v84-3-1-1]
Registration Form & Processing — Page and form for user data entry, backend logic to create the user record (initially unverified), and frontend success state. Includes `RegisterPage`, `RegistrationForm` with validation, `POST /auth/register` API endpoint, `POST /api/auth/register` BFF handler, and `AuthService.register`.

### [v84-3-1-2]
Verification, Welcome Email & Dashboard Access — Logic to process the verification link, activate the account, send the welcome email, and provide the landing destination for verified users. Includes `VerifyEmailPage` (status handling), `UserDashboardPage`, `GET /auth/verify/:token` API endpoint, `GET /api/auth/verify/:token` BFF handler, `AuthService.verifyEmail`, `VerificationEmail` template, `WelcomeEmail` template, and entity fields `isVerified`, `verificationToken`.

## [v84-3-2]
Password Recovery — The "forgot password" request flow and the subsequent password reset flow.

### [v84-3-2-1]
Forgot Password Request — Page and form for email entry, backend logic to generate the reset token and dispatch the email. Includes `ForgotPasswordPage`, `ForgotPasswordForm`, `POST /auth/forgot-password` API endpoint, `POST /api/auth/forgot-password` BFF handler, `AuthService.requestReset`, `PasswordResetEmail` template, and entity field `resetPasswordToken`.

### [v84-3-2-2]
Reset Password Action — Page and form for new password entry, backend logic to validate the reset token and update credentials. Includes `ResetPasswordPage`, `ResetPasswordForm`, `POST /auth/reset-password` API endpoint, `POST /api/auth/reset-password` BFF handler, `AuthService.resetPassword`, and success redirect logic.

# --- iteration 4 ---
## [v84-4]
Account security settings and two-factor authentication login challenge — logged-in users manage their security (2FA, email, password, sessions) from a central settings page, and the login flow adapts to enforce 2FA when enabled.

## [v84-4-1]
Two-Factor Authentication (Setup & Login) — Enable/disable 2FA with QR codes in settings, and challenge users with a 2FA code during login.

### [v84-4-1-1]
2FA Enable & Disable Flow — Settings page section where users generate a TOTP secret, scan the frontend-rendered QR with an authenticator app, enter the verification code to enable 2FA, or disable it. Includes `POST /auth/2fa/generate-secret` (returns the raw TOTP secret), `POST /auth/2fa/verify` (validates code during setup), `POST /auth/2fa/enable`, `POST /auth/2fa/disable`, `AuthService.generateSecret`, `AuthService.verifyTotp`, and entity fields `totpSecret`, `is2faEnabled`. The frontend builds the `otpauth://` URI from the returned secret and renders the QR locally.

### [v84-4-1-2]
Login 2FA in the same call — Login page adaptation that presents a code input field when the API signals it is required. Uses the existing single-shot `POST /auth/login` contract: request body is `{ email, password, totpCode? }`; when the account has 2FA enabled and `totpCode` is missing or wrong, the response is `{ requires2fa: true }` and the frontend prompts for the code and retries against the same endpoint. `AuthService.verifyTotp` is called inline inside the login flow; there is no separate verify-login endpoint.

## [v84-4-2]
Account Details Management — Update email and password with validation and verification workflows.

### [v84-4-2-1]
Password Change — Form and logic for users to update their password by providing their current password and a new one. Includes `PasswordChangeForm` with validation, `POST /auth/change-password` endpoint, `AuthService.changePassword`, and checks for `currentPassword` match before updating.

### [v84-4-2-2]
Email Change — Form and verification flow for users to request a new email address. Includes `EmailChangeForm`, `POST /auth/change-email` (generates token, sends `EmailChangeVerificationEmail`), and `GET /auth/verify-email/:token` (validates token, updates `user.email`). Reuses the generic verification logic from iteration 3.

## [v84-4-3]
Session Management — View active login sessions and revoke access for specific devices.

### [v84-4-3-1]
Active Session Listing — Fetch and display a list of the user's active sessions with device information. Includes `GET /auth/sessions` endpoint, `AuthService.getSessions`, and a session table component in the Settings page showing device details, IP, and last active time.

### [v84-4-3-2]
Session Revocation — UI and logic for users to terminate specific active sessions. Includes a "Revoke" button in the session table, `DELETE /auth/sessions/:id` endpoint, `AuthService.revokeSession`, and immediate UI update on success.
