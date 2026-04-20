// [v84-2-2-2][back-nestjs:api]
import { Injectable, UnauthorizedException } from '@nestjs/common';
import { PassportStrategy } from '@nestjs/passport';
import { ExtractJwt, Strategy } from 'passport-jwt';
import { ConfigService } from '@nestjs/config';
import { UsersService } from '../../modules/users/users.service';
import { User } from '../../modules/users/entities';

interface JwtPayload {
  sub: string;
  email: string;
  role: string;
  sessionId?: string;
}

@Injectable()
export class JwtStrategy extends PassportStrategy(Strategy) {
  constructor(
    configService: ConfigService,
    private usersService: UsersService,
  ) {
    super({
      jwtFromRequest: ExtractJwt.fromAuthHeaderAsBearerToken(),
      ignoreExpiration: false,
      secretOrKey: configService.get<string>('jwt.secret')!,
    });
  }

  async validate(payload: JwtPayload): Promise<User & { sessionId?: string }> {
    const user = await this.usersService.findById(payload.sub);
    if (!user) throw new UnauthorizedException();
    return Object.assign(user, { sessionId: payload.sessionId });
  }
}
