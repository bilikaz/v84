
# --- iteration 2 ---
[v84-2-1-1]#1 Verify User entity stores hashed password (bcrypt) in password_hash column; verify Session entity stores refresh_token_hash (not plain token); ensure UUID v7 is used for all IDs; check serialization excludes sensitive fields like password_hash
  task: Review entity definitions and serialization logic
  depends: [v84-1-2-2]#1
[v84-2-1-2]#1 Verify JWT access token expiry is short (e.g., 15m); verify refresh token rotation (invalidate old token on use); verify secure cookie attributes (HttpOnly, Secure, SameSite); check JWT algorithm configuration
  task: Review token generation, validation, and storage logic
  depends: [v84-2-1-2]#1
[v84-2-1-3]#1 Verify seed script hashes the default admin password with bcrypt; ensure no plaintext passwords in seed data or logs
  task: Review seed script for password handling
  depends: [v84-2-1-1]#1
[v84-2-2-1]#1 Verify login and refresh endpoints have rate limiting to prevent brute force; verify error messages do not reveal if an email exists or password is wrong; verify CORS is restricted to the frontend origin
  task: Review endpoint implementation for security controls
  depends: [v84-2-2-1]#1
[v84-2-2-2]#1 Verify AuthGuard correctly extracts and validates tokens from headers/cookies; verify RoleGuard checks role claims from the validated token; ensure no endpoint in the app module is accidentally left unprotected
  task: Review guard implementation and module configuration
  depends: [v84-2-2-1]#1
[v84-2-3-1]#1 Verify BFF proxy endpoints do not allow open redirects; verify secure cookie handling (HttpOnly, Secure, SameSite); check for CSRF protection; ensure proxy strips sensitive headers when forwarding to the API
  task: Review BFF handler implementation
  depends: [v84-2-2-2]#1
[v84-2-3-2]#1 Verify frontend does not attempt to store JWTs in LocalStorage (since BFF handles it); verify auth context updates are triggered by reliable events (e.g., cookie presence) and handle token expiration gracefully
  task: Review frontend auth state implementation
  depends: [v84-2-3-1]#1
[v84-2-4-1]#1 Verify User management DTOs use class-validator to whitelist fields (prevent mass assignment); verify user list endpoints exclude sensitive fields (passwordHash, refreshTokenHash); check for IDOR protection on user update/delete endpoints
  task: Review admin API endpoints and DTOs
  depends: [v84-2-4-1]#1
[v84-2-4-2]#1 Verify user management forms implement client-side validation but enforce server-side validation via DTOs; check for potential XSS in rendering user data (e.g., escaped HTML)
  task: Review admin UI implementation
  depends: [v84-2-4-1]#1
[v84-2-4-3]#1 Verify frontend route guards check for admin role from the server-side auth state, not just local UI state; ensure non-admin users cannot access admin routes even if they modify client-side logic
  task: Review frontend route protection
  depends: [v84-2-3-2]#1

# --- iteration 3 ---
[v84-3-1-1]#1 Registration endpoint lacks rate limiting and allows email enumeration
  risk: POST /api/auth/register is unrestricted, allowing bot spam; response body or status may differ for existing vs new emails
  impact: service degradation from spam accounts; user list harvesting via enumeration
  action: rate limiting must be enforced on POST /auth/register; the endpoint must return identical status, body, and latency regardless of email existence; password complexity rules must be enforced server-side
[v84-3-1-2]#1 Verification token lacks expiry and replay protection; post-verification redirect may allow open redirects
  risk: GET /auth/verify/:token accepts reused tokens indefinitely; redirect URL after verification is unsanitized
  impact: permanent account takeover if token is leaked; phishing via malicious redirect target
  action: GET /auth/verify/:token must enforce short token expiry and single-use invalidation; post-verification redirects must be constrained to allowed origins; isVerified must only update on valid tokens
[v84-3-2-1]#1 Password recovery endpoint leaks registered email addresses and lacks rate limiting
  risk: POST /api/auth/forgot-password returns different responses or timing for existing vs non-existing emails
  impact: account enumeration enables targeted phishing and credential stuffing attacks
  action: POST /auth/forgot-password must return identical status, body, and latency whether the email exists or not; token generation must be constant-time; strict rate limiting must be applied before email dispatch
[v84-3-2-2]#1 Password reset allows token reuse and fails to invalidate active sessions upon success
  risk: POST /auth/reset-password accepts the same reset token multiple times; existing active refresh tokens remain valid after password change
  impact: attacker retains persistent access if they intercepted the reset flow or if token was leaked; delayed breach detection
  action: POST /auth/reset-password must enforce single-use and expiry on reset tokens; a successful reset must invalidate all existing sessions and refresh tokens for that user; password complexity rules must be enforced on the new password

# --- iteration 4 ---
[v84-4-1-1]#1 TOTP secret generation lacks cryptographic strength
  risk: Weak RNG for `totpSecret` allows predictability; unencrypted DB storage exposes raw secret if DB is compromised
  impact: full 2FA bypass if secret is recovered from logs or database breach
  action: verify `totpSecret` is generated via cryptographically secure RNG and encrypted at rest; verify generation endpoint requires active authentication
[v84-4-1-1]#2 2FA disable flow lacks strong re-authentication
  risk: `POST /auth/2fa/disable` could succeed with a stale or hijacked session without verifying current identity
  impact: unauthorized attacker disables 2FA and locks out legitimate user or maintains persistent access
  action: disable must require re-authentication (current password or valid 2FA code) and invalidate affected refresh tokens immediately
[v84-4-1-2]#1 Login 2FA fallback leaks feature existence or timing
  risk: `POST /auth/login` response timing or error messages differ when `requires2fa` is triggered vs standard failure
  impact: attackers confirm 2FA is enabled on target accounts and optimize brute-force timing
  action: login must return identical latency and generic status codes whether password is wrong or 2FA is required; `requires2fa: true` is acceptable only when password succeeds
[v84-4-1-2]#2 Login 2FA code verification vulnerable to brute force
  risk: `POST /auth/login` retries with wrong `totpCode` are unrestricted or lack lockout/cooling
  impact: automated scripts exhaust possible TOTP codes (000000-999999) to gain access
  action: enforce strict rate limiting on 2FA code attempts per IP and per account; implement exponential backoff or temporary lockout after consecutive failures
[v84-4-2-1]#1 Password change does not invalidate existing sessions
  risk: `POST /auth/change-password` updates the hash but leaves active refresh tokens and sessions valid
  impact: attacker retaining a stale refresh token retains access until natural expiry despite password change
  action: successful password change must revoke all active sessions and refresh tokens for that user; require re-login everywhere
[v84-4-2-2]#1 Email change endpoint leaks existing email registration
  risk: `POST /auth/change-email` returns distinct errors or timing when the target email already exists or is already the current user's email
  impact: account enumeration and confirmation of valid email addresses within the platform
  action: return identical success response regardless of email uniqueness; validate ownership server-side silently and queue dispatch only if valid
[v84-4-3-1]#1 Session listing exposes sensitive session identifiers
  risk: `GET /auth/sessions` includes full refresh tokens, device fingerprints, or raw session tokens in the response payload
  impact: client-side storage or logging leaks session tokens enabling full account takeover
  action: response must only contain opaque session IDs, device metadata (OS, browser), IP, and last active timestamp; never expose tokens
[v84-4-3-2]#1 Session revocation suffers from IDOR or stale state
  risk: `DELETE /auth/sessions/:id` accepts any session ID without verifying ownership; or invalidated sessions persist in DB without cleanup
  impact: unauthorized session termination or continued access via revoked tokens
  action: verify session ownership against authenticated user; enforce immediate invalidation via Redis TTL or DB status flag checked on token validation
