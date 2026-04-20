// [v84-2-2-1][back-nestjs:api]
import { registerAs } from '@nestjs/config';

export default registerAs('auth', () => ({
  // Rate limit on /auth/login and /auth/refresh (brute-force protection).
  // ttl in ms, limit in requests-per-ttl.
  throttleTtl: parseInt(process.env.AUTH_THROTTLE_TTL ?? '60000'),
  throttleLimit: parseInt(process.env.AUTH_THROTTLE_LIMIT ?? '10'),
}));
