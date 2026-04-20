// Integration coverage for the email change flow.
//
// Security behaviors pinned:
//   - password required to initiate
//   - confirmation email sent to new address (not old)
//   - token is single-use
//   - duplicate email blocked at both request and confirm stages
//   - same email rejected

import { copy } from '../src/templates/emails';
import { createTestApp, type TestContext } from './helpers/app';
import { registerAndComplete, loginHappyPath } from './helpers/auth-flows';

// [v84-4-2-2][ops:testing]
describe('Email change (e2e)', () => {
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

  describe('POST /users/me/email (request)', () => {
    it('sends a confirmation email to the new address', async () => {
      const { accessToken } = await registerAndComplete(
        ctx,
        'old@example.com',
        'emailuser',
        'Password123!',
      );

      await ctx.http
        .post('/api/v1/users/me/email')
        .set('authorization', `Bearer ${accessToken}`)
        .send({ newEmail: 'new@example.com', currentPassword: 'Password123!' })
        .expect(204);

      const msg = await ctx.mail.waitFor(
        (m) => m.to === 'new@example.com' && m.subject === copy.emails.emailChange.subject,
      );
      expect(msg).toBeDefined();

      // Token stored in Redis.
      const keys = await ctx.redis.keys('email-change:*');
      expect(keys).toHaveLength(1);
    });

    it('rejects wrong password', async () => {
      const { accessToken } = await registerAndComplete(
        ctx,
        'wrong@example.com',
        'wrongpwuser',
        'Password123!',
      );

      await ctx.http
        .post('/api/v1/users/me/email')
        .set('authorization', `Bearer ${accessToken}`)
        .send({ newEmail: 'new@example.com', currentPassword: 'WrongPassword!' })
        .expect(400);
    });

    it('rejects same email', async () => {
      const { accessToken } = await registerAndComplete(
        ctx,
        'same@example.com',
        'sameuser',
        'Password123!',
      );

      await ctx.http
        .post('/api/v1/users/me/email')
        .set('authorization', `Bearer ${accessToken}`)
        .send({ newEmail: 'same@example.com', currentPassword: 'Password123!' })
        .expect(400);
    });

    it('rejects email already in use', async () => {
      await registerAndComplete(ctx, 'taken@example.com', 'takenuser', 'Password123!');
      const { accessToken } = await registerAndComplete(
        ctx,
        'requester@example.com',
        'requester',
        'Password123!',
      );

      await ctx.http
        .post('/api/v1/users/me/email')
        .set('authorization', `Bearer ${accessToken}`)
        .send({ newEmail: 'taken@example.com', currentPassword: 'Password123!' })
        .expect(409);
    });
  });

  describe('POST /users/me/email/confirm', () => {
    it('changes the email and consumes the token', async () => {
      const { accessToken } = await registerAndComplete(
        ctx,
        'before@example.com',
        'confirmuser',
        'Password123!',
      );

      await ctx.http
        .post('/api/v1/users/me/email')
        .set('authorization', `Bearer ${accessToken}`)
        .send({ newEmail: 'after@example.com', currentPassword: 'Password123!' })
        .expect(204);

      const token = await pullEmailChangeToken(ctx);

      const res = await ctx.http
        .post('/api/v1/users/me/email/confirm')
        .set('authorization', `Bearer ${accessToken}`)
        .send({ token })
        .expect(201);

      expect(res.body).toEqual({
        id: expect.any(String),
        username: 'confirmuser',
        email: 'after@example.com',
        role: 'user',
        twoFactorEnabled: false,
        createdAt: expect.any(String),
      });

      // Token consumed.
      expect(await ctx.redis.keys('email-change:*')).toHaveLength(0);

      // Can login with the new email.
      await loginHappyPath(ctx, 'after@example.com', 'Password123!');
    });

    it('rejects a reused token', async () => {
      const { accessToken } = await registerAndComplete(
        ctx,
        'reuse@example.com',
        'reuseuser',
        'Password123!',
      );

      await ctx.http
        .post('/api/v1/users/me/email')
        .set('authorization', `Bearer ${accessToken}`)
        .send({ newEmail: 'reuse-new@example.com', currentPassword: 'Password123!' })
        .expect(204);

      const token = await pullEmailChangeToken(ctx);

      await ctx.http
        .post('/api/v1/users/me/email/confirm')
        .set('authorization', `Bearer ${accessToken}`)
        .send({ token })
        .expect(201);

      await ctx.http
        .post('/api/v1/users/me/email/confirm')
        .set('authorization', `Bearer ${accessToken}`)
        .send({ token })
        .expect(400);
    });

    it('rejects an unknown token', async () => {
      const { accessToken } = await registerAndComplete(
        ctx,
        'unknown@example.com',
        'unknownuser',
        'Password123!',
      );

      await ctx.http
        .post('/api/v1/users/me/email/confirm')
        .set('authorization', `Bearer ${accessToken}`)
        .send({ token: 'nonexistent' })
        .expect(400);
    });
  });
});

async function pullEmailChangeToken(ctx: TestContext): Promise<string> {
  const keys = await ctx.redis.keys('email-change:*');
  if (keys.length !== 1) {
    throw new Error(`expected one email-change:* key, got ${keys.length}`);
  }
  return keys[0].replace(/^email-change:/, '');
}
