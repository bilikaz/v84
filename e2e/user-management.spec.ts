// [v84-2-4-2][ops:testing]
// End-to-end: admin user management UI.
//
// Covers the happy-path flows a human operator actually does: open the list,
// create a user, edit them, delete them, and see the table update after each
// mutation. We care that the UI wires the API correctly — business rules are
// covered by users-admin.e2e.spec.ts.
//
// Assumptions:
//   - The test stack has been seeded with `admin@admin.localhost` / `password`
//     (role=admin). Run `pnpm seed` against the test DB before Playwright.

import { test, expect } from '@playwright/test';
import { resetBackend } from './helpers/api';

const unique = () => `ui-${Date.now()}-${Math.random().toString(36).slice(2, 6)}`;

async function loginAsAdmin(page: import('@playwright/test').Page): Promise<void> {
  await page.goto('/auth/login');
  await page.getByLabel(/email/i).fill('admin@admin.localhost');
  await page.getByLabel(/password/i).fill('password');
  await page.getByRole('button', { name: /sign in/i }).click();
  // Admins land on /admin per landingPathForUser().
  await page.waitForURL('**/admin**', { timeout: 10000 });
}

test.describe('Admin user management UI', () => {
  test.beforeEach(async ({ page }) => {
    // Reset first so each test starts with the seeded admin + an empty users
    // table (aside from the baseline admin + user). Then login as admin.
    await resetBackend();
    await loginAsAdmin(page);
  });

  test('lists users and renders the user table', async ({ page }) => {
    await page.goto('/admin/users');
    await expect(page.getByRole('heading', { name: /^users$/i })).toBeVisible();
    // Table header is present.
    await expect(page.getByRole('columnheader', { name: /email/i })).toBeVisible();
    // At least one data row exists (admin itself exists at minimum).
    await expect(page.locator('tbody tr').first()).toBeVisible();
  });

  test('creates a user via the create form and shows it in the list', async ({ page }) => {
    const email = `${unique()}@test.local`;
    const username = `u${Date.now()}`;

    await page.goto('/admin/users/new');
    await page.getByLabel(/username/i).fill(username);
    await page.getByLabel(/email/i).fill(email);
    await page.getByLabel(/password/i).fill('TempPassword9!');
    await page.getByRole('button', { name: /create user/i }).click();

    await page.waitForURL('**/admin/users', { timeout: 10000 });
    await expect(page.getByText(email)).toBeVisible();
  });

  test('edits a user and persists the change', async ({ page }) => {
    // Create a user via the UI first so we have something to edit.
    const email = `${unique()}@test.local`;
    const originalUsername = `u${Date.now()}`;
    const newUsername = `renamed${Date.now()}`;

    await page.goto('/admin/users/new');
    await page.getByLabel(/username/i).fill(originalUsername);
    await page.getByLabel(/email/i).fill(email);
    await page.getByLabel(/password/i).fill('TempPassword9!');
    await page.getByRole('button', { name: /create user/i }).click();
    await page.waitForURL('**/admin/users', { timeout: 10000 });

    // Find the row and click Edit.
    const row = page.getByRole('row', { name: new RegExp(originalUsername) });
    await row.getByRole('button', { name: /edit/i }).click();

    // Rename and save.
    const usernameField = page.getByLabel(/username/i);
    await usernameField.fill(newUsername);
    await page.getByRole('button', { name: /save changes/i }).click();

    await page.waitForURL('**/admin/users', { timeout: 10000 });
    await expect(page.getByText(newUsername)).toBeVisible();
    await expect(page.getByText(originalUsername)).toHaveCount(0);
  });

  test('deletes a user after confirming the modal', async ({ page }) => {
    // Create a victim user.
    const email = `${unique()}@test.local`;
    const username = `doomed${Date.now()}`;

    await page.goto('/admin/users/new');
    await page.getByLabel(/username/i).fill(username);
    await page.getByLabel(/email/i).fill(email);
    await page.getByLabel(/password/i).fill('TempPassword9!');
    await page.getByRole('button', { name: /create user/i }).click();
    await page.waitForURL('**/admin/users', { timeout: 10000 });
    await expect(page.getByText(email)).toBeVisible();

    // Delete.
    const row = page.getByRole('row', { name: new RegExp(username) });
    await row.getByRole('button', { name: /delete/i }).click();

    // Confirm in the modal.
    const modal = page.getByRole('dialog').or(page.getByText(/delete user/i).first());
    await modal.getByRole('button', { name: /^delete$/i }).click();

    // Row is gone from the list.
    await expect(page.getByText(email)).toHaveCount(0);
  });
});
