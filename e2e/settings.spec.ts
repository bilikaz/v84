// End-to-end: account settings — password change and 2FA.
// Each test is self-contained: creates its own user, logs in, exercises settings.

import { test, expect } from '@playwright/test';
import { registerViaApi, resetBackend } from './helpers/api';
import { generateTotp } from './helpers/totp';

const unique = () => `e2e-${Date.now()}-${Math.random().toString(36).slice(2, 6)}`;

async function loginViaUI(
  page: import('@playwright/test').Page,
  email: string,
  password: string,
): Promise<void> {
  await page.goto('/auth/login');
  await page.getByLabel(/email/i).fill(email);
  await page.getByLabel(/password/i).fill(password);
  await page.getByRole('button', { name: /sign in/i }).click();
  await page.waitForURL('**/dashboard**', { timeout: 10000 });
}

// [v84-4-2-1][ops:testing]
test.describe('Settings — password change', () => {
  test.beforeEach(async () => {
    await resetBackend();
  });

  test('changes password and new credentials work', async ({ page }) => {
    const email = `${unique()}@test.local`;
    const username = `pwuser${Date.now()}`;
    const oldPassword = 'OldPassword9!';
    const newPassword = 'NewPassword9!';

    await registerViaApi(email, username, oldPassword);
    await loginViaUI(page, email, oldPassword);

    await page.goto('/dashboard/settings');
    // Use field IDs — labels are ambiguous because EmailChangeForm also has
    // a "Current password" field on the same page.
    await page.locator('#currentPassword').fill(oldPassword);
    await page.locator('#password').fill(newPassword);
    await page.locator('#confirmPassword').fill(newPassword);
    await page.getByRole('button', { name: /update password/i }).click();

    await expect(page.getByText(/password updated/i)).toBeVisible({ timeout: 5000 });

    // Logout and login with new password.
    await page.getByRole('button', { name: /logout/i }).click();
    await page.waitForURL('**/auth/login**', { timeout: 5000 });
    await loginViaUI(page, email, newPassword);
    // URL proves authentication.
  });
});

// [v84-4-1-1][ops:testing]
test.describe('Settings — 2FA', () => {
  test.beforeEach(async () => {
    await resetBackend();
  });

  test('enables 2FA, then login requires TOTP code', async ({ page }) => {
    const email = `${unique()}@test.local`;
    const username = `tfauser${Date.now()}`;
    const password = 'TwoFactorPw9!';

    await registerViaApi(email, username, password);
    await loginViaUI(page, email, password);

    await page.goto('/dashboard/settings');

    // Enable 2FA.
    await page.getByRole('button', { name: /enable 2fa/i }).click();

    // Wait for secret to appear.
    const secretEl = page.locator('code');
    await expect(secretEl).toBeVisible({ timeout: 10000 });
    const secret = (await secretEl.textContent())!.trim();

    // Verify with a real TOTP code.
    await page.locator('#totp-setup').fill(generateTotp(secret));
    await page.getByRole('button', { name: /verify and enable/i }).click();
    await expect(page.getByText(/enabled/i)).toBeVisible({ timeout: 5000 });

    // Logout.
    await page.getByRole('button', { name: /logout/i }).click();
    await page.waitForURL('**/auth/login**', { timeout: 5000 });

    // Login now requires TOTP.
    await page.goto('/auth/login');
    await page.getByLabel(/email/i).fill(email);
    await page.getByLabel(/password/i).fill(password);
    await page.getByRole('button', { name: /sign in/i }).click();

    const totpInput = page.locator('#totpCode');
    await expect(totpInput).toBeVisible({ timeout: 5000 });
    await totpInput.fill(generateTotp(secret));
    await page.getByRole('button', { name: /sign in/i }).click();

    await page.waitForURL('**/dashboard**', { timeout: 10000 });
    // URL proves authentication.
  });
});
