// [v84-1-3][back-nestjs:api]
import { registerAs } from '@nestjs/config';

export default registerAs('jwt', () => ({
  secret: process.env.JWT_SECRET,
  accessTtl: parseInt(process.env.JWT_ACCESS_TTL ?? '900'),
  refreshTtl: parseInt(process.env.JWT_REFRESH_TTL ?? '604800'),
  passwordResetTtl: parseInt(process.env.JWT_PASSWORD_RESET_TTL ?? '3600'),
  passwordResetPrefix: process.env.JWT_PASSWORD_RESET_PREFIX ?? 'reset:',
  emailVerificationTtl: parseInt(process.env.JWT_EMAIL_VERIFICATION_TTL ?? '86400'),
  emailVerificationPrefix: process.env.JWT_EMAIL_VERIFICATION_PREFIX ?? 'verify:',
}));
