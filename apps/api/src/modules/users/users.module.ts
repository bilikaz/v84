// [v84-2-4-1][back-nestjs:api]
import { Module } from '@nestjs/common';
import { TypeOrmModule } from '@nestjs/typeorm';
import { RedisService } from '../../database';
import { NotificationsModule } from '../notifications/notifications.module';
import { User } from './entities';
import { UsersService } from './users.service';
import { UsersController } from './users.controller';

@Module({
  imports: [TypeOrmModule.forFeature([User]), NotificationsModule],
  controllers: [UsersController],
  providers: [UsersService, RedisService],
  exports: [UsersService],
})
export class UsersModule {}
