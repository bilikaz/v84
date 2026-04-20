// End-to-end: auth flows through a real browser.
//
// Each test is self-contained — sets up its own user via the API when needed,
// then drives the UI. No test depends on another test's side effects.

import { test, expect } from '@playwright/test';
import {
  waitForEmail,
  extractVerifyLink,
  registerViaApi,
  resetBackend,
} from './helpers/api';

const unique = () => `e2e-${Date.now()}-${Math.random().toString(36).slice(2, 6)}`;

// [v84-4-1-2][ops:testing]
test.describe('Auth flow', () => {
  test.beforeEach(async () => {
    // Wipe DB/Redis/mail back to the seeded baseline so each test starts
    // from a known state, identical to how API integration tests behave.
    await resetBackend();
  });

  test('register → verify email → land on dashboard', async ({ page }) => {
    const email = `${unique()}@test.local`;
    const username = `user${Date.now()}`;
    const password = 'E2ePassword9!';

    // Step 1: submit email on register page.
    await page.goto('/auth/register');
    await page.getByLabel(/email/i).fill(email);
    await page.getByRole('button', { name: /continue/i }).click();
    await expect(page.getByRole('heading', { name: /check your email/i })).toBeVisible({
      timeout: 10000,
    });

    // Step 2: follow the verification link from the email.
    const msg = await waitForEmail(email);
    const verifyLink = await extractVerifyLink(msg.ID);
    const url = new URL(verifyLink);
    await page.goto(`${url.pathname}${url.search}`);

    // Step 3: complete registration.
    await expect(page.locator(`input[value="${email}"]`)).toBeVisible({ timeout: 10000 });
    await page.getByLabel(/username/i).fill(username);
    await page.getByLabel(/password/i).fill(password);
    await page.getByRole('button', { name: /create account/i }).click();

    // Should land on dashboard.
    await page.waitForURL('**/dashboard**', { timeout: 10000 });
    // URL proves authentication — BFF redirects to /auth/login if session is invalid.
  });

  test('login → dashboard → logout → back to login', async ({ page }) => {
    const email = `${unique()}@test.local`;
    const username = `loginuser${Date.now()}`;
    const password = 'E2ePassword9!';
    await registerViaApi(email, username, password);

    // Login.
    await page.goto('/auth/login');
    await page.getByLabel(/email/i).fill(email);
    await page.getByLabel(/password/i).fill(password);
    await page.getByRole('button', { name: /sign in/i }).click();
    await page.waitForURL('**/dashboard**', { timeout: 10000 });
    // URL proves authentication — BFF redirects to /auth/login if session is invalid.

    // Logout.
    await page.getByRole('button', { name: /logout/i }).click();
    await page.waitForURL('**/auth/login**', { timeout: 10000 });

    // Verify we're actually logged out — going to dashboard should redirect.
    await page.goto('/dashboard');
    await page.waitForURL('**/auth/login**', { timeout: 10000 });
  });

  test('login shows error on wrong password', async ({ page }) => {
    const email = `${unique()}@test.local`;
    await registerViaApi(email, 'wrongpwuser', 'E2ePassword9!');

    await page.goto('/auth/login');
    await page.getByLabel(/email/i).fill(email);
    await page.getByLabel(/password/i).fill('WrongPassword1!');
    await page.getByRole('button', { name: /sign in/i }).click();

    await expect(page.getByText(/invalid|unauthorized|failed/i)).toBeVisible({
      timeout: 5000,
    });
    await expect(page).toHaveURL(/\/auth\/login/);
  });
});
