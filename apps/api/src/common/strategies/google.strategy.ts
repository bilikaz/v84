// [v84-2-2-2][back-nestjs:api]
import { Injectable, UnauthorizedException } from '@nestjs/common';
import { PassportStrategy } from '@nestjs/passport';
import { Strategy } from 'passport-local';
import { AuthService } from '../../modules/auth/auth.service';
import { User } from '../../modules/users/entities';

// Google id token verification is handled manually in AuthService.
@Injectable()
export class GoogleStrategy extends PassportStrategy(Strategy, 'google-id-token') {
  constructor(private authService: AuthService) {
    super({ usernameField: 'idToken', passwordField: 'idToken' });
  }

  async validate(idToken: string): Promise<User> {
    const user = await this.authService.validateGoogleToken(idToken);
    if (!user) throw new UnauthorizedException('Google sign-in failed');
    return user;
  }
}
