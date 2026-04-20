// [v84-2-4-1][ops:testing]
// Integration coverage for the admin-only user CRUD surface.
//
// Pins:
//   - RolesGuard actually enforces admin on every listed endpoint
//   - each response body runs through `toUserResponse` — no passwordHash leaks
//   - admin can promote a role, create, update, delete
//   - cross-user isolation: an ordinary user cannot touch another user's row

import { createTestApp, type TestContext } from './helpers/app';
import { registerAndComplete, promoteToAdmin, loginHappyPath } from './helpers/auth-flows';

describe('Users admin (e2e)', () => {
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

  // Creates an admin account via register + direct DB promotion, then logs the
  // admin back in so the fresh access token carries `role: admin`.
  async function setupAdmin(): Promise<{ admin: { accessToken: string } }> {
    await registerAndComplete(ctx, 'admin@example.com', 'adminuser', 'Password123!');
    await promoteToAdmin(ctx, 'admin@example.com');
    const admin = await loginHappyPath(ctx, 'admin@example.com', 'Password123!');
    return { admin };
  }

  describe('role guard', () => {
    it('rejects non-admin with 403 on GET /users', async () => {
      const { accessToken } = await registerAndComplete(
        ctx,
        'plain@example.com',
        'plainuser',
        'Password123!',
      );
      await ctx.http
        .get('/api/v1/users')
        .set('authorization', `Bearer ${accessToken}`)
        .expect(403);
    });

    it('rejects non-admin with 403 on POST /users', async () => {
      const { accessToken } = await registerAndComplete(
        ctx,
        'plain2@example.com',
        'plainuser2',
        'Password123!',
      );
      await ctx.http
        .post('/api/v1/users')
        .set('authorization', `Bearer ${accessToken}`)
        .send({
          username: 'newuser',
          email: 'new@example.com',
          password: 'Password123!',
        })
        .expect(403);
    });

    it('rejects non-admin with 403 on DELETE /users/:id', async () => {
      const { accessToken } = await registerAndComplete(
        ctx,
        'plain3@example.com',
        'plainuser3',
        'Password123!',
      );
      await ctx.http
        .delete('/api/v1/users/some-other-id')
        .set('authorization', `Bearer ${accessToken}`)
        .expect(403);
    });

    it('rejects unauthenticated requests with 401', async () => {
      await ctx.http.get('/api/v1/users').expect(401);
    });
  });

  describe('GET /users', () => {
    it('lists all users and projects each row via toUserResponse', async () => {
      const { admin } = await setupAdmin();
      await registerAndComplete(ctx, 'other@example.com', 'otheruser', 'Password123!');

      const res = await ctx.http
        .get('/api/v1/users')
        .set('authorization', `Bearer ${admin.accessToken}`)
        .expect(200);

      expect(Object.keys(res.body).sort()).toEqual(
        ['items', 'total', 'page', 'limit', 'pages'].sort(),
      );
      expect(Array.isArray(res.body.items)).toBe(true);
      // beforeEach re-runs every seeder, so admin@admin.localhost +
      // user@user.localhost are always present alongside the two users this
      // test arranges. Assert on the exact email set so the test stays honest
      // when another seeder is added — the next drift will be a missing email,
      // not an off-by-N count.
      const emails = res.body.items.map((u: { email: string }) => u.email).sort();
      expect(emails).toEqual([
        'admin@admin.localhost',
        'admin@example.com',
        'other@example.com',
        'user@user.localhost',
      ]);
      expect(res.body.total).toBe(emails.length);
      expect(res.body.items.length).toBe(emails.length);
      for (const u of res.body.items) {
        expect(Object.keys(u).sort()).toEqual(
          ['id', 'username', 'email', 'role', 'twoFactorEnabled', 'createdAt'].sort(),
        );
      }
    });
  });

  describe('GET /users/:id', () => {
    it('returns a single user projected', async () => {
      const { admin } = await setupAdmin();
      await registerAndComplete(ctx, 'target@example.com', 'targetuser', 'Password123!');

      // Grab the target id from the list.
      const list = await ctx.http
        .get('/api/v1/users')
        .set('authorization', `Bearer ${admin.accessToken}`)
        .expect(200);
      const target = list.body.items.find(
        (u: { email: string }) => u.email === 'target@example.com',
      );

      const res = await ctx.http
        .get(`/api/v1/users/${target.id}`)
        .set('authorization', `Bearer ${admin.accessToken}`)
        .expect(200);

      expect(res.body).toEqual({
        id: target.id,
        username: 'targetuser',
        email: 'target@example.com',
        role: 'user',
        twoFactorEnabled: false,
        createdAt: expect.any(String),
      });
    });

    it('returns 404 for an unknown id', async () => {
      const { admin } = await setupAdmin();
      await ctx.http
        .get('/api/v1/users/00000000-0000-0000-0000-000000000000')
        .set('authorization', `Bearer ${admin.accessToken}`)
        .expect(404);
    });
  });

  describe('POST /users', () => {
    it('creates a user with the requested role', async () => {
      const { admin } = await setupAdmin();

      const res = await ctx.http
        .post('/api/v1/users')
        .set('authorization', `Bearer ${admin.accessToken}`)
        .send({
          username: 'freshadmin',
          email: 'fresh@example.com',
          password: 'Password123!',
          role: 'admin',
        })
        .expect(201);

      expect(res.body).toEqual({
        id: expect.any(String),
        username: 'freshadmin',
        email: 'fresh@example.com',
        role: 'admin',
        twoFactorEnabled: false,
        createdAt: expect.any(String),
      });
    });

    it('rejects duplicate email with 409', async () => {
      const { admin } = await setupAdmin();
      await ctx.http
        .post('/api/v1/users')
        .set('authorization', `Bearer ${admin.accessToken}`)
        .send({
          username: 'dupe',
          email: 'admin@example.com', // already used by setupAdmin
          password: 'Password123!',
        })
        .expect(409);
    });
  });

  describe('PATCH /users/:id', () => {
    it('updates role via admin endpoint', async () => {
      const { admin } = await setupAdmin();
      await registerAndComplete(ctx, 'promote@example.com', 'promoteuser', 'Password123!');
      const list = await ctx.http
        .get('/api/v1/users')
        .set('authorization', `Bearer ${admin.accessToken}`);
      const target = list.body.items.find(
        (u: { email: string }) => u.email === 'promote@example.com',
      );

      const res = await ctx.http
        .patch(`/api/v1/users/${target.id}`)
        .set('authorization', `Bearer ${admin.accessToken}`)
        .send({ role: 'admin' })
        .expect(200);

      expect(res.body).toEqual({
        id: target.id,
        username: 'promoteuser',
        email: 'promote@example.com',
        role: 'admin',
        twoFactorEnabled: false,
        createdAt: expect.any(String),
      });
    });
  });

  describe('DELETE /users/:id', () => {
    it('removes the user row', async () => {
      const { admin } = await setupAdmin();
      await registerAndComplete(ctx, 'gone@example.com', 'goneuser', 'Password123!');
      const list = await ctx.http
        .get('/api/v1/users')
        .set('authorization', `Bearer ${admin.accessToken}`);
      const target = list.body.items.find(
        (u: { email: string }) => u.email === 'gone@example.com',
      );

      await ctx.http
        .delete(`/api/v1/users/${target.id}`)
        .set('authorization', `Bearer ${admin.accessToken}`)
        .expect(204);

      await ctx.http
        .get(`/api/v1/users/${target.id}`)
        .set('authorization', `Bearer ${admin.accessToken}`)
        .expect(404);
    });
  });
});
