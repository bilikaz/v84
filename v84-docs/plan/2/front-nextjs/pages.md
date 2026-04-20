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
