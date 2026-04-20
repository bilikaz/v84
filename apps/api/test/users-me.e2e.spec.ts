// Integration coverage for PATCH /users/me (self-service profile updates).
//
// This is the only way a non-admin user can change their own password or
// username. The security contract: you must supply your current password to
// change either one. If that check is bypassed or inverted, any XSS or
// session-steal becomes a full account takeover.

import { createTestApp, type TestContext } from './helpers/app';
import { registerAndComplete, loginHappyPath } from './helpers/auth-flows';

// [v84-2-4-1][ops:testing]
describe('Users /me self-update (e2e)', () => {
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

  describe('password change', () => {
    it('changes the password when currentPassword is correct', async () => {
      const { accessToken } = await registerAndComplete(
        ctx,
        'pwchange@example.com',
        'pwchangeuser',
        'Password123!',
      );

      await ctx.http
        .patch('/api/v1/users/me')
        .set('authorization', `Bearer ${accessToken}`)
        .send({ currentPassword: 'Password123!', password: 'NewPassword456!' })
        .expect(200);

      // Old password no longer works.
      await ctx.http
        .post('/api/v1/auth/login')
        .send({ email: 'pwchange@example.com', password: 'Password123!' })
        .expect(401);

      // New password works.
      await loginHappyPath(ctx, 'pwchange@example.com', 'NewPassword456!');
    });

    it('rejects password change when currentPassword is wrong', async () => {
      const { accessToken } = await registerAndComplete(
        ctx,
        'wrongcurrent@example.com',
        'wrongcurrentuser',
        'Password123!',
      );

      await ctx.http
        .patch('/api/v1/users/me')
        .set('authorization', `Bearer ${accessToken}`)
        .send({ currentPassword: 'WrongPassword!', password: 'NewPassword456!' })
        .expect(400);

      // Original password still works — nothing changed.
      await loginHappyPath(ctx, 'wrongcurrent@example.com', 'Password123!');
    });

    it('rejects password change when currentPassword is missing', async () => {
      const { accessToken } = await registerAndComplete(
        ctx,
        'nocurrent@example.com',
        'nocurrentuser',
        'Password123!',
      );

      await ctx.http
        .patch('/api/v1/users/me')
        .set('authorization', `Bearer ${accessToken}`)
        .send({ password: 'NewPassword456!' })
        .expect(400);
    });
  });

  describe('username change', () => {
    it('updates the username when currentPassword is provided', async () => {
      const { accessToken } = await registerAndComplete(
        ctx,
        'rename@example.com',
        'oldname',
        'Password123!',
      );

      const res = await ctx.http
        .patch('/api/v1/users/me')
        .set('authorization', `Bearer ${accessToken}`)
        .send({ currentPassword: 'Password123!', username: 'newname' })
        .expect(200);

      expect(res.body).toEqual({
        id: expect.any(String),
        username: 'newname',
        email: 'rename@example.com',
        role: 'user',
        twoFactorEnabled: false,
        createdAt: expect.any(String),
      });
    });

    it('rejects a username that is already taken by another user', async () => {
      await registerAndComplete(ctx, 'first@example.com', 'taken', 'Password123!');
      const { accessToken } = await registerAndComplete(
        ctx,
        'second@example.com',
        'wannatake',
        'Password123!',
      );

      await ctx.http
        .patch('/api/v1/users/me')
        .set('authorization', `Bearer ${accessToken}`)
        .send({ currentPassword: 'Password123!', username: 'taken' })
        .expect(409);
    });
  });
});
