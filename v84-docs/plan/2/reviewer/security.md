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
