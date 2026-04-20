// [v84-1-5][front-nextjs:ui]
import type { Meta, StoryObj } from '@storybook/react';
import { Modal } from './Modal';

const meta: Meta<typeof Modal> = {
  title: 'UI/Modal',
  component: Modal,
};

export default meta;
type Story = StoryObj<typeof Modal>;

export const Confirmation: Story = {
  args: {
    open: true,
    title: 'Confirm Action',
    children: 'Are you sure you want to proceed?',
    confirmLabel: 'Yes, proceed',
    onConfirm: () => alert('Confirmed'),
    onCancel: () => alert('Cancelled'),
  },
};

export const Danger: Story = {
  args: {
    open: true,
    title: 'Delete Raffle',
    children: 'This action cannot be undone.',
    confirmLabel: 'Delete',
    confirmVariant: 'danger',
    onConfirm: () => alert('Deleted'),
    onCancel: () => alert('Cancelled'),
  },
};
