// TOTP code generator for Playwright tests — same algorithm as the API.
// We can't import otpauth from the monorepo (different node_modules), so
// we use a lightweight inline HMAC-SHA1 implementation via Node crypto.

import { createHmac } from 'crypto';

// [v84-4-1-1][ops:testing]
export function generateTotp(secretBase32: string): string {
  const secret = base32Decode(secretBase32);
  const counter = Math.floor(Date.now() / 1000 / 30);
  const counterBuf = Buffer.alloc(8);
  counterBuf.writeUInt32BE(Math.floor(counter / 0x100000000), 0);
  counterBuf.writeUInt32BE(counter >>> 0, 4);

  const hmac = createHmac('sha1', secret).update(counterBuf).digest();
  const offset = hmac[hmac.length - 1] & 0x0f;
  const code =
    ((hmac[offset] & 0x7f) << 24) |
    ((hmac[offset + 1] & 0xff) << 16) |
    ((hmac[offset + 2] & 0xff) << 8) |
    (hmac[offset + 3] & 0xff);

  return String(code % 1_000_000).padStart(6, '0');
}

const BASE32_CHARS = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ234567';

function base32Decode(input: string): Buffer {
  const cleaned = input.replace(/=+$/, '').toUpperCase();
  let bits = '';
  for (const c of cleaned) {
    const val = BASE32_CHARS.indexOf(c);
    if (val === -1) throw new Error(`Invalid base32 char: ${c}`);
    bits += val.toString(2).padStart(5, '0');
  }
  const bytes: number[] = [];
  for (let i = 0; i + 8 <= bits.length; i += 8) {
    bytes.push(parseInt(bits.slice(i, i + 8), 2));
  }
  return Buffer.from(bytes);
}
