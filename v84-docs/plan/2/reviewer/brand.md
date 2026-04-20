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
