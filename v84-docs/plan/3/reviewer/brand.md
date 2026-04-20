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
