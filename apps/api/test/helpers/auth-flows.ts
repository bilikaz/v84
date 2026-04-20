// Shared registration / login / token helpers used by every e2e suite.

import * as OTPAuth from 'otpauth';
import type { TestContext } from './app';

// [v84-2-2-1][ops:testing]
export interface IssuedTokens {
  accessToken: string;
  refreshToken: string;
}

// Pulls the verification token that startRegistration just dropped in Redis.
// Expects exactly one pending registration; if you need to register more than
// one user in a test, drain between calls.
export async function pullVerifyToken(ctx: TestContext): Promise<string> {
  const keys = await ctx.redis.keys('verify:*');
  if (keys.length !== 1) {
    throw new Error(`expected exactly one verify:* key, got ${keys.length}`);
  }
  return keys[0].replace(/^verify:/, '');
}

// Runs the full two-step register flow and returns the freshly issued tokens.
export async function registerAndComplete(
  ctx: TestContext,
  email: string,
  username: string,
  password: string,
): Promise<IssuedTokens> {
  await ctx.http.post('/api/v1/auth/register').send({ email }).expect(204);
  const token = await pullVerifyToken(ctx);
  const res = await ctx.http
    .post('/api/v1/auth/register/complete')
    .send({ token, username, password })
    .expect(201);
  return { accessToken: res.body.accessToken, refreshToken: res.body.refreshToken };
}

// Happy-path login — expects the server to issue tokens, not a 2FA challenge.
export async function loginHappyPath(
  ctx: TestContext,
  email: string,
  password: string,
  totpCode?: string,
): Promise<IssuedTokens> {
  const body: Record<string, string> = { email, password };
  if (totpCode) body.totpCode = totpCode;
  const res = await ctx.http.post('/api/v1/auth/login').send(body).expect(200);
  return { accessToken: res.body.accessToken, refreshToken: res.body.refreshToken };
}

// Decodes the middle segment of a JWT. No signature verification — tests only
// care about payload shape (sub/email/role/sessionId).
export function decodeJwtPayload(token: string): Record<string, unknown> {
  const parts = token.split('.');
  if (parts.length !== 3) throw new Error('malformed jwt');
  const json = Buffer.from(parts[1], 'base64url').toString('utf8');
  return JSON.parse(json) as Record<string, unknown>;
}

// Generates a live TOTP code from a base32 secret — matches the same settings
// users.service.ts uses to validate. Lets 2FA tests exercise the real path end
// to end instead of mocking.
export function generateTotp(secretBase32: string): string {
  const totp = new OTPAuth.TOTP({
    algorithm: 'SHA1',
    digits: 6,
    period: 30,
    secret: OTPAuth.Secret.fromBase32(secretBase32),
  });
  return totp.generate();
}

// Promotes a user to the ADMIN role directly in the database. Useful in tests
// that need an admin without going through a bootstrap flow that doesn't exist
// in the app (there is no public "create admin" endpoint on purpose).
export async function promoteToAdmin(ctx: TestContext, email: string): Promise<void> {
  await ctx.dataSource.query(`UPDATE users SET role = 'admin' WHERE email = ?`, [email]);
}
