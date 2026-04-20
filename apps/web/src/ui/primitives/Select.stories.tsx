// [v84-1-5][front-nextjs:ui]
import type { Meta, StoryObj } from '@storybook/react';
import { Select } from './Select';

const meta: Meta<typeof Select> = {
  title: 'Components/Select',
  component: Select,
  args: {
    label: 'Role',
    options: [
      { value: 'user', label: 'User' },
      { value: 'admin', label: 'Admin' },
    ],
  },
};

export default meta;
type Story = StoryObj<typeof Select>;

export const Default: Story = {};

export const WithPlaceholder: Story = {
  args: { placeholder: 'Select a role...' },
};

export const WithError: Story = {
  args: { error: 'Role is required' },
};

export const Required: Story = {
  args: { required: true },
};

export const Disabled: Story = {
  args: { disabled: true },
};
