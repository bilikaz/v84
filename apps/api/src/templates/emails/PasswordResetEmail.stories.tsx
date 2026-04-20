// [v84-3-2-1][back-nestjs:notifications]
import type { Meta, StoryObj } from '@storybook/react';
import { PasswordResetEmail } from './PasswordResetEmail';

const meta: Meta<typeof PasswordResetEmail> = {
  title: 'Emails/Templates/PasswordResetEmail',
  component: PasswordResetEmail,
  parameters: { layout: 'fullscreen' },
};

export default meta;
type Story = StoryObj<typeof PasswordResetEmail>;

export const Default: Story = {
  args: {
    appName: 'V84',
    resetLink: 'http://web.localhost/auth/reset-password/example-token-value',
    expiresInMinutes: 60,
  },
};

export const ShortExpiry: Story = {
  args: {
    appName: 'V84',
    resetLink: 'http://web.localhost/auth/reset-password/example-token-value',
    expiresInMinutes: 15,
  },
};
