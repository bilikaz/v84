// [v84-1-3][back-nestjs:api]
// Test-only controller — reachable only when NODE_ENV === 'test' (AppModule
// conditionally imports TestModule). Exposes a single endpoint that e2e tests
// hit in their beforeEach to return the stack to the freshly-seeded baseline.
//
// Not for dev. Not for prod. If this shows up in any non-test environment,
// something's wrong with the import guard in AppModule.

import { ApiExcludeController } from '@nestjs/swagger';
import { Controller, HttpCode, HttpStatus, Post } from '@nestjs/common';
import { DataSource } from 'typeorm';
import { RedisService } from '../../database';
import { resetDatabaseAndSeed } from '../../database/test-reset';

@ApiExcludeController()
@Controller('test')
export class TestController {
  constructor(
    private readonly dataSource: DataSource,
    private readonly redis: RedisService,
  ) {}

  @Post('reset')
  @HttpCode(HttpStatus.NO_CONTENT)
  async reset(): Promise<void> {
    await resetDatabaseAndSeed(this.dataSource, this.redis);
  }
}
