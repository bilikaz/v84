// [v84-2-4-2][front-nextjs:forms]
import { z } from 'zod';

export const createUserSchema = z.object({
  username: z.string().min(3, 'Username must be at least 3 characters'),
  email: z.string().email('Invalid email address'),
  password: z.string().min(8, 'Password must be at least 8 characters'),
  role: z.enum(['user', 'admin']),
});

export const editUserSchema = z.object({
  username: z.string().min(3, 'Username must be at least 3 characters'),
  password: z.string().min(8, 'Password must be at least 8 characters').or(z.literal('')),
  role: z.enum(['user', 'admin']),
});

export type CreateUserInput = z.infer<typeof createUserSchema>;
export type EditUserInput = z.infer<typeof editUserSchema>;
