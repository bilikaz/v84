
# --- iteration 1 ---
[v84-1-4]#1 Root layout with providers and brand metadata
  task: create app/layout.tsx — html shell, import globals.css, wrap children in AuthProvider + GoogleProvider, metadata from `@/config`. Layout reads copy and env from the config sub-barrel; direct `brand/*` or `process.env` access is not allowed here (use the wrappers from [v84-1-4]#8 below).
  files: apps/web/src/app/layout.tsx, apps/web/src/app/globals.css

[v84-1-4]#2 Public landing page (placeholder)
  task: create app/(public)/page.tsx as 2-line re-export from modules/home/pages/HomePage
  files: apps/web/src/app/(public)/page.tsx, apps/web/src/modules/home/pages/HomePage.tsx

[v84-1-4]#3 Auth route group — login, register, forgot/reset password, verification
  task: create page.tsx files under app/auth/* as 2-line re-exports from modules/auth. Verification and reset-password use path-param shape ([token]) so the token lands in the URL — the verify route nests under /auth/register/ because it's the final step of the registration journey, not a separate resource.
  files: apps/web/src/app/auth/login/page.tsx, apps/web/src/app/auth/register/page.tsx, apps/web/src/app/auth/register/[token]/page.tsx, apps/web/src/app/auth/forgot-password/page.tsx, apps/web/src/app/auth/reset-password/[token]/page.tsx

[v84-1-4]#4 Dashboard layout and index page
  task: create app/dashboard/layout.tsx (auth-gated shell) and app/dashboard/page.tsx as 2-line re-export from modules/dashboard
  files: apps/web/src/app/dashboard/layout.tsx, apps/web/src/app/dashboard/page.tsx
  depends: [v84-1-4]#1

[v84-1-4]#5 Dashboard settings pages
  task: create page.tsx files under app/dashboard/settings/* as 2-line re-exports from modules/account
  files: apps/web/src/app/dashboard/settings/page.tsx, apps/web/src/app/dashboard/settings/confirm-email/page.tsx
  depends: [v84-1-4]#4

[v84-1-4]#6 Admin layout and index page
  task: create app/admin/layout.tsx (admin-role-gated shell) and app/admin/page.tsx as 2-line re-export from modules/admin
  files: apps/web/src/app/admin/layout.tsx, apps/web/src/app/admin/page.tsx
  depends: [v84-1-4]#1

[v84-1-4]#7 Admin user management pages
  task: create page.tsx files under app/admin/users/* as 2-line re-exports from modules/users
  files: apps/web/src/app/admin/users/page.tsx, apps/web/src/app/admin/users/new/page.tsx, apps/web/src/app/admin/users/[id]/edit/page.tsx
  depends: [v84-1-4]#6

[v84-1-4]#8 Frontend config wrappers — brand re-export, env readers, sub-barrel
  task: frontend code imports env and brand exclusively through a single `@/config` sub-barrel so src/ stays insulated from repo-root `brand/` and from `process.env`. Create config/brand.ts that re-exports `copy` from the repo-root brand package (parallel to api's templates/emails/theme.ts re-export — brand lives outside apps/web/src/, so direct imports break tsc rootDir). Create config/public-env.ts that reads NEXT_PUBLIC_* values (safe in client and server code). Create config/server-env.ts that begins with `import 'server-only'` so any accidental client import fails at build time, and reads secrets / server-only env. Create config/index.ts that re-exports copy + publicEnv + routes helpers; do NOT re-export serverEnv from the top-level barrel (keep it reachable only via `@/config/server-env` so the server-only gate survives accidental client paths).
  files: apps/web/src/config/brand.ts, apps/web/src/config/public-env.ts, apps/web/src/config/server-env.ts, apps/web/src/config/index.ts
[v84-1-4]#9 Common sub-barrels for guards, hooks, providers
  task: create the sub-barrel index.ts files at `common/{guards,hooks,providers}/` that re-export the symbols in each folder. Per convention, imports go through these sub-barrels (`@/common/guards`, `@/common/hooks`, `@/common/providers`) — never a top-level `common/index.ts`. Initially each barrel may be empty; later iterations append their new symbols.
  files: apps/web/src/common/guards/index.ts, apps/web/src/common/hooks/index.ts, apps/web/src/common/providers/index.ts
[v84-1-4]#10 Dashboard shell and sub-barrel
  task: create `modules/dashboard/components/UserShell.tsx` — the auth-gated shell chrome used by `app/dashboard/layout.tsx` (nav, user dropdown, slot for page content) and re-export it from `modules/dashboard/components/index.ts`. UserShell composes the route guards and the page outline; the dashboard page components slot into its children.
  files: apps/web/src/modules/dashboard/components/UserShell.tsx, apps/web/src/modules/dashboard/components/index.ts
  depends: [v84-1-4]#4


# --- iteration 2 ---
[v84-2-3-2]#1 AuthProvider and useAuth hook
  task: implement AuthProvider context, useAuth hook, and auth state management (user, login, logout, session sync with BFF)
  files: apps/web/src/common/providers/AuthProvider.tsx, apps/web/src/common/hooks/useAuth.ts
[v84-2-3-2]#2 GoogleProvider for OAuth sign-in
  task: implement GoogleProvider component that loads Google Identity Services, exposes the button-render API, and hands the ID token to `useAuth().login` → upstream `/auth/google`. Mounted alongside `AuthProvider` so the Google button can appear on `LoginPage` when `NEXT_PUBLIC_GOOGLE_CLIENT_ID` is set.
  files: apps/web/src/common/providers/GoogleProvider.tsx
[v84-2-4-3]#1 Frontend route guards
  task: implement RequireAuth and RequireRole components that enforce authentication and role checks using AuthProvider, blocking unauthorized access
  files: apps/web/src/common/guards/RequireAuth.tsx, apps/web/src/common/guards/RequireRole.tsx
  depends: [v84-2-3-2]#1
[v84-2-4-2]#1 Admin layout and route files
  task: create thin re-export route files for the /admin section — layout wraps AdminShell, page re-exports DashboardPage, /admin/users/* re-exports UsersListPage/UserNewPage/UserEditPage. Configure navigation links and URL structure in routes.ts
  files: apps/web/src/app/admin/layout.tsx, apps/web/src/app/admin/page.tsx, apps/web/src/app/admin/users/page.tsx, apps/web/src/app/admin/users/new/page.tsx, apps/web/src/app/admin/users/[id]/edit/page.tsx, apps/web/src/config/routes.ts
  depends: [v84-2-4-3]#1
[v84-2-4-2]#2 AdminShell composable
  task: create AdminShell component that composes RequireRole guard and admin chrome, wrapping protected admin content
  files: apps/web/src/modules/admin/components/AdminShell.tsx
  depends: [v84-2-4-3]#1
[v84-2-4-2]#3 Users list page
  task: create UsersListPage component that consumes useAuth, fetches paginated users, and renders the admin table layout
  files: apps/web/src/modules/admin/pages/UsersListPage.tsx
  depends: [v84-2-4-2]#1, [v84-2-4-2]#2

[v84-2-4-2]#4 Admin module page components + user-create/edit pages
  task: create the module-level page components that the thin admin/users route files re-export — admin/pages/DashboardPage (landing content for /admin), users/pages/UserNewPage (wraps UserForm for creation), users/pages/UserEditPage (wraps UserForm for updates). Export them via the corresponding sub-barrels so the route files can import from `@/modules/{admin,users}/pages`. Create the users/components sub-barrel so UserForm can be re-exported for internal module use. Also create `modules/admin/components/index.ts` (re-exports AdminShell) and `modules/admin/pages/index.ts` + `modules/users/pages/index.ts` barrels.
  files: apps/web/src/modules/admin/pages/DashboardPage.tsx, apps/web/src/modules/users/pages/UserNewPage.tsx, apps/web/src/modules/users/pages/UserEditPage.tsx, apps/web/src/modules/users/components/index.ts, apps/web/src/modules/admin/components/index.ts, apps/web/src/modules/admin/pages/index.ts, apps/web/src/modules/users/pages/index.ts
  depends: [v84-2-4-2]#1, [v84-2-4-2]#2

[v84-2-4-2]#5 Login page
  task: create LoginPage component — form with email/password (zod validated), handles 2FA code prompt when the login response returns requiresTwoFactor, calls useAuth().login on submit, and redirects via landingPathForUser(user) on success. Supports Google SSO button when the client ID env is set. Also create the `modules/auth/pages/index.ts` sub-barrel so route files can import via `@/modules/auth/pages` — iter-3 appends RegisterPage, VerifyEmailPage, ForgotPasswordPage, and ResetPasswordPage exports to the same barrel.
  files: apps/web/src/modules/auth/pages/LoginPage.tsx, apps/web/src/modules/auth/pages/index.ts
  depends: [v84-2-3-2]#1

# --- iteration 3 ---
[v84-3-1-1]#1 Registration route & page component
  task: create (public) auth/register route file re-exporting RegisterPage, and add RegisterPage to auth/pages/
  files: apps/web/src/app/auth/register/page.tsx, apps/web/src/modules/auth/pages/RegisterPage.tsx
[v84-3-1-2]#1 Verification route & page component
  task: create (public) auth/register/[token] route file re-exporting VerifyEmailPage, and add VerifyEmailPage to auth/pages/. The verify step is part of the registration journey (the user clicks a link from the signup email and lands here to finish) — URL nests under /auth/register/, NOT under a separate /auth/verify/ path.
  files: apps/web/src/app/auth/register/[token]/page.tsx, apps/web/src/modules/auth/pages/VerifyEmailPage.tsx
[v84-3-1-2]#2 User dashboard route & page component
  task: create (protected) dashboard route file re-exporting UserDashboardPage, and add UserDashboardPage to modules/dashboard/pages/ (dashboard has its own module — NOT under auth, since a dashboard is post-auth landing content, not an auth flow). Scope auth context updates triggered by verification to token-only state to prevent unnecessary global provider re-renders on VerifyEmailPage and UserDashboardPage. Export UserDashboardPage via the dashboard/pages sub-barrel so the route file imports from `@/modules/dashboard/pages`.
  files: apps/web/src/app/dashboard/page.tsx, apps/web/src/modules/dashboard/pages/UserDashboardPage.tsx, apps/web/src/modules/dashboard/pages/index.ts
  depends: [v84-2-3-2]#2
[v84-3-2-1]#1 Forgot password route & page component
  task: create (public) auth/forgot-password route file re-exporting ForgotPasswordPage, and add ForgotPasswordPage to auth/pages/
  files: apps/web/src/app/auth/forgot-password/page.tsx, apps/web/src/modules/auth/pages/ForgotPasswordPage.tsx
[v84-3-2-2]#1 Reset password route & page component
  task: create (public) auth/reset-password/[token] route file re-exporting ResetPasswordPage, and add ResetPasswordPage to auth/pages/. Mandate importing UI text, placeholders, and branding tokens from brand/copy and brand/tokens instead of hardcoding them.
  files: apps/web/src/app/auth/reset-password/[token]/page.tsx, apps/web/src/modules/auth/pages/ResetPasswordPage.tsx
[v84-3-1-1]#2 Update central route map
  task: add registration, verification, dashboard, forgot-password, and reset-password paths to apps/web/src/config/routes.ts
  files: apps/web/src/config/routes.ts

# --- iteration 4 ---
[v84-4-1-1]#1 2FA section on AccountSettingsPage
  task: `AccountSettingsPage` in apps/web/src/modules/account/pages/AccountSettingsPage.tsx composes a 2FA section using the `TwoFactorSetup` component. Uses `useAuth()` to refresh session state after enable/disable, scoping context updates to lightweight flags so settings-page re-renders stay minimal during 2FA toggles. Barrel re-export from apps/web/src/modules/account/pages/index.ts keeps the route file's 2-line re-export clean.
  files: apps/web/src/modules/account/pages/AccountSettingsPage.tsx, apps/web/src/modules/account/pages/index.ts
  depends: [v84-1-4]#4
[v84-4-2-1]#1 Password change section on AccountSettingsPage
  task: `AccountSettingsPage` composes a password-change section using `PasswordChangeForm`; triggers `useAuth()` session refresh on success so the auth state stays consistent after the backend revokes other sessions.
  files: apps/web/src/modules/account/pages/AccountSettingsPage.tsx
  depends: [v84-1-4]#4
[v84-4-2-2]#1 Email confirmation route & page
  task: confirm-email route lives at apps/web/src/app/dashboard/settings/confirm-email/page.tsx — verifies the token via `modules/account/api.ts` `confirmEmailChange`, updates local auth state via `useAuth()`, and routes back to `AccountSettingsPage`.
  files: apps/web/src/app/dashboard/settings/confirm-email/page.tsx
  depends: [v84-3-1-2]#1
[v84-4-3-1]#1 Sessions section on AccountSettingsPage
  task: `AccountSettingsPage` composes a sessions section using `SessionsList`. The list reads from `modules/sessions/api.ts listSessions`; revoke actions call `revokeSession` / `revokeAllSessions` and update `useAuth()` state on success.
  files: apps/web/src/modules/account/pages/AccountSettingsPage.tsx
  depends: [v84-1-4]#4
[v84-4-1-2]#1 Login 2FA challenge composition
  task: update apps/web/src/modules/auth/pages/LoginPage.tsx to handle the `requiresTwoFactor` response from `/auth/login`, prompt for the TOTP code in-place, and retry the login mutation against the same endpoint with `{ email, password, totpCode }` — no form state is cleared between the password step and the code step.
  files: apps/web/src/modules/auth/pages/LoginPage.tsx
[v84-4-1-1]#2 Update central route map
  task: confirm `/dashboard/settings` and `/dashboard/settings/confirm-email` are in apps/web/src/config/routes.ts. 2FA, password change, and sessions are all sections of the single `AccountSettingsPage` — no separate sub-routes are required.
  files: apps/web/src/config/routes.ts
