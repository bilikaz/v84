[v84-4-1-1]#2 Disabling 2FA leaves legacy sessions active
  risk: `POST /auth/2fa/disable` turns off the TOTP requirement but does not terminate existing sessions or refresh tokens
  impact: an attacker who hijacked a session before 2FA was enabled maintains persistent access indefinitely
  action: disabling 2FA must immediately invalidate all active sessions and revoke associated refresh tokens for the user
[v84-4-1-2]#2 Missing 2FA recovery codes
  risk: the 2FA flow provides setup and login but omits generation of backup recovery codes
  impact: users who lose their authenticator device or phone are permanently locked out with no self-service recovery path
  action: enabling 2FA must generate and display single-use recovery codes that the user must save before activation
[v84-4-2-2]#1 Email change leaks existence via validation error
  risk: the draft action incorrectly suggests returning a validation error when the target email is already registered, contradicting security requirements for generic success responses
  impact: account enumeration — attackers can distinguish registered from unregistered emails via distinct error responses
  action: the service must return a generic success response regardless of target email uniqueness, deferring conflict resolution to the verification step
[v84-4-2-2]#2 Change-email verification token lacks expiry
  risk: following historical gaps, the email change token may be stored without an `expiresAt` timestamp
  impact: verification links remain usable indefinitely, expanding the window for token interception and replay attacks
  action: the verification token must include an expiration timestamp and be automatically rejected after the configured TTL
[v84-4-3-1]#1 Session records lack data retention policy
  risk: `Session` entity stores IP addresses and device info indefinitely without cleanup
  impact: violates privacy compliance (GDPR/CCPA) and accumulates unnecessary database bloat over time
  action: implement automatic pruning or TTL-based expiration for `Session` records older than a defined period (e.g., 90 days)
[v84-4-3-2]#1 Session revocation ineffective for stateless JWTs
  risk: `DELETE /auth/sessions/:id` removes the database record but does not invalidate active access tokens or refresh tokens
  impact: the UI shows the session as revoked while the attacker retains valid API access until token expiration
  action: revocation must either blacklist the JWT immediately, trigger Redis-based token invalidation, or rely on short-lived access tokens paired with refresh revocation
