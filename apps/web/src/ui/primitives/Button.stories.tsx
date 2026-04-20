// [v84-1-5][front-nextjs:ui]
import type { Meta, StoryObj } from '@storybook/react';
import { Button } from './Button';

const meta: Meta<typeof Button> = {
  title: 'UI/Button',
  component: Button,
  argTypes: {
    variant: { control: 'select', options: ['primary', 'secondary', 'danger'] },
    size: { control: 'select', options: ['sm', 'md', 'lg'] },
    disabled: { control: 'boolean' },
  },
};

export default meta;
type Story = StoryObj<typeof Button>;

export const Primary: Story = {
  args: { variant: 'primary', children: 'Primary Button' },
};

export const Secondary: Story = {
  args: { variant: 'secondary', children: 'Secondary Button' },
};

export const Danger: Story = {
  args: { variant: 'danger', children: 'Danger Button' },
};

export const Disabled: Story = {
  args: { variant: 'primary', children: 'Disabled', disabled: true },
};

export const Sizes: Story = {
  render: () => (
    <div className="flex items-center gap-3">
      <Button size="sm">Small</Button>
      <Button size="md">Medium</Button>
      <Button size="lg">Large</Button>
    </div>
  ),
};

export const TableActions: Story = {
  render: () => (
    <div className="flex gap-2">
      <Button size="sm" variant="secondary">Edit</Button>
      <Button size="sm" variant="danger">Delete</Button>
    </div>
  ),
};
