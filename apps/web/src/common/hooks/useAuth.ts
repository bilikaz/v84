'use client';
// [v84-2-3-2][front-nextjs:pages]

import { useContext } from 'react';
import { AuthContext, type AuthContextValue } from '../providers';

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error('useAuth must be used within AuthProvider');
  return ctx;
}
