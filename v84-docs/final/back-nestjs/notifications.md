
# --- iteration 1 ---
[v84-1-6]#1 EmailLayout shared template + story
  task: Create `EmailLayout` React component at apps/api/src/templates/emails/EmailLayout.tsx — the brand-aware shared shell that every transactional email wraps (logo, header, footer, spacing tokens). Imports colors/typography/spacing from the sibling `theme.ts` re-export. Colocated Storybook story in `EmailLayout.stories.tsx`. No business content — iteration 3 adds the first real email templates (VerificationEmail, WelcomeEmail, PasswordResetEmail) that slot their bodies into this layout.
  files: apps/api/src/templates/emails/EmailLayout.tsx, apps/api/src/templates/emails/EmailLayout.stories.tsx

# --- iteration 3 ---
[v84-3-1-2]#4 NotificationsModule & Service infrastructure
  task: stand up `NotificationsModule` and `NotificationsService` — service wraps nodemailer, exposes `sendVerificationEmail`, `sendWelcomeEmail`, `sendPasswordReset` (and later `sendEmailChangeConfirmation` in iter-4) and renders templates via `renderToHtmlAndText`. Module exports the service so `AuthService` and `UsersService` can consume it via DI. Must exist before any email template has a real consumer.
  files: apps/api/src/modules/notifications/notifications.module.ts, apps/api/src/modules/notifications/notifications.service.ts
  depends:
[v84-3-1-2]#1 VerificationEmail template and story
  task: Create VerificationEmail React component using @react-email/components, replacing hardcoded app name and inline hex colors with imports from apps/api/src/templates/emails/theme.ts, verification token link placeholder, HTML and plain-text rendering, plus colocated Storybook story. Email templates use noun+"Email" naming (like WelcomeEmail, PasswordResetEmail) — VerificationEmail NOT VerifyEmail.
  files: apps/api/src/templates/emails/VerificationEmail.tsx
         apps/api/src/templates/emails/VerificationEmail.stories.tsx
  depends:
[v84-3-1-2]#2 WelcomeEmail template and story
  task: Create WelcomeEmail React component using @react-email/components, replacing hardcoded app name and inline hex colors with imports from apps/api/src/templates/emails/theme.ts, personalized user greeting, dashboard link, HTML and plain-text rendering, plus colocated Storybook story.
  files: apps/api/src/templates/emails/WelcomeEmail.tsx
         apps/api/src/templates/emails/WelcomeEmail.stories.tsx
  depends:
[v84-3-2-1]#1 PasswordResetEmail template and story
  task: Create PasswordResetEmail React component using @react-email/components, replacing hardcoded app name and inline hex colors with imports from apps/api/src/templates/emails/theme.ts, password reset token link placeholder, expiry warning, HTML and plain-text rendering, plus colocated Storybook story.
  files: apps/api/src/templates/emails/PasswordResetEmail.tsx
         apps/api/src/templates/emails/PasswordResetEmail.stories.tsx
  depends:
[v84-3-1-2]#3 Email templates index barrel
  task: Create index barrel for apps/api/src/templates/emails/ to re-export all email templates for centralized consumer import.
  files: apps/api/src/templates/emails/index.ts
  depends: [v84-3-1-2]#1, [v84-3-1-2]#2, [v84-3-2-1]#1

# --- iteration 4 ---
[v84-4-2-2]#1 ConfirmEmailChange template and story
  task: create `ConfirmEmailChange` React component in apps/api/src/templates/emails/ using @react-email/components, reusing the established template patterns (theme.ts re-exports, HTML/text rendering, Storybook colocation). Use `brand/tokens` `fontFamily.sans` for text styling (no web fonts or hardcoded stacks) per email client rendering conventions.
  files: apps/api/src/templates/emails/ConfirmEmailChange.tsx, apps/api/src/templates/emails/ConfirmEmailChange.stories.tsx
  depends:
[v84-4-2-2]#2 Update email templates index barrel
  task: append `ConfirmEmailChange` export to apps/api/src/templates/emails/index.ts so `NotificationsService` can resolve it alongside the other templates.
  files: apps/api/src/templates/emails/index.ts
  depends: [v84-4-2-2]#1
