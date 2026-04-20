// Direct API + Mailpit helpers for Playwright test setup/teardown.
//
// Tests call the API and Mailpit directly on their exposed ports — no
// Traefik, no .localhost domains, works on any host (WSL2, CI, macOS).

const API_BASE = process.env.E2E_API_URL ?? 'http://localhost:3001/api/v1';
const MAILPIT_BASE = process.env.E2E_MAILPIT_URL ?? 'http://localhost:8025';

// [v84-3-1-1][ops:testing]
function apiFetch(path: string, init?: RequestInit): Promise<Response> {
  return fetch(`${API_BASE}${path}`, {
    ...init,
    headers: {
      'Content-Type': 'application/json',
      ...(init?.headers as Record<string, string>),
    },
  });
}

function mailFetch(path: string, init?: RequestInit): Promise<Response> {
  return fetch(`${MAILPIT_BASE}${path}`, init);
}

// Hit the test-only `/test/reset` endpoint (only mounted when NODE_ENV=test)
// so every e2e test starts from the freshly-seeded baseline — same state the
// API integration suite leaves behind after its own beforeEach.
export async function resetBackend(): Promise<void> {
  const res = await apiFetch('/test/reset', { method: 'POST' });
  if (!res.ok) {
    throw new Error(
      `POST /test/reset returned ${res.status}. Is NODE_ENV=test set on the api container?`,
    );
  }
  await deleteAllEmails();
}

// ── Mailpit ────────────────────────────────────────────────────────────────

interface MailpitMessage {
  ID: string;
  Subject: string;
  To: Array<{ Address: string }>;
  Snippet: string;
}

export async function deleteAllEmails(): Promise<void> {
  await mailFetch('/api/v1/messages', { method: 'DELETE' });
}

export async function waitForEmail(
  to: string,
  { timeoutMs = 10000, intervalMs = 500 } = {},
): Promise<MailpitMessage> {
  const deadline = Date.now() + timeoutMs;
  while (Date.now() < deadline) {
    const res = await mailFetch('/api/v1/messages');
    const body = (await res.json()) as { messages: MailpitMessage[] };
    const match = body.messages.find((m) =>
      m.To.some((t) => t.Address === to),
    );
    if (match) return match;
    await new Promise((r) => setTimeout(r, intervalMs));
  }
  throw new Error(`No email to ${to} within ${timeoutMs}ms`);
}

export async function extractVerifyLink(emailId: string): Promise<string> {
  const res = await mailFetch(`/api/v1/message/${emailId}`);
  const body = (await res.json()) as { Text: string };
  const match = body.Text.match(/(https?:\/\/\S*\/auth\/register\/\S+)/);
  if (!match) throw new Error('Could not find verify link in email text');
  return match[1];
}

// ── Direct API calls (for setup, not for testing) ──────────────────────────

export async function registerViaApi(
  email: string,
  username: string,
  password: string,
): Promise<void> {
  const regRes = await apiFetch('/auth/register', {
    method: 'POST',
    body: JSON.stringify({ email }),
  });
  if (!regRes.ok) {
    throw new Error(`register failed: ${regRes.status} ${await regRes.text()}`);
  }

  const msg = await waitForEmail(email);
  const link = await extractVerifyLink(msg.ID);
  // Token is the last path segment — notifications.service builds
  // `${webUrl}/auth/register/${token}` (path param, not query).
  const token = new URL(link).pathname.split('/').filter(Boolean).pop();
  if (!token) {
    throw new Error(`could not extract token from verify link: ${link}`);
  }

  const completeRes = await apiFetch('/auth/register/complete', {
    method: 'POST',
    body: JSON.stringify({ token, username, password }),
  });
  if (!completeRes.ok) {
    throw new Error(
      `register/complete failed: ${completeRes.status} ${await completeRes.text()}`,
    );
  }
}

export async function loginViaApi(
  email: string,
  password: string,
): Promise<{ accessToken: string }> {
  const res = await apiFetch('/auth/login', {
    method: 'POST',
    body: JSON.stringify({ email, password }),
  });
  if (!res.ok) throw new Error(`API login failed: ${res.status}`);
  return res.json() as Promise<{ accessToken: string }>;
}
