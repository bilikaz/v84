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
