// [v84-1-3][back-nestjs:api]
import { registerAs } from '@nestjs/config';

export default registerAs('mail', () => ({
  host: process.env.MAIL_HOST,
  port: parseInt(process.env.MAIL_PORT ?? '1025'),
  user: process.env.MAIL_USER,
  password: process.env.MAIL_PASSWORD,
  from: process.env.MAIL_FROM,
  fromName: process.env.MAIL_FROM_NAME,
}));
