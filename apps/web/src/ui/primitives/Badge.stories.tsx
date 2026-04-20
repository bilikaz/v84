// [v84-1-5][front-nextjs:ui]
import type { Meta, StoryObj } from '@storybook/react';
import { Badge } from './Badge';

const meta: Meta<typeof Badge> = {
  title: 'UI/Badge',
  component: Badge,
  argTypes: {
    status: { control: 'select', options: ['draft', 'active', 'drawn', 'closed'] },
  },
};

export default meta;
type Story = StoryObj<typeof Badge>;

export const Draft: Story = { args: { status: 'draft' } };
export const Active: Story = { args: { status: 'active' } };
export const Drawn: Story = { args: { status: 'drawn' } };
export const Closed: Story = { args: { status: 'closed' } };
