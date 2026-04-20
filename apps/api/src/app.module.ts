// [v84-1-3][back-nestjs:api]
import { Module } from '@nestjs/common';
import { ConfigModule } from '@nestjs/config';
import { appConfig, databaseConfig, jwtConfig, authConfig, redisConfig, mailConfig } from './config';
import { DatabaseModule } from './database';
import { UsersModule } from './modules/users/users.module';
import { SessionsModule } from './modules/sessions/sessions.module';
import { AuthModule } from './modules/auth/auth.module';
import { NotificationsModule } from './modules/notifications/notifications.module';
import { TestModule } from './modules/test/test.module';
import { HealthController } from './health.controller';

// Rate limiting intentionally lives at the edge (Traefik / upstream proxy),
// not in the app. See memory `feedback_rate_limit_edge`.
@Module({
  imports: [
    ConfigModule.forRoot({
      isGlobal: true,
      load: [appConfig, databaseConfig, jwtConfig, authConfig, redisConfig, mailConfig],
    }),
    DatabaseModule,
    UsersModule,
    SessionsModule,
    AuthModule,
    NotificationsModule,
    // Conditional: only mounted in the test stack (NODE_ENV=test set via
    // docker/test/.env). Dev and prod never see POST /api/v1/test/reset.
    ...(process.env.NODE_ENV === 'test' ? [TestModule] : []),
  ],
  controllers: [HealthController],
})
export class AppModule {}
