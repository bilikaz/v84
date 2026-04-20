[v84-2-4-2]#1 Define Zod schemas for user creation and update in the users feature module
  task: Create `createUserSchema` and `updateUserSchema` with strict validation rules for email, username, role, and password
  files: apps/web/src/modules/users/schemas.ts
[v84-2-4-2]#2 Implement form submission flow with field-level error mapping and safe retry
  task: Wire Zod `.safeParse` to form handlers, map validation issues to `Record<string, string>`, and catch `ApiError` to show inline feedback without clearing user input
  files: apps/web/src/modules/users/components/UserForm.tsx
  depends: [v84-2-4-2]#1
