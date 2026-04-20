// [v84-2-2-2][ops:testing]
// One-line guard-presence pins for every protected endpoint.
//
// These tests don't validate business logic — they verify the @UseGuards
// decorator is actually wired. Without this, a refactor that silently removes
// a guard would leak protected resources and no functional test would catch it
// (because functional tests usually supply a valid token).
//
// Rule: every endpoint that requires auth must 401 when hit with no Authorization
// header. Every endpoint that requires an admin role must 403 when hit with a
// regular-user token. Every state-mutating admin endpoint is additionally pinned
// against a non-admin user to catch RolesGuard gaps.

import { createTestApp, type TestContext } from './helpers/app';
import { registerAndComplete, promoteToAdmin, loginHappyPath } from './helpers/auth-flows';

describe('Auth guards presence (e2e)', () => {
  let ctx: TestContext;

  beforeAll(async () => {
    ctx = await createTestApp();
  });

  afterAll(async () => {
    await ctx.close();
  });

  beforeEach(async () => {
    await ctx.resetState();
  });

  // ── JwtAuthGuard: endpoints that require any logged-in user ───────────────
  describe.each([
    // users — self
    ['GET',    '/api/v1/users/me'],
    ['PATCH',  '/api/v1/users/me'],
    ['POST',   '/api/v1/users/me/2fa/enable'],
    ['POST',   '/api/v1/users/me/2fa/verify'],
    ['DELETE', '/api/v1/users/me/2fa'],
    ['POST',   '/api/v1/users/me/email'],
    ['POST',   '/api/v1/users/me/email/confirm'],
    // sessions
    ['GET',    '/api/v1/users/me/sessions'],
    ['DELETE', '/api/v1/users/me/sessions/all'],
    ['DELETE', '/api/v1/users/me/sessions/some-id'],
    // auth
    ['POST',   '/api/v1/auth/logout'],
    // admin — also guarded by RolesGuard but that runs after JwtAuthGuard
    ['GET',    '/api/v1/users'],
    ['GET',    '/api/v1/users/some-id'],
    ['POST',   '/api/v1/users'],
    ['PATCH',  '/api/v1/users/some-id'],
    ['DELETE', '/api/v1/users/some-id'],
  ])('%s %s rejects missing token with 401', (method, path) => {
    it('responds 401', async () => {
      const req = (ctx.http as any)[method.toLowerCase()](path);
      await req.expect(401);
    });
  });

  it('rejects malformed Authorization header with 401', async () => {
    await ctx.http
      .get('/api/v1/users/me')
      .set('Authorization', 'Bearer not-a-real-token')
      .expect(401);
  });

  // ── RolesGuard: admin-only endpoints reject regular users with 403 ────────
  describe('RolesGuard blocks non-admin', () => {
    async function userToken(): Promise<string> {
      const { accessToken } = await registerAndComplete(
        ctx,
        'plain@example.com',
        'plainuser',
        'Password123!',
      );
      return accessToken;
    }

    it.each([
      ['GET',    '/api/v1/users'],
      ['POST',   '/api/v1/users'],
      ['PATCH',  '/api/v1/users/some-id'],
      ['DELETE', '/api/v1/users/some-id'],
    ])('%s %s → 403 for regular user', async (method, path) => {
      const token = await userToken();
      const req = (ctx.http as any)[method.toLowerCase()](path);
      await req.set('Authorization', `Bearer ${token}`).expect(403);
    });

    it('admin passes the RolesGuard (200 on GET /users)', async () => {
      await registerAndComplete(ctx, 'admin@example.com', 'adminuser', 'Password123!');
      await promoteToAdmin(ctx, 'admin@example.com');
      const { accessToken } = await loginHappyPath(ctx, 'admin@example.com', 'Password123!');

      await ctx.http
        .get('/api/v1/users')
        .set('Authorization', `Bearer ${accessToken}`)
        .expect(200);
    });
  });
});
