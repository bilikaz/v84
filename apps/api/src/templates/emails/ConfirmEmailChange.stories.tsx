// [v84-4-2-2][back-nestjs:notifications]
import type { Meta, StoryObj } from '@storybook/react';
import { ConfirmEmailChange } from './ConfirmEmailChange';

const meta: Meta<typeof ConfirmEmailChange> = {
  title: 'Emails/Templates/ConfirmEmailChange',
  component: ConfirmEmailChange,
  parameters: { layout: 'fullscreen' },
};

export default meta;
type Story = StoryObj<typeof ConfirmEmailChange>;

export const Default: Story = {
  args: {
    appName: 'V84',
    confirmLink: 'http://web.localhost/dashboard/settings/confirm-email?token=example-token-value',
    newEmail: 'new-address@example.com',
    expiresInMinutes: 30,
  },
};
