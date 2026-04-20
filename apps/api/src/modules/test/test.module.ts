// [v84-1-3][back-nestjs:api]
import { Module } from '@nestjs/common';
import { DatabaseModule, RedisService } from '../../database';
import { TestController } from './test.controller';

@Module({
  // DatabaseModule provides DataSource globally via TypeOrmModule.forRootAsync.
  // RedisService is a plain provider — each consumer module (Auth, Users,
  // TestModule here) declares it in its own providers list, just like
  // AuthModule does.
  imports: [DatabaseModule],
  providers: [RedisService],
  controllers: [TestController],
})
export class TestModule {}
