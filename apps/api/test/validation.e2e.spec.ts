// Pins that the global ValidationPipe + forbidNonWhitelisted are actually wired.
//
// These don't test business logic — they test that the pipe exists on the app
// and that DTOs enforce their decorators. Without this, someone could
// accidentally remove the pipe from main.ts and every endpoint would silently
// accept garbage input.

import { createTestApp, type TestContext } from './helpers/app';
import { registerAndComplete } from './helpers/auth-flows';

// [v84-2-2-1][ops:testing]
describe('Validation (e2e)', () => {
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

  it('rejects register with an invalid email', async () => {
    const res = await ctx.http
      .post('/api/v1/auth/register')
      .send({ email: 'not-an-email' })
      .expect(400);

    expect(res.body.message).toEqual(expect.arrayContaining([
      expect.stringContaining('email'),
    ]));
  });

  it('rejects login with a totpCode that is not 6 chars', async () => {
    // Guards run before pipes in NestJS, so we need valid credentials for the
    // LocalAuthGuard to pass before ValidationPipe sees the DTO.
    await registerAndComplete(ctx, 'totp@example.com', 'totpuser', 'Password123!');

    await ctx.http
      .post('/api/v1/auth/login')
      .send({ email: 'totp@example.com', password: 'Password123!', totpCode: 'abc' })
      .expect(400);
  });

  it('rejects unexpected fields via forbidNonWhitelisted', async () => {
    const res = await ctx.http
      .post('/api/v1/auth/register')
      .send({ email: 'good@example.com', hackField: 'injected' })
      .expect(400);

    expect(res.body.message).toEqual(expect.arrayContaining([
      expect.stringContaining('hackField'),
    ]));
  });

  it('rejects register/complete with a short username', async () => {
    await ctx.http
      .post('/api/v1/auth/register/complete')
      .send({ token: 'x', username: 'ab', password: 'Password123!' })
      .expect(400);
  });

  it('rejects admin user creation with a short password', async () => {
    const { accessToken } = await registerAndComplete(
      ctx,
      'admin@example.com',
      'adminuser',
      'Password123!',
    );
    await ctx.dataSource.query(
      `UPDATE users SET role = 'admin' WHERE email = ?`,
      ['admin@example.com'],
    );
    // Re-login to get a token with admin role in JWT.
    const login = await ctx.http
      .post('/api/v1/auth/login')
      .send({ email: 'admin@example.com', password: 'Password123!' })
      .expect(200);

    await ctx.http
      .post('/api/v1/users')
      .set('authorization', `Bearer ${login.body.accessToken}`)
      .send({ username: 'newuser', email: 'new@example.com', password: 'short' })
      .expect(400);
  });
});
