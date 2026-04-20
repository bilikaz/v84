// [v84-2-1-3][back-nestjs:entities]
import 'dotenv/config';
import { readdirSync } from 'fs';
import { join, basename } from 'path';
import { DataSource } from 'typeorm';
import { AppDataSource } from './data-source';

interface Seeder {
  run(dataSource: DataSource): Promise<void>;
}

async function ensureSeedHistoryTable(dataSource: DataSource): Promise<void> {
  await dataSource.query(`
    CREATE TABLE IF NOT EXISTS seed_history (
      name VARCHAR(255) NOT NULL PRIMARY KEY,
      executed_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
    )
  `);
}

async function hasRun(dataSource: DataSource, name: string): Promise<boolean> {
  const rows = await dataSource.query(
    'SELECT 1 FROM seed_history WHERE name = ? LIMIT 1',
    [name],
  );
  return rows.length > 0;
}

async function markAsRun(dataSource: DataSource, name: string): Promise<void> {
  await dataSource.query('INSERT INTO seed_history (name) VALUES (?)', [name]);
}

async function discoverSeeders(): Promise<{ name: string; seeder: Seeder }[]> {
  const seedsDir = join(__dirname, 'seeds');
  const files = readdirSync(seedsDir)
    .filter((f) => f.endsWith('.seeder.ts') || f.endsWith('.seeder.js'))
    .sort();

  const seeders: { name: string; seeder: Seeder }[] = [];

  for (const file of files) {
    const mod = await import(join(seedsDir, file));
    const SeederClass = Object.values(mod).find(
      (v): v is new () => Seeder => typeof v === 'function' && v.prototype?.run,
    );

    if (SeederClass) {
      const name = basename(file).replace(/\.seeder\.(ts|js)$/, '');
      seeders.push({ name, seeder: new SeederClass() });
    }
  }

  return seeders;
}

// Reusable entry point. `force: true` runs every seeder regardless of whether
// `seed_history` says it's already executed — the test helper calls this after
// wiping rows so the initial seed state comes back between tests.
// `silent: true` suppresses the emoji/progress output tests don't care about.
export async function runAllSeeders(
  dataSource: DataSource,
  options: { force?: boolean; silent?: boolean } = {},
): Promise<void> {
  const { force = false, silent = false } = options;
  await ensureSeedHistoryTable(dataSource);
  const seeders = await discoverSeeders();

  if (seeders.length === 0 && !silent) {
    console.log('No seeders found.');
  }

  for (const { name, seeder } of seeders) {
    if (!force && (await hasRun(dataSource, name))) {
      if (!silent) console.log(`⏭  ${name} — already executed, skipping.`);
      continue;
    }

    if (!silent) console.log(`▶  ${name} — running...`);
    await seeder.run(dataSource);
    // markAsRun is idempotent: only insert if no row yet (so force-reruns
    // don't collide with the existing PK in seed_history).
    if (!(await hasRun(dataSource, name))) {
      await markAsRun(dataSource, name);
    }
    if (!silent) console.log(`✔  ${name} — done.`);
  }
}

async function main() {
  await AppDataSource.initialize();
  await runAllSeeders(AppDataSource);
  await AppDataSource.destroy();
  console.log('\nSeeding complete.');
}

// Only execute main() when this file is invoked directly as `pnpm seed`.
// Tests import `runAllSeeders` from here; we don't want side-effects then.
if (require.main === module) {
  main().catch((err) => {
    console.error('Seeding failed:', err);
    process.exit(1);
  });
}
