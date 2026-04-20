// [v84-2-2-1][back-nestjs:api]
import { Controller, Post, Get, UseGuards, Req, Body, Query, HttpCode, HttpStatus } from '@nestjs/common';
import { ApiTags, ApiOperation } from '@nestjs/swagger';
import { ThrottlerGuard } from '@nestjs/throttler';
import { Request } from 'express';
import { AuthService } from './auth.service';
import { LocalAuthGuard, AppleAuthGuard, GoogleAuthGuard, RefreshAuthGuard } from './guards';
import { JwtAuthGuard } from '../../common/guards';
import {
  LoginDto,
  AppleLoginDto,
  GoogleLoginDto,
  RefreshTokenDto,
  ForgotPasswordDto,
  ResetPasswordDto,
  RegisterDto,
  CompleteRegistrationDto,
} from './dto';
import { User } from '../users/entities';

@ApiTags('auth')
@Controller('auth')
export class AuthController {
  constructor(private readonly authService: AuthService) {}

  @Post('login')
  @HttpCode(HttpStatus.OK)
  @UseGuards(ThrottlerGuard, LocalAuthGuard)
  @ApiOperation({ summary: 'Email + password login' })
  async login(@Req() req: Request, @Body() dto: LoginDto) {
    return this.authService.loginWithTwoFactorCheck(req.user as User, dto.totpCode, {
      ip: req.ip,
      deviceName: req.headers['x-device-name'] as string | undefined,
      deviceOs: req.headers['x-device-os'] as string | undefined,
    });
  }

  @Post('apple')
  @HttpCode(HttpStatus.OK)
  @UseGuards(AppleAuthGuard)
  @ApiOperation({ summary: 'Apple identity token login' })
  async appleLogin(@Req() req: Request, @Body() _dto: AppleLoginDto) {
    return this.authService.issueTokens(req.user as User, { ip: req.ip });
  }

  @Post('google')
  @HttpCode(HttpStatus.OK)
  @UseGuards(GoogleAuthGuard)
  @ApiOperation({ summary: 'Google ID token login' })
  async googleLogin(@Req() req: Request, @Body() _dto: GoogleLoginDto) {
    return this.authService.issueTokens(req.user as User, { ip: req.ip });
  }

  @Post('refresh')
  @HttpCode(HttpStatus.OK)
  @UseGuards(ThrottlerGuard, RefreshAuthGuard)
  @ApiOperation({ summary: 'Refresh access token' })
  async refresh(@Req() req: Request, @Body() _dto: RefreshTokenDto) {
    return this.authService.issueTokens(req.user as User, { ip: req.ip });
  }

  @Post('logout')
  @HttpCode(HttpStatus.NO_CONTENT)
  @UseGuards(JwtAuthGuard)
  @ApiOperation({ summary: 'Logout and revoke current session' })
  async logout(@Req() req: Request) {
    const user = req.user as User & { sessionId?: string };
    if (user.sessionId) {
      await this.authService.logout(user.sessionId);
    }
  }

  // [v84-3-2-1][back-nestjs:api]
  @Post('forgot-password')
  @HttpCode(HttpStatus.NO_CONTENT)
  @ApiOperation({ summary: 'Request a password reset email' })
  async forgotPassword(@Body() dto: ForgotPasswordDto) {
    await this.authService.forgotPassword(dto.email);
  }

  // [v84-3-2-2][back-nestjs:api]
  @Post('reset-password')
  @HttpCode(HttpStatus.NO_CONTENT)
  @ApiOperation({ summary: 'Reset password using token from email' })
  async resetPassword(@Body() dto: ResetPasswordDto) {
    await this.authService.resetPassword(dto.token, dto.password);
  }

  // [v84-3-1-1][back-nestjs:api]
  @Post('register')
  @HttpCode(HttpStatus.NO_CONTENT)
  @ApiOperation({ summary: 'Step 1 — submit email; we send a verification link' })
  async register(@Body() dto: RegisterDto) {
    await this.authService.startRegistration(dto.email);
  }

  // [v84-3-1-2][back-nestjs:api]
  @Get('register/check')
  @HttpCode(HttpStatus.OK)
  @ApiOperation({ summary: 'Step 1.5 — check if a verification token is still valid' })
  async checkRegistration(@Query('token') token: string) {
    return this.authService.checkRegistrationToken(token);
  }

  // [v84-3-1-2][back-nestjs:api]
  @Post('register/complete')
  @HttpCode(HttpStatus.CREATED)
  @ApiOperation({ summary: 'Step 2 — finalize the account with username + password' })
  async completeRegistration(@Body() dto: CompleteRegistrationDto) {
    return this.authService.completeRegistration(dto);
  }
}
