// [v84-2-4-3][ops:testing]
// End-to-end: admin route protection.
//
// Pins that non-admin users are kept out of /admin/*. Anyone with a regular
// session should be redirected (by RequireRole) and should not see the admin
// UI even for a flash. Admin users pass through.
//
// Assumptions:
//   - The test stack has been seeded with `admin@admin.localhost` / `password`
//     (role=admin). Run `pnpm seed` against the test DB before Playwright.

import { test, expect } from '@playwright/test';
import { registerViaApi, resetBackend } from './helpers/api';

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
}

test.describe('Admin route protection', () => {
  test.beforeEach(async () => {
    await resetBackend();
  });

  test('regular user sees Access Denied on /admin', async ({ page }) => {
    const email = `${unique()}@test.local`;
    const username = `user${Date.now()}`;
    const password = 'UserPassword9!';

    await registerViaApi(email, username, password);
    await loginViaUI(page, email, password);
    await page.waitForURL('**/dashboard**', { timeout: 10000 });

    await page.goto('/admin');
    // RequireRole renders "Access Denied" in place of admin content.
    await expect(page.getByRole('heading', { name: /access denied/i })).toBeVisible();
  });

  test('regular user cannot see admin user table', async ({ page }) => {
    const email = `${unique()}@test.local`;
    const username = `user${Date.now()}`;
    const password = 'UserPassword9!';

    await registerViaApi(email, username, password);
    await loginViaUI(page, email, password);
    await page.waitForURL('**/dashboard**', { timeout: 10000 });

    await page.goto('/admin/users');
    await expect(page.getByRole('heading', { name: /access denied/i })).toBeVisible();
    // The admin table heading must NOT render.
    await expect(page.getByRole('heading', { name: /^users$/i })).toHaveCount(0);
  });

  test('admin user reaches /admin/users and sees the table', async ({ page }) => {
    // The api container seeds admin@admin.localhost / password before reporting healthy.
    await loginViaUI(page, 'admin@admin.localhost', 'password');
    // Admins land on /admin, not /dashboard, per landingPathForUser().
    await page.waitForURL('**/admin**', { timeout: 10000 });

    await page.goto('/admin/users');
    await expect(page).toHaveURL(/\/admin\/users$/);
    await expect(page.getByRole('heading', { name: /^users$/i })).toBeVisible();
  });
});
