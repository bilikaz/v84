// [v84-2-2-1][back-nestjs:api]
import { Module } from '@nestjs/common';
import { ConfigModule, ConfigService } from '@nestjs/config';
import { JwtModule } from '@nestjs/jwt';
import { PassportModule } from '@nestjs/passport';
import { TypeOrmModule } from '@nestjs/typeorm';
import { ThrottlerModule } from '@nestjs/throttler';
import { RedisService } from '../../database';
import { UsersModule } from '../users/users.module';
import { NotificationsModule } from '../notifications/notifications.module';
import { Session } from '../sessions/entities';
import { AuthController } from './auth.controller';
import { AuthService } from './auth.service';
import {
  LocalStrategy,
  JwtStrategy,
  RefreshTokenStrategy,
  AppleStrategy,
  GoogleStrategy,
} from '../../common/strategies';

@Module({
  imports: [
    PassportModule,
    JwtModule.registerAsync({
      imports: [ConfigModule],
      inject: [ConfigService],
      useFactory: (configService: ConfigService) => ({
        secret: configService.get<string>('jwt.secret'),
        signOptions: { expiresIn: configService.get<number>('jwt.accessTtl') },
      }),
    }),
    TypeOrmModule.forFeature([Session]),
    UsersModule,
    NotificationsModule,
    ThrottlerModule.forRootAsync({
      inject: [ConfigService],
      useFactory: (cfg: ConfigService) => [
        {
          ttl: cfg.get<number>('auth.throttleTtl') ?? 60_000,
          limit: cfg.get<number>('auth.throttleLimit') ?? 10,
        },
      ],
    }),
  ],
  controllers: [AuthController],
  providers: [
    AuthService,
    RedisService,
    LocalStrategy,
    JwtStrategy,
    RefreshTokenStrategy,
    AppleStrategy,
    GoogleStrategy,
  ],
  exports: [AuthService, JwtModule, RedisService],
})
export class AuthModule {}
