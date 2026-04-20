// [v84-2-2-2][back-nestjs:api]
import { Injectable, UnauthorizedException } from '@nestjs/common';
import { PassportStrategy } from '@nestjs/passport';
import { Strategy } from 'passport-local';
import { AuthService } from '../../modules/auth/auth.service';
import { User } from '../../modules/users/entities';

// Apple identity token verification is handled manually in AuthService.
// This strategy accepts the raw identityToken and delegates to AuthService.
@Injectable()
export class AppleStrategy extends PassportStrategy(Strategy, 'apple') {
  constructor(private authService: AuthService) {
    super({ usernameField: 'identityToken', passwordField: 'identityToken' });
  }

  async validate(identityToken: string): Promise<User> {
    const user = await this.authService.validateAppleToken(identityToken);
    if (!user) throw new UnauthorizedException('Apple sign-in failed');
    return user;
  }
}
