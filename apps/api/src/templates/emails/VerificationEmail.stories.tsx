// [v84-3-1-2][back-nestjs:notifications]
import type { Meta, StoryObj } from '@storybook/react';
import { VerificationEmail } from './VerificationEmail';

const meta: Meta<typeof VerificationEmail> = {
  title: 'Emails/Templates/VerificationEmail',
  component: VerificationEmail,
  parameters: { layout: 'fullscreen' },
};

export default meta;
type Story = StoryObj<typeof VerificationEmail>;

export const Default: Story = {
  args: {
    appName: 'V84',
    verifyLink: 'http://web.localhost/auth/register/example-token-value',
    expiresInMinutes: 1440,
  },
};
