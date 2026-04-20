
# --- iteration 2 ---
[v84-2-1-3]#1 Seed script verification for hardcoded brand strings
  task: Verify seed logic does not hardcode `copy.appName` in user-facing strings (e.g., welcome messages, automated test emails), importing from `brand/copy` if referencing the app name.
[v84-2-4-2]#2 Admin UI layout and content verification
  task: Verify the admin dashboard page imports copy.appName for header/footer branding and confirm that table headers, form labels, and button text are sourced from an i18n layer or component-level strings, not brand/copy.
[v84-2-4-2]#3 Admin UI token consumption verification
  task: Verify all admin UI components explicitly consume `brand/tokens` for colors, radii, and spacing and reject any inline hex values or Tailwind arbitrary values for brand primitives.
[v84-2-2-1]#4 Auth API message externalization verification
  task: Verify authentication endpoint error responses and validation messages do not embed the app name or brand-specific phrasing and ensure all user-facing strings are externalized via `brand/copy` or a message module.
[v84-2-3-1]#5 BFF handler branding verification
  task: Verify BFF server-side route handlers and logging statements avoid hardcoding the app name or brand tokens.

# --- iteration 3 ---
[v84-3-1-2]#1 Verification and Welcome email templates hardcode app name or brand colors
  risk: VerificationEmail and WelcomeEmail templates use literal strings (e.g., "Welcome to V84") and inline hex values instead of importing from brand/copy and brand/tokens.
  impact: A centralized rebrand in brand/ would leave sent emails and templates showing stale names and colors, violating verbal and visual identity standards.
  action: email templates must source their subject lines, headings, and styling from the centralized brand packages (importing via `apps/api/src/templates/emails/theme.ts` re-exports, not directly from `brand/*`).
[v84-3-2-1]#2 PasswordResetEmail template duplicates hardcoded brand references
  risk: The PasswordResetEmail template embeds the application name or brand-specific phrasing directly in its source or copy.
  impact: Recovery emails will display outdated branding; updating copy.mjs/copy.cjs will not propagate changes to the password reset flow.
  action: PasswordResetEmail must read all user-facing text and visual tokens from the centralized brand packages (via `apps/api/src/templates/emails/theme.ts` re-exports).
[v84-3-1-1]#3 Registration form UI strings are not externalized
  risk: RegisterPage and RegistrationForm contain hardcoded labels, validation messages, and success prompts (e.g., "Create your account").
  impact: Copy cannot be swapped for rebranding or localization without touching component logic, creating maintenance friction and inconsistency.
  action: form labels, validation messages, and success states must reference an externalized string source rather than raw literals.
[v84-3-2-2]#4 Reset password pages hardcode UI text and branding tokens
  risk: ResetPasswordPage, ResetPasswordForm, and success redirect logic embed hardcoded app names, taglines, or inline brand colors.
  impact: Inconsistent verbal identity across the recovery flow; visual tokens bypass the centralized design system, risking drift as the brand evolves.
  action: page copy, form placeholders, and UI components must import from brand/copy and brand/tokens, ensuring all recovery flow touchpoints reflect centralized branding.

# --- iteration 4 ---
[v84-4-1-1]#1 2FA setup UI labels hardcode brand strings and tokens
  risk: The 2FA enable/disable form uses raw string literals for labels (e.g., "Scan this QR code") and inline hex values or arbitrary Tailwind values for styling.
  impact: Rebranding requires manual edits in multiple UI components; visual tokens bypass the centralized design system leading to drift.
  action: 2FA form labels and page copy must import from `brand/copy` (or i18n layer) and all visual styling must consume `brand/tokens` primitives.
[v84-4-1-2]#2 Login 2FA challenge prompt hardcodes app name and brand tokens
  risk: The conditional 2FA input on the Login page embeds the application name or brand-specific color/spacing for the prompt and input field.
  impact: Inconsistent verbal identity during the login challenge; visual elements drift from the centralized design tokens.
  action: Login page 2FA prompt must source all text from `brand/copy` and use `brand/tokens` for layout and styling.
[v84-4-2-1]#3 Password Change form labels are not externalized
  risk: `PasswordChangeForm` contains hardcoded labels like "Current Password", "New Password", and validation messages.
  impact: Copy cannot be swapped for rebranding or localization without touching component logic, creating maintenance friction.
  action: form labels, validation messages, and success states must reference an externalized string source rather than raw literals.
[v84-4-2-2]#4 EmailChangeVerificationEmail hardcodes brand strings and fonts
  risk: The new `EmailChangeVerificationEmail` template embeds the app name or brand colors directly in its source and uses web fonts.
  impact: Account change notification emails will display outdated branding and broken styling; violates email client font rendering constraints.
  action: Email template must source copy from `brand/copy` (via re-exports) and use only the system `fontFamily.sans` stack from `brand/tokens` for styling.
[v84-4-3-1]#5 Session table UI hardcodes brand tokens
  risk: The session listing table component uses inline hex values or arbitrary Tailwind values for brand colors, spacing, or radii.
  impact: Visual identity drift as the design system evolves; inconsistent styling compared to other tables in the application.
  action: Session table UI must explicitly consume `brand/tokens` for all visual primitives.
