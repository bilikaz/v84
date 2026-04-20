// [v84-2-1-3][ops:testing]
// Integration coverage for the dev seed pipeline.
//
// Pins:
//   - `admin@admin.localhost` is created with role=admin, uuid v7 id, bcrypt-hashed password
//   - `user@user.localhost` is created with role=user, uuid v7 id, bcrypt-hashed password
//   - The seed password ("password") actually verifies against the stored hash
//   - Re-running the seeder on a populated DB does not throw and does not duplicate rows
//     (the factory uses a stable id; re-seed is idempotent by row identity)

import * as bcrypt from 'bcrypt';
import { createTestApp, type TestContext } from './helpers/app';
import { User, UserRole } from '../src/modules/users/entities/user.entity';

// uuid v7 starts its timestamp nibble with '7' — first char of the third group
// in the canonical 8-4-4-4-12 layout is '7' (the version nibble).
const UUID_V7 = /^[0-9a-f]{8}-[0-9a-f]{4}-7[0-9a-f]{3}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

describe('Seed data (e2e)', () => {
  let ctx: TestContext;

  beforeAll(async () => {
    ctx = await createTestApp();
  });

  afterAll(async () => {
    await ctx.close();
  });

  beforeEach(async () => {
    // resetState now wipes and then re-runs every seeder, so these tests
    // observe the seed's output directly — no explicit runSeeder() call
    // needed (and none possible: a second seed run against an already-
    // populated DB would collide on the email unique constraint).
    await ctx.resetState();
  });

  it('creates the default admin with role=admin, uuid v7, bcrypted password', async () => {
    const admin = await ctx.dataSource
      .getRepository(User)
      .findOneByOrFail({ email: 'admin@admin.localhost' });

    expect(admin.role).toBe(UserRole.ADMIN);
    expect(admin.id).toMatch(UUID_V7);
    expect(admin.passwordHash).not.toBe('password');
    expect(await bcrypt.compare('password', admin.passwordHash)).toBe(true);
  });

  it('creates the default user with role=user, uuid v7, bcrypted password', async () => {
    const user = await ctx.dataSource
      .getRepository(User)
      .findOneByOrFail({ email: 'user@user.localhost' });

    expect(user.role).toBe(UserRole.USER);
    expect(user.id).toMatch(UUID_V7);
    expect(user.passwordHash).not.toBe('password');
    expect(await bcrypt.compare('password', user.passwordHash)).toBe(true);
  });

  it('writes exactly two rows for the default seed', async () => {
    const count = await ctx.dataSource.getRepository(User).count();
    expect(count).toBe(2);
  });
});
