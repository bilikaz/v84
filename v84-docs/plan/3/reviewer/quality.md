[v84-3-2-1]#1 Missing reset token expiry field in plan
  risk: The plan lists the `resetPasswordToken` entity field but omits a corresponding `resetPasswordTokenExpiry` or TTL mechanism. Without time-bound validity, tokens remain usable indefinitely until manually revoked.
  impact: Long-term account compromise risk if a token is persisted in logs, browser history, or intercepted during transit.
  action: the user entity and `AuthService.requestReset` must enforce and check a `resetPasswordTokenExpiry` timestamp, automatically invalidating tokens that exceed the configured lifespan (e.g., 1 hour).
[v84-3-2-1]#4 Silent failure on email dispatch
  risk: `AuthService.requestReset` generates the token and triggers `PasswordResetEmail` delivery, but the plan does not account for SMTP/connection failures. If `nodemailer` or the mail service is down, the backend might throw an unhandled exception, causing a 500 error to the client.
  impact: Legitimate users see server errors when trying to recover access, while attackers see no difference between success and failure if the backend catches it poorly.
  action: the service must catch email dispatch errors, log them internally for debugging, and still return a standard success response to the caller.
