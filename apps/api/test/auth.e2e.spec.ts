// [v84-2-2-1][ops:testing]
// Integration coverage for the authentication surface.
//
// Runs against the real dev MariaDB (`local_test` schema), real Redis, and real
// Mailpit — no mocks. Each `it` gets a clean slate via `resetState()`.

import { copy } from '../src/templates/emails';
import { createTestApp, type TestContext } from './helpers/app';
import {
  pullVerifyToken,
  registerAndComplete,
  decodeJwtPayload,
} from './helpers/auth-flows';

describe('Auth (e2e)', () => {
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

  // ── Registration ──────────────────────────────────────────────────────────

  describe('register flow', () => {
    it('step 1 sends a verification email and stores a token in Redis', async () => {
      await ctx.http
        .post('/api/v1/auth/register')
        .send({ email: 'newbie@example.com' })
        .expect(204);

      await ctx.mail.waitFor(
        (m) => m.to === 'newbie@example.com' && m.subject === copy.emails.verify.subject,
      );

      const keys = await ctx.redis.keys('verify:*');
      expect(keys).toHaveLength(1);
      const storedEmail = await ctx.redis.get(keys[0]);
      expect(storedEmail).toBe('newbie@example.com');
    });

    it('step 1 rejects duplicate emails', async () => {
      // Pre-create a user so the duplicate check hits.
      await registerAndComplete(ctx, 'taken@example.com', 'takenuser', 'Password123!');

      await ctx.http
        .post('/api/v1/auth/register')
        .send({ email: 'taken@example.com' })
        .expect(409);
    });

    it('check endpoint returns the pending email for a valid token', async () => {
      await ctx.http
        .post('/api/v1/auth/register')
        .send({ email: 'checker@example.com' })
        .expect(204);
      const token = await pullVerifyToken(ctx);

      const res = await ctx.http
        .get(`/api/v1/auth/register/check`)
        .query({ token })
        .expect(200);

      expect(res.body).toEqual({ email: 'checker@example.com' });
    });

    it('check endpoint rejects an unknown token', async () => {
      await ctx.http
        .get('/api/v1/auth/register/check')
        .query({ token: 'nonexistent-token' })
        .expect(400);
    });

    it('step 2 creates the user, issues tokens, and sends a welcome email', async () => {
      await ctx.http
        .post('/api/v1/auth/register')
        .send({ email: 'welcome@example.com' })
        .expect(204);
      const token = await pullVerifyToken(ctx);

      const res = await ctx.http
        .post('/api/v1/auth/register/complete')
        .send({ token, username: 'welcomeuser', password: 'Password123!' })
        .expect(201);

      expect(res.body).toEqual({
        accessToken: expect.any(String),
        refreshToken: expect.any(String),
        expiresIn: expect.any(Number),
        tokenType: 'Bearer',
      });

      // Verification token is consumed.
      expect(await ctx.redis.keys('verify:*')).toHaveLength(0);

      // Welcome email landed.
      await ctx.mail.waitFor(
        (m) => m.to === 'welcome@example.com' && m.subject === copy.emails.welcome.subject,
      );
    });

    it('step 2 rejects an unknown or already-used token', async () => {
      await ctx.http
        .post('/api/v1/auth/register/complete')
        .send({ token: 'stale', username: 'x', password: 'Password123!' })
        .expect(400);
    });
  });

  // ── Login ─────────────────────────────────────────────────────────────────

  describe('login', () => {
    beforeEach(async () => {
      await registerAndComplete(ctx, 'loginuser@example.com', 'loginuser', 'Password123!');
    });

    it('returns tokens on happy path', async () => {
      const res = await ctx.http
        .post('/api/v1/auth/login')
        .send({ email: 'loginuser@example.com', password: 'Password123!' })
        .expect(200);

      expect(res.body).toEqual({
        accessToken: expect.any(String),
        refreshToken: expect.any(String),
        expiresIn: expect.any(Number),
        tokenType: 'Bearer',
      });
    });

    it('rejects wrong password', async () => {
      await ctx.http
        .post('/api/v1/auth/login')
        .send({ email: 'loginuser@example.com', password: 'wrong' })
        .expect(401);
    });

    it('rejects unknown email', async () => {
      await ctx.http
        .post('/api/v1/auth/login')
        .send({ email: 'ghost@example.com', password: 'whatever' })
        .expect(401);
    });

    it('the access token embeds a sessionId claim', async () => {
      const res = await ctx.http
        .post('/api/v1/auth/login')
        .send({ email: 'loginuser@example.com', password: 'Password123!' })
        .expect(200);

      const payload = decodeJwtPayload(res.body.accessToken);
      expect(payload).toEqual({
        sub: expect.any(String),
        email: 'loginuser@example.com',
        role: expect.any(String),
        sessionId: expect.any(String),
        iat: expect.any(Number),
        exp: expect.any(Number),
      });
    });
  });

  // ── /users/me projection (regression test for the passwordHash leak) ──────

  describe('/users/me', () => {
    it('never exposes passwordHash or twoFactorSecret', async () => {
      const tokens = await registerAndComplete(
        ctx,
        'projection@example.com',
        'projectionuser',
        'Password123!',
      );

      const res = await ctx.http
        .get('/api/v1/users/me')
        .set('authorization', `Bearer ${tokens.accessToken}`)
        .expect(200);

      expect(res.body).toEqual({
        id: expect.any(String),
        username: 'projectionuser',
        email: 'projection@example.com',
        role: 'user',
        twoFactorEnabled: false,
        createdAt: expect.any(String),
      });
    });

    it('rejects requests without a bearer token', async () => {
      await ctx.http.get('/api/v1/users/me').expect(401);
    });
  });

  // ── Logout ────────────────────────────────────────────────────────────────

  describe('logout', () => {
    it('invalidates the refresh token for the session', async () => {
      const tokens = await registerAndComplete(
        ctx,
        'logout@example.com',
        'logoutuser',
        'Password123!',
      );

      const beforeKeys = await ctx.redis.keys('refresh:*');
      expect(beforeKeys).toHaveLength(1);

      await ctx.http
        .post('/api/v1/auth/logout')
        .set('authorization', `Bearer ${tokens.accessToken}`)
        .expect(204);

      const afterKeys = await ctx.redis.keys('refresh:*');
      expect(afterKeys).toHaveLength(0);
    });
  });
});

