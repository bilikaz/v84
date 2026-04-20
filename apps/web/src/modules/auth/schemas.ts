import { z } from 'zod';

export const loginSchema = z.object({
  email: z.string().email('Invalid email address'),
  password: z.string().min(1, 'Password is required'),
  totpCode: z.string().optional(),
});

// [v84-3-1-1][front-nextjs:forms]
// Step 1: just an email — we send a verification link before creating any account.
export const registerSchema = z.object({
  email: z.string().email('Invalid email address'),
});

// [v84-3-1-2][front-nextjs:forms]
// Step 2: token comes from the link, user fills in username + password.
export const completeRegistrationSchema = z.object({
  username: z.string().min(3, 'Username must be at least 3 characters'),
  password: z.string().min(8, 'Password must be at least 8 characters'),
});

// [v84-3-2-1][front-nextjs:forms]
export const forgotPasswordSchema = z.object({
  email: z.string().email('Invalid email address'),
});

// [v84-3-2-2][front-nextjs:forms]
export const resetPasswordSchema = z
  .object({
    password: z.string().min(8, 'Password must be at least 8 characters'),
    confirmPassword: z.string(),
  })
  .refine((d) => d.password === d.confirmPassword, {
    message: 'Passwords do not match',
    path: ['confirmPassword'],
  });

export type LoginInput = z.infer<typeof loginSchema>;
export type RegisterInput = z.infer<typeof registerSchema>;
export type CompleteRegistrationInput = z.infer<typeof completeRegistrationSchema>;
export type ForgotPasswordInput = z.infer<typeof forgotPasswordSchema>;
export type ResetPasswordInput = z.infer<typeof resetPasswordSchema>;
