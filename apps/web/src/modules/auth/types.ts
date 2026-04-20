// [v84-2-3-1][front-nextjs:api]
import type { User } from '@/modules/users/types';

export type { User };

export interface AuthTokens {
  accessToken: string;
  refreshToken: string;
}

export interface LoginResponse extends AuthTokens {
  requiresTwoFactor?: boolean;
}
