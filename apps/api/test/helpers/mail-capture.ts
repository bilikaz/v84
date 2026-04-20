// In-process capture of every email the NotificationsService sends during a
// test run. Swaps the live nodemailer transporter for a recorder, so tests
// can assert on subject / recipient / rendered html without any network, any
// Mailpit container, and any polling beyond the fire-and-forget deferral in
// auth.service (which still needs a short wait).
//
// The real `NotificationsService.sendX` code path still runs — React Email
// templates are still rendered, DTOs are still built — so this is not a mock
// of the email layer, just of the transport at the SMTP boundary.

import type { INestApplication } from '@nestjs/common';
import { NotificationsService } from '../../src/modules/notifications/notifications.service';

// [v84-3-1-2][ops:testing]
export interface CapturedMail {
  from?: string;
  to: string;
  subject: string;
  html?: string;
  text?: string;
}

export interface MailCapture {
  messages: CapturedMail[];
  reset: () => void;
  waitFor: (
    predicate: (m: CapturedMail) => boolean,
    opts?: { timeoutMs?: number; intervalMs?: number },
  ) => Promise<CapturedMail>;
}

// Reach into the NotificationsService and replace its private transporter
// with a recorder. Must be called after `app.init()` — lifecycle hooks run
// during init and are what create the real transporter.
export function installMailCapture(app: INestApplication): MailCapture {
  const notifications = app.get(NotificationsService);
  const messages: CapturedMail[] = [];

  const recorder = {
    sendMail: async (options: {
      from?: string;
      to: string;
      subject: string;
      html?: string;
      text?: string;
    }) => {
      messages.push({
        from: options.from,
        to: options.to,
        subject: options.subject,
        html: options.html,
        text: options.text,
      });
      return { messageId: `test-${messages.length}` };
    },
  };

  // The field is private in the class; cast through unknown so the test helper
  // doesn't need changes to production code.
  (notifications as unknown as { transporter: typeof recorder }).transporter = recorder;

  return {
    messages,
    reset: () => {
      messages.length = 0;
    },
    waitFor: async (predicate, { timeoutMs = 2000, intervalMs = 20 } = {}) => {
      const deadline = Date.now() + timeoutMs;
      while (Date.now() < deadline) {
        const match = messages.find(predicate);
        if (match) return match;
        await new Promise((r) => setTimeout(r, intervalMs));
      }
      throw new Error(
        `Timed out after ${timeoutMs}ms waiting for a captured mail (got ${messages.length})`,
      );
    },
  };
}
