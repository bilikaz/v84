// Integration coverage for the 2FA surface.
//
// Uses the real otpauth TOTP generator so every flow is exercised end to end —
// no mocking the authenticator, no pretending a code matched. The `window: 1`
// validator on the API side tolerates a ±30s skew, so `generateTotp()` from
// the helpers is a valid code from the test's perspective.

import { createTestApp, type TestContext } from './helpers/app';
import {
  registerAndComplete,
  loginHappyPath,
  generateTotp,
} from './helpers/auth-flows';

// [v84-4-1-1][ops:testing]
describe('2FA (e2e)', () => {
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

  describe('enable → verify → disable roundtrip', () => {
    it('enables 2FA, flips twoFactorEnabled, and rejects the same secret on re-enable', async () => {
      const { accessToken } = await registerAndComplete(
        ctx,
        '2fa@example.com',
        'twofauser',
        'Password123!',
      );

      // 1. enable → receive secret, twoFactorEnabled still false (not until verify)
      const enableRes = await ctx.http
        .post('/api/v1/users/me/2fa/enable')
        .set('authorization', `Bearer ${accessToken}`)
        .expect(201);
      expect(enableRes.body.secret).toMatch(/^[A-Z2-7]+$/); // base32
      const secret: string = enableRes.body.secret;

      const meBeforeVerify = await ctx.http
        .get('/api/v1/users/me')
        .set('authorization', `Bearer ${accessToken}`)
        .expect(200);
      expect(meBeforeVerify.body.twoFactorEnabled).toBe(false);

      // 2. verify with a valid code → twoFactorEnabled flips to true
      const code = generateTotp(secret);
      await ctx.http
        .post('/api/v1/users/me/2fa/verify')
        .set('authorization', `Bearer ${accessToken}`)
        .send({ code })
        .expect(204);

      const meAfter = await ctx.http
        .get('/api/v1/users/me')
        .set('authorization', `Bearer ${accessToken}`)
        .expect(200);
      expect(meAfter.body.twoFactorEnabled).toBe(true);

      // 3. re-enabling on an already-enabled account is rejected
      await ctx.http
        .post('/api/v1/users/me/2fa/enable')
        .set('authorization', `Bearer ${accessToken}`)
        .expect(400);

      // 4. disable with password + current code flips it back off
      await ctx.http
        .delete('/api/v1/users/me/2fa')
        .set('authorization', `Bearer ${accessToken}`)
        .send({ password: 'Password123!', code: generateTotp(secret) })
        .expect(204);

      const meFinal = await ctx.http
        .get('/api/v1/users/me')
        .set('authorization', `Bearer ${accessToken}`)
        .expect(200);
      expect(meFinal.body.twoFactorEnabled).toBe(false);
    });

    it('rejects verify with a wrong code', async () => {
      const { accessToken } = await registerAndComplete(
        ctx,
        'wrongcode@example.com',
        'wronguser',
        'Password123!',
      );

      await ctx.http
        .post('/api/v1/users/me/2fa/enable')
        .set('authorization', `Bearer ${accessToken}`)
        .expect(201);

      await ctx.http
        .post('/api/v1/users/me/2fa/verify')
        .set('authorization', `Bearer ${accessToken}`)
        .send({ code: '000000' })
        .expect(400);

      // twoFactorEnabled stays false
      const me = await ctx.http
        .get('/api/v1/users/me')
        .set('authorization', `Bearer ${accessToken}`)
        .expect(200);
      expect(me.body.twoFactorEnabled).toBe(false);
    });

    it('rejects disable with wrong password', async () => {
      const secret = await enableAndVerify(ctx, 'wrongpw@example.com', 'wrongpwuser');

      await ctx.http
        .delete('/api/v1/users/me/2fa')
        .set('authorization', `Bearer ${(await loginHappyPath(ctx, 'wrongpw@example.com', 'Password123!', generateTotp(secret))).accessToken}`)
        .send({ password: 'NotThePassword!', code: generateTotp(secret) })
        .expect(400);
    });

    it('rejects verify call without a prior enable', async () => {
      const { accessToken } = await registerAndComplete(
        ctx,
        'noenable@example.com',
        'noenableuser',
        'Password123!',
      );
      await ctx.http
        .post('/api/v1/users/me/2fa/verify')
        .set('authorization', `Bearer ${accessToken}`)
        .send({ code: '123456' })
        .expect(400);
    });
  });

  describe('login with 2FA enabled', () => {
    it('returns requiresTwoFactor when no code is supplied', async () => {
      await enableAndVerify(ctx, 'challenge@example.com', 'challengeuser');

      const res = await ctx.http
        .post('/api/v1/auth/login')
        .send({ email: 'challenge@example.com', password: 'Password123!' })
        .expect(200);

      expect(res.body).toEqual({ requiresTwoFactor: true });

      // No refresh key issued.
      expect(await ctx.redis.keys('refresh:*')).toHaveLength(1); // only from setup
    });

    it('returns tokens when a valid code is supplied', async () => {
      const secret = await enableAndVerify(ctx, 'tokens@example.com', 'tokensuser');

      const res = await ctx.http
        .post('/api/v1/auth/login')
        .send({
          email: 'tokens@example.com',
          password: 'Password123!',
          totpCode: generateTotp(secret),
        })
        .expect(200);

      expect(res.body).toEqual({
        accessToken: expect.any(String),
        refreshToken: expect.any(String),
        expiresIn: expect.any(Number),
        tokenType: 'Bearer',
      });
    });

    it('rejects login with a wrong TOTP code', async () => {
      await enableAndVerify(ctx, 'badcode@example.com', 'badcodeuser');

      await ctx.http
        .post('/api/v1/auth/login')
        .send({
          email: 'badcode@example.com',
          password: 'Password123!',
          totpCode: '000000',
        })
        .expect(401);
    });
  });
});

// Registers a user, enables 2FA, verifies it, and returns the shared secret so
// the caller can mint codes. Leaves exactly one refresh token in Redis (the
// register call) — logins done afterwards should account for that.
async function enableAndVerify(
  ctx: TestContext,
  email: string,
  username: string,
): Promise<string> {
  const { accessToken } = await registerAndComplete(
    ctx,
    email,
    username,
    'Password123!',
  );

  const enableRes = await ctx.http
    .post('/api/v1/users/me/2fa/enable')
    .set('authorization', `Bearer ${accessToken}`)
    .expect(201);
  const secret: string = enableRes.body.secret;

  await ctx.http
    .post('/api/v1/users/me/2fa/verify')
    .set('authorization', `Bearer ${accessToken}`)
    .send({ code: generateTotp(secret) })
    .expect(204);

  return secret;
}
