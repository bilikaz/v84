// Boots the real AppModule and returns a supertest handle plus lifecycle
// helpers. Uses the same ValidationPipe + global prefix as main.ts so the HTTP
// contract matches production.

import { INestApplication, ValidationPipe } from '@nestjs/common';
import { Test } from '@nestjs/testing';
import { DataSource } from 'typeorm';
import supertest from 'supertest';
import { ConfigService } from '@nestjs/config';
import { AppModule } from '../../src/app.module';
import { RedisService } from '../../src/database';
import { resetDatabaseAndSeed } from '../../src/database/test-reset';
import { installMailCapture, type MailCapture } from './mail-capture';

// [v84-1-3][ops:testing]
export interface TestContext {
  app: INestApplication;
  http: supertest.Agent;
  dataSource: DataSource;
  redis: RedisService;
  mail: MailCapture;
  close: () => Promise<void>;
  resetState: () => Promise<void>;
}

export async function createTestApp(): Promise<TestContext> {
  const moduleRef = await Test.createTestingModule({
    imports: [AppModule],
  }).compile();

  const app = moduleRef.createNestApplication({ logger: ['error', 'warn'] });
  const configService = app.get(ConfigService);
  app.setGlobalPrefix(configService.get<string>('app.prefix')!);
  app.useGlobalPipes(
    new ValidationPipe({
      whitelist: true,
      forbidNonWhitelisted: true,
      transform: true,
    }),
  );
  await app.init();

  const dataSource = app.get(DataSource);
  const redis = app.get(RedisService);
  const http = supertest(app.getHttpServer());
  const mail = installMailCapture(app);

  return {
    app,
    http,
    dataSource,
    redis,
    mail,
    close: async () => {
      const server = app.getHttpServer();
      await app.close();
      // Explicitly close the HTTP server to release sockets held by supertest.
      // Without this, jest prints the "detectOpenHandles" warning on exit.
      await new Promise<void>((resolve) => server.close(() => resolve()));
    },
    resetState: async () => {
      // Wipe every TypeORM-managed table, flush Redis, re-run every seeder.
      // Same helper the POST /test/reset endpoint uses, so API unit tests and
      // Playwright e2e converge on the identical "freshly seeded" baseline.
      await resetDatabaseAndSeed(dataSource, redis);
      mail.reset();
    },
  };
}

