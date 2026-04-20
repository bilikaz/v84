import { UserShell } from '@/modules/dashboard/components';

// [v84-1-4][front-nextjs:pages]
export default function DashboardLayout({ children }: { children: React.ReactNode }) {
  return <UserShell>{children}</UserShell>;
}
