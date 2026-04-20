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
