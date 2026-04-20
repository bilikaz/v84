// [v84-2-1-2][back-nestjs:services]
import {
  Injectable,
  NotFoundException,
  BadRequestException,
  ConflictException,
} from '@nestjs/common';
import { ConfigService } from '@nestjs/config';
import { InjectRepository } from '@nestjs/typeorm';
import { Brackets, Repository } from 'typeorm';
import * as bcrypt from 'bcrypt';
import { randomBytes } from 'crypto';
import * as OTPAuth from 'otpauth';
import { RedisService } from '../../database';
import { NotificationsService } from '../notifications/notifications.service';
import { copy } from '../../templates/emails';
import { User, UserRole } from './entities';
import { UpdateUserDto, AdminUpdateUserDto, ListUsersQueryDto } from './dto';

@Injectable()
export class UsersService {
  private readonly emailChangePrefix = 'email-change:';

  constructor(
    @InjectRepository(User)
    private readonly userRepository: Repository<User>,
    private readonly redisService: RedisService,
    private readonly configService: ConfigService,
    private readonly notificationsService: NotificationsService,
  ) {}

  async findById(id: string): Promise<User> {
    const user = await this.userRepository.findOne({ where: { id } });
    if (!user) throw new NotFoundException('User not found');
    return user;
  }

  async findByEmail(email: string): Promise<User | null> {
    return this.userRepository.findOne({ where: { email } });
  }

  async findByUsername(username: string): Promise<User | null> {
    return this.userRepository.findOne({ where: { username } });
  }

  async create(data: {
    username: string;
    email: string;
    password: string;
    role?: UserRole;
  }): Promise<User> {
    const existingEmail = await this.findByEmail(data.email);
    if (existingEmail) throw new ConflictException('Email already in use');

    const existingUsername = await this.findByUsername(data.username);
    if (existingUsername) throw new ConflictException('Username already in use');

    const passwordHash = await bcrypt.hash(data.password, 12);
    const user = this.userRepository.create({
      username: data.username,
      email: data.email,
      passwordHash,
      role: data.role ?? UserRole.USER,
    });
    return this.userRepository.save(user);
  }

  // Auto-provision a user from a verified OAuth identity (Google, Apple).
  // No password is set — the user can only sign in via the OAuth provider
  // until they go through the forgot-password flow to set one.
  async createFromOAuth(data: { email: string; username: string }): Promise<User> {
    const passwordHash = await bcrypt.hash(randomBytes(32).toString('hex'), 12);
    const user = this.userRepository.create({
      username: data.username,
      email: data.email,
      passwordHash,
      role: UserRole.USER,
    });
    return this.userRepository.save(user);
  }

  async update(id: string, dto: UpdateUserDto): Promise<User> {
    const user = await this.findById(id);

    if (dto.password) {
      if (!dto.currentPassword) {
        throw new BadRequestException('Current password is required to set a new password');
      }
      const valid = await bcrypt.compare(dto.currentPassword, user.passwordHash);
      if (!valid) {
        throw new BadRequestException('Current password is incorrect');
      }
      user.passwordHash = await bcrypt.hash(dto.password, 12);
    }

    if (dto.username) {
      const existing = await this.findByUsername(dto.username);
      if (existing && existing.id !== id) {
        throw new ConflictException('Username already in use');
      }
      user.username = dto.username;
    }

    return this.userRepository.save(user);
  }

  async findAll(query: ListUsersQueryDto): Promise<[User[], number]> {
    const { page, limit, role, search } = query;
    const qb = this.userRepository.createQueryBuilder('u').orderBy('u.createdAt', 'DESC');
    if (role) qb.andWhere('u.role = :role', { role });
    if (search) {
      qb.andWhere(
        new Brackets((b) =>
          b.where('u.username LIKE :s', { s: `%${search}%` }).orWhere('u.email LIKE :s', { s: `%${search}%` }),
        ),
      );
    }
    return qb.skip((page - 1) * limit).take(limit).getManyAndCount();
  }

  async adminUpdate(id: string, dto: AdminUpdateUserDto): Promise<User> {
    const user = await this.findById(id);

    if (dto.username) {
      const existing = await this.findByUsername(dto.username);
      if (existing && existing.id !== id) {
        throw new ConflictException('Username already in use');
      }
      user.username = dto.username;
    }

    if (dto.password) {
      user.passwordHash = await bcrypt.hash(dto.password, 12);
    }

    if (dto.role) {
      user.role = dto.role;
    }

    return this.userRepository.save(user);
  }

  async remove(id: string): Promise<void> {
    const user = await this.findById(id);
    await this.userRepository.remove(user);
  }

  async save(user: User): Promise<User> {
    return this.userRepository.save(user);
  }

  async enableTwoFactor(userId: string): Promise<{ secret: string }> {
    const user = await this.findById(userId);
    if (user.twoFactorEnabled) {
      throw new BadRequestException('2FA is already enabled');
    }

    const secret = new OTPAuth.Secret({ size: 20 }).base32;
    user.twoFactorSecret = secret;
    await this.userRepository.save(user);

    return { secret };
  }

  async verifyAndActivateTwoFactor(userId: string, code: string): Promise<void> {
    const user = await this.findById(userId);
    if (user.twoFactorEnabled) {
      throw new BadRequestException('2FA is already enabled');
    }
    if (!user.twoFactorSecret) {
      throw new BadRequestException('Call enable endpoint first to generate a secret');
    }

    if (!this.checkTotpCode(user.twoFactorSecret, code)) {
      throw new BadRequestException('Invalid TOTP code');
    }

    user.twoFactorEnabled = true;
    await this.userRepository.save(user);
  }

  async disableTwoFactor(userId: string, password: string, code: string): Promise<void> {
    const user = await this.findById(userId);
    if (!user.twoFactorEnabled) {
      throw new BadRequestException('2FA is not enabled');
    }

    const passwordValid = await bcrypt.compare(password, user.passwordHash);
    if (!passwordValid) {
      throw new BadRequestException('Invalid password');
    }

    const codeValid = await this.verifyTotpCode(user, code);
    if (!codeValid) {
      throw new BadRequestException('Invalid TOTP code');
    }

    user.twoFactorEnabled = false;
    user.twoFactorSecret = null;
    await this.userRepository.save(user);
  }

  async verifyTotpCode(user: User, code: string): Promise<boolean> {
    if (!user.twoFactorSecret) return false;
    return this.checkTotpCode(user.twoFactorSecret, code);
  }

  // ── Email change ──

  async requestEmailChange(userId: string, newEmail: string, currentPassword: string): Promise<void> {
    const user = await this.findById(userId);

    const passwordValid = await bcrypt.compare(currentPassword, user.passwordHash);
    if (!passwordValid) {
      throw new BadRequestException('Current password is incorrect');
    }

    if (newEmail === user.email) {
      throw new BadRequestException('New email is the same as the current one');
    }

    const existing = await this.findByEmail(newEmail);
    if (existing) {
      throw new ConflictException('Email already in use');
    }

    const token = randomBytes(32).toString('hex');
    const ttl = this.configService.get<number>('jwt.emailVerificationTtl')!;
    await this.redisService.set(
      `${this.emailChangePrefix}${token}`,
      JSON.stringify({ userId, newEmail }),
      ttl,
    );

    await this.notificationsService.sendEmailChangeConfirmation(newEmail, token);
  }

  async confirmEmailChange(token: string): Promise<User> {
    const key = `${this.emailChangePrefix}${token}`;
    const raw = await this.redisService.get(key);
    if (!raw) {
      throw new BadRequestException('Invalid or expired email change token');
    }

    const { userId, newEmail } = JSON.parse(raw) as { userId: string; newEmail: string };

    // Re-check for collisions in case another user took the email during the wait.
    const existing = await this.findByEmail(newEmail);
    if (existing) {
      await this.redisService.del(key);
      throw new ConflictException('Email already in use');
    }

    const user = await this.findById(userId);
    user.email = newEmail;
    await this.userRepository.save(user);
    await this.redisService.del(key);

    return user;
  }

  // ── TOTP ──

  // Accept the current code and the adjacent window (±1 step = ±30s) to tolerate
  // small clock skew between the server and the authenticator app.
  private checkTotpCode(secretBase32: string, code: string): boolean {
    const totp = new OTPAuth.TOTP({
      issuer: copy.appName,
      algorithm: 'SHA1',
      digits: 6,
      period: 30,
      secret: OTPAuth.Secret.fromBase32(secretBase32),
    });
    return totp.validate({ token: code, window: 1 }) !== null;
  }
}
