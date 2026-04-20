// [v84-2-2-2][back-nestjs:api]
import { Injectable, UnauthorizedException } from '@nestjs/common';
import { PassportStrategy } from '@nestjs/passport';
import { ExtractJwt, Strategy } from 'passport-jwt';
import { ConfigService } from '@nestjs/config';
import { Request } from 'express';
import { AuthService } from '../../modules/auth/auth.service';
import { User } from '../../modules/users/entities';

interface JwtPayload {
  sub: string;
  sessionId: string;
}

@Injectable()
export class RefreshTokenStrategy extends PassportStrategy(Strategy, 'jwt-refresh') {
  constructor(
    configService: ConfigService,
    private authService: AuthService,
  ) {
    super({
      jwtFromRequest: ExtractJwt.fromBodyField('refreshToken'),
      ignoreExpiration: false,
      secretOrKey: configService.get<string>('jwt.secret')!,
      passReqToCallback: true,
    });
  }

  async validate(_req: Request, payload: JwtPayload): Promise<User> {
    // The JWT signature is already verified by Passport at this point.
    // We just check that the session hasn't been revoked.
    const user = await this.authService.validateRefreshToken(
      payload.sub,
      payload.sessionId,
    );
    if (!user) throw new UnauthorizedException('Invalid refresh token');
    return user;
  }
}
