[v84-4-2-2]#1 ConfirmEmailChange template and story
  task: create `ConfirmEmailChange` React component in apps/api/src/templates/emails/ using @react-email/components, reusing the established template patterns (theme.ts re-exports, HTML/text rendering, Storybook colocation). Use `brand/tokens` `fontFamily.sans` for text styling (no web fonts or hardcoded stacks) per email client rendering conventions.
  files: apps/api/src/templates/emails/ConfirmEmailChange.tsx, apps/api/src/templates/emails/ConfirmEmailChange.stories.tsx
  depends:
[v84-4-2-2]#2 Update email templates index barrel
  task: append `ConfirmEmailChange` export to apps/api/src/templates/emails/index.ts so `NotificationsService` can resolve it alongside the other templates.
  files: apps/api/src/templates/emails/index.ts
  depends: [v84-4-2-2]#1
