'use client';
// [v84-2-3-2][front-nextjs:pages]

import {
  createContext,
  useState,
  useEffect,
  useCallback,
  type ReactNode,
} from 'react';
import React from 'react';
import { apiFetch, ApiError } from '@/lib';
import type { User } from '@/modules/auth/types';

// All auth flows go through the BFF (apps/web/src/app/api/*). Tokens never
// reach the browser — they live in server-side session storage keyed by an
// opaque httpOnly cookie. This provider holds only the resolved User object
// in client state. The session itself is managed entirely server-side.

export type LoginResult = { requiresTwoFactor: true } | { user: User };

interface AuthContextValue {
  user: User | null;
  isLoading: boolean;
  login: (email: string, password: string, totpCode?: string) => Promise<LoginResult>;
  loginWithGoogle: (idToken: string) => Promise<User>;
  // Step 1 of registration — sends a verification email. No account is created yet.
  startRegistration: (email: string) => Promise<void>;
  // Step 2 — uses the token from the email link to actually create the account and log in.
  completeRegistration: (token: string, username: string, password: string) => Promise<User>;
  logout: () => Promise<void>;
  refreshUser: () => Promise<User | null>;
}

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  const fetchUser = useCallback(async (): Promise<User | null> => {
    try {
      const u = await apiFetch<User>('/users/me');
      setUser(u);
      return u;
    } catch (err) {
      // 401 just means we're not logged in — quietly clear and move on.
      if (err instanceof ApiError && err.status === 401) {
        setUser(null);
        return null;
      }
      // Anything else (network error, 500) — surface it later if needed.
      setUser(null);
      return null;
    }
  }, []);

  // Bootstrap: just call /api/users/me. If the cookie is valid, we get back
  // the user; if not, we get a 401 and stay logged out. No localStorage check.
  useEffect(() => {
    fetchUser().finally(() => setIsLoading(false));
  }, [fetchUser]);

  const login = useCallback(
    async (email: string, password: string, totpCode?: string): Promise<LoginResult> => {
      const body: Record<string, string> = { email, password };
      if (totpCode) body.totpCode = totpCode;

      const data = await apiFetch<{ ok?: true; requiresTwoFactor?: true }>('/auth/login', {
        method: 'POST',
        body: JSON.stringify(body),
      });

      if (data.requiresTwoFactor) {
        return { requiresTwoFactor: true };
      }

      // BFF set the session cookie on the response — fetchUser succeeds now.
      const fetched = await fetchUser();
      if (!fetched) throw new Error('Login succeeded but user fetch failed');
      return { user: fetched };
    },
    [fetchUser],
  );

  const loginWithGoogle = useCallback(
    async (idToken: string): Promise<User> => {
      await apiFetch('/auth/google', {
        method: 'POST',
        body: JSON.stringify({ idToken }),
      });
      const fetched = await fetchUser();
      if (!fetched) throw new Error('Google sign-in succeeded but user fetch failed');
      return fetched;
    },
    [fetchUser],
  );

  const startRegistration = useCallback(async (email: string): Promise<void> => {
    await apiFetch('/auth/register', {
      method: 'POST',
      body: JSON.stringify({ email }),
    });
  }, []);

  const completeRegistration = useCallback(
    async (token: string, username: string, password: string): Promise<User> => {
      await apiFetch('/auth/register/complete', {
        method: 'POST',
        body: JSON.stringify({ token, username, password }),
      });
      const fetched = await fetchUser();
      if (!fetched) throw new Error('Registration succeeded but user fetch failed');
      return fetched;
    },
    [fetchUser],
  );

  const logout = useCallback(async () => {
    try {
      await apiFetch('/auth/logout', { method: 'POST' });
    } catch {
      // ignore — the BFF clears the cookie regardless
    }
    setUser(null);
  }, []);

  return React.createElement(
    AuthContext.Provider,
    {
      value: {
        user,
        isLoading,
        login,
        loginWithGoogle,
        startRegistration,
        completeRegistration,
        logout,
        refreshUser: fetchUser,
      },
    },
    children,
  );
}

export { AuthContext };
export type { AuthContextValue };
