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
