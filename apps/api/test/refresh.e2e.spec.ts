// [v84-2-1-2][ops:testing]
// Integration coverage for POST /auth/refresh.
//
// The refresh endpoint is how the BFF transparently rotates access tokens.
// If it breaks, every authenticated request starts failing 15 seconds before
// the access token expires. If it doesn't properly invalidate old refresh
// tokens, session revocation becomes meaningless.

import { createTestApp, type TestContext } from './helpers/app';
import { registerAndComplete, decodeJwtPayload } from './helpers/auth-flows';

describe('Refresh (e2e)', () => {
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

  it('issues a fresh token pair from a valid refresh token', async () => {
    const original = await registerAndComplete(
      ctx,
      'refresh@example.com',
      'refreshuser',
      'Password123!',
    );

    const res = await ctx.http
      .post('/api/v1/auth/refresh')
      .send({ refreshToken: original.refreshToken })
      .expect(200);

    expect(res.body).toEqual({
      accessToken: expect.any(String),
      refreshToken: expect.any(String),
      expiresIn: expect.any(Number),
      tokenType: 'Bearer',
    });

    // The new access token is different from the original.
    expect(res.body.accessToken).not.toBe(original.accessToken);

    // The new access token is usable.
    await ctx.http
      .get('/api/v1/users/me')
      .set('authorization', `Bearer ${res.body.accessToken}`)
      .expect(200);
  });

  it('creates a new session row on refresh', async () => {
    const original = await registerAndComplete(
      ctx,
      'newsession@example.com',
      'newsessionuser',
      'Password123!',
    );

    const res = await ctx.http
      .post('/api/v1/auth/refresh')
      .send({ refreshToken: original.refreshToken })
      .expect(200);

    // The refreshed access token carries a different sessionId.
    const originalPayload = decodeJwtPayload(original.accessToken);
    const refreshedPayload = decodeJwtPayload(res.body.accessToken);
    expect(refreshedPayload.sessionId).not.toBe(originalPayload.sessionId);
  });

  it('rejects an invalid refresh token', async () => {
    await ctx.http
      .post('/api/v1/auth/refresh')
      .send({ refreshToken: 'garbage' })
      .expect(401);
  });

  it('rejects a refresh token after the session is revoked via logout', async () => {
    const tokens = await registerAndComplete(
      ctx,
      'revoked@example.com',
      'revokeduser',
      'Password123!',
    );

    // Logout revokes the session.
    await ctx.http
      .post('/api/v1/auth/logout')
      .set('authorization', `Bearer ${tokens.accessToken}`)
      .expect(204);

    // Refresh with the old token fails.
    await ctx.http
      .post('/api/v1/auth/refresh')
      .send({ refreshToken: tokens.refreshToken })
      .expect(401);
  });

  it('rejects a request with no body', async () => {
    await ctx.http
      .post('/api/v1/auth/refresh')
      .send({})
      .expect(401);
  });
});
