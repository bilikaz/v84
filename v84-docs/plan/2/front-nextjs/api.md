[v84-2-3-1]#1 Session storage
  task: add `import 'server-only'` at the top of the file; store accessToken and refreshToken in apps/web/src/lib/storage.ts; server-auth.ts handles only the opaque session ID cookie — tokens must never be placed directly in cookies
  files: apps/web/src/lib/storage.ts
[v84-2-3-1]#2 Server-auth cookie utilities
  task: provide helpers to read the session ID from incoming cookies, set the httpOnly/lax session cookie, conditionally set the Secure attribute to false when process.env.NODE_ENV is development, and clear it on logout
  files: apps/web/src/lib/server-auth.ts
[v84-2-3-1]#3 API fetch wrapper
  task: implement apiFetch<T>() that calls BFF routes at /api/* with credentials: same-origin, throws ApiError on non-ok responses. Re-export apiFetch + ApiError + Paginated/ListQuery types from the lib sub-barrel so consumers import via a single `@/lib` path.
  files: apps/web/src/lib/api.ts, apps/web/src/lib/index.ts
[v84-2-3-1]#4 Auth response types
  task: define TS interfaces for login response, session object, and API error shape
  files: apps/web/src/modules/auth/types.ts
[v84-2-3-1]#5 Auth module API wrappers
  task: define login, logout, and getSession API functions that delegate to apiFetch(/api/auth/*)
  files: apps/web/src/modules/auth/api.ts
  depends: [v84-2-3-1]#3, [v84-2-3-1]#4
[v84-2-3-1]#6 Shared lib types
  task: define Paginated<T> and ListQuery generic interfaces and ApiError class for cross-module type reuse
  files: apps/web/src/lib/types.ts
[v84-2-3-1]#7 Users response types
  task: define User interface, create/update input shapes, and apply Paginated<User> for list endpoints mirroring API DTOs
  files: apps/web/src/modules/users/types.ts
  depends: [v84-2-3-1]#6
[v84-2-3-1]#8 Users module API wrappers
  task: define listUsers, createUser, updateUser, and deleteUser functions that delegate to apiFetch(/api/users/*)
  files: apps/web/src/modules/users/api.ts
  depends: [v84-2-3-1]#3
[v84-2-3-1]#9 BFF login route handler
  task: forward credentials to upstream API /auth/login, store tokens server-side via storage.ts, set session cookie (containing opaque UUID) via server-auth.ts, return { ok: true }
  files: apps/web/src/app/api/auth/login/route.ts
  depends: [v84-2-3-1]#1, [v84-2-3-1]#2
[v84-2-3-1]#10 BFF logout route handler
  task: call backend /auth/logout to revoke the refresh token, clear its own session cookie with maxAge: 0, return { ok: true }
  files: apps/web/src/app/api/auth/logout/route.ts
  depends: [v84-2-3-1]#1, [v84-2-3-1]#2
[v84-2-3-1]#11 BFF proxy helpers
  task: implement shared proxyAuthed/proxyPublic helpers in lib/proxy.ts — attach stored Authorization Bearer token, enforce CSRF via same-origin Origin/Referer check on state-changing methods (POST/PATCH/DELETE), auto-refresh token and retry once on upstream 401. Every BFF route handler under app/api/*/route.ts uses these helpers.
  files: apps/web/src/lib/proxy.ts
  depends: [v84-2-3-1]#1

[v84-2-3-1]#12 BFF users CRUD route handlers
  task: proxy the admin user-management surface — GET /api/users (list, paginated) + POST /api/users (create) in the collection route, and GET/PATCH/DELETE /api/users/[id] in the item route. All handlers delegate to proxyAuthed (attach Bearer token + CSRF + refresh-on-401). No business logic in the BFF: forward body/params straight through and return the upstream response.
  files: apps/web/src/app/api/users/route.ts, apps/web/src/app/api/users/[id]/route.ts
  depends: [v84-2-3-1]#11
[v84-2-3-1]#13 BFF users/me and OAuth Google route handlers
  task: add the self-service endpoint `GET /api/users/me` (returns the current user) and the OAuth-login endpoint `POST /api/auth/google` (forwards Google ID token to upstream `/auth/google` for exchange) — both delegate to the shared proxy helpers. `/api/users/me` uses `proxyAuthed` for session-bound identity lookup; `/api/auth/google` uses `proxyPublic` because the client is not yet logged in.
  files: apps/web/src/app/api/users/me/route.ts, apps/web/src/app/api/auth/google/route.ts
  depends: [v84-2-3-1]#11
