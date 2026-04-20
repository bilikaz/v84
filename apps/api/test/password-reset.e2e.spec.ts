// Integration coverage for the forgot / reset-password flow.
//
// Important behaviors pinned here:
//   - forgot-password always returns 204 (no email enumeration)
//   - reset consumes the token exactly once
//   - reset revokes every active session — the security reason we do it
//   - weak passwords rejected by the DTO validator

import { copy } from '../src/templates/emails';
import { createTestApp, type TestContext } from './helpers/app';
import {
  registerAndComplete,
  loginHappyPath,
} from './helpers/auth-flows';

// [v84-3-2-1][ops:testing]
describe('Password reset (e2e)', () => {
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

  describe('forgot-password', () => {
    it('sends a reset email and stores a token in Redis for a known user', async () => {
      await registerAndComplete(ctx, 'forgot@example.com', 'forgotuser', 'Password123!');

      await ctx.http
        .post('/api/v1/auth/forgot-password')
        .send({ email: 'forgot@example.com' })
        .expect(204);

      await ctx.mail.waitFor(
        (m) => m.to === 'forgot@example.com' && m.subject === copy.emails.passwordReset.subject,
      );

      const keys = await ctx.redis.keys('reset:*');
      expect(keys).toHaveLength(1);
    });

    it('returns 204 even for an unknown email (no enumeration)', async () => {
      await ctx.http
        .post('/api/v1/auth/forgot-password')
        .send({ email: 'ghost@example.com' })
        .expect(204);

      // And no reset token is created.
      const keys = await ctx.redis.keys('reset:*');
      expect(keys).toHaveLength(0);
    });
  });

  describe('reset-password', () => {
    it('changes the password with a valid token', async () => {
      await registerAndComplete(ctx, 'reset@example.com', 'resetuser', 'OldPassword9!');
      const token = await requestReset(ctx, 'reset@example.com');

      await ctx.http
        .post('/api/v1/auth/reset-password')
        .send({ token, password: 'NewPassword9!' })
        .expect(204);

      // Old password no longer works.
      await ctx.http
        .post('/api/v1/auth/login')
        .send({ email: 'reset@example.com', password: 'OldPassword9!' })
        .expect(401);

      // New password works.
      await loginHappyPath(ctx, 'reset@example.com', 'NewPassword9!');
    });

    it('revokes every existing session for the user', async () => {
      await registerAndComplete(ctx, 'revoke@example.com', 'revokeuser', 'OldPassword9!');
      // Open two more sessions.
      await loginHappyPath(ctx, 'revoke@example.com', 'OldPassword9!');
      await loginHappyPath(ctx, 'revoke@example.com', 'OldPassword9!');
      expect((await ctx.redis.keys('refresh:*')).length).toBe(3);

      const token = await requestReset(ctx, 'revoke@example.com');
      await ctx.http
        .post('/api/v1/auth/reset-password')
        .send({ token, password: 'NewPassword9!' })
        .expect(204);

      // All refresh tokens gone.
      expect((await ctx.redis.keys('refresh:*')).length).toBe(0);
      // And the session rows.
      const rows = await ctx.dataSource.query(
        `SELECT COUNT(*) as c FROM sessions WHERE user_id = (SELECT id FROM users WHERE email = ?)`,
        ['revoke@example.com'],
      );
      expect(Number(rows[0].c)).toBe(0);
    });

    it('rejects a reused token', async () => {
      await registerAndComplete(ctx, 'reuse@example.com', 'reuseuser', 'OldPassword9!');
      const token = await requestReset(ctx, 'reuse@example.com');

      await ctx.http
        .post('/api/v1/auth/reset-password')
        .send({ token, password: 'NewPassword9!' })
        .expect(204);

      // Same token a second time is invalid.
      await ctx.http
        .post('/api/v1/auth/reset-password')
        .send({ token, password: 'Another9Pass!' })
        .expect(400);
    });

    it('rejects an unknown token', async () => {
      await ctx.http
        .post('/api/v1/auth/reset-password')
        .send({ token: 'nonexistent', password: 'Password9!' })
        .expect(400);
    });

    it('rejects a weak password', async () => {
      await registerAndComplete(ctx, 'weak@example.com', 'weakuser', 'OldPassword9!');
      const token = await requestReset(ctx, 'weak@example.com');

      // Too short + no symbol.
      await ctx.http
        .post('/api/v1/auth/reset-password')
        .send({ token, password: 'short' })
        .expect(400);
    });
  });
});

// Drives forgot-password and returns the raw token stored in Redis so the test
// can call reset-password directly.
async function requestReset(ctx: TestContext, email: string): Promise<string> {
  await ctx.http.post('/api/v1/auth/forgot-password').send({ email }).expect(204);
  const keys = await ctx.redis.keys('reset:*');
  if (keys.length !== 1) {
    throw new Error(`expected exactly one reset:* key, got ${keys.length}`);
  }
  return keys[0].replace(/^reset:/, '');
}
