'use client';

import { useState } from 'react';
import { QRCodeSVG } from 'qrcode.react';
import { ApiError } from '@/lib';
import { useAuth } from '@/common/hooks';
import { copy } from '@/config';
import { Button } from '@/ui/primitives';
import { enableTwoFactor, verifyTwoFactor, disableTwoFactor } from '../api';
import { verifyTotpSchema, disableTwoFactorSchema } from '../schemas';

// Three states:
//   - "off"     → user has 2FA disabled, button to start setup
//   - "setup"   → secret + QR code shown, waiting for the user to verify with a code
//   - "on"      → user has 2FA enabled, can disable with password + current code

type Mode = 'off' | 'setup' | 'on' | 'disabling';

// [v84-4-1-1][front-nextjs:forms]
export function TwoFactorSetup({ initiallyEnabled }: { initiallyEnabled: boolean }) {
  const [mode, setMode] = useState<Mode>(initiallyEnabled ? 'on' : 'off');

  if (mode === 'off') return <DisabledView onStart={() => setMode('setup')} />;
  if (mode === 'setup') {
    return (
      <SetupView
        onCancel={() => setMode('off')}
        onVerified={() => setMode('on')}
      />
    );
  }
  if (mode === 'on') return <EnabledView onStartDisable={() => setMode('disabling')} />;
  return <DisableView onCancel={() => setMode('on')} onDisabled={() => setMode('off')} />;
}

function DisabledView({ onStart }: { onStart: () => void }) {
  return (
    <div className="space-y-3">
      <p className="text-sm text-textMuted">
        Two-factor authentication adds a one-time code from your phone every time you sign
        in. We recommend enabling it.
      </p>
      <Button onClick={onStart}>Enable 2FA</Button>
    </div>
  );
}

function SetupView({
  onCancel,
  onVerified,
}: {
  onCancel: () => void;
  onVerified: () => void;
}) {
  const { user } = useAuth();
  const [secret, setSecret] = useState<string | null>(null);
  const [code, setCode] = useState('');
  const [error, setError] = useState('');
  const [fieldError, setFieldError] = useState('');
  const [busy, setBusy] = useState(false);

  // Lazily generate the secret on the first render (effects would also work).
  if (secret === null && !busy && !error) {
    setBusy(true);
    enableTwoFactor()
      .then((res) => setSecret(res.secret))
      .catch((err) =>
        setError(err instanceof ApiError ? err.message : 'Could not start 2FA setup'),
      )
      .finally(() => setBusy(false));
  }

  const otpauthUrl = secret && user
    ? `otpauth://totp/${encodeURIComponent(copy.appName)}:${encodeURIComponent(user.email)}?secret=${secret}&issuer=${encodeURIComponent(copy.appName)}`
    : null;

  async function handleVerify(e: React.FormEvent) {
    e.preventDefault();
    setError('');
    setFieldError('');

    const result = verifyTotpSchema.safeParse({ code });
    if (!result.success) {
      setFieldError(result.error.issues[0]?.message ?? 'Invalid code');
      return;
    }

    setBusy(true);
    try {
      await verifyTwoFactor(code);
      onVerified();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Could not verify code');
    } finally {
      setBusy(false);
    }
  }

  if (error && !secret) {
    return (
      <div className="space-y-3">
        <div className="rounded-md bg-red-50 p-3 text-sm text-danger">{error}</div>
        <Button variant="secondary" onClick={onCancel}>Cancel</Button>
      </div>
    );
  }

  if (!otpauthUrl) {
    return <p className="text-sm text-textMuted">Generating secret…</p>;
  }

  return (
    <div className="space-y-4">
      <ol className="list-inside list-decimal space-y-2 text-sm text-text">
        <li>Open your authenticator app (Google Authenticator, 1Password, Authy…)</li>
        <li>Scan the QR code below, or enter the secret manually</li>
        <li>Type the 6-digit code from your app to confirm</li>
      </ol>

      <div className="rounded-lg border border-border bg-surface p-4">
        <div className="flex justify-center">
          <QRCodeSVG value={otpauthUrl} size={180} level="M" />
        </div>
        <div className="mt-4">
          <p className="text-xs text-textMuted">Manual entry secret</p>
          <code className="mt-1 block break-all rounded bg-surfaceMuted p-2 font-mono text-xs text-text">
            {secret}
          </code>
        </div>
      </div>

      {error && (
        <div className="rounded-md bg-red-50 p-3 text-sm text-danger">{error}</div>
      )}

      <form onSubmit={handleVerify} className="space-y-3">
        <div>
          <label htmlFor="totp-setup" className="block text-sm font-medium text-text">
            Verification code
          </label>
          <input
            id="totp-setup"
            type="text"
            inputMode="numeric"
            autoComplete="one-time-code"
            value={code}
            onChange={(e) => setCode(e.target.value.replace(/\D/g, '').slice(0, 6))}
            className="mt-1 block w-full max-w-xs rounded-md border border-border px-3 py-2 text-center font-mono tracking-widest shadow-sm focus:border-brand focus:outline-none focus:ring-1 focus:ring-brand"
            placeholder="123456"
          />
          {fieldError && <p className="mt-1 text-sm text-danger">{fieldError}</p>}
        </div>

        <div className="flex gap-2">
          <Button type="submit" disabled={busy}>
            {busy ? 'Verifying…' : 'Verify and enable'}
          </Button>
          <Button type="button" variant="secondary" onClick={onCancel} disabled={busy}>
            Cancel
          </Button>
        </div>
      </form>
    </div>
  );
}

function EnabledView({ onStartDisable }: { onStartDisable: () => void }) {
  return (
    <div className="space-y-3">
      <div className="flex items-center gap-2">
        <span className="inline-flex items-center rounded-full bg-success px-2.5 py-0.5 text-xs font-medium text-textInverse">
          Enabled
        </span>
        <p className="text-sm text-textMuted">
          Two-factor authentication is on for this account.
        </p>
      </div>
      <Button variant="danger" size="sm" onClick={onStartDisable}>
        Disable 2FA
      </Button>
    </div>
  );
}

function DisableView({
  onCancel,
  onDisabled,
}: {
  onCancel: () => void;
  onDisabled: () => void;
}) {
  const [password, setPassword] = useState('');
  const [code, setCode] = useState('');
  const [error, setError] = useState('');
  const [fieldErrors, setFieldErrors] = useState<Record<string, string>>({});
  const [busy, setBusy] = useState(false);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError('');
    setFieldErrors({});

    const result = disableTwoFactorSchema.safeParse({ password, code });
    if (!result.success) {
      const errs: Record<string, string> = {};
      result.error.issues.forEach((i) => {
        errs[i.path[0] as string] = i.message;
      });
      setFieldErrors(errs);
      return;
    }

    setBusy(true);
    try {
      await disableTwoFactor(password, code);
      onDisabled();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Could not disable 2FA');
    } finally {
      setBusy(false);
    }
  }

  return (
    <form onSubmit={handleSubmit} className="space-y-4">
      <p className="text-sm text-textMuted">
        Confirm your password and a current 6-digit code from your authenticator app.
      </p>

      {error && (
        <div className="rounded-md bg-red-50 p-3 text-sm text-danger">{error}</div>
      )}

      <div>
        <label htmlFor="disable-password" className="block text-sm font-medium text-text">
          Password
        </label>
        <input
          id="disable-password"
          type="password"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          autoComplete="current-password"
          className="mt-1 block w-full rounded-md border border-border px-3 py-2 shadow-sm focus:border-brand focus:outline-none focus:ring-1 focus:ring-brand"
        />
        {fieldErrors.password && (
          <p className="mt-1 text-sm text-danger">{fieldErrors.password}</p>
        )}
      </div>

      <div>
        <label htmlFor="disable-code" className="block text-sm font-medium text-text">
          Current 2FA code
        </label>
        <input
          id="disable-code"
          type="text"
          inputMode="numeric"
          autoComplete="one-time-code"
          value={code}
          onChange={(e) => setCode(e.target.value.replace(/\D/g, '').slice(0, 6))}
          className="mt-1 block w-full max-w-xs rounded-md border border-border px-3 py-2 text-center font-mono tracking-widest shadow-sm focus:border-brand focus:outline-none focus:ring-1 focus:ring-brand"
          placeholder="123456"
        />
        {fieldErrors.code && <p className="mt-1 text-sm text-danger">{fieldErrors.code}</p>}
      </div>

      <div className="flex gap-2">
        <Button type="submit" variant="danger" disabled={busy}>
          {busy ? 'Disabling…' : 'Disable 2FA'}
        </Button>
        <Button type="button" variant="secondary" onClick={onCancel} disabled={busy}>
          Cancel
        </Button>
      </div>
    </form>
  );
}
