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
