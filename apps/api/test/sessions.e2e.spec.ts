// Integration coverage for the /users/me/sessions surface.
//
// Focus areas:
//   - the projection doesn't leak refreshTokenHash (regression pin)
//   - current-session detection via the sessionId JWT claim
//   - revoke rules: other sessions yes, current session 403, revoke-all keeps current

import { createTestApp, type TestContext } from './helpers/app';
import {
  registerAndComplete,
  loginHappyPath,
  decodeJwtPayload,
} from './helpers/auth-flows';

// [v84-4-3-1][ops:testing]
describe('Sessions (e2e)', () => {
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

  describe('GET /users/me/sessions', () => {
    it('returns a single session right after register', async () => {
      const { accessToken } = await registerAndComplete(
        ctx,
        'single@example.com',
        'singleuser',
        'Password123!',
      );

      const res = await ctx.http
        .get('/api/v1/users/me/sessions')
        .set('authorization', `Bearer ${accessToken}`)
        .expect(200);

      expect(res.body).toHaveLength(1);
      expect(res.body[0]).toMatchObject({
        id: expect.any(String),
        current: true,
        lastSeenAt: expect.any(String),
        createdAt: expect.any(String),
      });
    });

    it('never exposes refreshTokenHash or any non-DTO fields', async () => {
      const { accessToken } = await registerAndComplete(
        ctx,
        'leak@example.com',
        'leakuser',
        'Password123!',
      );

      const res = await ctx.http
        .get('/api/v1/users/me/sessions')
        .set('authorization', `Bearer ${accessToken}`)
        .expect(200);

      const session = res.body[0];
      expect(Object.keys(session).sort()).toEqual(
        [
          'id',
          'deviceName',
          'deviceOs',
          'ipAddress',
          'lastSeenAt',
          'createdAt',
          'current',
        ].sort(),
      );
    });

    it('marks only the calling session as current when multiple exist', async () => {
      await registerAndComplete(ctx, 'multi@example.com', 'multiuser', 'Password123!');

      // Log in a second time to open another session.
      const second = await loginHappyPath(ctx, 'multi@example.com', 'Password123!');

      const res = await ctx.http
        .get('/api/v1/users/me/sessions')
        .set('authorization', `Bearer ${second.accessToken}`)
        .expect(200);

      expect(res.body).toHaveLength(2);
      const currentCount = res.body.filter((s: { current: boolean }) => s.current).length;
      expect(currentCount).toBe(1);
      const currentId = decodeJwtPayload(second.accessToken).sessionId;
      expect(res.body.find((s: { current: boolean }) => s.current).id).toBe(currentId);
    });

    it('rejects requests without a bearer token', async () => {
      await ctx.http.get('/api/v1/users/me/sessions').expect(401);
    });
  });

  describe('DELETE /users/me/sessions/:id', () => {
    it('revokes another session and removes it from the list', async () => {
      const first = await registerAndComplete(
        ctx,
        'revoke@example.com',
        'revokeuser',
        'Password123!',
      );
      const second = await loginHappyPath(ctx, 'revoke@example.com', 'Password123!');

      // Use `second` to kill `first`.
      const firstSessionId = decodeJwtPayload(first.accessToken).sessionId as string;
      await ctx.http
        .delete(`/api/v1/users/me/sessions/${firstSessionId}`)
        .set('authorization', `Bearer ${second.accessToken}`)
        .expect(204);

      // The refresh key in Redis should be gone.
      const refreshKey = await ctx.redis.get(`refresh:${firstSessionId}`);
      expect(refreshKey).toBeNull();

      // And the session row.
      const remaining = await ctx.http
        .get('/api/v1/users/me/sessions')
        .set('authorization', `Bearer ${second.accessToken}`)
        .expect(200);
      expect(remaining.body).toHaveLength(1);
      expect(remaining.body[0].id).not.toBe(firstSessionId);
    });

    it('returns 403 when revoking the calling session', async () => {
      const { accessToken } = await registerAndComplete(
        ctx,
        'self@example.com',
        'selfuser',
        'Password123!',
      );
      const sessionId = decodeJwtPayload(accessToken).sessionId as string;

      await ctx.http
        .delete(`/api/v1/users/me/sessions/${sessionId}`)
        .set('authorization', `Bearer ${accessToken}`)
        .expect(403);

      // Session still exists.
      const refreshKey = await ctx.redis.get(`refresh:${sessionId}`);
      expect(refreshKey).not.toBeNull();
    });

    it('returns 404 for a session owned by a different user', async () => {
      const alice = await registerAndComplete(
        ctx,
        'alice@example.com',
        'aliceuser',
        'Password123!',
      );
      const bob = await registerAndComplete(
        ctx,
        'bob@example.com',
        'bobuser',
        'Password123!',
      );

      const bobSessionId = decodeJwtPayload(bob.accessToken).sessionId as string;

      // Alice tries to revoke Bob's session.
      await ctx.http
        .delete(`/api/v1/users/me/sessions/${bobSessionId}`)
        .set('authorization', `Bearer ${alice.accessToken}`)
        .expect(404);

      // Bob's session still works.
      const stillThere = await ctx.redis.get(`refresh:${bobSessionId}`);
      expect(stillThere).not.toBeNull();
    });
  });

  describe('DELETE /users/me/sessions/all', () => {
    it('revokes every other session but keeps the calling one', async () => {
      await registerAndComplete(ctx, 'all@example.com', 'alluser', 'Password123!');
      await loginHappyPath(ctx, 'all@example.com', 'Password123!');
      await loginHappyPath(ctx, 'all@example.com', 'Password123!');
      const third = await loginHappyPath(ctx, 'all@example.com', 'Password123!');

      // Four sessions total (one from register, three from login).
      const before = await ctx.http
        .get('/api/v1/users/me/sessions')
        .set('authorization', `Bearer ${third.accessToken}`)
        .expect(200);
      expect(before.body).toHaveLength(4);

      await ctx.http
        .delete('/api/v1/users/me/sessions/all')
        .set('authorization', `Bearer ${third.accessToken}`)
        .expect(204);

      const after = await ctx.http
        .get('/api/v1/users/me/sessions')
        .set('authorization', `Bearer ${third.accessToken}`)
        .expect(200);
      expect(after.body).toHaveLength(1);
      expect(after.body[0].current).toBe(true);

      // Only the current session's refresh key remains.
      const refreshKeys = await ctx.redis.keys('refresh:*');
      expect(refreshKeys).toHaveLength(1);
    });
  });
});

