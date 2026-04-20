// [v84-1-3][back-nestjs:api]
// Shared reset utilities for tests. Two flavours, both prefixed `reset*` so
// they sit next to each other in auto-complete / grep:
//
//   resetDatabase(dataSource)               — truncate every TypeORM-managed
//                                             table. Tables discovered via
//                                             dataSource.entityMetadatas so a
//                                             new @Entity() is wiped
//                                             automatically.
//
//   resetDatabaseAndSeed(dataSource, redis) — resetDatabase + flushdb + re-run
//                                             every seeder. Leaves the DB in
//                                             the freshly-seeded baseline.
//
// The default path every test takes is resetDatabaseAndSeed (via resetState
// in the Jest helper, or via POST /api/v1/test/reset for Playwright) so both
// suites consistently start with admin@admin.localhost + user@user.localhost
// present. Tests can assert on those accounts without arranging them first.
//
// resetDatabase is exported for the rare test that wants a strictly empty DB
// (e.g. verifying the health endpoint responds before any data exists). Most
// tests shouldn't need it.
//
// seed_history is a meta table managed outside TypeORM (raw SQL inside
// seed-runner.ts's ensureSeedHistoryTable), so it isn't in entityMetadatas.
// resetDatabase wipes it explicitly so "DB reset" really means fresh — without
// that, a subsequent runAllSeeders without force: true would see every seeder
// as "already executed" and silently skip it.
// TypeORM's migrations table is left alone — migrations are schema, not data.

import { DataSource } from 'typeorm';
import { RedisService } from './redis.service';
import { runAllSeeders } from './seed-runner';

export async function resetDatabase(dataSource: DataSource): Promise<void> {
  const tableNames = dataSource.entityMetadatas.map((m) => m.tableName);
  await dataSource.query('SET FOREIGN_KEY_CHECKS = 0');
  for (const name of tableNames) {
    await dataSource.query(`DELETE FROM \`${name}\``);
  }
  // seed_history is raw-SQL meta (not an @Entity), so entityMetadatas missed
  // it. Wipe it too — otherwise runAllSeeders without force:true would skip
  // every seeder, leaving "reset" silently empty.
  try {
    await dataSource.query('DELETE FROM seed_history');
  } catch {
    // Only exists after the first seed run; safe to ignore when absent.
  }
  await dataSource.query('SET FOREIGN_KEY_CHECKS = 1');
}

export async function resetDatabaseAndSeed(
  dataSource: DataSource,
  redis: RedisService,
): Promise<void> {
  await resetDatabase(dataSource);
  await redis.getClient().flushdb();
  await runAllSeeders(dataSource, { force: true, silent: true });
}
