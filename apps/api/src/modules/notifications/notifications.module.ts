import { Module } from '@nestjs/common';
import { NotificationsService } from './notifications.service';

// [v84-3-1-2][back-nestjs:notifications]
@Module({
  providers: [NotificationsService],
  exports: [NotificationsService],
})
export class NotificationsModule {}
