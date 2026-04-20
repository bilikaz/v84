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
