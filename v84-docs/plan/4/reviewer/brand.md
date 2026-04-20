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
