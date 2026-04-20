import { z } from 'zod';

// [v84-4-2-1][front-nextjs:forms]
export const changePasswordSchema = z
  .object({
    currentPassword: z.string().min(1, 'Current password is required'),
    password: z.string().min(8, 'New password must be at least 8 characters'),
    confirmPassword: z.string(),
  })
  .refine((d) => d.password === d.confirmPassword, {
    message: 'Passwords do not match',
    path: ['confirmPassword'],
  });

// [v84-4-1-1][front-nextjs:forms]
export const verifyTotpSchema = z.object({
  code: z.string().regex(/^\d{6}$/, 'Code must be 6 digits'),
});

// [v84-4-1-1][front-nextjs:forms]
export const disableTwoFactorSchema = z.object({
  password: z.string().min(1, 'Password is required'),
  code: z.string().regex(/^\d{6}$/, 'Code must be 6 digits'),
});

export type ChangePasswordInput = z.infer<typeof changePasswordSchema>;
export type VerifyTotpInput = z.infer<typeof verifyTotpSchema>;
export type DisableTwoFactorInput = z.infer<typeof disableTwoFactorSchema>;
