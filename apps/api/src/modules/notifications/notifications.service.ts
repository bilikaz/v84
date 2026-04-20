import { Injectable, Logger, OnModuleInit } from '@nestjs/common';
import { ConfigService } from '@nestjs/config';
import * as nodemailer from 'nodemailer';
import { renderToHtmlAndText } from '../../templates/render';
import {
  PasswordResetEmail,
  VerificationEmail,
  WelcomeEmail,
  ConfirmEmailChange,
  copy,
} from '../../templates/emails';

// [v84-3-1-2][back-nestjs:notifications]
@Injectable()
export class NotificationsService implements OnModuleInit {
  private readonly logger = new Logger(NotificationsService.name);
  private transporter!: nodemailer.Transporter;
  private fromHeader!: string;

  constructor(private readonly configService: ConfigService) {}

  onModuleInit(): void {
    const host = this.configService.get<string>('mail.host');
    const port = this.configService.get<number>('mail.port');
    const user = this.configService.get<string>('mail.user');
    const password = this.configService.get<string>('mail.password');
    const from = this.configService.get<string>('mail.from');
    const fromName = this.configService.get<string>('mail.fromName');

    this.transporter = nodemailer.createTransport({
      host,
      port,
      secure: false,
      ignoreTLS: true,
      auth: user ? { user, pass: password } : undefined,
    });

    this.fromHeader = fromName ? `"${fromName}" <${from}>` : from!;
  }

  async sendPasswordReset(email: string, token: string): Promise<void> {
    const webUrl = this.configService.get<string>('app.webUrl');
    const resetTtl = this.configService.get<number>('jwt.passwordResetTtl')!;
    const resetLink = `${webUrl}/auth/reset-password/${token}`;

    const { html, text } = await renderToHtmlAndText(PasswordResetEmail, {
      appName: copy.appName,
      resetLink,
      expiresInMinutes: Math.round(resetTtl / 60),
    });

    await this.transporter.sendMail({
      from: this.fromHeader,
      to: email,
      subject: copy.emails.passwordReset.subject,
      text,
      html,
    });

    this.logger.log(`Password reset email sent to ${email}`);
  }

  async sendVerificationEmail(email: string, token: string): Promise<void> {
    const webUrl = this.configService.get<string>('app.webUrl');
    const verifyTtl = this.configService.get<number>('jwt.emailVerificationTtl')!;
    const verifyLink = `${webUrl}/auth/register/${token}`;

    const { html, text } = await renderToHtmlAndText(VerificationEmail, {
      appName: copy.appName,
      verifyLink,
      expiresInMinutes: Math.round(verifyTtl / 60),
    });

    await this.transporter.sendMail({
      from: this.fromHeader,
      to: email,
      subject: copy.emails.verify.subject,
      text,
      html,
    });

    this.logger.log(`Verification email sent to ${email}`);
  }

  async sendWelcome(email: string, username: string): Promise<void> {
    const webUrl = this.configService.get<string>('app.webUrl');
    const dashboardLink = `${webUrl}/dashboard`;

    const { html, text } = await renderToHtmlAndText(WelcomeEmail, {
      appName: copy.appName,
      username,
      dashboardLink,
    });

    await this.transporter.sendMail({
      from: this.fromHeader,
      to: email,
      subject: copy.emails.welcome.subject,
      text,
      html,
    });

    this.logger.log(`Welcome email sent to ${email}`);
  }

  async sendEmailChangeConfirmation(
    newEmail: string,
    token: string,
  ): Promise<void> {
    const webUrl = this.configService.get<string>('app.webUrl');
    const ttl = this.configService.get<number>('jwt.emailVerificationTtl')!;
    const confirmLink = `${webUrl}/dashboard/settings/confirm-email?token=${token}`;

    const { html, text } = await renderToHtmlAndText(ConfirmEmailChange, {
      appName: copy.appName,
      confirmLink,
      newEmail,
      expiresInMinutes: Math.round(ttl / 60),
    });

    await this.transporter.sendMail({
      from: this.fromHeader,
      to: newEmail,
      subject: copy.emails.emailChange.subject,
      text,
      html,
    });

    this.logger.log(`Email change confirmation sent to ${newEmail}`);
  }
}
