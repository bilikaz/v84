// [v84-3-1-2][back-nestjs:notifications]
import type { Meta, StoryObj } from '@storybook/react';
import { WelcomeEmail } from './WelcomeEmail';

const meta: Meta<typeof WelcomeEmail> = {
  title: 'Emails/Templates/WelcomeEmail',
  component: WelcomeEmail,
  parameters: { layout: 'fullscreen' },
};

export default meta;
type Story = StoryObj<typeof WelcomeEmail>;

export const Default: Story = {
  args: {
    appName: 'V84',
    username: 'alex',
    dashboardLink: 'http://web.localhost/dashboard',
  },
};
