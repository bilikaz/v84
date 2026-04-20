// [v84-2-1-2][back-nestjs:services]
import { Injectable, BadRequestException, ConflictException, UnauthorizedException } from '@nestjs/common';
import { ConfigService } from '@nestjs/config';
import { JwtService } from '@nestjs/jwt';
import { InjectRepository } from '@nestjs/typeorm';
import { Repository } from 'typeorm';
import * as bcrypt from 'bcrypt';
import { createHash, randomBytes } from 'crypto';
import { v7 as uuidv7 } from 'uuid';
import { OAuth2Client } from 'google-auth-library';
import { RedisService } from '../../database';
import { UsersService } from '../users/users.service';
import { NotificationsService } from '../notifications/notifications.service';
import { User } from '../users/entities';
import { Session } from '../sessions/entities';

interface JwtPayload {
  sub: string;
  email: string;
  role: string;
  sessionId: string;
}

export interface AuthTokens {
  accessToken: string;
  refreshToken: string;
  /** Access token lifetime in seconds (matches `exp - iat` of the JWT). */
  expiresIn: number;
  tokenType: 'Bearer';
}

@Injectable()
export class AuthService {
  constructor(
    private usersService: UsersService,
    private jwtService: JwtService,
    private configService: ConfigService,
    private redisService: RedisService,
    private notificationsService: NotificationsService,
    @InjectRepository(Session)
    private sessionRepository: Repository<Session>,
  ) {}

  // [v84-3-1-1][back-nestjs:services]
  // Step 1 of registration: caller submits an email only. We store the pending
  // email in Redis under a random token and send a verification link. The account
  // is NOT created until the user follows the link and completes step 2.
  async startRegistration(email: string): Promise<void> {
    const registrationEnabled = this.configService.get<boolean>('app.registrationEnabled');
    if (!registrationEnabled) {
      throw new BadRequestException('Registration is disabled');
    }

    const existing = await this.usersService.findByEmail(email);
    if (existing) {
      // Don't leak whether the email exists — but a duplicate is still a hard error
      // because step 2 would fail anyway. Frontend shows the same "check your email"
      // screen, but we can also surface the conflict directly.
      throw new ConflictException('Email already in use');
    }

    const token = randomBytes(32).toString('hex');
    const ttl = this.configService.get<number>('jwt.emailVerificationTtl');
    const prefix = this.configService.get<string>('jwt.emailVerificationPrefix');
    await this.redisService.set(`${prefix}${token}`, email, ttl);

    await this.notificationsService.sendVerificationEmail(email, token);
  }

  // [v84-3-1-2][back-nestjs:services]
  // Step 1.5: frontend checks if a token is still valid before showing the
  // username/password form, so we can pre-fill (and lock) the email field.
  async checkRegistrationToken(token: string): Promise<{ email: string }> {
    const prefix = this.configService.get<string>('jwt.emailVerificationPrefix');
    const email = await this.redisService.get(`${prefix}${token}`);
    if (!email) {
      throw new BadRequestException('Invalid or expired verification token');
    }
    return { email };
  }

  // [v84-3-1-2][back-nestjs:services]
  // Step 2: user followed the link and submitted username + password. We re-check
  // the token, ensure no race created the user in the meantime, then create.
  // On success we dispatch the WelcomeEmail and issue auth tokens.
  async completeRegistration(data: {
    token: string;
    username: string;
    password: string;
  }): Promise<AuthTokens> {
    const prefix = this.configService.get<string>('jwt.emailVerificationPrefix');
    const key = `${prefix}${data.token}`;
    const email = await this.redisService.get(key);
    if (!email) {
      throw new BadRequestException('Invalid or expired verification token');
    }

    // Re-check for collisions in case another flow raced us during the wait.
    const existingEmail = await this.usersService.findByEmail(email);
    if (existingEmail) {
      await this.redisService.del(key);
      throw new ConflictException('Email already in use');
    }

    const user = await this.usersService.create({
      username: data.username,
      email,
      password: data.password,
    });

    await this.redisService.del(key);

    // Fire-and-forget — a transient SMTP failure shouldn't fail registration.
    void this.notificationsService.sendWelcome(user.email, user.username).catch(() => {});

    return this.issueTokens(user, {});
  }

  async validateCredentials(email: string, password: string): Promise<User | null> {
    const user = await this.usersService.findByEmail(email);
    if (!user) return null;
    const valid = await bcrypt.compare(password, user.passwordHash);
    return valid ? user : null;
  }

  async loginWithTwoFactorCheck(
    user: User,
    totpCode: string | undefined,
    options: { deviceName?: string; deviceOs?: string; ip?: string },
  ): Promise<AuthTokens | { requiresTwoFactor: true }> {
    if (user.twoFactorEnabled) {
      if (!totpCode) {
        return { requiresTwoFactor: true };
      }
      const valid = await this.usersService.verifyTotpCode(user, totpCode);
      if (!valid) {
        throw new UnauthorizedException('Invalid TOTP code');
      }
    }
    return this.issueTokens(user, options);
  }

  async validateAppleToken(identityToken: string): Promise<User | null> {
    try {
      const payload = this.jwtService.decode(identityToken);
      if (!payload?.email) return null;
      return this.usersService.findByEmail(payload.email);
    } catch {
      return null;
    }
  }

  async validateGoogleToken(idToken: string): Promise<User | null> {
    const clientId = this.configService.get<string>('app.googleClientId');
    if (!clientId) {
      throw new BadRequestException('Google sign-in is not configured');
    }

    const client = new OAuth2Client(clientId);
    let payload;
    try {
      const ticket = await client.verifyIdToken({ idToken, audience: clientId });
      payload = ticket.getPayload();
    } catch {
      return null;
    }

    if (!payload?.email || !payload.email_verified) return null;

    const existing = await this.usersService.findByEmail(payload.email);
    if (existing) return existing;

    // Auto-provision a new USER-role account for first-time Google sign-in.
    // Honors API_REGISTRATION_ENABLED just like the password register flow.
    const registrationEnabled = this.configService.get<boolean>('app.registrationEnabled');
    if (!registrationEnabled) return null;

    return this.usersService.createFromOAuth({
      email: payload.email,
      username: await this.generateUniqueUsername(payload.email, payload.name),
    });
  }

  private async generateUniqueUsername(email: string, name?: string | null): Promise<string> {
    const base = (name ?? email.split('@')[0])
      .toLowerCase()
      .replace(/[^a-z0-9._-]/g, '')
      .slice(0, 24) || 'user';
    let candidate = base;
    let n = 0;
    while (await this.usersService.findByUsername(candidate)) {
      n += 1;
      candidate = `${base}${n}`;
    }
    return candidate;
  }

  // The refresh token sent by the client is a signed JWT containing `{ sub, sessionId }`.
  // Passport's JwtStrategy already verified the signature, so by the time we get here
  // the token is proven genuine. We only need to confirm the session hasn't been revoked
  // (i.e. the Redis key still exists). The bcrypt hash stored in Redis is a revocation
  // flag — its presence means "this session is still alive."
  async validateRefreshToken(
    userId: string,
    sessionId: string,
  ): Promise<User | null> {
    const redisKey = `refresh:${sessionId}`;
    const exists = await this.redisService.get(redisKey);
    if (!exists) return null;

    return this.usersService.findById(userId);
  }

  async issueTokens(
    user: User,
    options: { deviceName?: string; deviceOs?: string; ip?: string },
  ): Promise<AuthTokens> {
    const sessionId = uuidv7();
    const refreshToken = uuidv7() + uuidv7();
    const refreshHash = await bcrypt.hash(refreshToken, 10);

    const refreshExpiresIn = this.configService.get<number>('jwt.refreshTtl');
    await this.redisService.set(`refresh:${sessionId}`, refreshHash, refreshExpiresIn);

    const session = this.sessionRepository.create({
      id: sessionId,
      userId: user.id,
      refreshTokenHash: createHash('sha256').update(refreshToken).digest('hex'),
      deviceName: options.deviceName ?? null,
      deviceOs: options.deviceOs ?? null,
      ipAddress: options.ip ?? null,
      lastSeenAt: new Date(),
    });
    await this.sessionRepository.save(session);

    const payload: JwtPayload = {
      sub: user.id,
      email: user.email,
      role: user.role,
      sessionId,
    };

    const accessTtl = this.configService.get<number>('jwt.accessTtl')!;
    const accessToken = this.jwtService.sign(payload, { expiresIn: accessTtl });

    const refreshPayload = { sub: user.id, sessionId };
    const signedRefresh = this.jwtService.sign(refreshPayload, { expiresIn: refreshExpiresIn });

    return {
      accessToken,
      refreshToken: signedRefresh,
      expiresIn: accessTtl,
      tokenType: 'Bearer',
    };
  }

  async logout(sessionId: string): Promise<void> {
    await this.redisService.del(`refresh:${sessionId}`);
    await this.sessionRepository.delete({ id: sessionId });
  }

  // [v84-3-2-1][back-nestjs:services]
  async forgotPassword(email: string): Promise<void> {
    const user = await this.usersService.findByEmail(email);
    // Always return success to prevent email enumeration
    if (!user) return;

    const token = randomBytes(32).toString('hex');
    const resetTtl = this.configService.get<number>('jwt.passwordResetTtl');
    const resetPrefix = this.configService.get<string>('jwt.passwordResetPrefix');
    await this.redisService.set(`${resetPrefix}${token}`, user.id, resetTtl);

    await this.notificationsService.sendPasswordReset(user.email, token);
  }

  // [v84-3-2-2][back-nestjs:services]
  async resetPassword(token: string, newPassword: string): Promise<void> {
    const resetPrefix = this.configService.get<string>('jwt.passwordResetPrefix');
    const redisKey = `${resetPrefix}${token}`;
    const userId = await this.redisService.get(redisKey);

    if (!userId) {
      throw new BadRequestException('Invalid or expired reset token');
    }

    const user = await this.usersService.findById(userId);
    user.passwordHash = await bcrypt.hash(newPassword, 12);
    await this.usersService.save(user);

    // Invalidate token
    await this.redisService.del(redisKey);

    // Revoke all existing sessions for security
    const sessions = await this.sessionRepository.find({ where: { userId: user.id } });
    for (const session of sessions) {
      await this.redisService.del(`refresh:${session.id}`);
    }
    await this.sessionRepository.delete({ userId: user.id });
  }
}
