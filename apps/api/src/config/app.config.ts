// [v84-1-3][back-nestjs:api]
import { registerAs } from '@nestjs/config';

function parseCorsOrigins(): string[] {
  const raw = process.env.CORS_ORIGINS;
  const list = raw
    ? raw.split(',').map((o) => o.trim()).filter(Boolean)
    : [];
  const webUrl = process.env.WEB_URL;
  if (webUrl && !list.includes(webUrl)) list.push(webUrl);
  return list;
}

export default registerAs('app', () => ({
  prefix: process.env.API_PREFIX ?? 'api/v1',
  port: parseInt(process.env.API_PORT ?? '3001'),
  name: process.env.API_NAME ?? 'API',
  description: process.env.API_DESCRIPTION ?? 'API',
  version: process.env.APP_VERSION ?? '1.0',
  webUrl: process.env.WEB_URL,
  corsOrigins: parseCorsOrigins(),
  registrationEnabled: process.env.API_REGISTRATION_ENABLED === '1',
  googleClientId: process.env.GOOGLE_CLIENT_ID,
}));
