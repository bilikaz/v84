// [v84-2-3-1][front-nextjs:api]
import { apiFetch } from '@/lib';

// [v84-3-2-1][front-nextjs:api]
export function requestPasswordReset(email: string): Promise<void> {
  return apiFetch('/auth/forgot-password', {
    method: 'POST',
    body: JSON.stringify({ email }),
  });
}

// [v84-3-2-2][front-nextjs:api]
export function resetPassword(token: string, password: string): Promise<void> {
  return apiFetch('/auth/reset-password', {
    method: 'POST',
    body: JSON.stringify({ token, password }),
  });
}

// [v84-3-1-2][front-nextjs:api]
// Returns the email associated with a pending registration token, or throws if invalid/expired.
export function checkRegistrationToken(token: string): Promise<{ email: string }> {
  return apiFetch<{ email: string }>(`/auth/register/check?token=${encodeURIComponent(token)}`);
}
