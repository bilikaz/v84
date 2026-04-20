// [v84-1-3][back-nestjs:api]
import { registerAs } from '@nestjs/config';

export default registerAs('database', () => ({
  host: process.env.DATABASE_HOST,
  port: parseInt(process.env.DATABASE_PORT ?? '3306'),
  username: process.env.DATABASE_USER,
  password: process.env.DATABASE_PASSWORD,
  name: process.env.DATABASE_NAME,
  logging: process.env.NODE_ENV === 'development',
}));
