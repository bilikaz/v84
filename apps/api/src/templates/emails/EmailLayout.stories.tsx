// [v84-1-6][back-nestjs:notifications]
import type { Meta, StoryObj } from '@storybook/react';
import { Text } from '@react-email/components';
import { EmailLayout } from './EmailLayout';

const meta: Meta<typeof EmailLayout> = {
  title: 'Emails/Layout/EmailLayout',
  component: EmailLayout,
  parameters: { layout: 'fullscreen' },
};

export default meta;
type Story = StoryObj<typeof EmailLayout>;

export const Default: Story = {
  args: {
    appName: 'V84',
    preview: 'Preview text shown in the inbox',
    children: (
      <Text style={{ fontSize: '15px', color: '#333' }}>
        This is placeholder body content used to preview the email layout.
      </Text>
    ),
  },
};

export const CustomFooter: Story = {
  args: {
    appName: 'V84',
    preview: 'Custom footer preview',
    footerText: 'You received this because you are a V84 admin.',
    children: (
      <Text style={{ fontSize: '15px', color: '#333' }}>
        Layout with a custom footer line.
      </Text>
    ),
  },
};
