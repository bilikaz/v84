// [v84-2-1-2][back-nestjs:services]
import { Module } from '@nestjs/common';
import { TypeOrmModule } from '@nestjs/typeorm';
import { Session } from './entities';
import { SessionsService } from './sessions.service';
import { SessionsController } from './sessions.controller';
import { RedisService } from '../../database';

@Module({
  imports: [TypeOrmModule.forFeature([Session])],
  controllers: [SessionsController],
  providers: [SessionsService, RedisService],
  exports: [SessionsService],
})
export class SessionsModule {}
