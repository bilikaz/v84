// [v84-1-5][front-nextjs:ui]
import type { Meta, StoryObj } from '@storybook/react';
import { Input } from './Input';

const meta: Meta<typeof Input> = {
  title: 'UI/Input',
  component: Input,
};

export default meta;
type Story = StoryObj<typeof Input>;

export const Text: Story = {
  args: { label: 'Name', type: 'text', placeholder: 'Enter your name', required: true },
};

export const Email: Story = {
  args: { label: 'Email', type: 'email', placeholder: 'you@example.com' },
};

export const WithError: Story = {
  args: { label: 'Email', type: 'email', error: 'Invalid email address', required: true },
};

export const NumberInput: Story = {
  args: { label: 'Max Tickets', type: 'number', min: 1 },
};

export const Textarea: Story = {
  args: { label: 'Description', as: 'textarea', rows: 4, placeholder: 'Enter description...' },
};
