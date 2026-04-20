// [v84-1-5][front-nextjs:ui]
import type { Meta, StoryObj } from '@storybook/react';
import { Table, type TableColumn } from './Table';

interface SampleUser {
  id: string;
  username: string;
  email: string;
  role: string;
}

const columns: TableColumn<SampleUser>[] = [
  { key: 'username', header: 'Username', render: (row) => row.username },
  { key: 'email', header: 'Email', render: (row) => row.email },
  { key: 'role', header: 'Role', render: (row) => row.role },
];

const sampleData: SampleUser[] = [
  { id: '1', username: 'admin', email: 'admin@example.com', role: 'admin' },
  { id: '2', username: 'jane', email: 'jane@example.com', role: 'user' },
  { id: '3', username: 'bob', email: 'bob@example.com', role: 'user' },
];

const meta: Meta<typeof Table<SampleUser>> = {
  title: 'Components/Table',
  component: Table,
};

export default meta;
type Story = StoryObj<typeof Table<SampleUser>>;

export const Default: Story = {
  args: {
    columns,
    data: sampleData,
    keyExtractor: (row: SampleUser) => row.id,
  },
};

export const Empty: Story = {
  args: {
    columns,
    data: [],
    keyExtractor: (row: SampleUser) => row.id,
    emptyMessage: 'No users found',
  },
};
