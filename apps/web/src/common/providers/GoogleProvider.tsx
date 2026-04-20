'use client';

import { GoogleOAuthProvider } from '@react-oauth/google';
import type { ReactNode } from 'react';
import { publicEnv } from '@/config';

// If NEXT_PUBLIC_GOOGLE_CLIENT_ID is not set, render children without wrapping —
// Google login just won't be available, rather than crashing the whole app.
// [v84-2-3-2][front-nextjs:pages]
export function GoogleProvider({ children }: { children: ReactNode }) {
  const clientId = publicEnv.googleClientId;
  if (!clientId) return <>{children}</>;
  return <GoogleOAuthProvider clientId={clientId}>{children}</GoogleOAuthProvider>;
}
