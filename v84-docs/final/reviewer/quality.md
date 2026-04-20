
# --- iteration 2 ---
[v84-2-1-1]#1 Session entity design
  task: verify Session entity includes device info, IP, and expiry fields matching requirements
[v84-2-1-1]#2 Migration prerequisite
  task: verify TypeORM migration is generated for User/Session entities due to synchronize: false convention
[v84-2-1-2]#1 Refresh token storage
  task: verify refresh token storage strategy (DB vs Redis) and ensure logout revokes tokens
[v84-2-1-2]#2 JWT secret
  task: verify JWT secret is loaded from env and not hardcoded
[v84-2-1-3]#1 Seed idempotency
  task: verify seed script is idempotent and handles duplicate admin creation
[v84-2-2-1]#2 Login validation
  task: verify input validation DTOs for login payload exist and are used
[v84-2-2-1]#3 Logout invalidation
  task: verify logout endpoint invalidates the refresh token/session
[v84-2-2-2]#1 Role guard
  task: verify role-based access guard implementation matches role column type
[v84-2-3-1]#2 Dev cookie compatibility
  task: verify cookie configuration handles local development environment correctly (e.g., `Secure` flag disabled for HTTP localhost or using an HTTPS dev proxy). The `Secure` flag strictly requires HTTPS; without conditional handling, local development will fail.
[v84-2-3-1]#3 Token exchange
  task: verify token exchange is atomic and handles race conditions
[v84-2-3-2]#1 Hydration
  task: verify Next.js hydration consistency between SSR cookie and client auth state
[v84-2-4-1]#2 Password reset scope
  task: verify admin-initiated password reset handling or explicit deferral of self-service features
[v84-2-4-2]#1 Form validation
  task: verify form validation uses Zod to match backend DTOs

# --- iteration 3 ---
[v84-3-2-1]#1 Missing reset token expiry field in plan
  risk: The plan lists the `resetPasswordToken` entity field but omits a corresponding `resetPasswordTokenExpiry` or TTL mechanism. Without time-bound validity, tokens remain usable indefinitely until manually revoked.
  impact: Long-term account compromise risk if a token is persisted in logs, browser history, or intercepted during transit.
  action: the user entity and `AuthService.requestReset` must enforce and check a `resetPasswordTokenExpiry` timestamp, automatically invalidating tokens that exceed the configured lifespan (e.g., 1 hour).
[v84-3-2-1]#4 Silent failure on email dispatch
  risk: `AuthService.requestReset` generates the token and triggers `PasswordResetEmail` delivery, but the plan does not account for SMTP/connection failures. If `nodemailer` or the mail service is down, the backend might throw an unhandled exception, causing a 500 error to the client.
  impact: Legitimate users see server errors when trying to recover access, while attackers see no difference between success and failure if the backend catches it poorly.
  action: the service must catch email dispatch errors, log them internally for debugging, and still return a standard success response to the caller.

# --- iteration 4 ---
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
